"""Private preset input cannot preserve offsets, payloads or injected SQL filters."""

import pytest
from pydantic import ValidationError

from apps.users.application.saved_views import validate_preset
from apps.users.domain.saved_views import SavedViewInput


def test_saved_query_preserves_order_columns_and_size_without_offset():
    data = SavedViewInput(
        name="My active forms",
        resource_kind="forms",
        command_key="create-1",
        query={
            "filters": [{"field_name": "name", "operation": "contains", "value": "private text"}],
            "sort_orders": [{"field_name": "created_at", "operation": "desc"}],
        },
        column_keys=["name", "created_at"],
        page_size=50,
    )
    result = validate_preset(data)
    assert result.query["filters"] == [
        {"field_name": "name", "operation": "contains", "value": "private text"}
    ]
    assert result.page_size == 50
    assert "page" not in result.query and "size" not in result.query


@pytest.mark.parametrize(
    "query",
    [
        {"page": 2},
        {"size": 100},
        {"actor_id": "other"},
        {"filters": [{"field_name": "name; DROP TABLE USER", "operation": "equal", "value": "x"}]},
        {"filters": [{"field_name": "deleted_at", "operation": "isNotNull"}]},
    ],
)
def test_saved_queries_refuse_offsets_authority_and_injection(query):
    with pytest.raises((ValueError, ValidationError)):
        validate_preset(
            SavedViewInput(
                name="Private",
                command_key="invalid",
                resource_kind="forms",
                query=query,
                column_keys=["name"],
            )
        )


def test_saved_view_rejects_privilege_fields_and_unknown_columns():
    with pytest.raises(ValidationError):
        SavedViewInput.model_validate(
            {
                "name": "Private",
                "command_key": "invalid",
                "resource_kind": "forms",
                "user_id": "other",
            }
        )
    with pytest.raises(ValueError):
        validate_preset(
            SavedViewInput(
                name="Private", command_key="invalid", resource_kind="forms", column_keys=["secret"]
            )
        )
