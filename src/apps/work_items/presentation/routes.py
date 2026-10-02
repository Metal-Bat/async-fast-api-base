"""Authenticated cartable queries and explicit human-work actions."""

from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from apps.forms.application.attachments import AttachmentService
from apps.forms.application.localization import localize_snapshot
from apps.forms.application.options import OptionService
from apps.forms.domain.attachment_dto import (
    AttachmentAddDTO,
    AttachmentReorderDTO,
    AttachmentReplaceDTO,
    SubmissionAttachmentDTO,
)
from apps.forms.domain.behavior import ManualOverrideRequest, ManualOverrideState
from apps.forms.domain.collection import CollectionEditRequest, CollectionState
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.entity import FormVersionEntity
from apps.forms.domain.options import OptionQuery, OptionResult
from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.processes.domain.entity import StepExecutionEntity
from apps.requests.domain.entity import BusinessRequestEntity
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import (
    CartableQueryDTO,
    WorkItemAttachmentMutationDTO,
    WorkItemCommandDTO,
    WorkItemCommentDTO,
    WorkItemCompleteDTO,
    WorkItemDTO,
    WorkItemForwardDTO,
    WorkItemSaveDTO,
    WorkItemStateDTO,
    WorkItemViewDTO,
)
from apps.work_items.domain.entity import WorkItemEntity
from core.deps import SessionDep
from core.ref_id import create_ref_id
from utils.base_schema import response_schema
from utils.exceptions import NotFoundException
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    success_response,
)

router = APIRouter(
    prefix="/work-items",
    tags=["work-items"],
    responses=response_schema(),
    dependencies=[Depends(private_no_store)],
)
WorkUser = Annotated[UserEntity, Depends(RequirePermission("requests.start"))]


async def work_item_dto(
    service: WorkItemService, item: WorkItemEntity, actor: UserEntity
) -> WorkItemDTO:
    request = await service.session.get(BusinessRequestEntity, item.business_request_id)
    execution = await service.session.get(StepExecutionEntity, item.step_execution_id)
    form = (
        await service.session.get(FormVersionEntity, item.form_version_id)
        if item.form_version_id
        else None
    )
    submission = await service.submission(item) if item.form_version_id else None
    claimant = (
        await service.session.get(UserEntity, item.claimed_by_user_id)
        if item.claimed_by_user_id
        else None
    )
    state = await service.state_for(item.id, actor.id)
    if request is None or execution is None:
        raise NotFoundException("Work-item dependency not found")
    snapshot = (
        localize_snapshot(
            submission.design_snapshot, FormDocuments.model_validate(form, from_attributes=True)
        )
        if submission and form
        else None
    )
    step = await service._step(item)
    visible_identity = submission.item_identity if submission else None
    if snapshot and step.task_contract:
        view = await service.task_view(create_ref_id(item.id, item.version), actor)
        snapshot = {
            key: value
            for key, value in snapshot.items()
            if key not in {"localization", "page_settings"}
        }
        snapshot["render_schema"] = view.render_schema
        visible_identity = view.item_identity
    return WorkItemDTO(
        ref_id=create_ref_id(item.id, item.version),
        request_ref_id=create_ref_id(request.id, request.version),
        step_execution_ref_id=create_ref_id(execution.id, execution.version),
        form_version_ref_id=create_ref_id(form.id, form.version) if form else None,
        submission_ref_id=create_ref_id(submission.id, submission.version) if submission else None,
        item_identity=visible_identity,
        design_snapshot=snapshot,
        status=item.status,
        priority=item.priority,
        claimant_ref_id=create_ref_id(claimant.id, claimant.version) if claimant else None,
        outcome_key=item.outcome_key,
        due_at=item.due_at,
        claimed_at=item.claimed_at,
        closed_at=item.closed_at,
        created_at=item.created_at,
        read_at=state.read_at if state else None,
        pinned_at=state.pinned_at if state else None,
        archived_at=state.archived_at if state else None,
        watching_at=state.watching_at if state else None,
    )


