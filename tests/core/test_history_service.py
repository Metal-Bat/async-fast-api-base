"""Tests for shared entity-history application behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from core.history_dto import HistoryQuery
from core.history_repository import HistoryRepository
from core.history_service import HistoryService
from utils.exceptions import NotFoundException


def test_history_row_normalizes_dynamic_values() -> None:
    """Dynamic database columns become stable before/after dictionaries."""
    row_id = uuid7()
    entity_id = uuid7()
    dto = HistoryRepository._to_dto(
        {
            "ID": row_id,
            "ENTITY_ID": entity_id,
            "MODIFIER_TYPE": "user",
            "MODIFIER_ID": "actor",
            "CHANGED_AT": datetime.now(UTC),
            "OPERATION": "update",
            "FROM_TITLE": "before",
            "TO_TITLE": "after",
        }
    )
    assert dto.id == row_id and dto.entity_id == entity_id
    assert dto.from_values == {"title": "before"}
    assert dto.to_values == {"title": "after"}


@pytest.mark.anyio
async def test_history_service_returns_paginated_response() -> None:
    """History service combines repository rows and total count."""
    repository = Mock()
    repository.list = AsyncMock(return_value=[])
    repository.count = AsyncMock(return_value=7)
    response = await HistoryService(repository).list(HistoryQuery(page=2, size=10))
    assert response.items == [] and response.total == 7


def test_history_service_resolves_registered_tables() -> None:
    """Factory accepts registered entities and rejects unknown names."""
    session = object.__new__(AsyncSession)
    assert HistoryService.for_entity(session, "user").repository.table.name == "USER_HISTORY"
    with pytest.raises(NotFoundException):
        HistoryService.for_entity(session, "unknown")
