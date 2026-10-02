"""Protected in-application notification search, detail, and read operations."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from apps.notifications.application.service import NotificationService
from apps.notifications.domain.dto import DeliveryDTO, NotificationDTO, NotificationQuery
from apps.notifications.domain.entity import NotificationEntity
from apps.processes.domain.entity import ProcessInstanceEntity
from apps.requests.domain.entity import BusinessRequestEntity
from core.deps import CurrentUser, SessionDep
from core.ref_id import create_ref_id
from utils.base_schema import response_schema
from utils.pagination import Page
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response

router = APIRouter(prefix="/notifications", tags=["notifications"], responses=response_schema())


def service(session: SessionDep) -> NotificationService:
    return NotificationService(session)


ServiceDep = Annotated[NotificationService, Depends(service)]


async def notification_dto(
    row: NotificationEntity, application: NotificationService
) -> NotificationDTO:
    deliveries = await application.deliveries(row.id)
    business_request = await application.session.get(BusinessRequestEntity, row.business_request_id)
    process = await application.session.get(ProcessInstanceEntity, row.process_instance_id)
    if business_request is None or process is None:
        raise RuntimeError("Notification context is unavailable")
    return NotificationDTO(
        ref_id=create_ref_id(row.id, row.version),
        request_ref_id=create_ref_id(business_request.id, business_request.version),
        process_ref_id=create_ref_id(process.id, process.version),
        template_key=row.template_key,
        template_version=row.template_version,
        locale=row.locale,
        subject=row.subject,
        content=row.content,
        priority=row.priority,
        status=row.status,
        read_at=row.read_at,
        created_at=row.created_at,
        deliveries=[
            DeliveryDTO(
                ref_id=create_ref_id(delivery.id, delivery.version),
                channel=delivery.channel,
                status=delivery.status,
                attempt_count=delivery.attempt_count,
                provider_message_ref=delivery.provider_message_ref,
                last_error_code=delivery.last_error_code,
                next_attempt_at=delivery.next_attempt_at,
                delivered_at=delivery.delivered_at,
            )
            for delivery in deliveries
        ],
    )


@router.post("/search", response_model=PageResponse[Page[NotificationDTO]])
async def search_notifications(
    request: Request,
    query: NotificationQuery,
    actor: CurrentUser,
    application: ServiceDep,
):
    page = await application.search(query, actor)
    return page_response(
        request,
        Page[NotificationDTO](
            items=[await notification_dto(row, application) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@router.post("/report", response_model=PageResponse[Page[NotificationDTO]])
async def report_notifications(
    request: Request,
    query: NotificationQuery,
    actor: CurrentUser,
    application: ServiceDep,
):
    return await search_notifications(request, query, actor, application)


@router.get("/{ref_id}", response_model=SuccessResponse[NotificationDTO])
async def notification_detail(
    request: Request, ref_id: str, actor: CurrentUser, application: ServiceDep
):
    row = await application.get(ref_id, actor)
    return success_response(request, await notification_dto(row, application))


@router.post("/{ref_id}/read", response_model=SuccessResponse[NotificationDTO])
async def mark_notification_read(
    request: Request,
    ref_id: str,
    actor: CurrentUser,
    application: ServiceDep,
    session: SessionDep,
):
    row = await application.mark_read(ref_id, actor)
    await session.commit()
    return success_response(request, await notification_dto(row, application))
