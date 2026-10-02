import builtins
from typing import Any
from uuid import UUID

from sqlalchemy import Table, select
from sqlmodel import func
from sqlmodel.ext.asyncio.session import AsyncSession

from core.history_dto import HistoryQuery, HistoryRecordDTO


class HistoryRepository:
    """Read one registered field-history table using SQL expression objects."""

    def __init__(self, session: AsyncSession, table: Table) -> None:
        self.session = session
        self.table = table

    def _statement(self, query: HistoryQuery, entity_id: UUID | None, *, paginate: bool):
        from types import SimpleNamespace

        from utils.pagination import apply_query

        columns = SimpleNamespace(**{column.name.lower(): column for column in self.table.c})
        statement = select(self.table) if paginate else select(func.count()).select_from(self.table)
        if entity_id is not None:
            statement = statement.where(self.table.c.ENTITY_ID == entity_id)
        return apply_query(
            statement, columns, query, paginate=paginate, default_ordering=("-changed_at", "-id")
        )

    async def list(
        self, query: HistoryQuery, entity_id: UUID | None = None
    ) -> builtins.list[HistoryRecordDTO]:
        """Return a validated, filtered page of history records."""
        result = await self.session.exec(self._statement(query, entity_id, paginate=True))
        return [self._to_dto(dict(row)) for row in result.mappings()]

    async def count(self, query: HistoryQuery, entity_id: UUID | None = None) -> int:
        """Count rows using exactly the same search filters as the result page."""
        result = await self.session.exec(self._statement(query, entity_id, paginate=False))
        return int(result.scalar_one())

    @staticmethod
    def _to_dto(row: dict[str, Any]) -> HistoryRecordDTO:
        """Normalize dynamic FROM_/TO_ columns into stable dictionaries."""
        from_values = {
            key.removeprefix("FROM_").lower(): value
            for key, value in row.items()
            if key.startswith("FROM_")
        }
        to_values = {
            key.removeprefix("TO_").lower(): value
            for key, value in row.items()
            if key.startswith("TO_")
        }
        return HistoryRecordDTO(
            id=row["ID"],
            entity_id=row["ENTITY_ID"],
            modifier_type=row["MODIFIER_TYPE"],
            modifier_id=row["MODIFIER_ID"],
            changed_at=row["CHANGED_AT"],
            operation=row["OPERATION"],
            request_id=row.get("REQUEST_ID"),
            trace_id=row.get("TRACE_ID"),
            reason=row.get("REASON"),
            source_ip=row.get("SOURCE_IP"),
            user_agent=row.get("USER_AGENT"),
            from_values=from_values,
            to_values=to_values,
        )