async def attachment_dto(
    service: AttachmentService, row, upload: UserUploadEntity | None = None
) -> SubmissionAttachmentDTO:
    upload = upload or await service.session.get(UserUploadEntity, row.user_upload_id)
    if upload is None:
        raise NotFoundException("Attachment upload not found")
    group_ref = None
    if row.contributing_group_id is not None:
        from apps.work_groups.domain.entity import WorkGroupEntity

        group = await service.session.get(WorkGroupEntity, row.contributing_group_id)
        if group is not None:
            group_ref = create_ref_id(group.id, group.version)
    return SubmissionAttachmentDTO(
        ref_id=create_ref_id(row.id, row.version),
        upload_ref_id=create_ref_id(upload.id, upload.version),
        field_path=row.field_path,
        position=row.position,
        caption=row.caption,
        kind=upload.kind,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        contributing_group_ref_id=group_ref,
        created_at=row.created_at,
    )


@router.post("/search", response_model=PageResponse[Page[WorkItemDTO]])
async def search_work_items(
    request: Request, query: CartableQueryDTO, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    page = await service.search(query, actor)
    return page_response(
        request,
        Page[WorkItemDTO](
            items=[await work_item_dto(service, item, actor) for item in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@router.get("/{ref_id}", response_model=SuccessResponse[WorkItemDTO])
async def get_work_item(request: Request, ref_id: str, actor: WorkUser, session: SessionDep):
    service = WorkItemService(session)
    item = await service.get(ref_id, actor)
    return success_response(request, await work_item_dto(service, item, actor))


@router.get(
    "/{ref_id}/view",
    response_model=SuccessResponse[WorkItemViewDTO],
    summary="Read a policy-filtered pinned human-task view",
    description="Requires requests.start and current work-item visibility. The named edit, summary or print view composes with the submission's pinned client variant and current locale. Read policy filters data, prior review data, feedback and render nodes; presentation visibility never grants write permission. Autosave uses the revision-bearing work-item ref and stale writes fail with VERSION_CONFLICT. Unsaved navigation requires a client warning. Private no-store response.",
)
async def get_work_item_view(
    request: Request,
    ref_id: str,
    actor: WorkUser,
    session: SessionDep,
    key: str | None = Query(default=None, max_length=64),
):
    return success_response(request, await WorkItemService(session).task_view(ref_id, actor, key))


@router.post(
    "/{ref_id}/feedback/{feedback_key}/resolve",
    response_model=SuccessResponse[WorkItemViewDTO],
    summary="Resolve linked correction feedback",
    description="Requires the current claimant of an editable correction work item. The ref_id must carry the latest revision; the feedback key is an opaque stable ID from the pinned correction draft. Resolves only OPEN feedback and records actor and time. A stale or repeated command fails with VERSION_CONFLICT. Private no-store response.",
)
async def resolve_work_item_feedback(
    request: Request,
    ref_id: str,
    feedback_key: str,
    actor: WorkUser,
    session: SessionDep,
):
    service = WorkItemService(session)
    await service.resolve_feedback(ref_id, feedback_key, actor)
    await session.commit()
    return success_response(request, await service.task_view(ref_id, actor))


@router.get("/{ref_id}/attachments", response_model=SuccessResponse[list[SubmissionAttachmentDTO]])
async def list_work_item_attachments(
    request: Request, ref_id: str, actor: WorkUser, session: SessionDep
):
    work_service = WorkItemService(session)
    rows = await work_service.list_attachments(ref_id, actor)
    attachment_service = AttachmentService(session)
    return success_response(
        request,
        [await attachment_dto(attachment_service, row, upload) for row, upload in rows],
    )


@router.post(
    "/{ref_id}/attachments",
    response_model=SuccessResponse[WorkItemAttachmentMutationDTO],
    status_code=201,
)
async def add_work_item_attachment(
    request: Request,
    ref_id: str,
    data: AttachmentAddDTO,
    actor: WorkUser,
    session: SessionDep,
):
    service = WorkItemService(session)
    item, row = await service.add_attachment(ref_id, data, actor)
    await session.commit()
    await session.refresh(item)
    return success_response(
        request,
        WorkItemAttachmentMutationDTO(
            work_item_ref_id=create_ref_id(item.id, item.version),
            attachment=await attachment_dto(AttachmentService(session), row),
        ),
        code=201,
    )


@router.put("/{ref_id}/attachments", response_model=SuccessResponse[WorkItemDTO])
async def reorder_work_item_attachments(
    request: Request,
    ref_id: str,
    data: AttachmentReorderDTO,
    actor: WorkUser,
    session: SessionDep,
):
    service = WorkItemService(session)
    item = await service.reorder_attachments(ref_id, data, actor)
    return await _command_response(request, service, item, actor, session)


@router.put(
    "/{ref_id}/attachments/{attachment_ref_id}",
    response_model=SuccessResponse[WorkItemAttachmentMutationDTO],
)
async def replace_work_item_attachment(
    request: Request,
    ref_id: str,
    attachment_ref_id: str,
    data: AttachmentReplaceDTO,
    actor: WorkUser,
    session: SessionDep,
):
    service = WorkItemService(session)
    item, row = await service.replace_attachment(ref_id, attachment_ref_id, data, actor)
    await session.commit()
    await session.refresh(item)
    return success_response(
        request,
        WorkItemAttachmentMutationDTO(
            work_item_ref_id=create_ref_id(item.id, item.version),
            attachment=await attachment_dto(AttachmentService(session), row),
        ),
    )


@router.delete(
    "/{ref_id}/attachments/{attachment_ref_id}", response_model=SuccessResponse[WorkItemDTO]
)
async def remove_work_item_attachment(
    request: Request,
    ref_id: str,
    attachment_ref_id: str,
    actor: WorkUser,
    session: SessionDep,
):
    service = WorkItemService(session)
    item = await service.remove_attachment(ref_id, attachment_ref_id, actor)
    return await _command_response(request, service, item, actor, session)


@router.get("/{ref_id}/attachments/{attachment_ref_id}/content")
async def download_work_item_attachment(
    ref_id: str,
    attachment_ref_id: str,
    actor: WorkUser,
    session: SessionDep,
) -> StreamingResponse:
    upload = await WorkItemService(session).attachment_upload(ref_id, attachment_ref_id, actor)
    return StreamingResponse(
        await UserUploadService(session).stream(upload),
        media_type=upload.content_type,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(upload.original_filename),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _command_response(
    request: Request,
    service: WorkItemService,
    item: WorkItemEntity,
    actor: UserEntity,
    session: SessionDep,
):
    await session.commit()
    await session.refresh(item)
    return success_response(request, await work_item_dto(service, item, actor))


@router.post("/{ref_id}/claim", response_model=SuccessResponse[WorkItemDTO])
async def claim_work_item(
    request: Request, ref_id: str, data: WorkItemCommandDTO, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    return await _command_response(
        request, service, await service.claim(ref_id, data.command_key, actor), actor, session
    )


@router.post("/{ref_id}/release", response_model=SuccessResponse[WorkItemDTO])
async def release_work_item(
    request: Request, ref_id: str, data: WorkItemCommandDTO, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    item = await service.claimant_action(ref_id, "release", data.command_key, actor)
    return await _command_response(request, service, item, actor, session)


@router.post("/{ref_id}/start", response_model=SuccessResponse[WorkItemDTO])
async def start_work_item(
    request: Request, ref_id: str, data: WorkItemCommandDTO, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    item = await service.claimant_action(ref_id, "start", data.command_key, actor)
    return await _command_response(request, service, item, actor, session)


@router.post(
    "/{ref_id}/collections/edit",
    response_model=SuccessResponse[CollectionState],
    description="Requires requests.start, current work-item ref_id, and the active claimant. Edits a declared collection on the draft submission using stable UUIDv7 item keys. Returns canonical data and the identity map; stale revisions fail with VERSION_CONFLICT.",
)
async def edit_work_item_collection(
    request: Request,
    ref_id: str,
    data: CollectionEditRequest,
    actor: WorkUser,
    session: SessionDep,
):
    result = await WorkItemService(session).edit_collection(ref_id, data, actor)
    await session.commit()
    return success_response(
        request,
        CollectionState(data=result.data, item_identity=result.identity, issues=result.issues),
    )


@router.post(
    "/{ref_id}/overrides",
    response_model=SuccessResponse[ManualOverrideState],
    description="Requires a current owned or claimed draft and the calculation's declared override permission. Set records actor, reason, value and input fingerprint; reset recomputes from current inputs. Source changes invalidate an override at submission.",
)
async def override_calculation(
    request: Request,
    ref_id: str,
    data: ManualOverrideRequest,
    actor: WorkUser,
    session: SessionDep,
):
    values, provenance = await WorkItemService(session).apply_override(ref_id, data, actor)
    await session.commit()
    return success_response(
        request, ManualOverrideState(data=values, override_provenance=provenance)
    )


@router.post(
    "/{ref_id}/save",
    response_model=SuccessResponse[WorkItemDTO],
    summary="Autosave a claimed human-task draft",
    description="Requires requests.start and the current claimant. The revision-bearing ref_id and command_key guard stale and duplicate writes; a reused key with different data fails. Data replaces the draft, may be incomplete, but supplied types and the pinned task write policy are enforced. Hidden or read-only changes fail with pointer issues. UI navigation should warn about unsaved edits.",
)
async def save_work_item(
    request: Request, ref_id: str, data: WorkItemSaveDTO, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    item = await service.save(ref_id, data.command_key, data.data, actor)
    return await _command_response(request, service, item, actor, session)


async def _finish_response(
    request: Request,
    ref_id: str,
    action: Literal["complete", "reject", "return"],
    data: WorkItemCompleteDTO,
    actor: UserEntity,
    session: SessionDep,
):
    service = WorkItemService(session)
    item = await service.finish(
        ref_id,
        action,
        data.command_key,
        data.outcome_key,
        data.data,
        actor,
        data.comment,
        data.feedback,
    )
    return await _command_response(request, service, item, actor, session)


@router.post(
    "/{ref_id}/complete",
    response_model=SuccessResponse[WorkItemDTO],
    summary="Complete a declared human-task action",
    description="Requires current claimant, revision-bearing ref_id and command_key. The pinned task contract must declare a matching complete action and workflow transition. Full/action-specific validation, write policy and governed attachments run before one atomic idempotent process resume. Submitted data becomes immutable.",
)
async def complete_work_item(
    request: Request, ref_id: str, data: WorkItemCompleteDTO, actor: WorkUser, session: SessionDep
):
    return await _finish_response(request, ref_id, "complete", data, actor, session)


@router.post(
    "/{ref_id}/reject",
    response_model=SuccessResponse[WorkItemDTO],
    summary="Reject through a declared human-task action",
    description="Requires current claimant and a declared reject action/outcome. New task contracts require a comment when the action says require_comment. Action-specific validation preserves type and business constraints; the transition and submission commit atomically. Reusing command_key with identical payload is idempotent.",
)
async def reject_work_item(
    request: Request, ref_id: str, data: WorkItemCompleteDTO, actor: WorkUser, session: SessionDep
):
    return await _finish_response(request, ref_id, "reject", data, actor, session)


@router.post(
    "/{ref_id}/return",
    response_model=SuccessResponse[WorkItemDTO],
    summary="Return work with field or row feedback for correction",
    description="Requires current claimant, declared return outcome, reason, and at least one authorized feedback target for new task contracts. Feedback uses schema field scopes and UUIDv7 item keys for repeated rows. The submitted form stays immutable; a correction_entry task creates a linked draft with governed attachment links. Repeated command_key/payload replays idempotently.",
)
async def return_work_item(
    request: Request, ref_id: str, data: WorkItemCompleteDTO, actor: WorkUser, session: SessionDep
):
    return await _finish_response(request, ref_id, "return", data, actor, session)


@router.post("/{ref_id}/forward", response_model=SuccessResponse[WorkItemDTO])
async def forward_work_item(
    request: Request, ref_id: str, data: WorkItemForwardDTO, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    item = await service.forward(ref_id, data, actor)
    return await _command_response(request, service, item, actor, session)


async def _administrative_response(
    request: Request,
    ref_id: str,
    action: Literal["cancel", "expire"],
    data: WorkItemCommandDTO,
    actor: UserEntity,
    session: SessionDep,
):
    service = WorkItemService(session)
    item = await service.administrative_close(ref_id, action, data.command_key, actor)
    return await _command_response(request, service, item, actor, session)


@router.post("/{ref_id}/cancel", response_model=SuccessResponse[WorkItemDTO])
async def cancel_work_item(
    request: Request, ref_id: str, data: WorkItemCommandDTO, actor: WorkUser, session: SessionDep
):
    return await _administrative_response(request, ref_id, "cancel", data, actor, session)


@router.post("/{ref_id}/expire", response_model=SuccessResponse[WorkItemDTO])
async def expire_work_item(
    request: Request, ref_id: str, data: WorkItemCommandDTO, actor: WorkUser, session: SessionDep
):
    return await _administrative_response(request, ref_id, "expire", data, actor, session)


@router.post("/{ref_id}/comment", response_model=SuccessResponse[WorkItemDTO])
async def comment_on_work_item(
    request: Request, ref_id: str, data: WorkItemCommentDTO, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    item = await service.comment(ref_id, data.command_key, data.comment, actor)
    return await _command_response(request, service, item, actor, session)


async def _state_response(
    request: Request,
    ref_id: str,
    field: Literal["read_at", "pinned_at", "archived_at", "watching_at"],
    data: WorkItemStateDTO,
    actor: UserEntity,
    session: SessionDep,
):
    service = WorkItemService(session)
    item = await service.set_user_state(ref_id, actor, field, data.value)
    return await _command_response(request, service, item, actor, session)


@router.post("/{ref_id}/read", response_model=SuccessResponse[WorkItemDTO])
async def read_work_item(
    request: Request, ref_id: str, data: WorkItemStateDTO, actor: WorkUser, session: SessionDep
):
    return await _state_response(request, ref_id, "read_at", data, actor, session)


@router.post("/{ref_id}/pin", response_model=SuccessResponse[WorkItemDTO])
async def pin_work_item(
    request: Request, ref_id: str, data: WorkItemStateDTO, actor: WorkUser, session: SessionDep
):
    return await _state_response(request, ref_id, "pinned_at", data, actor, session)


@router.post("/{ref_id}/archive", response_model=SuccessResponse[WorkItemDTO])
async def archive_work_item(
    request: Request, ref_id: str, data: WorkItemStateDTO, actor: WorkUser, session: SessionDep
):
    return await _state_response(request, ref_id, "archived_at", data, actor, session)


@router.post("/{ref_id}/watch", response_model=SuccessResponse[WorkItemDTO])
async def watch_work_item(
    request: Request, ref_id: str, data: WorkItemStateDTO, actor: WorkUser, session: SessionDep
):
    return await _state_response(request, ref_id, "watching_at", data, actor, session)


@router.post(
    "/{ref_id}/options",
    responses={
        200: {
            "headers": {
                "Cache-Control": {
                    "description": "Protected option and navigation responses must not be cached.",
                    "schema": {"type": "string", "const": "private, no-store"},
                }
            }
        }
    },
    response_model=PageResponse[OptionResult],
    summary="Resolve options for a pinned human-task form",
    description="Requires requests.start and current work-item visibility. Uses the exact pinned form and interaction variant, with current actor-filtered domain membership. Input data supplies unsaved dependency values; completion rechecks persisted submission membership. Results echo generation and dependency fingerprint for stale-response rejection. No server URL fetch or shared cache.",
)
async def work_item_options(
    request: Request, ref_id: str, query: OptionQuery, actor: WorkUser, session: SessionDep
):
    service = WorkItemService(session)
    item = await service.get(ref_id, actor)
    submission = await service.submission(item)
    form = await session.get(FormVersionEntity, submission.form_version_id)
    if form is None:
        raise NotFoundException("Pinned form version not found")
    documents = FormDocuments.model_validate(form, from_attributes=True)
    snapshot = localize_snapshot(submission.design_snapshot, documents)
    render = snapshot["render_schema"] if snapshot else documents.render_schema
    step = await service._step(item)
    if step.task_contract:
        from apps.work_items.application.task_views import (
            allowed_view_scopes,
            filter_render,
            project_data,
        )
        from apps.work_items.domain.task_contract import HumanTaskContract

        contract = HumanTaskContract.model_validate(step.task_contract)
        view = next(row for row in contract.views if row.key == contract.default_view)
        scopes = allowed_view_scopes(view, step.field_policy or {})
        render = filter_render(render, scopes)
        query = query.model_copy(update={"data": project_data(query.data, scopes)})
    return page_response(
        request, await OptionService(session).resolve(documents, query, actor, render=render)
    )
