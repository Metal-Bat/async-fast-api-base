"""Authorize named resources through their owners, then refresh their opaque references."""

from pydantic import TypeAdapter, ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.agent_service import AIAgentService
from apps.clients.application.service import ClientService
from apps.designer.domain.resource_links import (
    ResourceKind,
    ResourceLink,
    ResourceReference,
    ResourceSummary,
)
from apps.forms.application.library import LibraryService
from apps.forms.application.service import FormService
from apps.integrations.application.dependencies import connection_service
from apps.requests.application.service import RequestService
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.users.application.authorization import user_permissions
from apps.users.application.service import get_user_service
from apps.users.domain.entity import UserEntity
from apps.work_groups.application.service import WorkGroupService
from apps.workflows.application.service import WorkflowService
from core.base_entity import BaseEntity
from core.ref_id import create_ref_id, open_ref_id
from core.resource_locator import create_locator, open_locator
from utils.exceptions import InvalidReferenceException, NotAllowedException, NotFoundException

_PERMISSIONS = {
    "users": "admin.users.manage",
    "work_groups": "admin.work_groups.manage",
    "clients": "forms.manage",
    "client_releases": "forms.manage",
    "forms": "forms.manage",
    "form_versions": "forms.manage",
    "request_types": "requests.manage",
    "connections": "integrations.manage",
    "components": "forms.manage",
    "component_versions": "forms.manage",
    "data_types": "forms.manage",
    "data_type_versions": "forms.manage",
}


def _summary(
    kind: ResourceKind, row: BaseEntity, label: str, available: bool, number: int | None = None
) -> ResourceSummary:
    return ResourceSummary(
        kind=kind,
        ref_id=create_ref_id(row.id, row.version),
        label=label,
        number=number,
        available=available,
    )


class ResourceLinkService:
    """The dispatch list is code-owned; it cannot load an arbitrary ORM table or route."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summary(
        self, resource: ResourceReference, actor: UserEntity, *, selection: bool = False
    ) -> ResourceSummary:
        active = await self.session.get(UserEntity, actor.id, populate_existing=True)
        if active is None or active.deleted_at is not None:
            raise NotFoundException("Resource not found")
        permissions = await user_permissions(active, self.session)
        permission = _PERMISSIONS.get(resource.kind, "workflows.manage")
        if selection and resource.kind in {"users", "work_groups", "request_types", "connections"}:
            permission = "workflows.manage"
        if "*" not in permissions and permission not in permissions:
            raise NotFoundException("Resource not found")
        try:
            result = await self._owned_summary(resource, active, selection=selection)
        except NotAllowedException, InvalidReferenceException, NotFoundException:
            raise NotFoundException("Resource not found") from None
        if selection and not result.available:
            raise NotFoundException("Selected resource is unavailable")
        return result

    async def mint(self, resource: ResourceReference, actor: UserEntity) -> ResourceLink:
        summary = await self.summary(resource, actor)
        identity, _ = open_ref_id(summary.ref_id)
        return ResourceLink(
            **summary.model_dump(),
            route_key=resource.kind,
            locator=create_locator(resource.kind, identity),
        )

    async def resolve(self, locator: str, actor: UserEntity) -> ResourceLink:
        try:
            kind, identity = open_locator(locator)
            resource_kind = TypeAdapter(ResourceKind).validate_python(kind)
        except InvalidReferenceException, ValidationError:
            raise NotFoundException("Resource not found") from None
        return await self.mint(
            ResourceReference(kind=resource_kind, ref_id=create_ref_id(identity, 0)), actor
        )

    async def _owned_summary(
        self, resource: ResourceReference, actor: UserEntity, *, selection: bool
    ) -> ResourceSummary:
        kind, ref = resource.kind, resource.ref_id
        if kind in {"forms", "form_versions"}:
            owner = FormService(self.session)
            if kind == "forms":
                root = await owner.get(ref)
                row, number = root, None
                available = root.is_active
            else:
                row = await owner.get_version(ref)
                root = await owner.get(create_ref_id(row.form_definition_id, 0))
                number = row.number
                available = root.is_active and row.status == "PUBLISHED"
            if selection and not (actor.is_superuser or root.owner_user_id == actor.id):
                raise NotFoundException("Resource not found")
            return _summary(kind, row, root.name, available, number)
        if kind in {"workflows", "workflow_versions"}:
            owner = WorkflowService(self.session, get_registry())
            if kind == "workflows":
                root = await owner.get(ref)
                row, number = root, None
                available = root.is_active
            else:
                row = await owner.get_version(ref)
                root = await owner.get(create_ref_id(row.workflow_definition_id, 0))
                number = row.number
                available = root.is_active and row.status == "PUBLISHED"
            if not await owner.can_access(root, actor, "view"):
                raise NotFoundException("Resource not found")
            return _summary(kind, row, root.name, available, number)
        if kind in {"clients", "client_releases"}:
            owner = ClientService(self.session)
            if kind == "clients":
                row = await owner.get_client(ref)
                return _summary(kind, row, row.name, row.is_active)
            row = await owner.get_release(ref)
            root = await owner.get_client(create_ref_id(row.client_id, 0))
            return _summary(
                kind, row, f"{root.name} · {row.release_version}", root.is_active and row.is_enabled
            )
        if kind in {"components", "component_versions", "data_types", "data_type_versions"}:
            owner = LibraryService(self.session)
            library_kind = "component" if kind.startswith("component") else "data_type"
            if kind.endswith("versions"):
                row = await owner.version(library_kind, ref, actor)
                root = await owner.definition(library_kind, create_ref_id(row.root_id, 0), actor)
                return _summary(
                    kind, row, root.name, root.is_active and row.status == "PUBLISHED", row.number
                )
            root = await owner.definition(library_kind, ref, actor)
            return _summary(kind, root, root.name, root.is_active)
        if kind == "users":
            row = await get_user_service(self.session).get_by_id(ref)
            return _summary(kind, row, row.username, True)
        if kind == "work_groups":
            row = await WorkGroupService(self.session).get_group(ref)
            return _summary(kind, row, row.name, row.is_active)
        if kind == "request_types":
            row = await RequestService(self.session).get_type(ref)
            available = row.is_active
            if selection:
                owner = WorkflowService(self.session, get_registry())
                root = await owner.get(create_ref_id(row.workflow_definition_id, 0))
                if not await owner.can_access(root, actor, "view"):
                    raise NotFoundException("Resource not found")
                available = available and root.is_active
            return _summary(kind, row, row.name, available)
        if kind == "connections":
            row = await connection_service(self.session).get(ref, actor)
            return _summary(
                kind,
                row,
                row.name,
                row.status == "ACTIVE" and row.verification_status == "VERIFIED",
            )
        if kind == "agent_versions":
            row = await AIAgentService(self.session).get(ref, actor)
            return _summary(kind, row, row.name, row.status == "PUBLISHED", row.number)
        handler = await StepTypeService(self.session, get_registry()).detail(ref)
        # detail is an owner DTO and does not expose code or arbitrary config execution.
        return ResourceSummary(
            kind=kind,
            ref_id=handler.ref_id,
            label=handler.name,
            number=handler.number,
            available=handler.is_available and handler.status == "PUBLISHED",
        )
