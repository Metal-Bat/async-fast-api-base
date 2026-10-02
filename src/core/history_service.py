from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from core.history import history_tables
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_repository import HistoryRepository
from utils.exceptions import NotFoundException
from utils.pagination import Page


class HistoryService:
    """Resolve a history table and return stable paginated responses."""

    def __init__(self, repository: HistoryRepository) -> None:
        self.repository = repository

    @classmethod
    def for_entity(cls, session: AsyncSession, entity_name: str) -> HistoryService:
        """Build a service for one registered source-table name."""
        table = history_tables().get(entity_name)
        if table is None:
            raise NotFoundException("History entity not found")
        return cls(HistoryRepository(session, table))

    async def list(
        self, query: HistoryQuery, entity_id: UUID | None = None
    ) -> Page[HistoryRecordDTO]:
        """Return one history page and its total matching row count."""
        items = await self.repository.list(query, entity_id)
        total = await self.repository.count(query, entity_id)
        return Page[HistoryRecordDTO](items=items, total=total, page=query.page, size=query.size)
