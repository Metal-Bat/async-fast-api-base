from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from apps.media.application.service import safe_filename
from apps.reporting.application.service import ReportService
from apps.reporting.domain.dto import ReportDetailDTO, ReportDTO, ReportQuery
from core.deps import CurrentUser, SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import open_ref_id
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    success_response,
)

router = APIRouter(responses=response_schema(), prefix="/reports", tags=["reports"])


async def get_report_service(session: SessionDep) -> ReportService:
    """Build the request-scoped reporting service."""
    return ReportService(session)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


@router.post(
    "/search", response_model=PageResponse[Page[ReportDTO]], responses=PRIVATE_NO_STORE_RESPONSES
)
async def search_reports(
    request: Request,
    response: Response,
    query: ReportQuery,
    user: CurrentUser,
    service: ReportServiceDep,
) -> PageResponse[Page[ReportDTO]]:
    """Return only the requesting user's report records."""
    page = TypeAdapter(Page[ReportDTO]).validate_python(
        await service.list_owned(user.id, query), from_attributes=True
    )
    private_no_store(response)
    return page_response(request, page)


@router.get(
    "/{ref_id}",
    response_model=SuccessResponse[ReportDetailDTO],
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def get_report(
    request: Request,
    response: Response,
    ref_id: str,
    user: CurrentUser,
    service: ReportServiceDep,
) -> SuccessResponse[ReportDetailDTO]:
    """Return owned report details, including the AES archive password."""
    report = await service.get_owned(ref_id, user.id)
    detail = TypeAdapter(ReportDetailDTO).validate_python(report, from_attributes=True)
    private_no_store(response)
    return success_response(request, detail)


@router.get(
    "/{ref_id}/download",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Authorized private bytes; no JSON envelope. / محتوای خصوصی مجاز؛ بدون پوشش JSON.",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "const": "private, no-store"}},
                "Content-Disposition": {"schema": {"type": "string"}},
                "X-Content-Type-Options": {"schema": {"type": "string", "const": "nosniff"}},
            },
        }
    },
)
async def download_report(
    ref_id: str,
    user: CurrentUser,
    service: ReportServiceDep,
) -> StreamingResponse:
    """Stream an owned report through a masked application URL."""
    report = await service.get_owned(ref_id, user.id)
    content = await service.download(report)
    return StreamingResponse(
        content=content,
        media_type=report.content_type or "application/zip",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(safe_filename(report.file_name), safe=""),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{ref_id}/history",
    response_model=PageResponse[Page[HistoryRecordDTO]],
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def report_history(
    request: Request,
    response: Response,
    ref_id: str,
    query: HistoryQuery,
    user: CurrentUser,
    service: ReportServiceDep,
    session: SessionDep,
) -> PageResponse[Page[HistoryRecordDTO]]:
    """Return lifecycle history for one report owned by the current user."""
    await service.get_owned(ref_id, user.id)
    report_id = open_ref_id(ref_id)[0]
    page = await HistoryService.for_entity(session, "report").list(query, report_id)
    private_no_store(response)
    return page_response(request, page)


@router.delete(
    "/{ref_id}", response_model=SuccessResponse[None], responses=PRIVATE_NO_STORE_RESPONSES
)
async def delete_report(
    request: Request,
    response: Response,
    ref_id: str,
    user: CurrentUser,
    service: ReportServiceDep,
) -> SuccessResponse[None]:
    """Cancel an owned report and remove its private artifact."""
    report = await service.get_owned(ref_id, user.id)
    await service.delete(report)
    private_no_store(response)
    return success_response(request, None, code=204)
