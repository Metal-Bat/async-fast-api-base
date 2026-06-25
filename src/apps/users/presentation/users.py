from fastapi import APIRouter, Depends, Request

from apps.users.application.service import UserService, get_user_service
from apps.users.domain.dto import UserDTO, UserQuery

# from core.deps import get_current_active_superuser
from utils.base_schema import (
    BaseHeaders,
    PaginatedResponse,
    get_base_headers,
    response_schema,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/",
    # dependencies=[Depends(get_current_active_superuser)],
    responses=response_schema(PaginatedResponse[UserDTO]),
)
async def users_list(
    request: Request,
    query: UserQuery,  # type: ignore
    headers: BaseHeaders = Depends(get_base_headers),
    service: UserService = Depends(get_user_service),
):
    return await service.list(query)
