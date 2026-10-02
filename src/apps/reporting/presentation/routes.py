from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from apps.reporting.application.service import ReportService
from apps.reporting.domain.dto import ReportDetailDTO, ReportDTO, ReportQuery
from core.deps import CurrentUser, SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import open_ref_id
from utils.base_schema import response_schema
from utils.pagination import Page
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response

router = APIRouter(responses=response_schema(), prefix="/reports", tags=["reports"])


async def get_report_service(session: SessionDep) -> ReportService:
    """Build the request-scoped reporting service."""
    return ReportService(session)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


@router.post("/search", response_model=PageResponse[Page[ReportDTO]])
async def search_reports(
    request: Request,
    query: ReportQuery,
    user: CurrentUser,
    service: ReportServiceDep,
) -> PageResponse[Page[ReportDTO]]:
    """Return only the requesting user's report records."""
    page = TypeAdapter(Page[ReportDTO]).validate_python(
        await service.list_owned(user.id, query), from_attributes=True
    )
    return page_response(request, page)


@router.get("/{ref_id}", response_model=SuccessResponse[ReportDetailDTO])
async def get_report(
    request: Request,
    ref_id: str,
    user: CurrentUser,
    service: ReportServiceDep,
) -> SuccessResponse[ReportDetailDTO]:
    """Return owned report details, including the AES archive password."""
    report = await service.get_owned(ref_id, user.id)
    detail = TypeAdapter(ReportDetailDTO).validate_python(report, from_attributes=True)
    return success_response(request, detail)


@router.get("/{ref_id}/download")
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
        headers={"Content-Disposition": f'attachment; filename="{report.file_name}"'},
    )


@router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def report_history(
    request: Request,
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
    return page_response(request, page)


@router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_report(
    request: Request,
    ref_id: str,
    user: CurrentUser,
    service: ReportServiceDep,
) -> SuccessResponse[None]:
    """Cancel an owned report and remove its private artifact."""
    report = await service.get_owned(ref_id, user.id)
    await service.delete(report)
    return success_response(request, None, code=204)
