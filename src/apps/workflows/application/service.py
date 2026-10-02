"""Workflow authoring lifecycle and publication validation."""

from collections import defaultdict
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import delete, null, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.integrations.domain.entity import (
    IntegrationConnectionEntity,
    IntegrationConnectionGrantEntity,
)
from apps.step_types.application.automation import resolve_operation
from apps.step_types.application.registry import HandlerRegistry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeEntity, StepTypePortEntity, StepTypeVersionEntity
from apps.users.domain.auth_entity import AuthAuditEventEntity
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.workflows.application.validation import GraphValidator
from apps.workflows.domain.dto import (
    GraphSnapshot,
    GraphValidationResult,
    WorkflowCreateDTO,
    WorkflowGrantDTO,
    WorkflowVersionCreateDTO,
    WorkflowVersionUpdateDTO,
)
from apps.workflows.domain.entity import (
    WorkflowAccessGrantEntity,
    WorkflowDefinitionEntity,
    WorkflowStepEntity,
    WorkflowStepInputBindingEntity,
    WorkflowStepTargetEntity,
    WorkflowTransitionEntity,
    WorkflowVersionEntity,
)
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    InvalidReferenceException,
    NotAllowedException,
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)


class WorkflowService:
    def __init__(self, session: AsyncSession, registry: HandlerRegistry) -> None:
        self.session = session
        self.registry = registry
        self.validator = GraphValidator()

    async def get(self, ref_id: str, *, update: bool = False) -> WorkflowDefinitionEntity:
        entity_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            WorkflowDefinitionEntity, entity_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Workflow not found")
        if update and row.version != expected:
            raise VersionConflictException("Workflow is stale")
        return row

    async def create(self, data: WorkflowCreateDTO, actor_id: UUID) -> WorkflowDefinitionEntity:
        row = WorkflowDefinitionEntity(**data.model_dump(), owner_user_id=actor_id)
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, ref_id: str, data: WorkflowCreateDTO) -> WorkflowDefinitionEntity:
        row = await self.get(ref_id, update=True)
        row.sqlmodel_update(data.model_dump())
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete(self, ref_id: str) -> None:
        row = await self.get(ref_id, update=True)
        row.deleted_at = get_datetime_utc()
        row.is_active = False
        await self.session.flush()

    async def get_version(self, ref_id: str, *, update: bool = False) -> WorkflowVersionEntity:
        entity_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            WorkflowVersionEntity, entity_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Workflow version not found")
        if update and row.version != expected:
            raise VersionConflictException("Workflow version is stale")
        return row

    async def create_version(self, data: WorkflowVersionCreateDTO) -> WorkflowVersionEntity:
        root = await self.get(data.workflow_ref_id, update=True)
        if not root.is_active:
            raise VersionConflictException("Workflow is inactive")
        row = WorkflowVersionEntity(
            workflow_definition_id=root.id,
            number=data.number,
            default_priority=data.default_priority,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def update_version(
        self, ref_id: str, data: WorkflowVersionUpdateDTO
    ) -> WorkflowVersionEntity:
        row = await self._draft(ref_id)
        row.default_priority = data.default_priority
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete_version(self, ref_id: str) -> None:
        row = await self._draft(ref_id)
        row.deleted_at = get_datetime_utc()
        await self.session.flush()

    async def replace_graph(
        self, ref_id: str, graph: GraphSnapshot, actor_id: UUID | None = None
    ) -> WorkflowVersionEntity:
        version = await self._draft(ref_id)
        result = await self.validate_graph(graph, actor_id, parent_version_id=version.id)
        if not result.valid:
            raise ValidationDetailsException([issue.model_dump() for issue in result.issues])

        version.subprocess_interface = (
            graph.interface.model_dump(mode="json") if graph.interface else None
        )
        step_ids = list(
            (
                await self.session.exec(
                    select(WorkflowStepEntity.id).where(
                        WorkflowStepEntity.workflow_version_id == version.id
                    )
                )
            ).all()
        )
        if step_ids:
            await self.session.exec(
                delete(WorkflowTransitionEntity).where(
                    col(WorkflowTransitionEntity.workflow_version_id) == version.id
                )
            )
            await self.session.exec(
                delete(WorkflowStepInputBindingEntity).where(
                    col(WorkflowStepInputBindingEntity.workflow_step_id).in_(step_ids)
                )
            )
            await self.session.exec(
                delete(WorkflowStepTargetEntity).where(
                    col(WorkflowStepTargetEntity.workflow_step_id).in_(step_ids)
                )
            )
            await self.session.exec(
                delete(WorkflowStepEntity).where(
                    col(WorkflowStepEntity.workflow_version_id) == version.id
                )
            )
            await self.session.flush()

        type_versions, ports = await self._dependency_maps(graph)
        steps: dict[str, WorkflowStepEntity] = {}
        for item in graph.steps:
            type_version = type_versions[item.type_version_ref or ""]
            form_id = open_ref_id(item.form_ref)[0] if item.form_ref else None
            row = WorkflowStepEntity(
                workflow_version_id=version.id,
                step_type_version_id=type_version.id,
                step_key=item.key,
                config=item.config,
                flow=item.flow.model_dump(mode="json", exclude_defaults=True),
                form_version_id=form_id,
                field_policy=(item.field_policy or {}) if item.form_ref else None,
                task_contract=item.task_contract.model_dump(mode="json")
                if item.task_contract
                else None,
                subprocess_call=item.subprocess.model_dump(mode="json")
                if item.subprocess
                else None,
                default_priority=item.default_priority,
                timeout_seconds=item.timeout_seconds,
                display_order=item.display_order,
            )
            self.session.add(row)
            steps[item.key] = row
        await self.session.flush()

        for item in graph.bindings:
            self.session.add(
                WorkflowStepInputBindingEntity(
                    workflow_step_id=steps[item.step].id,
                    target_port_id=ports[(item.step, "INPUT", item.target_port)].id,
                    ordinal=item.ordinal,
                    source_kind=item.source_kind,
                    source_path=item.source_path,
                    source_step_id=steps[item.source_step].id if item.source_step else None,
                    source_port_id=ports[(item.source_step, "OUTPUT", item.source_port)].id
                    if item.source_step and item.source_port
                    else None,
                    constant_value=(
                        item.constant_value if item.source_kind == "CONSTANT" else null()
                    ),
                )
            )
        for item in graph.targets:
            self.session.add(
                WorkflowStepTargetEntity(
                    workflow_step_id=steps[item.step].id,
                    user_id=open_ref_id(item.user_ref)[0] if item.user_ref else None,
                    work_group_id=open_ref_id(item.work_group_ref)[0]
                    if item.work_group_ref
                    else None,
                    condition=item.condition,
                    priority=item.priority,
                )
            )
        for item in graph.transitions:
            self.session.add(
                WorkflowTransitionEntity(
                    workflow_version_id=version.id,
                    source_step_id=steps[item.source].id,
                    target_step_id=steps[item.target].id,
                    outcome=item.outcome,
                    condition=item.condition,
                    is_default=item.is_default,
                    priority=item.priority,
                )
            )
        version.updated_at = get_datetime_utc()
        await self.session.flush()
        return version

    async def validate_graph(
        self,
        graph: GraphSnapshot,
        actor_id: UUID | None = None,
        *,
        parent_version_id: UUID | None = None,
    ) -> GraphValidationResult:
        output_schemas = await self._validate_dependencies(graph, actor_id)
        from apps.workflows.application.subprocess import SubprocessValidator

        await SubprocessValidator(self.session, self).validate(graph, actor_id, parent_version_id)
        return self.validator.validate(graph, step_output_schemas=output_schemas)

    async def publish(self, ref_id: str, actor_id: UUID) -> WorkflowVersionEntity:
        version = await self._draft(ref_id)
        root = await self.session.get(
            WorkflowDefinitionEntity, version.workflow_definition_id, with_for_update=True
        )
        if root is None or root.deleted_at or not root.is_active:
            raise VersionConflictException("Workflow is inactive")
        graph = await self.snapshot(version.id)
        result = await self.validate_graph(graph, actor_id, parent_version_id=version.id)
        if not result.valid or result.checksum is None:
            raise ValidationDetailsException([issue.model_dump() for issue in result.issues])
        version.graph_checksum = result.checksum
        version.status = "PUBLISHED"
        version.published_by_user_id = actor_id
        version.published_at = get_datetime_utc()
        version.updated_at = version.published_at
        await self.session.flush()
        return version

    async def retire(self, ref_id: str) -> WorkflowVersionEntity:
        row = await self.get_version(ref_id, update=True)
        if row.status != "PUBLISHED":
            raise VersionConflictException("Only published workflows can be retired")
        row.status = "RETIRED"
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def add_grant(
        self, workflow_ref: str, data: WorkflowGrantDTO, actor_id: UUID
    ) -> WorkflowAccessGrantEntity:
        root = await self.get(workflow_ref, update=True)
        user_id = open_ref_id(data.user_ref_id)[0] if data.user_ref_id else None
        group_id = open_ref_id(data.work_group_ref_id)[0] if data.work_group_ref_id else None
        user = await self.session.get(UserEntity, user_id) if user_id else None
        group = await self.session.get(WorkGroupEntity, group_id) if group_id else None
        if user_id and (user is None or user.deleted_at):
            raise NotFoundException("Active grant user not found")
        if group_id and (group is None or group.deleted_at or not group.is_active):
            raise NotFoundException("Active grant work group not found")
        row = (
            await self.session.exec(
                select(WorkflowAccessGrantEntity).where(
                    WorkflowAccessGrantEntity.workflow_definition_id == root.id,
                    WorkflowAccessGrantEntity.user_id == user_id,
                    WorkflowAccessGrantEntity.work_group_id == group_id,
                    col(WorkflowAccessGrantEntity.deleted_at).is_(None),
                )
            )
        ).one_or_none()
        if row is None:
            row = WorkflowAccessGrantEntity(
                workflow_definition_id=root.id,
                user_id=user_id,
                work_group_id=group_id,
            )
            self.session.add(row)
        row.can_view = data.can_view
        row.can_start = data.can_start
        row.updated_at = get_datetime_utc()
        self._audit_grant(root.id, actor_id, "changed", row.user_id or row.work_group_id)
        await self.session.flush()
        return row

    async def remove_grant(self, workflow_ref: str, grant_ref: str, actor_id: UUID) -> None:
        root = await self.get(workflow_ref, update=True)
        grant_id, expected = open_ref_id(grant_ref)
        row = await self.session.get(
            WorkflowAccessGrantEntity,
            grant_id,
            with_for_update=True,
            populate_existing=True,
        )
        if row is None or row.deleted_at or row.workflow_definition_id != root.id:
            raise NotFoundException("Workflow grant not found")
        if row.version != expected:
            raise VersionConflictException("Workflow grant is stale")
        row.deleted_at = get_datetime_utc()
        row.updated_at = row.deleted_at
        self._audit_grant(root.id, actor_id, "removed", row.user_id or row.work_group_id)
        await self.session.flush()

    def _audit_grant(
        self, workflow_id: UUID, actor_id: UUID, action: str, target_id: UUID | None
    ) -> None:
        self.session.add(
            AuthAuditEventEntity(
                user_id=actor_id,
                event_type=f"workflow.grant_{action}",
                details={"workflow_id": str(workflow_id), "target_id": str(target_id)},
            )
        )

    async def can_access(
        self,
        workflow: WorkflowDefinitionEntity,
        actor: UserEntity,
        action: Literal["view", "start"],
    ) -> bool:
        if actor.deleted_at:
            return False
        if actor.is_superuser or workflow.owner_user_id == actor.id:
            return True
        if workflow.access_mode == "OPEN":
            return True
        capability = (
            WorkflowAccessGrantEntity.can_start
            if action == "start"
            else WorkflowAccessGrantEntity.can_view
        )
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
        grant = (
            await self.session.exec(
                select(WorkflowAccessGrantEntity.id).where(
                    WorkflowAccessGrantEntity.workflow_definition_id == workflow.id,
                    col(WorkflowAccessGrantEntity.deleted_at).is_(None),
                    col(capability).is_(True),
                    or_(
                        col(WorkflowAccessGrantEntity.user_id) == actor.id,
                        col(WorkflowAccessGrantEntity.work_group_id).in_(groups),
                    ),
                )
            )
        ).first()
        return grant is not None

    async def snapshot(self, version_id: UUID) -> GraphSnapshot:
        steps = list(
            (
                await self.session.exec(
                    select(WorkflowStepEntity)
                    .where(WorkflowStepEntity.workflow_version_id == version_id)
                    .order_by(
                        col(WorkflowStepEntity.display_order), col(WorkflowStepEntity.step_key)
                    )
                )
            ).all()
        )
        if not steps:
            version = await self.session.get(WorkflowVersionEntity, version_id)
            return GraphSnapshot(
                steps=[], interface=version.subprocess_interface if version else None
            )
        step_ids = [step.id for step in steps]
        type_ids = {step.step_type_version_id for step in steps}
        versions = {
            row.id: row
            for row in (
                await self.session.exec(
                    select(StepTypeVersionEntity).where(col(StepTypeVersionEntity.id).in_(type_ids))
                )
            ).all()
        }
        roots = {
            row.id: row
            for row in (
                await self.session.exec(
                    select(StepTypeEntity).where(
                        col(StepTypeEntity.id).in_({row.step_type_id for row in versions.values()})
                    )
                )
            ).all()
        }
        ports = {
            row.id: row
            for row in (
                await self.session.exec(
                    select(StepTypePortEntity).where(
                        col(StepTypePortEntity.step_type_version_id).in_(type_ids)
                    )
                )
            ).all()
        }
        form_ids = {step.form_version_id for step in steps if step.form_version_id}
        forms = {
            row.id: row
            for row in (
                await self.session.exec(
                    select(FormVersionEntity).where(col(FormVersionEntity.id).in_(form_ids))
                )
            ).all()
        }
        from apps.workflows.domain.dto import GraphBinding, GraphStep, GraphTarget, GraphTransition
        from core.ref_id import create_ref_id

        key_by_id = {step.id: step.step_key for step in steps}
        transform_contracts: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        graph_steps = []
        for step in steps:
            type_version = versions[step.step_type_version_id]
            contract = self.registry.transform_contract(
                type_version.handler_key, type_version.handler_version, step.config
            )
            if contract is not None:
                transform_contracts[step.step_key] = contract
            graph_steps.append(
                GraphStep(
                    key=step.step_key,
                    type_code=cast(Any, roots[type_version.step_type_id].code),
                    type_version_ref=create_ref_id(type_version.id, type_version.version),
                    config=step.config,
                    flow=step.flow,
                    form_ref=(
                        create_ref_id(step.form_version_id, forms[step.form_version_id].version)
                        if step.form_version_id
                        else None
                    ),
                    field_policy=step.field_policy,
                    task_contract=step.task_contract,
                    subprocess=step.subprocess_call,
                    default_priority=step.default_priority,
                    timeout_seconds=step.timeout_seconds,
                    display_order=step.display_order,
                )
            )
        bindings = []
        for row in (
            await self.session.exec(
                select(WorkflowStepInputBindingEntity).where(
                    col(WorkflowStepInputBindingEntity.workflow_step_id).in_(step_ids)
                )
            )
        ).all():
            target = ports[row.target_port_id]
            source = ports.get(row.source_port_id)
            step_key = key_by_id[row.workflow_step_id]
            source_step_key = key_by_id.get(row.source_step_id)
            bindings.append(
                GraphBinding(
                    step=step_key,
                    target_port=target.port_key,
                    target_schema=(
                        transform_contracts[step_key][0]
                        if step_key in transform_contracts and target.port_key == "value"
                        else target.value_schema
                    ),
                    ordinal=row.ordinal,
                    source_kind=cast(Any, row.source_kind),
                    source_path=row.source_path,
                    source_step=source_step_key,
                    source_port=source.port_key if source else None,
                    source_schema=(
                        transform_contracts[source_step_key][1]
                        if source
                        and source_step_key in transform_contracts
                        and source.port_key == "result"
                        else source.value_schema
                        if source
                        else None
                    ),
                    constant_value=row.constant_value,
                )
            )
        target_rows = list(
            (
                await self.session.exec(
                    select(WorkflowStepTargetEntity).where(
                        col(WorkflowStepTargetEntity.workflow_step_id).in_(step_ids)
                    )
                )
            ).all()
        )
        user_ids = {row.user_id for row in target_rows if row.user_id}
        group_ids = {row.work_group_id for row in target_rows if row.work_group_id}
        users = {
            row.id: row
            for row in (
                await self.session.exec(select(UserEntity).where(col(UserEntity.id).in_(user_ids)))
            ).all()
        }
        groups = {
            row.id: row
            for row in (
                await self.session.exec(
                    select(WorkGroupEntity).where(col(WorkGroupEntity.id).in_(group_ids))
                )
            ).all()
        }
        targets = [
            GraphTarget(
                step=key_by_id[row.workflow_step_id],
                user_ref=create_ref_id(row.user_id, users[row.user_id].version)
                if row.user_id
                else None,
                work_group_ref=create_ref_id(row.work_group_id, groups[row.work_group_id].version)
                if row.work_group_id
                else None,
                condition=row.condition,
                priority=row.priority,
            )
            for row in target_rows
        ]
        transitions = [
            GraphTransition(
                source=key_by_id[row.source_step_id],
                target=key_by_id[row.target_step_id],
                outcome=row.outcome,
                condition=row.condition,
                is_default=row.is_default,
                priority=row.priority,
            )
            for row in (
                await self.session.exec(
                    select(WorkflowTransitionEntity).where(
                        WorkflowTransitionEntity.workflow_version_id == version_id
                    )
                )
            ).all()
        ]
        version = await self.session.get(WorkflowVersionEntity, version_id)
        return GraphSnapshot(
            steps=graph_steps,
            bindings=bindings,
            targets=targets,
            transitions=transitions,
            interface=version.subprocess_interface if version else None,
        )

    async def _draft(self, ref_id: str) -> WorkflowVersionEntity:
        row = await self.get_version(ref_id, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Workflow version is immutable")
        return row

    async def _dependency_maps(
        self, graph: GraphSnapshot
    ) -> tuple[dict[str, StepTypeVersionEntity], dict[tuple[str, str, str], StepTypePortEntity]]:
        versions: dict[str, StepTypeVersionEntity] = {}
        ports: dict[tuple[str, str, str], StepTypePortEntity] = {}
        service = StepTypeService(self.session, self.registry)
        for step in graph.steps:
            if not step.type_version_ref:
                continue
            try:
                version_id, _ = open_ref_id(step.type_version_ref)
                version = await service.resolve_version(version_id, for_new_use=True)
            except (
                InvalidReferenceException,
                NotAllowedException,
                NotFoundException,
                VersionConflictException,
                ValueError,
            ):
                continue
            versions[step.type_version_ref] = version
            for port in (
                await self.session.exec(
                    select(StepTypePortEntity).where(
                        StepTypePortEntity.step_type_version_id == version.id
                    )
                )
            ).all():
                ports[(step.key, port.direction, port.port_key)] = port
        return versions, ports

    async def _validate_dependencies(
        self, graph: GraphSnapshot, actor_id: UUID | None = None
    ) -> dict[str, dict[str, dict[str, Any]]]:
        issues: list[dict[str, str]] = []
        versions, ports = await self._dependency_maps(graph)
        versions_by_step = {
            step.key: versions.get(step.type_version_ref or "") for step in graph.steps
        }
        human_outcomes: dict[str, set[str]] = {}
        transform_contracts: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for index, step in enumerate(graph.steps):
            if not step.type_version_ref or step.type_version_ref not in versions:
                issues.append(
                    {"pointer": f"/steps/{index}/type_version_ref", "code": "step_type.required"}
                )
                continue
            version = versions[step.type_version_ref]
            root = await self.session.get(StepTypeEntity, version.step_type_id)
            if root is None or root.code != step.type_code:
                issues.append(
                    {"pointer": f"/steps/{index}/type_code", "code": "step_type.mismatch"}
                )
            config: dict[str, Any] = step.config
            if step.type_code == "HUMAN_TASK" and step.form_ref:
                config = {**config, "form_version_ref": step.form_ref}
                try:
                    form_id, _ = open_ref_id(step.form_ref)
                    form = await self.session.get(FormVersionEntity, form_id)
                except InvalidReferenceException:
                    form = None
                form_root = (
                    await self.session.get(FormDefinitionEntity, form.form_definition_id)
                    if form is not None
                    else None
                )
                if (
                    form is None
                    or form.status != "PUBLISHED"
                    or form_root is None
                    or not form_root.is_active
                    or form_root.deleted_at
                ):
                    issues.append(
                        {"pointer": f"/steps/{index}/form_ref", "code": "human.form.not_published"}
                    )
                elif not self._valid_field_policy(step.field_policy or {}, form.data_schema):
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/field_policy",
                            "code": "human.field_policy.invalid",
                        }
                    )
                else:
                    human_outcomes[step.key] = set(form.render_schema.get("outcomes", []))
                    if step.task_contract is not None:
                        from apps.work_items.application.task_views import (
                            TaskPolicyError,
                            validate_contract,
                        )

                        try:
                            validate_contract(
                                step.task_contract,
                                step.field_policy or {},
                                form.data_schema,
                                human_outcomes[step.key],
                                {
                                    edge.outcome
                                    for edge in graph.transitions
                                    if edge.source == step.key
                                },
                            )
                        except TaskPolicyError as exc:
                            issues.append(
                                {
                                    "pointer": f"/steps/{index}/task_contract",
                                    "code": str(exc),
                                }
                            )
            elif step.task_contract is not None:
                issues.append(
                    {"pointer": f"/steps/{index}/task_contract", "code": "task.contract.human_only"}
                )
            try:
                self.registry.validate_config(version.handler_key, version.handler_version, config)
                contract = self.registry.transform_contract(
                    version.handler_key, version.handler_version, config
                )
                if contract is not None:
                    transform_contracts[step.key] = contract
            except ValueError:
                issues.append({"pointer": f"/steps/{index}/config", "code": "step.config.invalid"})
            if step.type_code == "NOTIFICATION":
                try:
                    from apps.notifications.application.templates import (
                        NotificationTemplateRegistry,
                    )
                    from apps.step_types.application.registry import NotificationConfigV2

                    notification_config = NotificationConfigV2.model_validate(config)
                    NotificationTemplateRegistry().resolve(
                        notification_config.template_key, notification_config.template_version
                    )
                except ValueError:
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/config/template_key",
                            "code": "notification.template.unknown",
                        }
                    )
            handler = self.registry.resolve(version.handler_key, version.handler_version)
            if handler.handler_key == "ai_decision":
                if not any(
                    edge.source == step.key and edge.outcome == "next" for edge in graph.transitions
                ):
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/config",
                            "code": "ai.normal_handoff.required",
                        }
                    )
                review_targets = {
                    edge.target
                    for edge in graph.transitions
                    if edge.source == step.key and edge.outcome == "review"
                }
                if not any(
                    target.key in review_targets and target.type_code == "HUMAN_TASK"
                    for target in graph.steps
                ):
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/config",
                            "code": "ai.review_handoff.required",
                        }
                    )
                if actor_id is not None:
                    from apps.ai.application.agent_service import AIAgentService

                    actor = await self.session.get(UserEntity, actor_id)
                    try:
                        agent_ref = config.get("agent_ref")
                        if not isinstance(agent_ref, str) or actor is None:
                            raise ValueError("AI agent reference is required")
                        await AIAgentService(self.session).published(agent_ref, actor)
                    except (
                        InvalidReferenceException,
                        NotAllowedException,
                        NotFoundException,
                        VersionConflictException,
                        ValueError,
                    ):
                        issues.append(
                            {
                                "pointer": f"/steps/{index}/config/agent_ref",
                                "code": "ai.agent.unavailable",
                            }
                        )
            needs_connection = (
                step.type_code in {"SERVICE_TASK", "NOTIFICATION"}
                or "integration.connection.use" in handler.required_capabilities
            )
            if needs_connection:
                connection_ref = config.get("connection_ref")
                expected_kind = "NOTIFICATION" if step.type_code == "NOTIFICATION" else "SERVICE"
                try:
                    if not isinstance(connection_ref, str):
                        raise TypeError
                    connection_id, connection_version = open_ref_id(connection_ref)
                    connection = await self.session.get(IntegrationConnectionEntity, connection_id)
                    if (
                        connection is None
                        or connection.version != connection_version
                        or connection.deleted_at
                        or connection.status != "ACTIVE"
                        or connection.verification_status != "VERIFIED"
                        or connection.kind != expected_kind
                    ):
                        raise ValueError
                    if actor_id is not None and not await self._can_use_connection(
                        connection, actor_id
                    ):
                        raise ValueError
                except AttributeError, InvalidReferenceException, TypeError, ValueError:
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/config/connection_ref",
                            "code": "connection.unavailable",
                        }
                    )
            if step.type_code == "SERVICE_TASK":
                try:
                    resolve_operation(
                        str(config.get("operation_key", "")),
                        version.handler_key,
                        version.handler_version,
                    )
                except ValueError:
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/config/operation_key",
                            "code": "automation.operation.unknown",
                        }
                    )
        for index, transition in enumerate(graph.transitions):
            allowed = human_outcomes.get(transition.source)
            if allowed is not None and transition.outcome not in allowed:
                issues.append(
                    {
                        "pointer": f"/transitions/{index}/outcome",
                        "code": "transition.outcome.unknown",
                    }
                )
        bindings_by_port: dict[tuple[str, str], list[int]] = {}
        for index, binding in enumerate(graph.bindings):
            target = ports.get((binding.step, "INPUT", binding.target_port))
            if target is None:
                issues.append(
                    {
                        "pointer": f"/bindings/{index}/target_port",
                        "code": "binding.target_port.unknown",
                    }
                )
            elif (
                transform_contracts[binding.step][0]
                if binding.step in transform_contracts and binding.target_port == "value"
                else target.value_schema
            ) != binding.target_schema:
                issues.append(
                    {
                        "pointer": f"/bindings/{index}/target_schema",
                        "code": "binding.target_schema.mismatch",
                    }
                )
            else:
                bindings_by_port.setdefault((binding.step, binding.target_port), []).append(
                    binding.ordinal
                )
                if target.cardinality == "SCALAR" and binding.ordinal != 0:
                    issues.append(
                        {
                            "pointer": f"/bindings/{index}/ordinal",
                            "code": "binding.scalar.ordinal",
                        }
                    )
            if binding.source_kind == "STEP_OUTPUT":
                source = ports.get((binding.source_step or "", "OUTPUT", binding.source_port or ""))
                if source is None:
                    issues.append(
                        {
                            "pointer": f"/bindings/{index}/source_port",
                            "code": "binding.source_port.unknown",
                        }
                    )
                elif (
                    transform_contracts[binding.source_step or ""][1]
                    if binding.source_step in transform_contracts
                    and binding.source_port == "result"
                    else source.value_schema
                ) != binding.source_schema:
                    issues.append(
                        {
                            "pointer": f"/bindings/{index}/source_schema",
                            "code": "binding.source_schema.mismatch",
                        }
                    )
            if binding.source_kind == "CONSTANT" and target is not None:
                try:
                    # Registry port adapters enforce cardinality and nullability precisely.
                    step_version = versions_by_step.get(binding.step)
                    if step_version is None:
                        raise ValueError
                    definition = self.registry.resolve(
                        step_version.handler_key,
                        step_version.handler_version,
                    )
                    port = next(
                        port
                        for port in definition.ports
                        if port.direction == "INPUT" and port.port_key == binding.target_port
                    )
                    port.adapter().validate_python(binding.constant_value, strict=True)
                    graph_step = next(step for step in graph.steps if step.key == binding.step)
                    if graph_step.type_code == "NOTIFICATION" and binding.target_port == "data":
                        from apps.notifications.application.templates import (
                            NotificationTemplateRegistry,
                        )
                        from apps.step_types.application.registry import NotificationConfigV2

                        notification_config = NotificationConfigV2.model_validate(graph_step.config)
                        NotificationTemplateRegistry().validate_data(
                            notification_config.template_key,
                            notification_config.template_version,
                            binding.constant_value,
                        )
                except ValueError, StopIteration:
                    issues.append(
                        {
                            "pointer": f"/bindings/{index}/constant_value",
                            "code": "binding.constant.invalid",
                        }
                    )
        for step_index, step in enumerate(graph.steps):
            for (key, direction, port_key), port in ports.items():
                if key != step.key or direction != "INPUT":
                    continue
                ordinals = sorted(bindings_by_port.get((key, port_key), []))
                if port.required and not ordinals:
                    issues.append(
                        {
                            "pointer": f"/steps/{step_index}/key",
                            "code": "binding.required.missing",
                        }
                    )
                if port.cardinality == "LIST" and ordinals != list(range(len(ordinals))):
                    issues.append({"pointer": "/bindings", "code": "binding.list.ordinal"})
        for index, target in enumerate(graph.targets):
            if target.user_ref:
                try:
                    user = await self.session.get(UserEntity, open_ref_id(target.user_ref)[0])
                except InvalidReferenceException:
                    user = None
                if user is None or user.deleted_at:
                    issues.append(
                        {"pointer": f"/targets/{index}/user_ref", "code": "human.user.unknown"}
                    )
            if target.work_group_ref:
                try:
                    group = await self.session.get(
                        WorkGroupEntity, open_ref_id(target.work_group_ref)[0]
                    )
                except InvalidReferenceException:
                    group = None
                if group is None or not group.is_active or group.deleted_at:
                    issues.append(
                        {
                            "pointer": f"/targets/{index}/work_group_ref",
                            "code": "human.work_group.inactive",
                        }
                    )
        if issues:
            raise ValidationDetailsException(issues)
        output_schemas: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for (step_key, direction, port_key), port in ports.items():
            if direction == "OUTPUT":
                output_schemas[step_key][port_key] = port.value_schema
        for step_key, (_, output_schema) in transform_contracts.items():
            output_schemas[step_key]["result"] = output_schema
        return dict(output_schemas)

    async def _can_use_connection(
        self, connection: IntegrationConnectionEntity, actor_id: UUID
    ) -> bool:
        actor = await self.session.get(UserEntity, actor_id)
        if actor is None or actor.deleted_at:
            return False
        if actor.is_superuser or connection.owner_user_id == actor_id:
            return True
        groups = (
            select(WorkGroupMemberEntity.work_group_id)
            .join(
                WorkGroupEntity,
                col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id),
            )
            .where(
                WorkGroupMemberEntity.user_id == actor_id,
                col(WorkGroupMemberEntity.is_active).is_(True),
                col(WorkGroupEntity.is_active).is_(True),
                col(WorkGroupEntity.deleted_at).is_(None),
            )
        )
        grant = (
            await self.session.exec(
                select(IntegrationConnectionGrantEntity.id).where(
                    IntegrationConnectionGrantEntity.integration_connection_id == connection.id,
                    col(IntegrationConnectionGrantEntity.deleted_at).is_(None),
                    or_(
                        col(IntegrationConnectionGrantEntity.can_use).is_(True),
                        col(IntegrationConnectionGrantEntity.can_manage).is_(True),
                    ),
                    or_(
                        col(IntegrationConnectionGrantEntity.user_id) == actor_id,
                        col(IntegrationConnectionGrantEntity.work_group_id).in_(groups),
                    ),
                )
            )
        ).first()
        return grant is not None

    @staticmethod
    def _valid_field_policy(policy: dict[str, list[str]], schema: dict[str, Any]) -> bool:
        if set(policy) != {"read", "write", "required", "hidden"}:
            return False
        paths = {item for values in policy.values() for item in values}
        if any(not item.startswith("/") for item in paths):
            return False
        required = {f"/properties/{key}" for key in schema.get("required", [])}
        visible_or_required = (
            set(policy["read"]) | set(policy["write"]) | set(policy["required"]) | required
        )
        if set(policy["hidden"]) & visible_or_required:
            return False
        return all(GraphValidator._schema_at(schema, path) is not None for path in paths)
