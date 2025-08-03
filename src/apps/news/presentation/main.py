from fastapi import APIRouter

from src.apps.news.presentation.news_controller import router as news_router

api_router = APIRouter()
api_router.include_router(news_router)
