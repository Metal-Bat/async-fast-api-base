from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.apps.news.data.news import NewsProvider
from src.core.engine import engine


async def get_list_of_news(
    offset_value: int,
    limit_value: int,
) -> list[NewsProvider]:
    async with AsyncSession(engine) as session:
        statement = (
            select(NewsProvider)
            .order_by("priority")
            .offset(offset_value)
            .limit(limit_value)
        )
        results = await session.exec(statement)
        return results.all()
