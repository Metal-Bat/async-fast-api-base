"""Request-type configuration and atomic draft submission lifecycle."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import and_, exists, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.domain.contracts import (
    ClientContext,
    ClientTarget,
    ReleaseRange,
    matches_client_targets,
)
from apps.clients.domain.entity import ClientEntity
from apps.forms.application.behavior import pinned_behavior_documents
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.options import OptionService
from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.processes.domain import entity as process_entities  # noqa: F401
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    BusinessRequestUpdateDTO,
    EligibleRequestTypeDTO,
    EligibleRequestTypeQuery,
    RequestTypeClientTargetDTO,
    RequestTypeCreateDTO,
)
from apps.requests.domain.entity import (
    BusinessRequestEntity,
    FormSubmissionEntity,
    RequestTypeClientTargetEntity,
    RequestTypeEntity,
)
from apps.step_types.application.registry import get_registry
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_items.domain import entity as work_item_entities  # noqa: F401
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.entity import (
    WorkflowAccessGrantEntity,
    WorkflowDefinitionEntity,
    WorkflowVersionEntity,
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


class RequestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_type(self, ref_id: str, *, update: bool = False) -> RequestTypeEntity:
        entity_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            RequestTypeEntity, entity_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Request type not found")
        if update and row.version != expected:
            raise VersionConflictException("Request type is stale", conflict_kind="revision")
        return row

    async def create_type(self, data: RequestTypeCreateDTO) -> RequestTypeEntity:
        workflow, form = await self._definition_roots(data.workflow_ref_id, data.form_ref_id)
        row = RequestTypeEntity(
            **data.model_dump(exclude={"workflow_ref_id", "form_ref_id", "client_targets"}),
            workflow_definition_id=workflow.id,
            form_definition_id=form.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self._replace_client_targets(row.id, data.client_targets)
        return row

    async def update_type(self, ref_id: str, data: RequestTypeCreateDTO) -> RequestTypeEntity:
        row = await self.get_type(ref_id, update=True)
        workflow, form = await self._definition_roots(data.workflow_ref_id, data.form_ref_id)
        row.sqlmodel_update(
            data.model_dump(exclude={"workflow_ref_id", "form_ref_id", "client_targets"})
            | {"workflow_definition_id": workflow.id, "form_definition_id": form.id}
        )
        row.updated_at = get_datetime_utc()
        if "client_targets" in data.model_fields_set:
            await self._replace_client_targets(row.id, data.client_targets)
        await self.session.flush()
        return row

    async def delete_type(self, ref_id: str) -> None:
        row = await self.get_type(ref_id, update=True)
        row.is_active = False
        row.deleted_at = get_datetime_utc()
        await self.session.flush()

    async def runtime_state(
        self, ref_id: str, actor: UserEntity, client_context: ClientContext | None = None
    ):
        from apps.forms.application.localization import localize_snapshot
        from apps.forms.application.runtime import display_page, render_scopes, runtime_projection
        from apps.forms.domain.runtime import RuntimeFormStateDTO
        from apps.users.application.authorization import user_permissions
        from core.i18n import get_language

        row = await self.get_request(ref_id, actor)
        # Request participants may track, but a request form is disclosed only to its owner/superuser.
        if not actor.is_superuser and row.requester_user_id != actor.id:
            raise NotFoundException("Request form not found")
        submission = await self.submission_for(row.id)
        self._require_origin_client(row, client_context, submission)
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.render_dialect != "bpms.render/1":
            raise VersionConflictException(
                "Runtime form dialect is incompatible", conflict_kind="lifecycle"
            )
        snapshot = (
            localize_snapshot(
                submission.design_snapshot, FormDocuments.model_validate(form, from_attributes=True)
            )
            or {}
        )
        render = snapshot.get("render_schema", form.render_schema)
        scopes = render_scopes(render)
        editable = row.status == "DRAFT" and row.requester_user_id == actor.id
        required = {
            "/properties/" + key.replace("~", "~0").replace("/", "~1")
            for key in form.data_schema.get("required", [])
        }
        projection = runtime_projection(
            submission.data,
            submission.item_identity,
            submission.override_provenance,
            form.data_schema,
            render,
            None,
            None,
            scopes if editable else set(),
            required,
            permissions=await user_permissions(actor, self.session),
        )
        locale = (snapshot.get("localization") or {}).get("resolved_locale", get_language())
        return RuntimeFormStateDTO(
            resource_kind="REQUEST",
            page_settings=display_page(
                snapshot.get("page_settings", form.page_settings),
                set(projection["readable_scopes"]),
            ),
            resource_ref_id=create_ref_id(row.id, row.version),
            form_version_ref_id=create_ref_id(form.id, form.version),
            form_version_number=form.number,
            submission_ref_id=create_ref_id(submission.id, submission.version),
            design_key=snapshot.get("variant_key", "default"),
            view_key="request",
            purpose="edit" if editable else "summary",
            resolved_locale=locale,
            direction="rtl" if locale == "fa" else "ltr",
            **projection,
        )

    async def history_metadata(self, ref_id, query, actor):
        """Project only metadata after checking request ownership."""
        from core.history_dto import HistoryQuery, ResourceHistoryDTO
        from core.history_service import HistoryService
        from utils.pagination import Page

        row = await self.get_request(ref_id, actor)
        if not actor.is_superuser and row.requester_user_id != actor.id:
            raise NotFoundException("Request history not found")
        submission = await self.submission_for(row.id)
        result = await HistoryService.for_entity(self.session, "form_submission").list(
            HistoryQuery.model_validate(query.model_dump()), submission.id
        )
        return Page[ResourceHistoryDTO](
            items=[
                ResourceHistoryDTO(changed_at=item.changed_at, operation=item.operation)
                for item in result.items
            ],
            total=result.total,
            page=result.page,
            size=result.size,
        )

    async def eligible_types(
        self,
        query: EligibleRequestTypeQuery,
        actor: UserEntity,
        context: ClientContext | None = None,
    ) -> Page[EligibleRequestTypeDTO]:
        context = context or ClientContext.legacy()
        items = []
        total = 0
        if not query.supported_render_dialects:
            return Page(items=[], page=query.page, size=query.size, total=0)
        offset = 0
        while True:
            candidates = (
                await self.session.exec(
                    select(RequestTypeEntity)
                    .where(
                        col(RequestTypeEntity.deleted_at).is_(None),
                        col(RequestTypeEntity.is_active).is_(True),
                    )
                    .order_by(col(RequestTypeEntity.code), col(RequestTypeEntity.id))
                    .offset(offset)
                    .limit(128)
                )
            ).all()
            for row in candidates:
                try:
                    workflow, form_version = await self._eligible_dependencies(row, actor, context)
                    if form_version.render_dialect not in query.supported_render_dialects:
                        continue
                except NotFoundException, NotAllowedException, VersionConflictException:
                    continue
                total += 1
                if (query.page - 1) * query.size < total <= query.page * query.size:
                    items.append(
                        EligibleRequestTypeDTO(
                            ref_id=create_ref_id(row.id, row.version),
                            code=row.code,
                            name=row.name,
                            workflow_version_ref_id=create_ref_id(workflow.id, workflow.version),
                            form_version_ref_id=create_ref_id(
                                form_version.id, form_version.version
                            ),
                            render_dialect=form_version.render_dialect,
                        )
                    )
            if len(candidates) < 128:
                break
            offset += 128
        return Page(items=items, page=query.page, size=query.size, total=total)

    async def _eligible_dependencies(
        self, request_type: RequestTypeEntity, actor: UserEntity, context: ClientContext
    ):
        if not request_type.is_active or request_type.deleted_at:
            raise VersionConflictException("Request type is inactive", conflict_kind="lifecycle")
        workflow = await self.session.get(
            WorkflowDefinitionEntity, request_type.workflow_definition_id
        )
        form = await self.session.get(FormDefinitionEntity, request_type.form_definition_id)
        if (
            workflow is None
            or not workflow.is_active
            or workflow.deleted_at
            or form is None
            or not form.is_active
            or form.deleted_at
        ):
            raise VersionConflictException(
                "Request type dependencies are inactive", conflict_kind="lifecycle"
            )
        if not await WorkflowService(self.session, get_registry()).can_access(
            workflow, actor, "start"
        ):
            raise NotAllowedException("Workflow start access required")
        if not matches_client_targets(await self._client_targets(request_type.id), context):
            raise NotAllowedException("Registered client release is required")
        workflow_version = await self._published_workflow(request_type.workflow_definition_id)
        form_version = await self._published_form(request_type.form_definition_id)
        try:
            resolve_form_documents(
                FormDocuments.model_validate(form_version, from_attributes=True), context
            )
        except ValueError:
            raise NotAllowedException("Client cannot render the pinned form") from None
        return workflow_version, form_version

    async def process_reference(self, request_id: UUID) -> str | None:
        from apps.processes.domain.entity import ProcessInstanceEntity

        process = (
            await self.session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == request_id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                )
            )
        ).one_or_none()
        return create_ref_id(process.id, process.version) if process else None

    async def create_draft(
        self,
        data: BusinessRequestCreateDTO,
        actor: UserEntity,
        client_context: ClientContext | None = None,
    ) -> tuple[BusinessRequestEntity, FormSubmissionEntity]:
        request_type = await self.get_type(data.request_type_ref_id)
        context = client_context or ClientContext.legacy()
        workflow_version, form_version = await self._eligible_dependencies(
            request_type, actor, context
        )
        priority = (
            data.priority
            if data.priority is not None
            else request_type.default_priority
            if request_type.default_priority is not None
            else workflow_version.default_priority
        )
        request = BusinessRequestEntity(
            request_type_id=request_type.id,
            requester_user_id=actor.id,
            workflow_version_id=workflow_version.id,
            priority=priority,
            origin_client_context=context.snapshot(),
        )
        self.session.add(request)
        await self.session.flush()
        documents = FormDocuments.model_validate(form_version, from_attributes=True)
        try:
            design = resolve_form_documents(documents, context)
        except ValueError:
            raise NotAllowedException("Client cannot render the pinned form") from None
        initial_data = data.data
        item_identity = None
        if documents.behavior_dialect is not None:
            from apps.forms.application.behavior import BehaviorError, evaluate_behavior
            from apps.forms.application.collections import initialize_identity

            try:
                initial_data = evaluate_behavior(
                    pinned_behavior_documents(documents, {"variant_key": design.key}),
                    initial_data,
                    initialize=True,
                    enforce_required=False,
                ).data
                item_identity = initialize_identity(initial_data, schema=form_version.data_schema)
            except BehaviorError as exc:
                raise ValidationDetailsException([{"pointer": "/data", "code": str(exc)}]) from None
        submission = FormSubmissionEntity(
            business_request_id=request.id,
            form_version_id=form_version.id,
            data=initial_data,
            item_identity=item_identity,
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
        return request, submission

    async def _replace_client_targets(
        self, request_type_id: UUID, inputs: list[RequestTypeClientTargetDTO]
    ) -> None:
        old = (
            await self.session.exec(
                select(RequestTypeClientTargetEntity).where(
                    RequestTypeClientTargetEntity.request_type_id == request_type_id,
                    col(RequestTypeClientTargetEntity.deleted_at).is_(None),
                )
            )
        ).all()
        for row in old:
            row.deleted_at = get_datetime_utc()
        await self.session.flush()
        seen: set[UUID] = set()
        for item in inputs:
            client_id, expected = open_ref_id(item.client_ref_id)
            client = await self.session.get(ClientEntity, client_id)
            if (
                client is None
                or client.deleted_at
                or not client.is_active
                or client.version != expected
                or client.secret_hash is None
            ):
                raise VersionConflictException(
                    "Restricted client must be active and confidential", conflict_kind="lifecycle"
                )
            if client_id in seen:
                raise ValueError("Duplicate restricted client target")
            seen.add(client_id)
            self.session.add(
                RequestTypeClientTargetEntity(
                    request_type_id=request_type_id,
                    client_id=client_id,
                    minimum_release=item.minimum_release,
                    maximum_release_exclusive=item.maximum_release_exclusive,
                )
            )
        await self.session.flush()

    async def client_target_dtos(self, request_type_id: UUID) -> list[RequestTypeClientTargetDTO]:
        rows = (
            await self.session.exec(
                select(RequestTypeClientTargetEntity)
                .where(
                    RequestTypeClientTargetEntity.request_type_id == request_type_id,
                    col(RequestTypeClientTargetEntity.deleted_at).is_(None),
                )
                .order_by(col(RequestTypeClientTargetEntity.client_id))
            )
        ).all()
        result = []
        for row in rows:
            client = await self.session.get(ClientEntity, row.client_id)
            if client is None:
                raise NotFoundException("Request type client target is unavailable")
            result.append(
                RequestTypeClientTargetDTO(
                    client_ref_id=create_ref_id(client.id, client.version),
                    minimum_release=row.minimum_release,
                    maximum_release_exclusive=row.maximum_release_exclusive,
                )
            )
        return result

    async def _client_targets(self, request_type_id: UUID) -> tuple[ClientTarget, ...]:
        rows = (
            await self.session.exec(
                select(RequestTypeClientTargetEntity).where(
                    RequestTypeClientTargetEntity.request_type_id == request_type_id,
                    col(RequestTypeClientTargetEntity.deleted_at).is_(None),
                )
            )
        ).all()
        return tuple(
            ClientTarget(
                row.client_id,
                ReleaseRange(row.minimum_release, row.maximum_release_exclusive),
            )
            for row in rows
        )

    @staticmethod
    def _require_origin_client(
        row: BusinessRequestEntity,
        context: ClientContext | None,
        submission: FormSubmissionEntity | None = None,
    ) -> None:
        origin = (
            (submission.design_snapshot or {}).get("client")
            if submission
            else row.origin_client_context
        )
        if origin is None:
            return
        current = context or ClientContext.legacy()
        if (
            current.client_id is None
            or str(current.client_id) != origin.get("client_id")
            or (str(current.release_id) if current.release_id else None) != origin.get("release_id")
            or (origin.get("trusted") and not current.trusted)
        ):
            raise NotAllowedException("Form interaction requires its pinned client release")

    async def get_request(
        self, ref_id: str, actor: UserEntity, *, update: bool = False
    ) -> BusinessRequestEntity:
        entity_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            BusinessRequestEntity, entity_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at or not await self.can_view(row, actor):
            raise NotFoundException("Business request not found")
        if update and row.version != expected:
            raise VersionConflictException("Business request is stale", conflict_kind="revision")
        return row

    async def resume_presentation(
        self, ref_id: str, actor: UserEntity, context: ClientContext
    ) -> tuple[BusinessRequestEntity, FormSubmissionEntity]:
        """Open a new audited draft interaction without changing its origin or data pin."""
        row = await self.get_request(ref_id, actor, update=True)
        self._own_draft(row, actor)
        submission = await self._submission(row.id, update=True)
        current = (submission.design_snapshot or {}).get("client")
        if (
            current
            and current.get("client_id") == str(context.client_id)
            and current.get("release_id")
            == (str(context.release_id) if context.release_id else None)
        ):
            return row, submission
        request_type = await self.session.get(RequestTypeEntity, row.request_type_id)
        if (
            request_type is None
            or not request_type.allow_cross_client_resume
            or not context.trusted
            or context.client_id is None
        ):
            raise NotAllowedException("Cross-client resume is not enabled for this request")
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.status not in {"PUBLISHED", "RETIRED"}:
            raise VersionConflictException(
                "Pinned form version is unavailable", conflict_kind="lifecycle"
            )
        try:
            design = resolve_form_documents(
                FormDocuments.model_validate(form, from_attributes=True), context
            )
        except ValueError:
            raise NotAllowedException("Client cannot render the pinned form") from None
        revision = (submission.design_snapshot or {}).get("interaction_revision", 0) + 1
        submission.design_snapshot = {
            "variant_key": design.key,
            "design_revision": design.revision,
            "render_schema": design.render_schema,
            "page_settings": design.page_settings,
            "localization": design.localization.model_dump(mode="json")
            if design.localization
            else None,
            "client": context.snapshot(),
            "interaction_revision": revision,
        }
        submission.updated_at = get_datetime_utc()
        await self.session.flush()
        return row, submission

    async def update_draft(
        self,
        ref_id: str,
        data: BusinessRequestUpdateDTO,
        actor: UserEntity,
        client_context: ClientContext | None = None,
    ) -> tuple[BusinessRequestEntity, FormSubmissionEntity]:
        row = await self.get_request(ref_id, actor, update=True)
        self._own_draft(row, actor)
        submission = await self._submission(row.id, update=True)
        self._require_origin_client(row, client_context, submission)
        submission.data = data.data
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is not None and form.behavior_dialect is not None:
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
            except BehaviorError as exc:
                raise ValidationDetailsException([{"pointer": "/data", "code": str(exc)}]) from None
            except CollectionError as exc:
                raise ValidationDetailsException(
                    [{"pointer": "/item_identity", "code": str(exc)}]
                ) from None
        if data.priority is not None:
            row.priority = data.priority
        now = get_datetime_utc()
        row.updated_at = now
        submission.updated_at = now
        await self.session.flush()
        return row, submission

    async def edit_collection(
        self,
        ref_id: str,
        data,
        actor: UserEntity,
        client_context: ClientContext | None = None,
    ):
        from apps.forms.application.collections import CollectionError, edit_submission_collection
        from utils.exceptions import ValidationDetailsException

        row = await self.get_request(ref_id, actor, update=True)
        self._own_draft(row, actor)
        submission = await self._submission(row.id, update=True)
        self._require_origin_client(row, client_context, submission)
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.status not in {"PUBLISHED", "RETIRED"}:
            raise VersionConflictException(
                "Pinned form version is unavailable", conflict_kind="lifecycle"
            )
        try:
            result = await edit_submission_collection(
                self.session, submission, form, data, actor.id
            )
        except CollectionError as exc:
            raise ValidationDetailsException(
                [{"pointer": "/collection", "code": str(exc)}]
            ) from None
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return result

    async def apply_override(
        self,
        ref_id: str,
        command,
        actor: UserEntity,
        client_context: ClientContext | None = None,
    ):
        from apps.forms.application.behavior import BehaviorError, apply_manual_override
        from apps.users.application.authorization import user_permissions

        row = await self.get_request(ref_id, actor, update=True)
        self._own_draft(row, actor)
        submission = await self._submission(row.id, update=True)
        self._require_origin_client(row, client_context, submission)
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
        except BehaviorError as exc:
            raise ValidationDetailsException([{"pointer": "/override", "code": str(exc)}]) from None
        submission.data = changed
        submission.override_provenance = provenance
        submission.updated_at = get_datetime_utc()
        row.updated_at = submission.updated_at
        await self.session.flush()
        return changed, provenance

    async def cancel(
        self, ref_id: str, actor: UserEntity, client_context: ClientContext | None = None
    ) -> BusinessRequestEntity:
        row = await self.get_request(ref_id, actor, update=True)
        self._own_draft(row, actor)
        submission = await self._submission(row.id, update=True)
        self._require_origin_client(row, client_context, submission)
        now = get_datetime_utc()
        row.status = "CANCELLED"
        row.closed_at = now
        row.updated_at = now
        submission.status = "ABANDONED"
        submission.updated_at = now
        await self.session.flush()
        return row

    async def submit(
        self,
        ref_id: str,
        data: BusinessRequestSubmitDTO,
        actor: UserEntity,
        client_context: ClientContext | None = None,
    ) -> tuple[BusinessRequestEntity, FormSubmissionEntity]:
        entity_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            BusinessRequestEntity, entity_id, with_for_update=True, populate_existing=True
        )
        if row is None or row.deleted_at or row.requester_user_id != actor.id:
            raise NotFoundException("Business request not found")
        submission = await self._submission(row.id, update=True)
        self._require_origin_client(row, client_context, submission)
        payload_hash = self._payload_hash(submission.data)
        if row.submit_key == data.submit_key:
            if row.submit_payload_hash != payload_hash:
                raise VersionConflictException(
                    "Submit key payload mismatch", conflict_kind="idempotency"
                )
            return row, submission
        if row.status != "DRAFT":
            raise VersionConflictException(
                "Only drafts can be submitted", conflict_kind="lifecycle"
            )
        if row.version != expected:
            raise VersionConflictException("Business request is stale", conflict_kind="revision")
        from apps.forms.application.attachments import AttachmentService

        await AttachmentService(self.session).materialize(submission)
        payload_hash = self._payload_hash(submission.data)
        duplicate = (
            await self.session.exec(
                select(BusinessRequestEntity.id).where(
                    BusinessRequestEntity.requester_user_id == actor.id,
                    BusinessRequestEntity.submit_key == data.submit_key,
                )
            )
        ).first()
        if duplicate is not None:
            raise VersionConflictException(
                "Submit key is already used", conflict_kind="idempotency"
            )
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None or form.status not in {"PUBLISHED", "RETIRED"}:
            raise VersionConflictException(
                "Pinned form version is unavailable", conflict_kind="lifecycle"
            )
        validation = FormValidator().validate(
            pinned_behavior_documents(
                FormDocuments.model_validate(form, from_attributes=True),
                submission.design_snapshot,
            ),
            submission.data,
            overrides=submission.override_provenance,
        )
        if not validation.valid:
            raise ValidationDetailsException([issue.model_dump() for issue in validation.issues])
        if validation.evaluated_data is not None:
            submission.data = validation.evaluated_data
            payload_hash = self._payload_hash(submission.data)
        await OptionService(self.session).validate_submission(
            FormDocuments.model_validate(form, from_attributes=True), submission.data, actor
        )
        now = get_datetime_utc()
        submission.status = "SUBMITTED"
        submission.submitted_by_user_id = actor.id
        submission.submitted_at = now
        submission.updated_at = now
        row.status = "SUBMITTED"
        row.submitted_at = now
        row.submit_key = data.submit_key
        row.submit_payload_hash = payload_hash
        row.start_command = {
            "command_key": data.submit_key,
            "business_request_id": str(row.id),
            "workflow_version_id": str(row.workflow_version_id),
            "form_submission_id": str(submission.id),
        }
        row.updated_at = now
        await self.session.flush()
        from apps.processes.application.service import ProcessService

        await ProcessService(self.session).start_request(row, submission, data.submit_key)
        return row, submission

    async def can_view(self, row: BusinessRequestEntity, actor: UserEntity) -> bool:
        if actor.is_superuser or row.requester_user_id == actor.id:
            return True
        from apps.work_items.application.service import WorkItemService

        if await WorkItemService(self.session).can_view_request(row.id, actor):
            return True
        version = await self.session.get(WorkflowVersionEntity, row.workflow_version_id)
        workflow = (
            await self.session.get(WorkflowDefinitionEntity, version.workflow_definition_id)
            if version
            else None
        )
        return bool(
            workflow
            and await WorkflowService(self.session, get_registry()).can_access(
                workflow, actor, "view"
            )
        )

    def visibility_criteria(self, actor: UserEntity, *, mine: bool = False):
        if mine:
            return (BusinessRequestEntity.requester_user_id == actor.id,)
        if actor.is_superuser:
            return ()
        active_groups = (
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
        grants = exists(
            select(WorkflowAccessGrantEntity.id)
            .where(
                WorkflowAccessGrantEntity.workflow_definition_id
                == WorkflowVersionEntity.workflow_definition_id,
                col(WorkflowAccessGrantEntity.deleted_at).is_(None),
                col(WorkflowAccessGrantEntity.can_view).is_(True),
                or_(
                    col(WorkflowAccessGrantEntity.user_id) == actor.id,
                    col(WorkflowAccessGrantEntity.work_group_id).in_(active_groups),
                ),
            )
            .correlate(WorkflowVersionEntity)
        )
        visible_versions = (
            select(WorkflowVersionEntity.id)
            .join(
                WorkflowDefinitionEntity,
                col(WorkflowDefinitionEntity.id)
                == col(WorkflowVersionEntity.workflow_definition_id),
            )
            .where(
                col(WorkflowDefinitionEntity.deleted_at).is_(None),
                or_(
                    col(WorkflowDefinitionEntity.owner_user_id) == actor.id,
                    col(WorkflowDefinitionEntity.access_mode) == "OPEN",
                    grants,
                ),
            )
        )
        from apps.processes.domain.entity import StepExecutionEntity
        from apps.work_items.domain.entity import WorkItemCandidateEntity, WorkItemEntity
        from apps.workflows.domain.entity import WorkflowStepEntity

        direct_items = select(WorkItemCandidateEntity.work_item_id).where(
            WorkItemCandidateEntity.user_id == actor.id
        )
        group_items = select(WorkItemCandidateEntity.work_item_id).where(
            col(WorkItemCandidateEntity.work_group_id).in_(active_groups)
        )
        visible_work_requests = (
            select(WorkItemEntity.business_request_id)
            .join(
                StepExecutionEntity,
                col(StepExecutionEntity.id) == col(WorkItemEntity.step_execution_id),
            )
            .join(
                WorkflowStepEntity,
                col(WorkflowStepEntity.id) == col(StepExecutionEntity.workflow_step_id),
            )
            .where(
                col(WorkflowStepEntity.task_contract).is_(None),
                or_(
                    col(WorkItemEntity.claimed_by_user_id) == actor.id,
                    and_(
                        col(WorkItemEntity.status) == "OPEN",
                        or_(
                            col(WorkItemEntity.id).in_(direct_items),
                            col(WorkItemEntity.id).in_(group_items),
                        ),
                    ),
                ),
            )
        )
        return (
            or_(
                col(BusinessRequestEntity.requester_user_id) == actor.id,
                col(BusinessRequestEntity.workflow_version_id).in_(visible_versions),
                col(BusinessRequestEntity.id).in_(visible_work_requests),
            ),
        )

    async def submission_for(
        self, request_id: UUID, *, update: bool = False
    ) -> FormSubmissionEntity:
        return await self._submission(request_id, update=update)

    async def _submission(self, request_id: UUID, *, update: bool = False) -> FormSubmissionEntity:
        query = select(FormSubmissionEntity).where(
            FormSubmissionEntity.business_request_id == request_id,
            col(FormSubmissionEntity.step_execution_id).is_(None),
        )
        if update:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = (await self.session.exec(query)).one_or_none()
        if row is None:
            raise NotFoundException("Form submission not found")
        return row

    @staticmethod
    def _own_draft(row: BusinessRequestEntity, actor: UserEntity) -> None:
        if row.requester_user_id != actor.id:
            raise NotAllowedException("Only the requester can change a draft")
        if row.status != "DRAFT":
            raise VersionConflictException("Only drafts can be changed", conflict_kind="lifecycle")

    async def _definition_roots(
        self, workflow_ref: str, form_ref: str
    ) -> tuple[WorkflowDefinitionEntity, FormDefinitionEntity]:
        workflow = await self.session.get(WorkflowDefinitionEntity, open_ref_id(workflow_ref)[0])
        form = await self.session.get(FormDefinitionEntity, open_ref_id(form_ref)[0])
        if workflow is None or workflow.deleted_at:
            raise NotFoundException("Workflow not found")
        if form is None or form.deleted_at:
            raise NotFoundException("Form not found")
        return workflow, form

    async def _published_workflow(self, definition_id: UUID) -> WorkflowVersionEntity:
        row = (
            await self.session.exec(
                select(WorkflowVersionEntity)
                .where(
                    WorkflowVersionEntity.workflow_definition_id == definition_id,
                    WorkflowVersionEntity.status == "PUBLISHED",
                )
                .order_by(col(WorkflowVersionEntity.number).desc(), col(WorkflowVersionEntity.id))
                .limit(1)
            )
        ).one_or_none()
        if row is None:
            raise VersionConflictException(
                "Published workflow version not found", conflict_kind="lifecycle"
            )
        return row

    async def _published_form(self, definition_id: UUID) -> FormVersionEntity:
        row = (
            await self.session.exec(
                select(FormVersionEntity)
                .where(
                    FormVersionEntity.form_definition_id == definition_id,
                    FormVersionEntity.status == "PUBLISHED",
                )
                .order_by(col(FormVersionEntity.number).desc(), col(FormVersionEntity.id))
                .limit(1)
            )
        ).one_or_none()
        if row is None:
            raise VersionConflictException(
                "Published form version not found", conflict_kind="lifecycle"
            )
        return row

    @staticmethod
    def _payload_hash(data: dict[str, object]) -> str:
        try:
            payload = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except TypeError, ValueError, RecursionError:
            raise ValidationDetailsException(
                [{"pointer": "/data", "code": "data.invalid"}]
            ) from None
        return hashlib.sha256(payload.encode()).hexdigest()
