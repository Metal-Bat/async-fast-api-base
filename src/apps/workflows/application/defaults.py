"""Preview and atomically apply exact immutable-template restoration intent."""

import hashlib
from typing import Any

import jwt
from pydantic import ValidationError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.step_types.application.registry import get_registry
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.application.workspace import WorkspaceService, graph_checksum
from apps.workflows.domain.defaults import (
    RestoreApplyInput,
    RestorePlan,
    RestorePreviewInput,
    RestoreResult,
)
from apps.workflows.domain.dto import (
    GraphIssue,
    GraphSnapshot,
    GraphValidationResult,
    WorkflowVersionCreateDTO,
)
from apps.workflows.domain.entities.restore import WorkflowRestoreEntity
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from apps.workflows.domain.workspace import (
    WorkflowWorkspaceDTO,
    WorkspaceDocument,
    WorkspaceUpdateDTO,
    WorkspaceViewport,
)
from core.base_dto import BaseDTO
from core.ref_id import create_ref_id, open_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)

PLAN_AUDIENCE = "workflow-default/1"


def dependency_slots(graph: GraphSnapshot) -> dict[str, tuple[BaseDTO | dict[str, Any], str]]:
    """Return named references from registered graph ownership surfaces."""
    slots: dict[str, tuple[BaseDTO | dict[str, Any], str]] = {}
    for step in graph.steps:
        if step.type_version_ref is not None:
            slots[f"step_type:{step.key}"] = (step, "type_version_ref")
        if step.form_ref is not None:
            slots[f"form:{step.key}"] = (step, "form_ref")
        if step.subprocess:
            slots[f"subprocess:{step.key}"] = (step.subprocess, "workflow_version_ref")
        for name, kind in (("connection_ref", "connection"), ("agent_ref", "agent")):
            if isinstance(step.config.get(name), str):
                slots[f"{kind}:{step.key}"] = (step.config, name)
    for index, target in enumerate(graph.targets):
        name, kind = (
            ("user_ref", "user")
            if target.user_ref is not None
            else ("work_group_ref", "work_group")
        )
        slots[f"{kind}:{target.step}:{index}"] = (target, name)
    return slots


def bind_graph(graph: GraphSnapshot, bindings: dict[str, str]) -> dict[str, str]:
    slots = dependency_slots(graph)
    if set(bindings) - slots.keys():
        raise ValidationDetailsException(
            [{"pointer": "/bindings", "code": "template.binding.unknown"}]
        )
    values: dict[str, str] = {}
    for key, (owner, field) in slots.items():
        if key in bindings:
            if isinstance(owner, dict):
                owner[field] = bindings[key]
            else:
                setattr(owner, field, bindings[key])
        value = owner[field] if isinstance(owner, dict) else getattr(owner, field)
        if not isinstance(value, str):
            raise ValidationDetailsException(
                [{"pointer": "/bindings", "code": "template.binding.invalid"}]
            )
        values[key] = value
    return values


class WorkflowDefaultsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workflows = WorkflowService(session, get_registry())
        self.workspaces = WorkspaceService(self.workflows)

    async def authorized(
        self,
        reference: str,
        actor: UserEntity,
        *,
        lock: bool = False,
        require_revision: bool = True,
    ) -> tuple[UserEntity, WorkflowVersionEntity, WorkflowDefinitionEntity]:
        live_actor = await self.session.get(
            UserEntity, actor.id, with_for_update=lock, populate_existing=True
        )
        if live_actor is None or live_actor.deleted_at is not None:
            raise NotAllowedException()
        actor = live_actor
        permissions = await user_permissions(actor, self.session)
        if "*" not in permissions and "workflows.manage" not in permissions:
            raise NotAllowedException()
        version = await self.workflows.get_version(reference)
        root = await self.session.get(
            WorkflowDefinitionEntity,
            version.workflow_definition_id,
            with_for_update=lock,
            populate_existing=True,
        )
        if (
            root is None
            or root.deleted_at
            or not root.is_active
            or not await self.workflows.can_access(root, actor, "view")
        ):
            raise NotFoundException()
        if lock and require_revision:
            version = await self.workflows.get_version(reference, update=True)
        return actor, version, root

    async def source(
        self,
        target: WorkflowVersionEntity,
        source_ref: str | None,
        actor: UserEntity,
    ) -> tuple[WorkflowVersionEntity, str]:
        provenance = target.template_source or {}
        selected = source_ref or provenance.get("source_ref_id")
        if not isinstance(selected, str):
            raise ValidationDetailsException(
                [{"pointer": "/source_ref_id", "code": "template.selection.required"}]
            )
        source = await self.workflows.get_version(selected)
        root = await self.session.get(WorkflowDefinitionEntity, source.workflow_definition_id)
        if (
            source.status not in {"PUBLISHED", "RETIRED"}
            or source.graph_checksum is None
            or root is None
            or root.deleted_at
            or not await self.workflows.can_access(root, actor, "view")
        ):
            raise NotFoundException("Published template is unavailable")
        if source_ref is not None and source.version != open_ref_id(selected)[1]:
            raise VersionConflictException("Template reference is stale")
        if source_ref is None and provenance.get("source_checksum") != source.graph_checksum:
            raise VersionConflictException("Template provenance differs")
        return source, create_ref_id(source.id, source.version)

    async def preview(
        self, reference: str, data: RestorePreviewInput, actor: UserEntity
    ) -> RestorePlan:
        actor, target, _ = await self.authorized(reference, actor)
        if target.version != open_ref_id(reference)[1]:
            raise VersionConflictException()
        if data.mode == "replace_draft" and target.status != "DRAFT":
            raise VersionConflictException("Replace requires a draft")
        workspace = await self.workspaces.row(target.id)
        self.workspaces.require_current(workspace, data.workspace_ref_id)
        source, selected = await self.source(target, data.source_ref_id, actor)
        graph = await self.workflows.snapshot(source.id)
        recorded_bindings = (target.template_source or {}).get("bindings", {})
        if not isinstance(recorded_bindings, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in recorded_bindings.items()
        ):
            raise VersionConflictException("Template binding provenance is invalid")
        bindings = (
            {**recorded_bindings, **data.bindings} if data.source_ref_id is None else data.bindings
        )
        dependencies = bind_graph(graph, bindings)
        try:
            WorkspaceDocument(graph=graph.model_dump(mode="json"))
        except ValidationError:
            valid = GraphValidationResult(
                valid=False,
                issues=[GraphIssue(pointer="/graph", code="workspace.graph.invalid")],
            )
        else:
            try:
                valid = await self.workflows.validate_graph(
                    graph, actor.id, parent_version_id=target.id
                )
            except ValidationDetailsException as error:
                valid = GraphValidationResult(
                    valid=False, issues=[GraphIssue.model_validate(issue) for issue in error.issues]
                )
        current = await self.workflows.snapshot(target.id)
        old = {step.key: step.model_dump(mode="json") for step in current.steps}
        new = {step.key: step.model_dump(mode="json") for step in graph.steps}
        changed = sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key))
        now = int(get_datetime_utc().timestamp())
        payload = {
            "aud": PLAN_AUDIENCE,
            "iss": PLAN_AUDIENCE,
            "sub": str(actor.id),
            "iat": now,
            "exp": now + 600,
            "target": reference,
            "source": selected,
            "source_checksum": source.graph_checksum,
            "workspace": data.workspace_ref_id,
            "mode": data.mode,
            "bindings": bindings,
            "graph_hash": graph_checksum(graph, graph),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256") if valid.valid else None
        return RestorePlan(
            template_ref_id=selected,
            template_checksum=source.graph_checksum or "",
            mode=data.mode,
            dependencies=dependencies,
            changed_step_keys=changed,
            changed_paths=[
                "/" + key
                for key in ("steps", "transitions", "bindings", "targets", "interface")
                if current.model_dump(mode="json")[key] != graph.model_dump(mode="json")[key]
            ]
            + (["/default_priority"] if target.default_priority != source.default_priority else []),
            blockers=valid.issues,
            plan_token=token,
        )

    async def apply(
        self, reference: str, data: RestoreApplyInput, actor: UserEntity
    ) -> RestoreResult:
        try:
            plan = jwt.decode(
                data.plan_token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                audience=PLAN_AUDIENCE,
                issuer=PLAN_AUDIENCE,
                options={"verify_exp": False, "require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.InvalidTokenError:
            raise VersionConflictException("Restore plan is invalid") from None
        if plan["sub"] != str(actor.id) or plan.get("target") != reference:
            raise VersionConflictException("Restore plan belongs to another target or actor")
        # Serialize all restore commands on the live actor and workflow root before reading receipts.
        actor, target, root = await self.authorized(
            reference, actor, lock=True, require_revision=False
        )
        digest = hashlib.sha256(data.plan_token.encode()).hexdigest()
        prior = (
            await self.session.exec(
                select(WorkflowRestoreEntity).where(
                    WorkflowRestoreEntity.actor_id == actor.id,
                    WorkflowRestoreEntity.target_id == target.id,
                    WorkflowRestoreEntity.command_key == data.command_key,
                )
            )
        ).one_or_none()
        if prior:
            if prior.plan_hash != digest:
                raise VersionConflictException("Command key binds another reviewed plan")
            result = await self.workflows.get_version(create_ref_id(prior.result_id, 0))
            workspace = await self.workspaces.row(result.id)
            if workspace is None:
                raise VersionConflictException("Restore receipt has no workspace")
            return RestoreResult(
                workflow_version_ref_id=create_ref_id(result.id, result.version),
                workspace_ref_id=create_ref_id(workspace.id, workspace.version),
                replayed=True,
            )
        if plan["exp"] <= int(get_datetime_utc().timestamp()):
            raise VersionConflictException("Restore plan expired")
        target = await self.workflows.get_version(reference, update=True)
        workspace = await self.workspaces.row(target.id, lock=True)
        self.workspaces.require_current(workspace, plan.get("workspace"))
        source, _ = await self.source(target, plan["source"], actor)
        if source.graph_checksum != plan["source_checksum"]:
            raise VersionConflictException("Template checksum changed")
        graph = await self.workflows.snapshot(source.id)
        bind_graph(graph, plan["bindings"])
        if graph_checksum(graph, graph) != plan["graph_hash"]:
            raise VersionConflictException("Template bindings changed")
        if plan["mode"] == "successor":
            number = (
                await self.session.exec(
                    select(func.max(WorkflowVersionEntity.number)).where(
                        WorkflowVersionEntity.workflow_definition_id == root.id
                    )
                )
            ).one() or 0
            result = await self.workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(root.id, root.version),
                    number=number + 1,
                    default_priority=source.default_priority,
                )
            )
            workspace = None
        else:
            if target.status != "DRAFT":
                raise VersionConflictException("Replace requires a draft")
            result = target
            result.default_priority = source.default_priority
        result = await self.workflows.replace_graph(
            create_ref_id(result.id, result.version), graph, actor.id
        )
        result.template_source = {
            "source_ref_id": plan["source"],
            "source_checksum": source.graph_checksum,
            "mode": "REFERENCE",
            "bindings": plan["bindings"],
        }
        await self.session.flush()
        document = WorkspaceDocument(graph=graph.model_dump(mode="json"))
        await self.workspaces.save(
            create_ref_id(result.id, result.version),
            WorkspaceUpdateDTO(
                workspace_ref_id=create_ref_id(workspace.id, workspace.version)
                if workspace
                else None,
                document=document,
            ),
        )
        workspace = await self.workspaces.row(result.id)
        if workspace is None:
            raise VersionConflictException("Restore workspace is unavailable")
        workspace.promoted_graph_checksum = graph_checksum(
            graph, await self.workflows.snapshot(result.id)
        )
        self.session.add(
            WorkflowRestoreEntity(
                actor_id=actor.id,
                target_id=target.id,
                command_key=data.command_key,
                plan_hash=digest,
                result_id=result.id,
            )
        )
        await self.session.flush()
        return RestoreResult(
            workflow_version_ref_id=create_ref_id(result.id, result.version),
            workspace_ref_id=create_ref_id(workspace.id, workspace.version),
        )

    async def reset_layout(
        self,
        reference: str,
        workspace_ref: str,
        actor: UserEntity,
    ) -> WorkflowWorkspaceDTO:
        _, target, _ = await self.authorized(reference, actor, lock=True)
        row = await self.workspaces.row(target.id, lock=True)
        self.workspaces.require_current(row, workspace_ref)
        if row is None:
            raise NotFoundException()
        document = WorkspaceDocument.model_validate(row.document)
        document.positions, document.routing, document.collapsed = {}, {}, []
        document.viewport = WorkspaceViewport()
        return await self.workspaces.save(
            reference, WorkspaceUpdateDTO(workspace_ref_id=workspace_ref, document=document)
        )
