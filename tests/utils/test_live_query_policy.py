"""Shared live pagination leaves explicit historical queries unaffected."""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlmodel import select

from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from utils.pagination import apply_query, paginate_entities


@pytest.mark.anyio
async def test_paginated_items_and_totals_apply_same_live_predicate() -> None:
    rows, count = Mock(), Mock()
    rows.all.return_value = []
    count.one.return_value = 0
    session = Mock(exec=AsyncMock(side_effect=[rows, count]))
    page = await paginate_entities(session, UserEntity, UserQuery(page=10, size=1))
    assert page.total == 0 and page.items == []
    for call in session.exec.await_args_list:
        assert '"USER"."DELETED_AT" IS NULL' in str(call.args[0])


def test_historical_query_builder_does_not_hide_deleted_rows() -> None:
    statement = apply_query(select(UserEntity), UserEntity, UserQuery(), paginate=False)
    assert "IS NULL" not in str(statement)
