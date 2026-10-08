"""Transactional human work and bounded cartable projections."""

import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from typing import Any, Literal
from uuid import UUID, uuid7

from sqlalchemy import and_, exists, func, or_, update
from sqlalchemy.orm import aliased
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.domain.contracts import ClientContext
from apps.forms.application.attachments import AttachmentService
from apps.forms.application.behavior import pinned_behavior_documents
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.options import OptionService
from apps.forms.domain.attachment_dto import (
    AttachmentAddDTO,
    AttachmentReorderDTO,
    AttachmentReplaceDTO,
)
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.entity import FormVersionEntity
from apps.media.domain.entity import UserUploadEntity
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
from apps.requests.domain.entity import (
    BusinessRequestEntity,
    FormSubmissionAttachmentEntity,
    FormSubmissionEntity,
)
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_items.application.task_mutations import (
    merge_task_data,
    normalize_task_behavior,
    project_task_state,
)
from apps.work_items.domain.dto import CartableKind, CartableQueryDTO, WorkItemForwardDTO
from apps.work_items.domain.entity import (
    UserWorkItemStateEntity,
    WorkItemActionEntity,
    WorkItemCandidateEntity,
    WorkItemEntity,
)
from apps.work_items.domain.state import transition
from apps.work_items.domain.task_contract import HumanTaskContract
from apps.workflows.domain.entity import (
    WorkflowStepEntity,
    WorkflowStepTargetEntity,
    WorkflowTransitionEntity,
)
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)
from utils.pagination import Page

_TERMINAL = {"COMPLETED", "REJECTED", "RETURNED", "CANCELLED", "EXPIRED"}


