from typing import Annotated

from fastapi import APIRouter, Depends, Request

from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import open_ref_id
from utils.base_schema import response_schema
from utils.pagination import Page
from utils.presenter import PageResponse, page_response

router = APIRouter(responses=response_schema(), prefix="/admin/history", tags=["admin"])
HistoryAdmin = Annotated[UserEntity, Depends(RequirePermission("admin.history.read"))]


@router.post("/{entity_name}/search", response_model=PageResponse[Page[HistoryRecordDTO]])
async def query_history(
    request: Request,
    entity_name: str,
    query: HistoryQuery,
    _: HistoryAdmin,
    session: SessionDep,
    entity_ref: str | None = None,
) -> PageResponse[Page[HistoryRecordDTO]]:
    """Return registered operational history; self-only personal documents remain inaccessible."""
    entity_id = open_ref_id(entity_ref)[0] if bool(entity_ref) else None
    return page_response(
        request, await HistoryService.for_entity(session, entity_name).list(query, entity_id)
    )
