"""Protected request-type CRUD and business-request lifecycle routes."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from apps.forms.application.attachments import AttachmentService
from apps.forms.application.localization import localize_snapshot
from apps.forms.application.options import OptionService
from apps.forms.domain.attachment_dto import (
    AttachmentAddDTO,
    AttachmentMutationDTO,
    AttachmentReorderDTO,
    AttachmentReplaceDTO,
    SubmissionAttachmentDTO,
)
from apps.forms.domain.behavior import ManualOverrideRequest, ManualOverrideState
from apps.forms.domain.collection import CollectionEditRequest
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.forms.domain.options import OptionQuery, OptionResult
from apps.forms.domain.runtime import RuntimeFormStateDTO
from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestDTO,
    BusinessRequestQuery,
    BusinessRequestSubmitDTO,
    BusinessRequestUpdateDTO,
    EligibleRequestTypeDTO,
    EligibleRequestTypeQuery,
    RequestTypeCreateDTO,
    RequestTypeDTO,
    RequestTypeQuery,
)
from apps.requests.domain.entity import BusinessRequestEntity, RequestTypeEntity
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from core.deps import ClientContextDep, SessionDep
from core.history_dto import (
    HistoryQuery,
    HistoryRecordDTO,
    ResourceHistoryDTO,
    ResourceHistoryQuery,
)
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.exceptions import NotFoundException
from utils.pagination import Page, paginate_entities
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    success_response,
)

types_router = APIRouter(
    prefix="/request-types", tags=["request-types"], responses=response_schema()
)
requests_router = APIRouter(
    prefix="/business-requests",
    tags=["business-requests"],
    responses=response_schema(),
    dependencies=[Depends(private_no_store)],
)
RequestAdmin = Annotated[UserEntity, Depends(RequirePermission("requests.manage"))]
RequestUser = Annotated[UserEntity, Depends(RequirePermission("requests.start"))]


@types_router.post(
    "/eligible/search",
    response_model=PageResponse[Page[EligibleRequestTypeDTO]],
    dependencies=[Depends(private_no_store)],
    summary="Search request types this requester can start",
    responses=PRIVATE_NO_STORE_RESPONSES,
    description="Requires requests.start, not requests.manage or forms.manage. Server filters active types/dependencies, workflow start access, current published pins and trusted registered-client/release targets before one-based bounded pagination. Declared supported_render_dialects further narrows compatibility; empty capabilities return an empty page without disclosing inaccessible choices. Empty/incompatible/ineligible results all appear as no eligible choices; selection grants no authority. Draft creation independently repeats eligibility checks. Page/size default to 1/20, size <=100; private no-store response. Client identity comes from the authenticated session, never browser identity headers.",
)
async def search_eligible_request_types(
    request: Request,
    data: EligibleRequestTypeQuery,
    actor: RequestUser,
    session: SessionDep,
    client: ClientContextDep,
):
    return page_response(request, await RequestService(session).eligible_types(data, actor, client))


async def type_dto(service: RequestService, row: RequestTypeEntity) -> RequestTypeDTO:
    workflow = await service.session.get(WorkflowDefinitionEntity, row.workflow_definition_id)
    form = await service.session.get(FormDefinitionEntity, row.form_definition_id)
    if workflow is None or form is None:
        raise NotFoundException("Request type dependency not found")
    return RequestTypeDTO(
        ref_id=create_ref_id(row.id, row.version),
        code=row.code,
        name=row.name,
        workflow_ref_id=create_ref_id(workflow.id, workflow.version),
        form_ref_id=create_ref_id(form.id, form.version),
        is_active=row.is_active,
        allow_cross_client_resume=row.allow_cross_client_resume,
        default_priority=row.default_priority,
        extension_contract=row.extension_contract,
        client_targets=await service.client_target_dtos(row.id),
        created_at=row.created_at,
    )


async def request_dto(service: RequestService, row: BusinessRequestEntity) -> BusinessRequestDTO:
    submission = await service.submission_for(row.id)
    request_type = await service.session.get(RequestTypeEntity, row.request_type_id)
    requester = await service.session.get(UserEntity, row.requester_user_id)
    workflow = await service.session.get(WorkflowVersionEntity, row.workflow_version_id)
    form = await service.session.get(FormVersionEntity, submission.form_version_id)
    if request_type is None or requester is None or workflow is None or form is None:
        raise NotFoundException("Business request dependency not found")
    return BusinessRequestDTO(
        process_ref_id=await service.process_reference(row.id),
        ref_id=create_ref_id(row.id, row.version),
        request_type_ref_id=create_ref_id(request_type.id, request_type.version),
        requester_ref_id=create_ref_id(requester.id, requester.version),
        workflow_version_ref_id=create_ref_id(workflow.id, workflow.version),
        form_version_ref_id=create_ref_id(form.id, form.version),
        status=row.status,
        priority=row.priority,
        data=submission.data,
        item_identity=submission.item_identity,
        submitted_at=row.submitted_at,
        closed_at=row.closed_at,
        created_at=row.created_at,
        origin_client=row.origin_client_context,
        design_snapshot=localize_snapshot(
            submission.design_snapshot, FormDocuments.model_validate(form, from_attributes=True)
        ),
    )


@requests_router.get(
    "/{ref_id}/view",
    response_model=SuccessResponse[RuntimeFormStateDTO],
    summary="Read an ordinary requester's pinned runtime form",
    responses=PRIVATE_NO_STORE_RESPONSES,
    description="Requires requests.start plus ownership/superuser and the pinned origin-client policy. No forms.manage is required. Returns bpms.runtime/1 with exact form/design identity, current request/submission refs, visible display/validation metadata, canonical values, row keys and effective writable/required scopes. DRAFT owners may edit; submitted/closed views are read-only. Accept-Language resolves the pinned catalog without changing the client variant. Incompatible dialects return 409; unauthorized forms return 404; private no-store response.",
)
async def get_request_runtime(
    request: Request, ref_id: str, actor: RequestUser, session: SessionDep, client: ClientContextDep
):
    return success_response(
        request, await RequestService(session).runtime_state(ref_id, actor, client)
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


@types_router.post("/search", response_model=PageResponse[Page[RequestTypeDTO]])
async def search_types(
    request: Request, query: RequestTypeQuery, _: RequestAdmin, session: SessionDep
):
    service = RequestService(session)
    page = await paginate_entities(session, RequestTypeEntity, query)
    return page_response(
        request,
        Page[RequestTypeDTO](
            items=[await type_dto(service, row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@types_router.get("/{ref_id}", response_model=SuccessResponse[RequestTypeDTO])
async def get_type(request: Request, ref_id: str, _: RequestAdmin, session: SessionDep):
    service = RequestService(session)
    return success_response(request, await type_dto(service, await service.get_type(ref_id)))


@types_router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def history_type(
    request: Request, ref_id: str, query: HistoryQuery, _: RequestAdmin, session: SessionDep
):
    await RequestService(session).get_type(ref_id)
    return page_response(
        request,
        await HistoryService.for_entity(session, "request_type").list(
            query, open_ref_id(ref_id)[0]
        ),
    )


@types_router.post("/report", response_model=PageResponse[Page[RequestTypeDTO]])
async def report_types(
    request: Request, query: RequestTypeQuery, actor: RequestAdmin, session: SessionDep
):
    return await search_types(request, query, actor, session)


@types_router.post("", response_model=SuccessResponse[RequestTypeDTO], status_code=201)
async def create_type(
    request: Request, data: RequestTypeCreateDTO, _: RequestAdmin, session: SessionDep
):
    service = RequestService(session)
    row = await service.create_type(data)
    await session.commit()
    return success_response(request, await type_dto(service, row), code=201)


@types_router.put("/{ref_id}", response_model=SuccessResponse[RequestTypeDTO])
async def update_type(
    request: Request,
    ref_id: str,
    data: RequestTypeCreateDTO,
    _: RequestAdmin,
    session: SessionDep,
):
    service = RequestService(session)
    row = await service.update_type(ref_id, data)
    await session.commit()
    return success_response(request, await type_dto(service, row))


@types_router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_type(request: Request, ref_id: str, _: RequestAdmin, session: SessionDep):
    await RequestService(session).delete_type(ref_id)
    await session.commit()
    return success_response(request, None)


@requests_router.post("/search", response_model=PageResponse[Page[BusinessRequestDTO]])
async def search_requests(
    request: Request, query: BusinessRequestQuery, actor: RequestUser, session: SessionDep
):
    service = RequestService(session)
    page = await paginate_entities(
        session,
        BusinessRequestEntity,
        query,
        criteria=service.visibility_criteria(actor),
    )
    return page_response(
        request,
        Page[BusinessRequestDTO](
            items=[await request_dto(service, row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@requests_router.get("/{ref_id}", response_model=SuccessResponse[BusinessRequestDTO])
async def get_request(request: Request, ref_id: str, actor: RequestUser, session: SessionDep):
    service = RequestService(session)
    return success_response(
        request, await request_dto(service, await service.get_request(ref_id, actor))
    )


@requests_router.post("/report", response_model=PageResponse[Page[BusinessRequestDTO]])
async def report_requests(
    request: Request, query: BusinessRequestQuery, actor: RequestUser, session: SessionDep
):
    return await search_requests(request, query, actor, session)


@requests_router.post("", response_model=SuccessResponse[BusinessRequestDTO], status_code=201)
async def create_request(
    request: Request,
    data: BusinessRequestCreateDTO,
    actor: RequestUser,
    client: ClientContextDep,
    session: SessionDep,
):
    service = RequestService(session)
    row, _ = await service.create_draft(data, actor, client)
    await session.commit()
    return success_response(request, await request_dto(service, row), code=201)


@requests_router.post(
    "/{ref_id}/collections/edit",
    response_model=SuccessResponse[RuntimeFormStateDTO],
    description="Requires requests.start and ownership of the current draft revision and authenticated origin client. Mutates a declared array by stable item_key; returns actor-filtered runtime data, the current owning revision and UUIDv7 identities. Nested identities and attachment paths move with items. Duplicate items receive new keys. Stale ref_id fails with VERSION_CONFLICT.",
)
async def edit_request_collection(
    request: Request,
    ref_id: str,
    data: CollectionEditRequest,
    actor: RequestUser,
    client: ClientContextDep,
    session: SessionDep,
):
    service = RequestService(session)
    await service.edit_collection(ref_id, data, actor, client)
    await session.commit()
    return success_response(request, await service.runtime_state(ref_id, actor, client))


@requests_router.post(
    "/{ref_id}/overrides",
    response_model=SuccessResponse[ManualOverrideState],
    description="Requires a current owned or claimed draft and the calculation's declared override permission. Set records actor, reason, value and input fingerprint; reset recomputes from current inputs. Source changes invalidate an override at submission.",
)
async def override_calculation(
    request: Request,
    ref_id: str,
    data: ManualOverrideRequest,
    actor: RequestUser,
    client: ClientContextDep,
    session: SessionDep,
):
    values, provenance = await RequestService(session).apply_override(ref_id, data, actor, client)
    await session.commit()
    return success_response(
        request, ManualOverrideState(data=values, override_provenance=provenance)
    )


@requests_router.put("/{ref_id}", response_model=SuccessResponse[BusinessRequestDTO])
async def update_request(
    request: Request,
    ref_id: str,
    data: BusinessRequestUpdateDTO,
    actor: RequestUser,
    client: ClientContextDep,
    session: SessionDep,
):
    service = RequestService(session)
    row, _ = await service.update_draft(ref_id, data, actor, client)
    await session.commit()
    return success_response(request, await request_dto(service, row))


@requests_router.post(
    "/{ref_id}/resume-presentation",
    response_model=SuccessResponse[BusinessRequestDTO],
    summary="Open an authorized draft presentation on this client",
    description=(
        "Requires requests.start, request ownership, an enabled cross-client resume policy, "
        "and a trusted registered client release. Keeps the original request client and pinned "
        "form version while auditing a new design snapshot."
    ),
)
async def resume_request_presentation(
    request: Request,
    ref_id: str,
    actor: RequestUser,
    client: ClientContextDep,
    session: SessionDep,
):
    service = RequestService(session)
    row, _ = await service.resume_presentation(ref_id, actor, client)
    await session.commit()
    return success_response(request, await request_dto(service, row))


@requests_router.post("/{ref_id}/submit", response_model=SuccessResponse[BusinessRequestDTO])
async def submit_request(
    request: Request,
    ref_id: str,
    data: BusinessRequestSubmitDTO,
    actor: RequestUser,
    client: ClientContextDep,
    session: SessionDep,
):
    service = RequestService(session)
    row, _ = await service.submit(ref_id, data, actor, client)
    await session.commit()
    return success_response(request, await request_dto(service, row))


@requests_router.get(
    "/{ref_id}/attachments", response_model=SuccessResponse[list[SubmissionAttachmentDTO]]
)
async def list_attachments(request: Request, ref_id: str, actor: RequestUser, session: SessionDep):
    service = AttachmentService(session)
    rows = await service.list_for_request(ref_id, actor)
    return success_response(
        request, [await attachment_dto(service, row, upload) for row, upload in rows]
    )


@requests_router.post(
    "/{ref_id}/attachments", response_model=SuccessResponse[AttachmentMutationDTO], status_code=201
)
async def add_attachment(
    request: Request,
    ref_id: str,
    data: AttachmentAddDTO,
    actor: RequestUser,
    session: SessionDep,
):
    service = AttachmentService(session)
    business_request, row = await service.add(ref_id, data, actor)
    await session.commit()
    return success_response(
        request,
        AttachmentMutationDTO(
            request_ref_id=create_ref_id(business_request.id, business_request.version),
            attachment=await attachment_dto(service, row),
        ),
        code=201,
    )


@requests_router.put("/{ref_id}/attachments", response_model=SuccessResponse[BusinessRequestDTO])
async def reorder_attachments(
    request: Request,
    ref_id: str,
    data: AttachmentReorderDTO,
    actor: RequestUser,
    session: SessionDep,
):
    service = AttachmentService(session)
    row = await service.reorder(ref_id, data, actor)
    await session.commit()
    return success_response(request, await request_dto(RequestService(session), row))


@requests_router.put(
    "/{ref_id}/attachments/{attachment_ref_id}",
    response_model=SuccessResponse[AttachmentMutationDTO],
)
async def replace_attachment(
    request: Request,
    ref_id: str,
    attachment_ref_id: str,
    data: AttachmentReplaceDTO,
    actor: RequestUser,
    session: SessionDep,
):
    service = AttachmentService(session)
    business_request, row = await service.replace(ref_id, attachment_ref_id, data, actor)
    await session.commit()
    return success_response(
        request,
        AttachmentMutationDTO(
            request_ref_id=create_ref_id(business_request.id, business_request.version),
            attachment=await attachment_dto(service, row),
        ),
    )


@requests_router.delete(
    "/{ref_id}/attachments/{attachment_ref_id}", response_model=SuccessResponse[BusinessRequestDTO]
)
async def remove_attachment(
    request: Request,
    ref_id: str,
    attachment_ref_id: str,
    actor: RequestUser,
    session: SessionDep,
):
    service = AttachmentService(session)
    row = await service.remove(ref_id, attachment_ref_id, actor)
    await session.commit()
    return success_response(request, await request_dto(RequestService(session), row))


@requests_router.get(
    "/{ref_id}/attachments/{attachment_ref_id}/content",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Authorized private bytes; no JSON envelope. / محتوای خصوصی مجاز؛ بدون پوشش JSON.",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "const": "private, no-store"}},
                "Content-Disposition": {"schema": {"type": "string"}},
                "X-Content-Type-Options": {"schema": {"type": "string", "const": "nosniff"}},
            },
        }
    },
)
async def download_attachment(
    ref_id: str, attachment_ref_id: str, actor: RequestUser, session: SessionDep
) -> StreamingResponse:
    upload = await AttachmentService(session).upload_for_download(ref_id, attachment_ref_id, actor)
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


@requests_router.post("/{ref_id}/cancel", response_model=SuccessResponse[BusinessRequestDTO])
async def cancel_request(
    request: Request, ref_id: str, actor: RequestUser, client: ClientContextDep, session: SessionDep
):
    service = RequestService(session)
    row = await service.cancel(ref_id, actor, client)
    await session.commit()
    return success_response(request, await request_dto(service, row))


@requests_router.post(
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
    summary="Resolve options for a pinned request form",
    description="Requires requests.start and current request visibility. Uses the exact pinned form and interaction variant; caller data supplies unsaved dependency values only. Current user/group visibility and ref revisions are checked independently. Results carry source revision, dependency fingerprint and generation; stale responses must be discarded. Submission revalidates saved values. No shared cache or server-side URL fetching.",
)
async def request_options(
    request: Request, ref_id: str, query: OptionQuery, actor: RequestUser, session: SessionDep
):
    service = RequestService(session)
    row = await service.get_request(ref_id, actor)
    submission = await service.submission_for(row.id)
    form = await session.get(FormVersionEntity, submission.form_version_id)
    if form is None:
        raise NotFoundException("Pinned form version not found")
    documents = FormDocuments.model_validate(form, from_attributes=True)
    snapshot = localize_snapshot(submission.design_snapshot, documents)
    render = snapshot["render_schema"] if bool(snapshot) else documents.render_schema
    return page_response(
        request, await OptionService(session).resolve(documents, query, actor, render=render)
    )


@requests_router.post(
    "/{ref_id}/history",
    response_model=PageResponse[Page[ResourceHistoryDTO]],
    summary="Read owned request submission history",
    description="Requires requests.start and ownership or superuser status. Reads the latest owned submission by opaque revision-bearing ref_id; it does not mutate or repin the request. Body page defaults to 1, size to 20 (1–100); filters/sort_orders allow changed_at and operation only. Stable descending change-time order is used by default. Canonical values, comments and actor identities are omitted. Inaccessible resources return 404. / نیازمند requests.start و مالکیت درخواست یا دسترسی مدیر است. نسخهٔ کنونی فرم را با صفحه‌بندی می‌خواند؛ داده‌های فرم، نظرها و هویت کاربران بازگردانده نمی‌شوند. منبع غیرمجاز خطای 404 دارد.",
)
async def request_history(
    request: Request,
    ref_id: str,
    query: ResourceHistoryQuery,
    actor: RequestUser,
    session: SessionDep,
):
    return page_response(
        request, await RequestService(session).history_metadata(ref_id, query, actor)
    )