class WorkItemService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_for_wait(
        self,
        execution: StepExecutionEntity,
        step: WorkflowStepEntity,
        request: BusinessRequestEntity,
        targets: list[WorkflowStepTargetEntity],
        initial_data: dict[str, Any],
    ) -> WorkItemEntity:
        existing = (
            await self.session.exec(
                select(WorkItemEntity).where(
                    WorkItemEntity.step_execution_id == execution.id,
                    col(WorkItemEntity.status).in_(["OPEN", "CLAIMED", "IN_PROGRESS"]),
                )
            )
        ).one_or_none()
        if existing is not None:
            return existing
        if not targets:
            raise VersionConflictException(
                "Human task has no eligible candidates", conflict_kind="lifecycle"
            )
        if step.form_version_id is None:
            raise VersionConflictException(
                "Human task has no pinned form", conflict_kind="lifecycle"
            )
        now = get_datetime_utc()
        item = WorkItemEntity(
            step_execution_id=execution.id,
            business_request_id=request.id,
            priority=step.default_priority
            if step.default_priority is not None
            else request.priority,
            due_at=now + timedelta(seconds=step.timeout_seconds)
            if bool(step.timeout_seconds)
            else None,
            form_version_id=step.form_version_id,
        )
        self.session.add(item)
        await self.session.flush()
        for target in targets:
            self.session.add(
                WorkItemCandidateEntity(
                    work_item_id=item.id,
                    user_id=target.user_id,
                    work_group_id=target.work_group_id,
                    source_target_id=target.id,
                )
            )
        form = await self.session.get(FormVersionEntity, step.form_version_id)
        if form is None:
            raise VersionConflictException(
                "Human form version is unavailable", conflict_kind="lifecycle"
            )
        correction_source = None
        if bool(step.task_contract) and step.task_contract.get("correction_entry"):
            prior = (
                await self.session.exec(
                    select(FormSubmissionEntity)
                    .join(
                        WorkItemEntity,
                        col(WorkItemEntity.step_execution_id)
                        == col(FormSubmissionEntity.step_execution_id),
                    )
                    .where(
                        FormSubmissionEntity.business_request_id == request.id,
                        WorkItemEntity.status == "RETURNED",
                    )
                    .order_by(col(WorkItemEntity.closed_at).desc(), col(WorkItemEntity.id).desc())
                    .limit(1)
                    .with_for_update(of=FormSubmissionEntity)
                )
            ).first()
            if prior is not None:
                consumed = (
                    await self.session.exec(
                        select(FormSubmissionEntity.id).where(
                            FormSubmissionEntity.correction_source_submission_id == prior.id
                        )
                    )
                ).first()
                if consumed is not None:
                    raise VersionConflictException(
                        "Correction source is already consumed", conflict_kind="lifecycle"
                    )
                correction_source = prior
                initial_data = deepcopy(prior.data)
        inherited_source = None
        if (
            bool(step.task_contract)
            and step.task_contract.get("inherit_previous")
            and correction_source is None
        ):
            inherited_source = (
                await self.session.exec(
                    select(FormSubmissionEntity)
                    .where(
                        FormSubmissionEntity.business_request_id == request.id,
                        FormSubmissionEntity.status == "SUBMITTED",
                    )
                    .order_by(
                        col(FormSubmissionEntity.submitted_at).desc(),
                        col(FormSubmissionEntity.id).desc(),
                    )
                    .limit(1)
                )
            ).first()
            if inherited_source is not None:
                initial_data = {**deepcopy(inherited_source.data), **initial_data}
        context = ClientContext.from_origin_snapshot(request.origin_client_context)
        try:
            design = resolve_form_documents(
                FormDocuments.model_validate(form, from_attributes=True), context
            )
        except ValueError:
            raise VersionConflictException(
                "Origin client cannot render the human form", conflict_kind="lifecycle"
            ) from None
        item_identity = None
        if form.behavior_dialect is not None:
            from apps.forms.application.behavior import BehaviorError, evaluate_behavior
            from apps.forms.application.collections import initialize_identity

            try:
                initial_data = evaluate_behavior(
                    pinned_behavior_documents(
                        FormDocuments.model_validate(form, from_attributes=True),
                        {"variant_key": design.key},
                    ),
                    initial_data,
                    initialize=correction_source is None and inherited_source is None,
                    enforce_required=False,
                    overrides=correction_source.override_provenance if correction_source else None,
                ).data
                item_identity = initialize_identity(
                    initial_data,
                    correction_source.item_identity
                    if correction_source
                    else inherited_source.item_identity
                    if inherited_source
                    else None,
                    form.data_schema,
                )
            except BehaviorError as exc:
                raise ValidationDetailsException([{"pointer": "/data", "code": str(exc)}]) from None
        submission = FormSubmissionEntity(
            business_request_id=request.id,
            form_version_id=step.form_version_id,
            step_execution_id=execution.id,
            data=initial_data,
            item_identity=item_identity,
            override_provenance=deepcopy(correction_source.override_provenance)
            if correction_source
            else None,
            correction_source_submission_id=correction_source.id if correction_source else None,
            correction_feedback=deepcopy(correction_source.correction_feedback)
            if correction_source
            else deepcopy(inherited_source.correction_feedback)
            if inherited_source
            else None,
            design_snapshot={
                "variant_key": design.key,
                "design_revision": design.revision,
                "render_schema": design.render_schema,
                "page_settings": design.page_settings,
                "localization": design.localization.model_dump(mode="json")
                if design.localization
                else None,
                "client": context.snapshot(),
                "interaction_revision": 1,
            },
        )
        self.session.add(submission)
        await self.session.flush()
        attachment_source = correction_source or inherited_source
        if attachment_source is not None:
            attachments = (
                await self.session.exec(
                    select(FormSubmissionAttachmentEntity).where(
                        FormSubmissionAttachmentEntity.form_submission_id == attachment_source.id,
                        FormSubmissionAttachmentEntity.status == "ACTIVE",
                    )
                )
            ).all()
            for source_link in attachments:
                self.session.add(
                    FormSubmissionAttachmentEntity(
                        form_submission_id=submission.id,
                        field_path=source_link.field_path,
                        user_upload_id=source_link.user_upload_id,
                        added_by_user_id=source_link.added_by_user_id,
                        contributing_group_id=source_link.contributing_group_id,
                        position=source_link.position,
                        caption=source_link.caption,
                    )
                )
        await self._record(item, None, "CREATE", f"create:{execution.id}", submission=submission)
        await self.session.flush()
        return item

    async def get(
        self, ref_id: str, actor: UserEntity, *, update_row: bool = False
    ) -> WorkItemEntity:
        item_id, expected = open_ref_id(ref_id)
        item = await self.session.get(
            WorkItemEntity, item_id, with_for_update=update_row, populate_existing=update_row
        )
        if item is None or item.deleted_at is not None or not await self.can_view(item, actor):
            raise NotFoundException("Work item not found")
        if update_row and item.version != expected:
            raise VersionConflictException("Work item is stale", conflict_kind="revision")
        return item

    async def can_view(self, item: WorkItemEntity, actor: UserEntity) -> bool:
        if actor.is_superuser or item.claimed_by_user_id == actor.id:
            return True
        request = await self.session.get(BusinessRequestEntity, item.business_request_id)
        if request is not None and request.requester_user_id == actor.id:
            return True
        return item.status == "OPEN" and await self._eligible(
            item.id, actor.id, require_claim=False
        )

    async def can_view_request(self, request_id: UUID, actor: UserEntity) -> bool:
        items = (
            await self.session.exec(
                select(WorkItemEntity).where(
                    WorkItemEntity.business_request_id == request_id,
                    col(WorkItemEntity.deleted_at).is_(None),
                )
            )
        ).all()
        for item in items:
            step = await self._step(item)
            if step.task_contract is not None:
                continue  # Contract tasks expose only the filtered task view.
            if item.claimed_by_user_id == actor.id:
                return True
            if item.status == "OPEN" and await self._eligible(
                item.id, actor.id, require_claim=False
            ):
                return True
        return False

    async def claim(self, ref_id: str, command_key: str, actor: UserEntity) -> WorkItemEntity:
        item_id, expected = open_ref_id(ref_id)
        payload_hash = self._hash({"action": "claim"})
        if await self._idempotent(item_id, command_key, actor.id, payload_hash):
            item = await self.session.get(WorkItemEntity, item_id)
            if item is None:
                raise NotFoundException("Work item not found")
            return item
        if not await self._eligible(item_id, actor.id, require_claim=True):
            raise NotFoundException("Work item not found")
        now = get_datetime_utc()
        result = await self.session.exec(
            update(WorkItemEntity)
            .where(
                col(WorkItemEntity.id) == item_id,
                col(WorkItemEntity.version) == expected,
                col(WorkItemEntity.status) == "OPEN",
                col(WorkItemEntity.deleted_at).is_(None),
            )
            .values(
                status="CLAIMED",
                claimed_by_user_id=actor.id,
                claimed_at=now,
                updated_at=now,
                version=col(WorkItemEntity.version) + 1,
            )
            .returning(col(WorkItemEntity.id))
        )
        if result.first() is None:
            raise VersionConflictException(
                "Work item is no longer available", conflict_kind="lifecycle"
            )
        item = await self.session.get(
            WorkItemEntity, item_id, populate_existing=True, with_for_update=True
        )
        if item is None:
            raise NotFoundException("Work item not found")
        await self._record(
            item, actor, "CLAIM", command_key, details={"payload_hash": payload_hash}
        )
        await self.session.flush()
        return item

    async def claimant_action(
        self,
        ref_id: str,
        action: Literal["release", "start"],
        command_key: str,
        actor: UserEntity,
    ) -> WorkItemEntity:
        item_id, _ = open_ref_id(ref_id)
        payload_hash = self._hash({"action": action})
        if await self._idempotent(item_id, command_key, actor.id, payload_hash):
            item = await self.session.get(WorkItemEntity, item_id)
            if item is None:
                raise NotFoundException("Work item not found")
            return item
        item = await self.get(ref_id, actor, update_row=True)
        self._require_claimant(item, actor)
        try:
            item.status = transition(item.status, action)  # ty:ignore[invalid-argument-type]
        except ValueError as exc:
            raise VersionConflictException(str(exc), conflict_kind="lifecycle") from exc
        now = get_datetime_utc()
        if action == "release":
            item.claimed_by_user_id = None
            item.claimed_at = None
        item.updated_at = now
        await self._record(
            item, actor, action.upper(), command_key, details={"payload_hash": payload_hash}
        )
        await self.session.flush()
        return item

    async def save(
        self,
        ref_id: str,
        command_key: str,
        data: dict[str, Any],
        actor: UserEntity,
        *,
        view_key: str | None = None,
        delete_paths: list[str] | None = None,
    ) -> WorkItemEntity:
        payload_hash = self._hash(
            {
                "data": data,
                **({"view_key": view_key} if view_key is not None else {}),
                **({"delete_paths": delete_paths} if bool(delete_paths) else {}),
            }
        )
        item_id, _ = open_ref_id(ref_id)
        if await self._idempotent(item_id, command_key, actor.id, payload_hash):
            item = await self.session.get(WorkItemEntity, item_id)
            if item is None:
                raise NotFoundException("Work item not found")
            return item
        item = await self.get(ref_id, actor, update_row=True)
        self._require_claimant(item, actor)
        if item.status not in {"CLAIMED", "IN_PROGRESS"}:
            raise VersionConflictException(
                "Work item cannot save a form in this state", conflict_kind="lifecycle"
            )
        submission = await self.submission(item, update_row=True)
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None:
            raise VersionConflictException(
                "Pinned form version is unavailable", conflict_kind="lifecycle"
            )

        step = await self._step(item)
        scopes = self._mutation_scopes(step, view_key)
        canonical = merge_task_data(
            submission.data, data, step.field_policy, view_scopes=scopes, delete_paths=delete_paths
        )
        documents = pinned_behavior_documents(
            FormDocuments.model_validate(form, from_attributes=True), submission.design_snapshot
        )
        canonical = normalize_task_behavior(
            documents, submission.data, data, canonical, submission.override_provenance
        )
        submission.data = self._validate_visible_data(
            step.field_policy,
            scopes,
            documents,
            canonical,
            None,
            submission.override_provenance,
            partial=True,
        )
        if form.behavior_dialect is not None:
            from apps.forms.application.behavior import BehaviorError, evaluate_behavior
            from apps.forms.application.collections import CollectionError, initialize_identity

            try:
                submission.data = evaluate_behavior(
                    pinned_behavior_documents(
                        FormDocuments.model_validate(form, from_attributes=True),
                        submission.design_snapshot,
                    ),
                    submission.data,
                    overrides=submission.override_provenance,
                    enforce_required=False,
                ).data
                submission.item_identity = initialize_identity(
                    submission.data, submission.item_identity, form.data_schema
                )
            except BehaviorError:
                raise ValidationDetailsException(
                    [{"pointer": "/data", "code": "task.validation"}]
                ) from None
            except CollectionError:
                raise ValidationDetailsException(
                    [{"pointer": "/item_identity", "code": "task.validation"}]
                ) from None
        submission.updated_at = get_datetime_utc()
        item.updated_at = submission.updated_at
        await self._record(
            item,
            actor,
            "SAVE",
            command_key,
            submission=submission,
            details={"payload_hash": payload_hash},
        )
        await self.session.flush()
        return item

    async def finish(
        self,
        ref_id: str,
        action: Literal["complete", "reject", "return"],
        command_key: str,
        outcome_key: str,
        data: dict[str, Any],
        actor: UserEntity,
        comment: str | None = None,
        feedback: list[Any] | None = None,
        *,
        view_key: str | None = None,
        delete_paths: list[str] | None = None,
    ) -> WorkItemEntity:
        payload_hash = self._hash(
            {
                "action": action,
                "outcome": outcome_key,
                "data": data,
                "comment": comment,
                "feedback": [row.model_dump() for row in feedback or []],
                **({"view_key": view_key} if view_key is not None else {}),
                **({"delete_paths": delete_paths} if bool(delete_paths) else {}),
            }
        )
        item_id, _ = open_ref_id(ref_id)
        if await self._idempotent(item_id, command_key, actor.id, payload_hash):
            item = await self.session.get(WorkItemEntity, item_id)
            if item is None:
                raise NotFoundException("Work item not found")
            return item
        item = await self.get(ref_id, actor, update_row=True)
        self._require_claimant(item, actor)
        try:
            target = transition(item.status, action)  # ty:ignore[invalid-argument-type]
        except ValueError as exc:
            raise VersionConflictException(str(exc), conflict_kind="lifecycle") from exc
        submission = await self.submission(item, update_row=True)
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.status not in {"PUBLISHED", "RETIRED"}:
            raise VersionConflictException(
                "Pinned form version is unavailable", conflict_kind="lifecycle"
            )
        step = await self._step(item)
        from apps.work_items.application.task_views import (
            action_for,
        )

        contract = (
            HumanTaskContract.model_validate(step.task_contract)
            if bool(step.task_contract)
            else None
        )
        profile = action_for(contract, action, outcome_key) if contract else None
        declared = set(form.render_schema.get("outcomes", []))
        route_match = (
            await self.session.exec(
                select(WorkflowTransitionEntity.id).where(
                    WorkflowTransitionEntity.source_step_id == step.id,
                    WorkflowTransitionEntity.outcome == outcome_key,
                )
            )
        ).first()
        if outcome_key not in declared or route_match is None:
            raise ValidationDetailsException(
                [{"pointer": "/outcome_key", "code": "task.action.unavailable"}]
            )
        if profile and profile.require_comment and not (comment or "").strip():
            raise ValidationDetailsException(
                [{"pointer": "/comment", "code": "task.action.reason_required"}]
            )
        if profile and action == "return" and not bool(feedback):
            raise ValidationDetailsException(
                [{"pointer": "/feedback", "code": "task.feedback.required"}]
            )
        if bool(feedback) and contract is None:
            raise ValidationDetailsException(
                [{"pointer": "/feedback", "code": "task.feedback.unavailable"}]
            )
        if bool(feedback) and action != "return":
            raise ValidationDetailsException(
                [{"pointer": "/feedback", "code": "task.feedback.return_only"}]
            )
        scopes = self._mutation_scopes(step, view_key)
        before = deepcopy(submission.data)
        submission.data = merge_task_data(
            submission.data, data, step.field_policy, view_scopes=scopes, delete_paths=delete_paths
        )
        await AttachmentService(self.session).materialize(submission)
        documents = pinned_behavior_documents(
            FormDocuments.model_validate(form, from_attributes=True),
            submission.design_snapshot,
        )
        submission.data = normalize_task_behavior(
            documents, before, data, submission.data, submission.override_provenance
        )
        submission.data = self._validate_visible_data(
            step.field_policy,
            scopes,
            documents,
            submission.data,
            profile,
            submission.override_provenance,
            policy_required=(step.field_policy or {}).get("required", []),
        )
        try:
            await OptionService(self.session).validate_submission(
                FormDocuments.model_validate(form, from_attributes=True), submission.data, actor
            )
        except ValidationDetailsException as exc:
            raise self._visible_error(exc, step.field_policy, scopes) from None
        if bool(feedback):
            submission.correction_feedback = self._record_feedback(
                submission, feedback, actor, step.field_policy
            )
        now = get_datetime_utc()
        submission.status = "SUBMITTED"
        submission.submitted_by_user_id = actor.id
        submission.submitted_at = now
        submission.updated_at = now
        execution = await self.session.get(StepExecutionEntity, item.step_execution_id)
        if execution is None:
            raise NotFoundException("Step execution not found")
        process = await self.session.get(ProcessInstanceEntity, execution.process_instance_id)
        if process is None:
            raise NotFoundException("Process not found")
        from apps.processes.application.service import ProcessService

        item.status = target
        item.outcome_key = outcome_key
        item.closed_at = now
        item.updated_at = now
        await self._record(
            item,
            actor,
            action.upper(),
            command_key,
            outcome=outcome_key,
            submission=submission,
            comment=comment,
            details={"payload_hash": payload_hash},
        )
        await ProcessService(self.session).resume_execution(
            process.id,
            execution.id,
            f"work-item:{item.id}:{command_key}",
            outcome_key,
            {"submission": submission.data},
            actor_user_id=actor.id,
        )
        await self.session.flush()
        return item

    async def forward(
        self, ref_id: str, data: WorkItemForwardDTO, actor: UserEntity
    ) -> WorkItemEntity:
        payload_hash = self._hash(data.model_dump())
        item_id, _ = open_ref_id(ref_id)
        if await self._idempotent(item_id, data.command_key, actor.id, payload_hash):
            prior = await self._prior(item_id, data.command_key, actor.id)
            if prior is None:
                raise VersionConflictException(
                    "Forward command state is inconsistent", conflict_kind="idempotency"
                )
            forwarded_id = UUID(str(prior.details["forwarded_work_item_id"]))
            forwarded = await self.session.get(WorkItemEntity, forwarded_id)
            if forwarded is None:
                raise NotFoundException("Forwarded work item not found")
            return forwarded
        item = await self.get(ref_id, actor, update_row=True)
        self._require_claimant(item, actor)
        if item.form_version_id is None:
            raise VersionConflictException(
                "AI tool approvals cannot be forwarded", conflict_kind="lifecycle"
            )
        if item.status not in {"CLAIMED", "IN_PROGRESS"}:
            raise VersionConflictException(
                "Work item cannot be forwarded in this state", conflict_kind="lifecycle"
            )
        principals = await self._forward_principals(data)
        now = get_datetime_utc()
        item.status = "RETURNED"
        item.closed_at = now
        item.outcome_key = "forward"
        item.updated_at = now
        await self.session.flush()
        forwarded = WorkItemEntity(
            step_execution_id=item.step_execution_id,
            business_request_id=item.business_request_id,
            priority=item.priority,
            due_at=item.due_at,
            form_version_id=item.form_version_id,
        )
        self.session.add(forwarded)
        await self.session.flush()
        for user_id, group_id in principals:
            self.session.add(
                WorkItemCandidateEntity(
                    work_item_id=forwarded.id, user_id=user_id, work_group_id=group_id
                )
            )
        await self._record(
            item,
            actor,
            "FORWARD",
            data.command_key,
            comment=data.reason,
            details={
                "payload_hash": payload_hash,
                "forwarded_work_item_id": str(forwarded.id),
            },
        )
        await self._record(forwarded, actor, "REASSIGN", f"forward:{item.id}:{data.command_key}")
        await self.session.flush()
        return forwarded

    async def administrative_close(
        self,
        ref_id: str,
        action: Literal["cancel", "expire"],
        command_key: str,
        actor: UserEntity,
    ) -> WorkItemEntity:
        item_id, _ = open_ref_id(ref_id)
        payload_hash = self._hash({"action": action})
        if await self._idempotent(item_id, command_key, actor.id, payload_hash):
            item = await self.session.get(WorkItemEntity, item_id)
            if item is None:
                raise NotFoundException("Work item not found")
            return item
        item = await self.get(ref_id, actor, update_row=True)
        request = await self.session.get(BusinessRequestEntity, item.business_request_id)
        if not actor.is_superuser and (
            action == "expire" or not request or request.requester_user_id != actor.id
        ):
            raise NotAllowedException("Only the requester or an administrator can close this item")
        now = get_datetime_utc()
        if action == "expire" and (item.due_at is None or item.due_at > now):
            raise VersionConflictException("Work item has not expired", conflict_kind="lifecycle")
        execution = await self.session.get(StepExecutionEntity, item.step_execution_id)
        process = (
            await self.session.get(ProcessInstanceEntity, execution.process_instance_id)
            if execution
            else None
        )
        if process is None or execution is None:
            raise NotFoundException("Process not found")
        from apps.processes.application.service import ProcessService

        process_service = ProcessService(self.session)
        process_ref = create_ref_id(process.id, process.version)
        if action == "cancel":
            await process_service.command(
                process_ref,
                "cancel",
                f"work-item:{item.id}:{command_key}",
                actor_user_id=actor.id,
            )
        else:
            await process_service.timeout_execution(
                process.id,
                execution.id,
                f"work-item:{item.id}:{command_key}",
                actor_user_id=actor.id,
            )
        try:
            item.status = transition(item.status, action)  # ty:ignore[invalid-argument-type]
        except ValueError as exc:
            raise VersionConflictException(str(exc), conflict_kind="lifecycle") from exc
        item.closed_at = now
        item.updated_at = item.closed_at
        await self._record(
            item, actor, action.upper(), command_key, details={"payload_hash": payload_hash}
        )
        await self.session.flush()
        return item

    async def comment(
        self, ref_id: str, command_key: str, comment: str, actor: UserEntity
    ) -> WorkItemEntity:
        payload_hash = self._hash({"comment": comment})
        item_id, _ = open_ref_id(ref_id)
        if await self._idempotent(item_id, command_key, actor.id, payload_hash):
            item = await self.session.get(WorkItemEntity, item_id)
            if item is None:
                raise NotFoundException("Work item not found")
            return item
        item = await self.get(ref_id, actor, update_row=True)
        await self._record(
            item,
            actor,
            "COMMENT",
            command_key,
            comment=comment,
            details={"payload_hash": payload_hash},
        )
        await self.session.flush()
        return item

    async def set_user_state(
        self,
        ref_id: str,
        actor: UserEntity,
        field: Literal["read_at", "pinned_at", "archived_at", "watching_at"],
        enabled: bool,
    ) -> WorkItemEntity:
        item = await self.get(ref_id, actor)
        state = await self.session.get(UserWorkItemStateEntity, (actor.id, item.id))
        if state is None:
            state = UserWorkItemStateEntity(user_id=actor.id, work_item_id=item.id)
            self.session.add(state)
        now = get_datetime_utc()
        setattr(state, field, now if enabled else None)
        state.updated_at = now
        await self.session.flush()
        return item

    async def search(self, query: CartableQueryDTO, actor: UserEntity) -> Page[WorkItemEntity]:
        criterion = self._cartable_criterion(query.cartable, actor.id)
        criteria = criterion if isinstance(criterion, tuple) else (criterion,)
        base = [*criteria, col(WorkItemEntity.deleted_at).is_(None)]
        if query.cartable != "watching":
            archived = select(UserWorkItemStateEntity.work_item_id).where(
                UserWorkItemStateEntity.user_id == actor.id,
                col(UserWorkItemStateEntity.archived_at).is_not(None),
            )
            base.append(col(WorkItemEntity.id).not_in(archived))
        items = list(
            (
                await self.session.exec(
                    select(WorkItemEntity)
                    .where(*base)
                    .order_by(
                        col(WorkItemEntity.priority).desc(),
                        col(WorkItemEntity.due_at).asc().nulls_last(),
                        col(WorkItemEntity.created_at),
                        col(WorkItemEntity.id),
                    )
                    .offset((query.page - 1) * query.size)
                    .limit(query.size)
                )
            ).all()
        )
        total = (
            await self.session.exec(select(func.count()).select_from(WorkItemEntity).where(*base))
        ).one()
        return Page[WorkItemEntity](items=items, page=query.page, size=query.size, total=total)

    @staticmethod
    def _record_feedback(
        submission: FormSubmissionEntity,
        feedback: list[Any],
        actor: UserEntity,
        policy: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        from apps.work_items.application.task_views import _data_path

        readable = set((policy or {}).get("read", [])) | set((policy or {}).get("write", []))
        recorded = deepcopy(submission.correction_feedback or [])
        for row in feedback:
            if row.scope not in readable or row.scope in (policy or {}).get("hidden", []):
                raise ValidationDetailsException(
                    [{"pointer": "/feedback/scope", "code": "task.feedback.scope"}]
                )
            schema_path = _data_path(row.scope)
            if "*" in schema_path:
                if row.item_key is None:
                    raise ValidationDetailsException(
                        [{"pointer": "/feedback/item_key", "code": "task.feedback.item_key"}]
                    )
                array_pattern = schema_path[: len(schema_path) - 1 - schema_path[::-1].index("*")]
                matched = any(
                    len(path.split("/")[1:]) == len(array_pattern)
                    and all(
                        part == bound or bound == "*"
                        for part, bound in zip(path.split("/")[1:], array_pattern, strict=True)
                    )
                    and row.item_key in keys
                    for path, keys in (submission.item_identity or {}).items()
                )
                if not matched:
                    raise ValidationDetailsException(
                        [{"pointer": "/feedback/item_key", "code": "task.feedback.item_key"}]
                    )
            elif row.item_key is not None:
                raise ValidationDetailsException(
                    [{"pointer": "/feedback/item_key", "code": "task.feedback.item_key"}]
                )
            recorded.append(
                {
                    "key": str(uuid7()),
                    "scope": row.scope,
                    "item_key": row.item_key,
                    "message": row.message,
                    "actor_ref_id": create_ref_id(actor.id, actor.version),
                    "status": "OPEN",
                    "created_at": get_datetime_utc().isoformat(),
                    "resolved_at": None,
                    "resolved_by_ref_id": None,
                }
            )
        return recorded

    async def resolve_feedback(
        self, ref_id: str, feedback_key: str, actor: UserEntity
    ) -> FormSubmissionEntity:
        item, submission = await self._editable_submission(ref_id, actor)
        if submission.correction_source_submission_id is None:
            raise ValidationDetailsException(
                [{"pointer": "/feedback_key", "code": "task.feedback.unavailable"}]
            )
        rows = deepcopy(submission.correction_feedback or [])
        target = next((row for row in rows if row.get("key") == feedback_key), None)
        if target is None:
            raise NotFoundException("Correction feedback not found")
        step = await self._step(item)
        if bool(step.task_contract):
            from apps.work_items.application.task_views import allowed_view_scopes

            contract = HumanTaskContract.model_validate(step.task_contract)
            view = next(row for row in contract.views if row.key == contract.default_view)
            if target.get("scope") not in allowed_view_scopes(view, step.field_policy or {}):
                raise NotFoundException("Correction feedback not found")
        if target.get("status") != "OPEN":
            raise VersionConflictException(
                "Correction feedback is already resolved", conflict_kind="lifecycle"
            )
        target["status"] = "RESOLVED"
        target["resolved_at"] = get_datetime_utc().isoformat()
        target["resolved_by_ref_id"] = create_ref_id(actor.id, actor.version)
        submission.correction_feedback = rows
        submission.updated_at = get_datetime_utc()
        item.updated_at = submission.updated_at
        await self.session.flush()
        return submission

    async def task_view(self, ref_id: str, actor: UserEntity, view_key: str | None = None):
        from apps.forms.application.localization import localize_snapshot
        from apps.work_items.application.task_views import (
            allowed_view_scopes,
            filter_render,
        )
        from apps.work_items.domain.dto import CorrectionFeedbackDTO, WorkItemViewDTO
        from core.i18n import get_language

        item = await self.get(ref_id, actor)
        submission = await self.submission(item)
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None:
            raise NotFoundException("Pinned form version not found")
        step = await self._step(item)
        snapshot = (
            localize_snapshot(
                submission.design_snapshot, FormDocuments.model_validate(form, from_attributes=True)
            )
            or {}
        )
        contract = (
            HumanTaskContract.model_validate(step.task_contract)
            if bool(step.task_contract)
            else None
        )
        if contract is None:
            if view_key not in {None, "shared"}:
                raise NotFoundException("Task view not found")
            from apps.work_items.application.task_mutations import visible_scopes

            scopes: set[str] | None = visible_scopes(step.field_policy)
            purpose = "edit"
            title = "Task"
            actions = [
                {
                    "key": outcome,
                    "kind": "complete",
                    "outcome_key": outcome,
                    "title": outcome,
                    "confirmation": None,
                    "required_scopes": [],
                    "require_comment": False,
                    "validation": "complete",
                }
                for outcome in form.render_schema.get("outcomes", [])
            ]
            key = "shared"
        else:
            key = view_key or contract.default_view
            view = next((row for row in contract.views if row.key == key), None)
            if view is None:
                raise NotFoundException("Task view not found")
            scopes = allowed_view_scopes(view, step.field_policy or {})
            purpose = view.purpose
            language = get_language()
            title = view.title.fa if language == "fa" and bool(view.title.fa) else view.title.en
            actions = [
                {
                    "key": action.key,
                    "kind": action.kind,
                    "outcome_key": action.outcome_key,
                    "title": action.title.fa
                    if language == "fa" and bool(action.title.fa)
                    else action.title.en,
                    "confirmation": (
                        action.confirmation.fa
                        if language == "fa" and action.confirmation and bool(action.confirmation.fa)
                        else action.confirmation.en
                        if action.confirmation
                        else None
                    ),
                    "required_scopes": action.required_scopes,
                    "require_comment": action.require_comment,
                    "validation": action.validation,
                }
                for action in contract.actions
            ]
        if (
            item.claimed_by_user_id != actor.id
            or item.status not in {"CLAIMED", "IN_PROGRESS"}
            or purpose != "edit"
        ):
            actions = []
        projected = project_task_state(
            submission.data,
            submission.item_identity,
            submission.override_provenance,
            [],
            step.field_policy,
            scopes,
        )
        data = projected["data"]
        render = snapshot.get("render_schema", form.render_schema)
        if scopes is not None:
            render = filter_render(render, scopes)
        from apps.forms.application.runtime import display_render

        render = display_render(render, step.field_policy, scopes)
        source = (
            await self.session.get(FormSubmissionEntity, submission.correction_source_submission_id)
            if submission.correction_source_submission_id
            else None
        )
        if source is None:
            source = (
                await self.session.exec(
                    select(FormSubmissionEntity)
                    .where(
                        FormSubmissionEntity.business_request_id == item.business_request_id,
                        FormSubmissionEntity.id != submission.id,
                        FormSubmissionEntity.status == "SUBMITTED",
                        FormSubmissionEntity.created_at <= submission.created_at,
                    )
                    .order_by(col(FormSubmissionEntity.created_at).desc())
                    .limit(1)
                )
            ).first()
        before_state = (
            project_task_state(
                source.data, source.item_identity, None, [], step.field_policy, scopes
            )
            if source
            else None
        )
        feedback_rows = [
            CorrectionFeedbackDTO.model_validate(row)
            for row in submission.correction_feedback or []
            if scopes is None or row.get("scope") in scopes
        ]
        return WorkItemViewDTO(
            work_item_ref_id=create_ref_id(item.id, item.version),
            submission_ref_id=create_ref_id(submission.id, submission.version),
            view_key=key,
            purpose=purpose,
            title=title,
            data=data,
            item_identity=projected["item_identity"],
            before_data=before_state["data"] if bool(before_state) else None,
            before_item_identity=before_state["item_identity"] if bool(before_state) else None,
            render_schema=render,
            actions=actions,
            feedback=feedback_rows,
        )

    @staticmethod
    def _mutation_scopes(step: WorkflowStepEntity, view_key: str | None) -> set[str] | None:
        if not bool(step.task_contract):
            if view_key not in {None, "shared"}:
                raise NotFoundException("Task view not found")
            return None
        from apps.work_items.application.task_views import allowed_view_scopes

        contract = HumanTaskContract.model_validate(step.task_contract)
        key = view_key or contract.default_view
        view = next((view for view in contract.views if view.key == key), None)
        if view is None:
            raise NotFoundException("Task view not found")
        if view.purpose != "edit":
            raise NotAllowedException("A named edit view is required")
        return allowed_view_scopes(view, step.field_policy or {})

    @staticmethod
    def _visible_error(
        exc: ValidationDetailsException, policy, scopes
    ) -> ValidationDetailsException:
        issues = project_task_state({}, {}, {}, exc.issues, policy, scopes)["issues"]
        return ValidationDetailsException(
            issues or [{"pointer": "/data", "code": "task.validation"}]
        )

    @classmethod
    def _validate_visible_data(cls, policy, scopes, *args, **kwargs):
        from apps.work_items.application.task_views import validate_action_data

        try:
            return validate_action_data(*args, **kwargs)
        except ValidationDetailsException as exc:
            raise cls._visible_error(exc, policy, scopes) from None

    async def history_metadata(self, ref_id, query, actor):
        """Page only metadata for an authorized task; never expose action details."""
        from types import SimpleNamespace

        from sqlmodel import func

        from core.history_dto import ResourceHistoryDTO
        from utils.pagination import Page, apply_query

        item = await self.get(ref_id, actor)
        columns = SimpleNamespace(
            changed_at=WorkItemActionEntity.occurred_at,
            operation=WorkItemActionEntity.action,
            id=WorkItemActionEntity.id,
        )
        predicate = WorkItemActionEntity.work_item_id == item.id
        statement = apply_query(
            select(WorkItemActionEntity).where(predicate),
            columns,
            query,
            default_ordering=("-changed_at", "-id"),
        )
        count = apply_query(
            select(func.count()).select_from(WorkItemActionEntity).where(predicate),
            columns,
            query,
            paginate=False,
        )
        actions = (await self.session.exec(statement)).all()
        total = (await self.session.exec(count)).one()
        return Page[ResourceHistoryDTO](
            items=[
                ResourceHistoryDTO(changed_at=action.occurred_at, operation=action.action)
                for action in actions
            ],
            total=total,
            page=query.page,
            size=query.size,
        )

    async def runtime_state(self, ref_id: str, actor: UserEntity, view_key: str | None = None):
        from apps.forms.application.runtime import display_page, runtime_projection
        from apps.forms.domain.runtime import RuntimeFormStateDTO
        from apps.users.application.authorization import user_permissions
        from core.i18n import get_language

        item = await self.get(ref_id, actor)
        view = await self.task_view(ref_id, actor, view_key)
        submission = await self.submission(item)
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.render_dialect != "bpms.render/1":
            raise VersionConflictException(
                "Runtime form dialect is incompatible", conflict_kind="lifecycle"
            )
        step = await self._step(item)
        editable = (
            item.claimed_by_user_id == actor.id
            and item.status in {"CLAIMED", "IN_PROGRESS"}
            and view.purpose == "edit"
        )
        policy = step.field_policy or {}
        from apps.work_items.application.task_mutations import visible_scopes

        scopes = visible_scopes(policy)
        if bool(step.task_contract):
            contract = HumanTaskContract.model_validate(step.task_contract)
            selected = next(row for row in contract.views if row.key == view.view_key)
            scopes = set(selected.scopes)
        from apps.forms.application.runtime import render_scopes

        readable = render_scopes(view.render_schema) if scopes is None else scopes
        writable = (
            (set(policy.get("write", [])) if any(policy.values()) else readable)
            if editable
            else set()
        )
        required = set(policy.get("required", []))
        from apps.forms.application.localization import localize_snapshot

        snapshot = (
            localize_snapshot(
                submission.design_snapshot, FormDocuments.model_validate(form, from_attributes=True)
            )
            or {}
        )
        projected = runtime_projection(
            submission.data,
            submission.item_identity,
            submission.override_provenance,
            form.data_schema,
            snapshot.get("render_schema", form.render_schema),
            policy,
            readable,
            writable,
            required,
            permissions=await user_permissions(actor, self.session),
        )
        locale = (snapshot.get("localization") or {}).get("resolved_locale", get_language())
        return RuntimeFormStateDTO(
            resource_kind="WORK_ITEM",
            before_data=view.before_data,
            before_item_identity=view.before_item_identity,
            page_settings=display_page(
                snapshot.get("page_settings", form.page_settings), set(projected["readable_scopes"])
            ),
            resource_ref_id=create_ref_id(item.id, item.version),
            form_version_ref_id=create_ref_id(form.id, form.version),
            form_version_number=form.number,
            submission_ref_id=create_ref_id(submission.id, submission.version),
            design_key=(submission.design_snapshot or {}).get("variant_key", "default"),
            view_key=view.view_key,
            purpose="correction"
            if editable and submission.correction_source_submission_id
            else view.purpose
            if editable or view.purpose != "edit"
            else "observer",
            resolved_locale=locale,
            direction="rtl" if locale == "fa" else "ltr",
            actions=[
                action
                for action in view.actions
                if set(action.required_scopes) <= set(projected["readable_scopes"])
            ],
            **projected,
        )

    async def item_kind(
        self, item: WorkItemEntity
    ) -> Literal["HUMAN_TASK", "AI_APPROVAL", "UNSUPPORTED"]:
        if item.form_version_id is not None:
            return "HUMAN_TASK"
        from apps.ai.domain.entity import AIToolApprovalEntity

        approval = (
            await self.session.exec(
                select(AIToolApprovalEntity.id).where(AIToolApprovalEntity.work_item_id == item.id)
            )
        ).first()
        return "AI_APPROVAL" if approval is not None else "UNSUPPORTED"

    async def _step(self, item: WorkItemEntity) -> WorkflowStepEntity:
        execution = await self.session.get(StepExecutionEntity, item.step_execution_id)
        step = (
            await self.session.get(WorkflowStepEntity, execution.workflow_step_id)
            if execution is not None
            else None
        )
        if step is None:
            raise VersionConflictException(
                "Pinned workflow step is unavailable", conflict_kind="lifecycle"
            )
        return step

    async def submission(
        self, item: WorkItemEntity, *, update_row: bool = False
    ) -> FormSubmissionEntity:
        query = select(FormSubmissionEntity).where(
            FormSubmissionEntity.step_execution_id == item.step_execution_id
        )
        if update_row:
            query = query.with_for_update().execution_options(populate_existing=True)
        submission = (await self.session.exec(query)).one_or_none()
        if submission is None:
            raise NotFoundException("Work-item form submission not found")
        return submission

    async def _field_allowed(self, item: WorkItemEntity, field_path: str, *, write: bool) -> bool:
        from apps.work_items.application.task_views import _matches

        step = await self._step(item)
        if not bool(step.task_contract):
            return True
        policy = step.field_policy or {}
        scopes = set(policy.get("write", []))
        if not write:
            scopes |= set(policy.get("read", []))
        scopes -= set(policy.get("hidden", []))
        path = tuple(
            part.replace("~1", "/").replace("~0", "~") for part in field_path.split("/")[1:]
        )
        return any(_matches(path, scope) for scope in scopes)

    async def _require_field(self, item: WorkItemEntity, field_path: str, *, write: bool) -> None:
        if not await self._field_allowed(item, field_path, write=write):
            raise NotFoundException("Task field not found")

    async def _require_attachment_field(
        self,
        item: WorkItemEntity,
        submission: FormSubmissionEntity,
        attachment_ref: str,
        *,
        write: bool,
    ) -> None:
        attachment_id, _ = open_ref_id(attachment_ref)
        row = await self.session.get(FormSubmissionAttachmentEntity, attachment_id)
        if row is None or row.form_submission_id != submission.id:
            raise NotFoundException("Attachment not found")
        await self._require_field(item, row.field_path, write=write)

    async def add_attachment(
        self, ref_id: str, data: AttachmentAddDTO, actor: UserEntity
    ) -> tuple[WorkItemEntity, FormSubmissionAttachmentEntity]:
        item, submission = await self._editable_submission(ref_id, actor)
        await self._require_field(item, data.field_path, write=True)
        if data.contributing_group_ref_id is not None:
            group_id, _ = open_ref_id(data.contributing_group_ref_id)
            candidate = (
                await self.session.exec(
                    select(WorkItemCandidateEntity.id).where(
                        WorkItemCandidateEntity.work_item_id == item.id,
                        WorkItemCandidateEntity.work_group_id == group_id,
                    )
                )
            ).first()
            if candidate is None:
                raise NotAllowedException("Contributing group is not a work-item candidate")
        row = await AttachmentService(self.session).add_to_submission(submission, data, actor)
        item.updated_at = get_datetime_utc()
        await self.session.flush()
        return item, row

    async def reorder_attachments(
        self, ref_id: str, data: AttachmentReorderDTO, actor: UserEntity
    ) -> WorkItemEntity:
        item, submission = await self._editable_submission(ref_id, actor)
        await self._require_field(item, data.field_path, write=True)
        await AttachmentService(self.session).reorder_submission(submission, data, actor)
        item.updated_at = get_datetime_utc()
        await self.session.flush()
        return item

    async def replace_attachment(
        self,
        ref_id: str,
        attachment_ref: str,
        data: AttachmentReplaceDTO,
        actor: UserEntity,
    ) -> tuple[WorkItemEntity, FormSubmissionAttachmentEntity]:
        item, submission = await self._editable_submission(ref_id, actor)
        await self._require_attachment_field(item, submission, attachment_ref, write=True)
        row = await AttachmentService(self.session).replace_in_submission(
            submission, attachment_ref, data, actor
        )
        item.updated_at = get_datetime_utc()
        await self.session.flush()
        return item, row

    async def remove_attachment(
        self, ref_id: str, attachment_ref: str, actor: UserEntity
    ) -> WorkItemEntity:
        item, submission = await self._editable_submission(ref_id, actor)
        await self._require_attachment_field(item, submission, attachment_ref, write=True)
        await AttachmentService(self.session).remove_from_submission(
            submission, attachment_ref, actor
        )
        item.updated_at = get_datetime_utc()
        await self.session.flush()
        return item

    async def list_attachments(
        self, ref_id: str, actor: UserEntity
    ) -> list[tuple[FormSubmissionAttachmentEntity, UserUploadEntity]]:
        item = await self.get(ref_id, actor)
        rows = await AttachmentService(self.session).list_for_submission(
            await self.submission(item)
        )
        return [
            row for row in rows if await self._field_allowed(item, row[0].field_path, write=False)
        ]

    async def edit_collection(self, ref_id: str, data, actor: UserEntity):
        from apps.forms.application.collections import CollectionError, edit_submission_collection

        item, submission = await self._editable_submission(ref_id, actor)
        await self._require_field(item, data.path, write=True)
        step = await self._step(item)
        scopes = self._mutation_scopes(step, None)
        from apps.work_items.application.task_mutations import _covers, _instance_path

        path = _instance_path(data.path)
        if scopes is not None and not any(_covers(path, scope) for scope in scopes):
            raise NotFoundException("Task field not found")
        if data.operation == "add":

            def check_value(value, current):
                if any(
                    _covers(current, scope) for scope in (step.field_policy or {}).get("hidden", [])
                ):
                    raise NotAllowedException("Collection value is not writable")
                if isinstance(value, dict):
                    for key, child in value.items():
                        check_value(child, (*current, key))
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        check_value(child, (*current, str(index)))
                elif any((step.field_policy or {}).values()) and not any(
                    _covers(current, scope) for scope in (step.field_policy or {}).get("write", [])
                ):
                    raise NotAllowedException("Collection value is not writable")

            check_value(data.value, (*path, "*"))
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.status not in {"PUBLISHED", "RETIRED"}:
            raise VersionConflictException(
                "Pinned form version is unavailable", conflict_kind="lifecycle"
            )
        try:
            result = await edit_submission_collection(
                self.session, submission, form, data, actor.id
            )
        except CollectionError:
            raise ValidationDetailsException(
                [{"pointer": "/collection", "code": "task.validation"}]
            ) from None
        item.updated_at = get_datetime_utc()
        await self.session.flush()
        from dataclasses import replace

        step = await self._step(item)
        projected = project_task_state(
            result.data,
            result.identity,
            submission.override_provenance,
            result.issues,
            step.field_policy,
            self._mutation_scopes(step, None),
        )
        return replace(
            result,
            data=projected["data"],
            identity=projected["item_identity"],
            issues=projected["issues"],
        )

    async def apply_override(self, ref_id: str, command, actor: UserEntity):
        from apps.forms.application.behavior import BehaviorError, apply_manual_override
        from apps.users.application.authorization import user_permissions

        item, submission = await self._editable_submission(ref_id, actor)
        await self._require_field(item, "/" + "/".join(command.scope.split("/")[2::2]), write=True)
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.status not in {"PUBLISHED", "RETIRED"}:
            raise VersionConflictException(
                "Pinned form version is unavailable", conflict_kind="lifecycle"
            )
        try:
            changed, provenance = apply_manual_override(
                pinned_behavior_documents(
                    FormDocuments.model_validate(form, from_attributes=True),
                    submission.design_snapshot,
                ),
                submission.data,
                submission.override_provenance,
                command,
                actor_ref_id=create_ref_id(actor.id, actor.version),
                permissions=await user_permissions(actor, self.session),
            )
        except BehaviorError:
            raise ValidationDetailsException(
                [{"pointer": "/override", "code": "task.validation"}]
            ) from None
        submission.data = changed
        submission.override_provenance = provenance
        submission.updated_at = get_datetime_utc()
        item.updated_at = submission.updated_at
        await self.session.flush()
        step = await self._step(item)
        projected = project_task_state(
            changed,
            submission.item_identity,
            provenance,
            [],
            step.field_policy,
            self._mutation_scopes(step, None),
        )
        return projected["data"], projected["override_provenance"]

    async def attachment_upload(
        self, ref_id: str, attachment_ref: str, actor: UserEntity
    ) -> UserUploadEntity:
        item = await self.get(ref_id, actor)
        submission = await self.submission(item)
        await self._require_attachment_field(item, submission, attachment_ref, write=False)
        return await AttachmentService(self.session).upload_from_submission(
            submission, attachment_ref
        )

    async def state_for(self, item_id: UUID, user_id: UUID) -> UserWorkItemStateEntity | None:
        return await self.session.get(UserWorkItemStateEntity, (user_id, item_id))

    async def _editable_submission(
        self, ref_id: str, actor: UserEntity
    ) -> tuple[WorkItemEntity, FormSubmissionEntity]:
        item = await self.get(ref_id, actor, update_row=True)
        self._require_claimant(item, actor)
        if item.status not in {"CLAIMED", "IN_PROGRESS"}:
            raise VersionConflictException(
                "Work-item attachments are immutable in this state", conflict_kind="lifecycle"
            )
        submission = await self.submission(item, update_row=True)
        if submission.status != "DRAFT":
            raise VersionConflictException(
                "Work-item attachments are immutable", conflict_kind="lifecycle"
            )
        return item, submission

    async def _eligible(self, item_id: UUID, user_id: UUID, *, require_claim: bool) -> bool:
        candidates = (
            await self.session.exec(
                select(WorkItemCandidateEntity).where(
                    WorkItemCandidateEntity.work_item_id == item_id,
                    col(WorkItemCandidateEntity.can_claim).is_(True) if require_claim else True,
                )
            )
        ).all()
        for candidate in candidates:
            if candidate.user_id == user_id:
                return True
            if candidate.work_group_id is None:
                continue
            group = await self.session.get(WorkGroupEntity, candidate.work_group_id)
            member = await self.session.get(
                WorkGroupMemberEntity, (candidate.work_group_id, user_id)
            )
            if (
                group is not None
                and group.deleted_at is None
                and group.is_active
                and member is not None
                and member.is_active
            ):
                return True
        return False

    def _cartable_criterion(self, kind: CartableKind, user_id: UUID):
        direct = col(WorkItemEntity.id).in_(
            select(WorkItemCandidateEntity.work_item_id).where(
                WorkItemCandidateEntity.user_id == user_id,
                col(WorkItemCandidateEntity.can_claim).is_(True),
            )
        )
        active_groups = (
            select(WorkGroupMemberEntity.work_group_id)
            .join(
                WorkGroupEntity,
                col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id),
            )
            .where(
                WorkGroupMemberEntity.user_id == user_id,
                col(WorkGroupMemberEntity.is_active).is_(True),
                col(WorkGroupEntity.is_active).is_(True),
                col(WorkGroupEntity.deleted_at).is_(None),
            )
        )
        grouped = col(WorkItemEntity.id).in_(
            select(WorkItemCandidateEntity.work_item_id).where(
                col(WorkItemCandidateEntity.work_group_id).in_(active_groups),
                col(WorkItemCandidateEntity.can_claim).is_(True),
            )
        )
        candidate = or_(direct, grouped)
        state_items = select(UserWorkItemStateEntity.work_item_id).where(
            UserWorkItemStateEntity.user_id == user_id
        )
        if kind == "available":
            return col(WorkItemEntity.status) == "OPEN", candidate
        if kind == "claimed":
            return (
                col(WorkItemEntity.claimed_by_user_id) == user_id,
                col(WorkItemEntity.status).in_(["CLAIMED", "IN_PROGRESS"]),
            )
        if kind == "completed":
            return (
                col(WorkItemEntity.claimed_by_user_id) == user_id,
                col(WorkItemEntity.status).in_(_TERMINAL),
            )
        if kind == "watching":
            return col(WorkItemEntity.id).in_(
                state_items.where(col(UserWorkItemStateEntity.watching_at).is_not(None))
            )
        if kind == "submitted":
            later = aliased(WorkItemEntity)
            is_latest = ~exists(
                select(later.id).where(
                    later.business_request_id == WorkItemEntity.business_request_id,
                    or_(
                        col(later.created_at) > col(WorkItemEntity.created_at),
                        and_(
                            col(later.created_at) == col(WorkItemEntity.created_at),
                            col(later.id) > col(WorkItemEntity.id),
                        ),
                    ),
                )
            )
            return (
                col(WorkItemEntity.business_request_id).in_(
                    select(BusinessRequestEntity.id).where(
                        BusinessRequestEntity.requester_user_id == user_id
                    )
                ),
                is_latest,
            )
        visible = or_(
            candidate,
            col(WorkItemEntity.claimed_by_user_id) == user_id,
            col(WorkItemEntity.business_request_id).in_(
                select(BusinessRequestEntity.id).where(
                    BusinessRequestEntity.requester_user_id == user_id
                )
            ),
        )
        read_items = select(UserWorkItemStateEntity.work_item_id).where(
            UserWorkItemStateEntity.user_id == user_id,
            col(UserWorkItemStateEntity.read_at).is_not(None),
        )
        return visible, col(WorkItemEntity.id).not_in(read_items)

    async def _forward_principals(
        self, data: WorkItemForwardDTO
    ) -> list[tuple[UUID | None, UUID | None]]:
        principals: list[tuple[UUID | None, UUID | None]] = []
        for ref_id in data.user_ref_ids:
            user_id, version = open_ref_id(ref_id)
            user = await self.session.get(UserEntity, user_id)
            if user is None or user.version != version or user.deleted_at is not None:
                raise NotFoundException("Forward user not found")
            principals.append((user.id, None))
        for ref_id in data.work_group_ref_ids:
            group_id, version = open_ref_id(ref_id)
            group = await self.session.get(WorkGroupEntity, group_id)
            if (
                group is None
                or group.version != version
                or group.deleted_at is not None
                or not group.is_active
            ):
                raise NotFoundException("Forward work group not found")
            principals.append((None, group.id))
        return principals

    async def _prior(
        self, item_id: UUID, command_key: str, actor_id: UUID
    ) -> WorkItemActionEntity | None:
        row = (
            await self.session.exec(
                select(WorkItemActionEntity).where(
                    WorkItemActionEntity.work_item_id == item_id,
                    WorkItemActionEntity.command_key == command_key,
                )
            )
        ).one_or_none()
        if row is not None and row.actor_user_id != actor_id:
            raise VersionConflictException(
                "Command key is already used", conflict_kind="idempotency"
            )
        return row

    async def _idempotent(
        self, item_id: UUID, command_key: str, actor_id: UUID, payload_hash: str
    ) -> bool:
        prior = await self._prior(item_id, command_key, actor_id)
        if prior is None:
            return False
        if prior.details.get("payload_hash") != payload_hash:
            raise VersionConflictException(
                "Command key payload does not match", conflict_kind="idempotency"
            )
        return True

    @staticmethod
    def _require_claimant(item: WorkItemEntity, actor: UserEntity) -> None:
        if item.claimed_by_user_id != actor.id:
            raise NotAllowedException("Only the claimant can perform this action")

    async def _record(
        self,
        item: WorkItemEntity,
        actor: UserEntity | None,
        action: str,
        command_key: str,
        *,
        outcome: str | None = None,
        submission: FormSubmissionEntity | None = None,
        comment: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            WorkItemActionEntity(
                work_item_id=item.id,
                actor_user_id=actor.id if actor else None,
                action=action,
                outcome_key=outcome,
                form_submission_id=submission.id if submission else None,
                comment=comment,
                details=details or {},
                command_key=command_key,
            )
        )
        execution = await self.session.get(StepExecutionEntity, item.step_execution_id)
        if execution is None:
            raise NotFoundException("Step execution not found")
        from apps.processes.application.events import ProcessEventService

        event_type = {
            "CREATE": "work_item.created",
            "REASSIGN": "work_item.created",
            "CLAIM": "work_item.claimed",
            "RELEASE": "work_item.released",
            "START": "work_item.started",
            "SAVE": "work_item.saved",
            "COMPLETE": "work_item.completed",
            "REJECT": "work_item.rejected",
            "RETURN": "work_item.returned",
            "FORWARD": "work_item.forwarded",
            "CANCEL": "work_item.cancelled",
            "EXPIRE": "work_item.expired",
            "COMMENT": "work_item.commented",
        }[action]
        await ProcessEventService(self.session).append(
            execution.process_instance_id,
            event_type,
            actor_user_id=actor.id if actor else None,
            step_execution_id=execution.id,
            work_item_id=item.id,
            command_key=command_key,
            payload={
                "action": action.casefold(),
                "outcome": outcome,
                "status": item.status,
                "candidate_count": len(details or {}) if action == "REASSIGN" else None,
                "submission_status": submission.status if submission else None,
            },
        )

    @staticmethod
    def _hash(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode()).hexdigest()
