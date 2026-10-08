"""Permission-aware, bounded designer catalogs, selectors, and completion."""

from collections.abc import Iterable
from typing import Any, cast
from uuid import UUID

from sqlalchemy import exists, func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.domain.contracts import client_expression_schema
from apps.designer.domain.dto import (
    CatalogItemDTO,
    CompletionItemDTO,
    CompletionQuery,
    DesignerQuery,
    SelectorKind,
)
from apps.forms.application.fields import field_catalog
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.requests.domain.entity import RequestTypeEntity
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeEntity, StepTypePortEntity, StepTypeVersionEntity
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.workflows.domain.entity import (
    WorkflowAccessGrantEntity,
    WorkflowDefinitionEntity,
    WorkflowStepEntity,
    WorkflowTransitionEntity,
    WorkflowVersionEntity,
)
from core.i18n import _
from core.ref_id import create_ref_id, open_ref_id
from utils.exceptions import NotFoundException
from utils.pagination import Page
from utils.select import SelectOption

_EXPRESSION_FUNCTIONS = (
    "choose",
    "contains",
    "ends_with",
    "length",
    "lower",
    "starts_with",
    "upper",
    "version_in_range",
)
_CONVERSIONS = ("array", "boolean", "date", "date_time", "decimal", "integer", "object", "string")
_OUTCOMES = ("approve", "failure", "next", "reject", "success")
_EXPRESSION_OPERATORS = (
    "add",
    "and",
    "div",
    "eq",
    "gt",
    "gte",
    "in",
    "is",
    "is_not",
    "lt",
    "lte",
    "mod",
    "mul",
    "ne",
    "not",
    "not_in",
    "or",
    "sub",
)
_PROCESS_NEXT = {
    "RUNNING": ("WAITING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"),
    "WAITING": ("RUNNING", "PAUSED", "FAILED", "CANCELLED"),
    "PAUSED": ("RUNNING", "CANCELLED"),
    "FAILED": ("RUNNING", "CANCELLED"),
    "COMPLETED": (),
    "CANCELLED": (),
}

_ENUM_SELECTORS = {
    "definition_status": ("DRAFT", "PUBLISHED", "RETIRED"),
    "request_status": ("DRAFT", "SUBMITTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"),
    "process_status": tuple(_PROCESS_NEXT),
    "outcome": _OUTCOMES,
}


def _enum_options(kind: str) -> list[SelectOption[str]]:
    labels = {
        "DRAFT": _("Draft"),
        "PUBLISHED": _("Published"),
        "RETIRED": _("Retired"),
        "SUBMITTED": _("Submitted"),
        "RUNNING": _("Running"),
        "WAITING": _("Waiting"),
        "PAUSED": _("Paused"),
        "COMPLETED": _("Completed"),
        "FAILED": _("Failed"),
        "CANCELLED": _("Cancelled"),
        "approve": _("Approve"),
        "reject": _("Reject"),
        "next": _("Next"),
        "success": _("Success"),
        "failure": _("Failure"),
    }
    return [SelectOption(key=key, value=labels[key]) for key in sorted(_ENUM_SELECTORS[kind])]


class DesignerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def catalog(
        self, query: DesignerQuery, actor: UserEntity | None = None
    ) -> Page[CatalogItemDTO]:
        items: list[CatalogItemDTO] = []
        for handler in await StepTypeService(self.session, get_registry()).catalog(limit=100):
            if not handler.is_available:
                continue
            items.append(
                CatalogItemDTO(
                    key=f"{handler.code}:{handler.number}",
                    title=handler.name,
                    category="step_type",
                    type_schema=handler.config_schema,
                    metadata={
                        "code": handler.code,
                        "ref_id": handler.ref_id,
                        "number": handler.number,
                        "handler_key": handler.handler_key,
                        "handler_version": handler.handler_version,
                        "execution_mode": handler.execution_mode,
                        "ports": [port.model_dump(mode="json") for port in handler.ports],
                        "runtime_available": True,
                    },
                )
            )
        if actor is not None:
            versions = (
                await self.session.exec(
                    select(WorkflowVersionEntity, WorkflowDefinitionEntity)
                    .join(
                        WorkflowDefinitionEntity,
                        col(WorkflowDefinitionEntity.id)
                        == col(WorkflowVersionEntity.workflow_definition_id),
                    )
                    .where(
                        WorkflowVersionEntity.status == "PUBLISHED",
                        col(WorkflowVersionEntity.subprocess_interface).is_not(None),
                        col(WorkflowDefinitionEntity.deleted_at).is_(None),
                        col(WorkflowDefinitionEntity.is_active).is_(True),
                        self._workflow_visibility(actor),
                    )
                    .order_by(
                        col(WorkflowDefinitionEntity.code),
                        col(WorkflowVersionEntity.number),
                    )
                    .limit(100)
                )
            ).all()
            for version, workflow in versions:
                items.append(
                    CatalogItemDTO(
                        key=f"{workflow.code}:{version.number}",
                        title=workflow.name,
                        category="subprocess",
                        type_schema={},
                        metadata={
                            "workflow_version_ref": create_ref_id(version.id, version.version),
                            "interface": version.subprocess_interface,
                            "runtime_available": True,
                            "call_step_type": "SUBPROCESS",
                        },
                    )
                )
        items.extend(
            CatalogItemDTO(
                key=item.key,
                title=item.key.replace("_", " ").title(),
                category="form_component",
                type_schema=item.data_schema,
                metadata=item.model_dump(mode="json"),
            )
            for item in field_catalog()
        )
        items.extend(self._simple_catalog("renderer", ("compact", "default")))
        items.extend(self._simple_catalog("form_operator", ("eq", "ne", "present")))
        items.extend(self._simple_catalog("form_function", ("concat", "count", "sum")))
        items.extend(self._simple_catalog("expression_function", _EXPRESSION_FUNCTIONS))
        items.extend(self._simple_catalog("expression_operator", _EXPRESSION_OPERATORS))
        items.extend(self._simple_catalog("conversion", _CONVERSIONS))
        items.extend(self._simple_catalog("outcome", _OUTCOMES))
        items.extend(self._simple_catalog("definition_status", ("DRAFT", "PUBLISHED", "RETIRED")))
        items.extend(
            self._simple_catalog(
                "request_status",
                ("DRAFT", "SUBMITTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"),
            )
        )
        for status, targets in _PROCESS_NEXT.items():
            items.append(
                CatalogItemDTO(
                    key=status,
                    title=status.replace("_", " ").title(),
                    category="process_status",
                    type_schema={"type": "string"},
                    metadata={"compatible_next_values": list(targets)},
                )
            )
        items.sort(key=lambda item: (item.category, item.key))
        if bool(query.search):
            term = query.search.casefold()
            items = [
                item
                for item in items
                if term in item.key.casefold() or term in item.title.casefold()
            ]
        return self._slice(items, query)

    async def selector(
        self, kind: SelectorKind, query: DesignerQuery, actor: UserEntity
    ) -> Page[SelectOption[str]]:
        if kind in _ENUM_SELECTORS:
            options = _enum_options(kind)
            if bool(query.search):
                term = query.search.casefold()
                options = [
                    item
                    for item in options
                    if term in item.key.casefold() or term in item.value.casefold()
                ]
            return self._slice(options, query)
        if kind == "users":
            statement = select(UserEntity).where(col(UserEntity.deleted_at).is_(None))
            statement = self._search(statement, UserEntity.username, query.search)
            rows, total = await self._rows(statement, UserEntity, query, "username")
            return self._options(rows, total, query, lambda row: row.username)
        if kind == "work_groups":
            statement = select(WorkGroupEntity).where(
                col(WorkGroupEntity.deleted_at).is_(None),
                col(WorkGroupEntity.is_active).is_(True),
            )
            statement = self._search(statement, WorkGroupEntity.name, query.search)
            rows, total = await self._rows(statement, WorkGroupEntity, query, "name")
            return self._options(rows, total, query, lambda row: row.name)
        if kind == "forms":
            statement = select(FormDefinitionEntity).where(
                col(FormDefinitionEntity.deleted_at).is_(None),
                col(FormDefinitionEntity.is_active).is_(True),
            )
            if not actor.is_superuser:
                statement = statement.where(FormDefinitionEntity.owner_user_id == actor.id)
            statement = self._search(statement, FormDefinitionEntity.name, query.search)
            rows, total = await self._rows(statement, FormDefinitionEntity, query, "name")
            return self._options(rows, total, query, lambda row: row.name)
        if kind == "form_versions":
            statement = (
                select(FormVersionEntity, FormDefinitionEntity)
                .join(
                    FormDefinitionEntity,
                    col(FormDefinitionEntity.id) == col(FormVersionEntity.form_definition_id),
                )
                .where(
                    col(FormVersionEntity.deleted_at).is_(None),
                    col(FormVersionEntity.status) == "PUBLISHED",
                    col(FormDefinitionEntity.deleted_at).is_(None),
                    col(FormDefinitionEntity.is_active).is_(True),
                )
            )
            if not actor.is_superuser:
                statement = statement.where(FormDefinitionEntity.owner_user_id == actor.id)
            statement = self._search(statement, FormDefinitionEntity.name, query.search)
            rows, total = await self._rows(statement, FormVersionEntity, query, "number")
            return self._version_options(rows, total, query)
        visibility = self._workflow_visibility(actor)
        if kind == "workflows":
            statement = select(WorkflowDefinitionEntity).where(
                col(WorkflowDefinitionEntity.deleted_at).is_(None),
                col(WorkflowDefinitionEntity.is_active).is_(True),
                visibility,
            )
            statement = self._search(statement, WorkflowDefinitionEntity.name, query.search)
            rows, total = await self._rows(statement, WorkflowDefinitionEntity, query, "name")
            return self._options(rows, total, query, lambda row: row.name)
        if kind == "workflow_versions":
            statement = (
                select(WorkflowVersionEntity, WorkflowDefinitionEntity)
                .join(
                    WorkflowDefinitionEntity,
                    col(WorkflowDefinitionEntity.id)
                    == col(WorkflowVersionEntity.workflow_definition_id),
                )
                .where(
                    col(WorkflowVersionEntity.deleted_at).is_(None),
                    col(WorkflowVersionEntity.status) == "PUBLISHED",
                    col(WorkflowDefinitionEntity.deleted_at).is_(None),
                    col(WorkflowDefinitionEntity.is_active).is_(True),
                    visibility,
                )
            )
            statement = self._search(statement, WorkflowDefinitionEntity.name, query.search)
            rows, total = await self._rows(statement, WorkflowVersionEntity, query, "number")
            return self._version_options(rows, total, query)
        statement = (
            select(RequestTypeEntity)
            .join(
                WorkflowDefinitionEntity,
                col(WorkflowDefinitionEntity.id) == col(RequestTypeEntity.workflow_definition_id),
            )
            .where(
                col(RequestTypeEntity.deleted_at).is_(None),
                col(RequestTypeEntity.is_active).is_(True),
                col(WorkflowDefinitionEntity.deleted_at).is_(None),
                col(WorkflowDefinitionEntity.is_active).is_(True),
                visibility,
            )
        )
        statement = self._search(statement, RequestTypeEntity.name, query.search)
        rows, total = await self._rows(statement, RequestTypeEntity, query, "name")
        return self._options(rows, total, query, lambda row: row.name)

    async def completion(
        self, query: CompletionQuery, actor: UserEntity
    ) -> Page[CompletionItemDTO]:
        version_id, _ = open_ref_id(query.workflow_version_ref_id)
        version = await self.session.get(WorkflowVersionEntity, version_id)
        workflow = (
            await self.session.get(WorkflowDefinitionEntity, version.workflow_definition_id)
            if version
            else None
        )
        if (
            version is None
            or version.deleted_at
            or workflow is None
            or workflow.deleted_at
            or not workflow.is_active
            or (
                version.status == "DRAFT"
                and not (actor.is_superuser or workflow.owner_user_id == actor.id)
            )
            or not await self._can_view(workflow, actor)
        ):
            raise NotFoundException("Workflow version not found")
        request_type_id, _ = open_ref_id(query.request_type_ref_id)
        request_type = await self.session.get(RequestTypeEntity, request_type_id)
        if (
            request_type is None
            or request_type.deleted_at
            or not request_type.is_active
            or request_type.workflow_definition_id != workflow.id
        ):
            raise NotFoundException("Request type not found")
        form = (
            await self.session.exec(
                select(FormVersionEntity)
                .where(
                    FormVersionEntity.form_definition_id == request_type.form_definition_id,
                    FormVersionEntity.status == "PUBLISHED",
                )
                .order_by(col(FormVersionEntity.number).desc())
                .limit(1)
            )
        ).one_or_none()
        if form is None:
            raise NotFoundException("Published request form not found")
        steps = list(
            (
                await self.session.exec(
                    select(WorkflowStepEntity).where(
                        WorkflowStepEntity.workflow_version_id == version.id
                    )
                )
            ).all()
        )
        by_key = {step.step_key: step for step in steps}
        current = by_key.get(query.current_step_key)
        if current is None:
            raise NotFoundException("Workflow step not found")
        ancestors = await self._available_predecessors(version.id, current.id)
        items = self._schema_paths(form.data_schema, "request", "request")
        items.extend(self._schema_paths(client_expression_schema(), "client", "client"))
        items.extend(
            [
                CompletionItemDTO(
                    path="process.priority",
                    source="process",
                    type_schema={"type": "integer"},
                    nullable=False,
                    cardinality="SCALAR",
                ),
                CompletionItemDTO(
                    path="process.status",
                    source="process",
                    type_schema={"type": "string"},
                    nullable=False,
                    cardinality="SCALAR",
                ),
                CompletionItemDTO(
                    path="current_user.ref_id",
                    source="current_user",
                    type_schema={"type": "string"},
                    nullable=False,
                    cardinality="SCALAR",
                ),
            ]
        )
        if ancestors:
            port_rows = (
                await self.session.exec(
                    select(WorkflowStepEntity, StepTypePortEntity, StepTypeVersionEntity)
                    .join(
                        StepTypeVersionEntity,
                        col(StepTypeVersionEntity.id)
                        == col(WorkflowStepEntity.step_type_version_id),
                    )
                    .join(
                        StepTypeEntity,
                        col(StepTypeEntity.id) == col(StepTypeVersionEntity.step_type_id),
                    )
                    .join(
                        StepTypePortEntity,
                        col(StepTypePortEntity.step_type_version_id)
                        == col(StepTypeVersionEntity.id),
                    )
                    .where(
                        col(WorkflowStepEntity.id).in_(ancestors),
                        StepTypePortEntity.direction == "OUTPUT",
                    )
                )
            ).all()
            registry = get_registry()
            for step, port, type_version in port_rows:
                contract = registry.transform_contract(
                    type_version.handler_key, type_version.handler_version, step.config
                )
                schema = (
                    contract[1]
                    if contract is not None and port.port_key == "result"
                    else port.value_schema
                )
                schema_types = schema.get("type")
                types = {schema_types} if isinstance(schema_types, str) else set(schema_types or [])
                items.append(
                    CompletionItemDTO(
                        path=f"steps.{step.step_key}.outputs.{port.port_key}",
                        source="step_output",
                        type_schema=schema,
                        nullable="null" in types if types else port.nullable,
                        cardinality=cast(Any, "LIST" if "array" in types else port.cardinality),
                        source_step=step.step_key,
                    )
                )
        items.sort(key=lambda item: item.path)
        if bool(query.search):
            term = query.search.casefold()
            items = [item for item in items if term in item.path.casefold()]
        return self._slice(items, query)

    async def _available_predecessors(self, version_id: UUID, current_id: UUID) -> set[UUID]:
        edges = (
            await self.session.exec(
                select(
                    WorkflowTransitionEntity.source_step_id,
                    WorkflowTransitionEntity.target_step_id,
                ).where(WorkflowTransitionEntity.workflow_version_id == version_id)
            )
        ).all()
        incoming: dict[UUID, set[UUID]] = {}
        outgoing: dict[UUID, set[UUID]] = {}
        for source, target in edges:
            incoming.setdefault(target, set()).add(source)
            outgoing.setdefault(source, set()).add(target)
        ancestors: set[UUID] = set()
        pending = list(incoming.get(current_id, set()))
        while pending:
            candidate = pending.pop()
            if candidate in ancestors:
                continue
            ancestors.add(candidate)
            pending.extend(incoming.get(candidate, set()))
        descendants: set[UUID] = set()
        pending = list(outgoing.get(current_id, set()))
        while pending:
            candidate = pending.pop()
            if candidate in descendants:
                continue
            descendants.add(candidate)
            pending.extend(outgoing.get(candidate, set()))
        return ancestors - descendants - {current_id}

    async def _can_view(self, workflow: WorkflowDefinitionEntity, actor: UserEntity) -> bool:
        if (
            actor.is_superuser
            or workflow.owner_user_id == actor.id
            or workflow.access_mode == "OPEN"
        ):
            return True
        return (
            await self.session.exec(
                select(WorkflowDefinitionEntity.id).where(
                    WorkflowDefinitionEntity.id == workflow.id,
                    self._workflow_visibility(actor),
                )
            )
        ).first() is not None

    def _workflow_visibility(self, actor: UserEntity):
        if actor.is_superuser:
            return col(WorkflowDefinitionEntity.id).is_not(None)
        groups = (
            select(WorkGroupMemberEntity.work_group_id)
            .join(
                WorkGroupEntity,
                col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id),
            )
            .where(
                WorkGroupMemberEntity.user_id == actor.id,
                col(WorkGroupMemberEntity.is_active).is_(True),
                col(WorkGroupEntity.is_active).is_(True),
                col(WorkGroupEntity.deleted_at).is_(None),
            )
        )
        grant = exists(
            select(WorkflowAccessGrantEntity.id).where(
                WorkflowAccessGrantEntity.workflow_definition_id == WorkflowDefinitionEntity.id,
                col(WorkflowAccessGrantEntity.deleted_at).is_(None),
                col(WorkflowAccessGrantEntity.can_view).is_(True),
                or_(
                    col(WorkflowAccessGrantEntity.user_id) == actor.id,
                    col(WorkflowAccessGrantEntity.work_group_id).in_(groups),
                ),
            )
        )
        return or_(
            col(WorkflowDefinitionEntity.owner_user_id) == actor.id,
            col(WorkflowDefinitionEntity.access_mode) == "OPEN",
            grant,
        )

    async def _rows(self, statement, model, query: DesignerQuery, order_field: str):
        count = (
            await self.session.exec(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
        ).one()
        rows = list(
            (
                await self.session.exec(
                    statement.order_by(getattr(model, order_field), model.id)
                    .offset((query.page - 1) * query.size)
                    .limit(query.size)
                )
            ).all()
        )
        return rows, count

    @staticmethod
    def _search(statement, column, value: str | None):
        if not bool(value):
            return statement
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return statement.where(column.ilike(f"%{escaped}%", escape="\\"))

    @staticmethod
    def _options(rows, total: int, query: DesignerQuery, title) -> Page[SelectOption[str]]:
        return Page[SelectOption[str]](
            items=[
                SelectOption(key=create_ref_id(row.id, row.version), value=title(row))
                for row in rows
            ],
            page=query.page,
            size=query.size,
            total=total,
        )

    @staticmethod
    def _version_options(rows, total: int, query: DesignerQuery) -> Page[SelectOption[str]]:
        return Page[SelectOption[str]](
            items=[
                SelectOption(
                    key=create_ref_id(version.id, version.version),
                    value=f"{definition.name} · v{version.number}",
                )
                for version, definition in rows
            ],
            page=query.page,
            size=query.size,
            total=total,
        )

    @staticmethod
    def _simple_catalog(category: str, values: Iterable[str]) -> list[CatalogItemDTO]:
        return [
            CatalogItemDTO(
                key=value,
                title=value.replace("_", " ").title(),
                category=category,
                type_schema={"type": "string"},
            )
            for value in values
        ]

    @staticmethod
    def _slice[Item](items: list[Item], query: DesignerQuery) -> Page[Item]:
        start = (query.page - 1) * query.size
        return Page[Item](
            items=items[start : start + query.size],
            page=query.page,
            size=query.size,
            total=len(items),
        )

    @classmethod
    def _schema_paths(
        cls, schema: dict[str, Any], prefix: str, source: str
    ) -> list[CompletionItemDTO]:
        result: list[CompletionItemDTO] = []
        required = set(schema.get("required", []))
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return result
        for key in sorted(properties):
            child = properties[key]
            if not isinstance(child, dict):
                continue
            path = f"{prefix}.{key}"
            types = child.get("type")
            type_values = {types} if isinstance(types, str) else set(types or [])
            result.append(
                CompletionItemDTO(
                    path=path,
                    source=source,  # ty:ignore[invalid-argument-type]
                    type_schema=child,
                    nullable=key not in required or "null" in type_values,
                    cardinality="LIST" if "array" in type_values else "SCALAR",
                )
            )
            if "object" in type_values:
                result.extend(cls._schema_paths(child, path, source))
        return result
