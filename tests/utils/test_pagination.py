"""Tests for filtering, ordering, and pagination utilities."""

import pytest
from pydantic import ValidationError
from sqlmodel import select

from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from utils.pagination import FilterCriteria, PageRequest, apply_query, paginate_values


def _sql(operator: str, value: object) -> str:
    query = UserQuery(
        filters=[FilterCriteria(field_name="username", operation=operator, value=value)]
    )
    return str(apply_query(select(UserEntity), UserEntity, query))


def test_notin_filter() -> None:
    assert "NOT IN" in _sql("nin", ["a", "b"])


def test_startswith_filter() -> None:
    assert "LIKE" in _sql("startWith", "prefix")


def test_endswith_filter() -> None:
    assert "LIKE" in _sql("endsWith", "suffix")


def test_between_filter_requires_two_values() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="two-item"):
        UserQuery(
            filters=[
                FilterCriteria(field_name="created_at", operation="between", value=["2026-01-01"])
            ]
        )


def test_default_uuid_ordering() -> None:
    assert 'ORDER BY "USER"."ID" ASC' in str(
        apply_query(select(UserEntity), UserEntity, UserQuery())
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"filters": [{"field_name": "hashed_password", "operation": "equal", "value": "secret"}]},
        {"filters": [{"field_name": "created_at", "operation": "contains", "value": "x"}]},
        {"filters": [{"field_name": "created_at", "operation": "gt", "value": "invalid-date"}]},
        {"filters": [{"field_name": "username", "operation": "in", "value": "not-a-list"}]},
        {"filters": [{"field_name": "username", "operation": "isNull", "value": "x"}]},
        {"sort_orders": [{"field_name": "hashed_password", "operation": "asc"}]},
        {"sort_orders": [{"multi_field": ["username", "unknown"], "operation": "desc"}]},
        {"sort_orders": [{"field_name": "username", "multi_field": ["email"]}]},
        {"size": 0},
        {"page": 0},
    ],
)
def test_search_rejects_invalid_fields_operations_and_values(payload) -> None:
    with pytest.raises(ValidationError):
        UserQuery.model_validate(payload)


def test_multi_field_sort_and_count_use_the_same_filters() -> None:
    payload = {
        "filters": [{"field_name": "username", "operation": "contains", "value": "a%b"}],
        "sort_orders": [{"multi_field": ["username", "created_at"], "operation": "desc"}],
        "page": 3,
        "size": 5,
    }
    query = UserQuery.model_validate(payload)
    statement = apply_query(select(UserEntity), UserEntity, query)
    compiled = statement.compile()
    assert '"USERNAME" DESC' in str(statement) and '"CREATED_AT" DESC' in str(statement)
    assert '"ID" ASC' in str(statement)
    assert "a/%b" in compiled.params.values()
    assert 10 in compiled.params.values() and 5 in compiled.params.values()
    count = str(apply_query(select(UserEntity), UserEntity, query, paginate=False))
    assert "WHERE" in count and "LIMIT" not in count and "ORDER BY" not in count
    assert set(query.model_dump()) == {"filters", "sort_orders", "page", "size"}


def test_legacy_camel_case_search_input_serializes_as_snake_case() -> None:
    query = UserQuery.model_validate(
        {
            "filters": [{"fieldName": "username", "operation": "equal", "value": "ada"}],
            "sortOrders": [{"fieldName": "username", "operation": "asc"}],
        }
    )

    payload = query.model_dump(mode="json")
    assert payload["filters"][0]["field_name"] == "username"
    assert payload["sort_orders"][0]["field_name"] == "username"
    assert "sortOrders" not in payload


def test_paginate_values_uses_the_shared_page_contract() -> None:
    page = paginate_values(["a", "b", "c"], PageRequest(page=2, size=2))
    assert page.items == ["c"]
    assert page.total == 3
    assert page.total_pages == 2
