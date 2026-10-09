"""Enrich authoritative publication validation without replacing its graph engine."""

from typing import Literal, cast

import anyio
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.application.service import ClientService
from apps.designer.application.resource_links import ResourceLinkService
from apps.designer.domain.readiness import (
    DependencyPin,
    DependencyReadiness,
    DependencyReadinessQuery,
    RepairIssue,
)
from apps.designer.domain.resource_links import ResourceKind, ResourceReference
from apps.forms.application.designs import resolve_form_documents
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.entity import FormVersionEntity
from apps.step_types.application.registry import get_registry
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupMemberEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.application.workspace import WorkspaceService
from apps.workflows.domain.entity import WorkflowVersionEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    InvalidReferenceException,
    NotAllowedException,
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)


def repair_issue(issue: dict[str, object], node_key: str | None) -> RepairIssue:
    code = str(issue["code"])
    repair = (
        "form_versions"
        if code.startswith(("human.form", "human.field", "task.contract"))
        else "step_types"
        if code.startswith("step_type")
        else "connections"
        if code.startswith("connection")
        else "agent_versions"
        if code.startswith("ai.agent")
        else "work_groups"
        if code.startswith(("human.target", "human.user", "human.group", "human.candidate"))
        else "clients"
        if code.startswith("client")
        else "workflow_versions"
    )
    return RepairIssue(
        pointer=str(issue["pointer"]), code=code, node_key=node_key, repair_key=repair
    )


class DependencyReadinessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workflows = WorkflowService(session, get_registry())

    async def inspect(
        self, query: DependencyReadinessQuery, actor: UserEntity
    ) -> DependencyReadiness:
        permissions = await user_permissions(actor, self.session)
        if "*" not in permissions and "workflows.manage" not in permissions:
            raise NotAllowedException("Workflow authoring permission required")
        version = await self.workflows.get_version(query.workflow_version_ref_id)
        root = await self.workflows.get(create_ref_id(version.workflow_definition_id, 0))
        if not (actor.is_superuser or root.owner_user_id == actor.id):
            raise NotFoundException("Workflow version not found")
        if version.version != open_ref_id(query.workflow_version_ref_id)[1]:
            raise VersionConflictException("Workflow readiness plan is stale")
        with anyio.fail_after(10):
            return await self._inspect(query, actor, version)

    async def _inspect(self, query, actor, version) -> DependencyReadiness:
        graph = await self.workflows.snapshot(version.id)
        raw: list[dict[str, object]] = []
        checksum = None
        try:
            result = await self.workflows.validate_graph(
                graph, actor.id, parent_version_id=version.id
            )
            checksum = result.checksum
            raw.extend(issue.model_dump() for issue in result.issues)
        except ValidationDetailsException as exc:
            raw.extend(dict(issue) for issue in exc.issues)
        except (
            InvalidReferenceException,
            NotFoundException,
            NotAllowedException,
            VersionConflictException,
            ValueError,
        ):
            raw.append({"pointer": "/steps", "code": "dependency.unavailable"})
        if version.status == "DRAFT":
            try:
                await WorkspaceService(self.workflows).require_promoted(version.id)
            except ValidationDetailsException as exc:
                raw.extend(dict(issue) for issue in exc.issues)
            except VersionConflictException:
                raw.append({"pointer": "/workspace", "code": "workspace.promotion.required"})
        pins = []
        resources = ResourceLinkService(self.session)
        client_context = None
        client_readiness: Literal["not_checked", "ready", "blocked"] = "not_checked"
        if query.client_release_ref_id is not None:
            client_readiness = "blocked"
            try:
                link = await resources.mint(
                    ResourceReference(kind="client_releases", ref_id=query.client_release_ref_id),
                    actor,
                )
                release = await ClientService(self.session).get_release(query.client_release_ref_id)
                if release.version != open_ref_id(query.client_release_ref_id)[1]:
                    raise VersionConflictException("Client readiness pin is stale")
                if not link.available:
                    raise NotFoundException()
                client = await ClientService(self.session).get_client(
                    create_ref_id(release.client_id, 0)
                )
                client_context = ClientService._context(client, release)
                client_readiness = "ready"
                pins.append(
                    DependencyPin(
                        pointer="/client_release_ref_id",
                        requested_ref_id=query.client_release_ref_id,
                        resource=link,
                    )
                )
            except NotFoundException, InvalidReferenceException:
                raw.append({"pointer": "/client_release_ref_id", "code": "client.unavailable"})
        for index, step in enumerate(graph.steps):
            candidates = [
                ("step_versions", step.type_version_ref, "type_version_ref"),
                ("form_versions", step.form_ref, "form_ref"),
                ("connections", step.config.get("connection_ref"), "config/connection_ref"),
                ("agent_versions", step.config.get("agent_ref"), "config/agent_ref"),
            ]
            if step.subprocess is not None:
                candidates.append(
                    (
                        "workflow_versions",
                        step.subprocess.workflow_version_ref,
                        "subprocess/workflow_version_ref",
                    )
                )
            for kind, ref, suffix in candidates:
                if not isinstance(ref, str):
                    continue
                pointer = f"/steps/{index}/{suffix}"
                try:
                    resource = await resources.mint(
                        ResourceReference(kind=cast(ResourceKind, kind), ref_id=ref), actor
                    )
                except NotFoundException:
                    raw.append({"pointer": pointer, "code": "dependency.inaccessible"})
                    continue
                pin_checksum = None
                row = None
                if kind in {"form_versions", "workflow_versions"}:
                    model = FormVersionEntity if kind == "form_versions" else WorkflowVersionEntity
                    row = await self.session.get(model, open_ref_id(ref)[0])
                    pin_checksum = (
                        getattr(row, "checksum", None)
                        if kind == "form_versions"
                        else getattr(row, "graph_checksum", None)
                    )
                if kind == "form_versions" and client_context is not None and row is not None:
                    try:
                        resolve_form_documents(
                            FormDocuments.model_validate(row, from_attributes=True), client_context
                        )
                    except ValueError:
                        client_readiness = "blocked"
                        raw.append({"pointer": pointer, "code": "client.renderer.incompatible"})
                pins.append(
                    DependencyPin(
                        pointer=pointer,
                        requested_ref_id=ref,
                        resource=resource,
                        checksum=pin_checksum,
                    )
                )
                if not resource.available:
                    raw.append({"pointer": pointer, "code": "dependency.retired"})
        for index, target in enumerate(graph.targets):
            if bool(target.work_group_ref):
                member = (
                    await self.session.exec(
                        select(WorkGroupMemberEntity.user_id)
                        .join(UserEntity, col(UserEntity.id) == col(WorkGroupMemberEntity.user_id))
                        .where(
                            WorkGroupMemberEntity.work_group_id
                            == open_ref_id(target.work_group_ref)[0],
                            col(WorkGroupMemberEntity.is_active).is_(True),
                            col(UserEntity.deleted_at).is_(None),
                        )
                        .limit(1)
                    )
                ).first()
                if member is None:
                    raw.append(
                        {
                            "pointer": f"/targets/{index}/work_group_ref",
                            "code": "human.candidates.empty",
                        }
                    )
        issues = []
        for issue in raw[:256]:
            pointer = str(issue["pointer"])
            node = None
            parts = pointer.split("/")
            if (
                len(parts) > 2
                and parts[1] == "steps"
                and parts[2].isdigit()
                and int(parts[2]) < len(graph.steps)
            ):
                node = graph.steps[int(parts[2])].key
            issues.append(repair_issue(issue, node))
        return DependencyReadiness(
            workflow_version_ref_id=query.workflow_version_ref_id,
            checked_at=get_datetime_utc(),
            ready=not raw,
            graph_checksum=checksum,
            issues=issues,
            pins=pins,
            client_readiness=client_readiness,
        )
