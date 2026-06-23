from fastapi import APIRouter

from apps.users.presentation.login import router as login_router
from apps.users.presentation.users import router as users_router

api_router = APIRouter()
api_router.include_router(login_router)
api_router.include_router(users_router)
