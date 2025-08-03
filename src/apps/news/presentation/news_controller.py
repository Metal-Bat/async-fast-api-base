from fastapi import APIRouter, Depends, Query, Request

from src.apps.news.data.news import NewsProvider
from src.apps.news.domain.news_service import get_list_of_news
from src.utils.base_schema import BaseHeaders, get_base_headers, response_schema

router = APIRouter(tags=["news"])


@router.get("/news", responses=response_schema(list[NewsProvider]))
async def list_news(
    request: Request,
    headers: BaseHeaders = Depends(get_base_headers),
    page: int = Query(0, ge=0, description="number of page"),
    page_size: int = Query(10, ge=1, le=100, description="items in this page"),
):
    news = await get_list_of_news(page, page_size)
    return news
