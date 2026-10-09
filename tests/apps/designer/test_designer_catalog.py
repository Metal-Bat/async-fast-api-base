"""Stable, bounded designer catalog and OpenAPI contracts."""

from unittest.mock import Mock

import pytest

from apps.designer.application.service import DesignerService
from apps.designer.domain.dto import CompletionItemDTO, DesignerQuery
from apps.step_types.application.registry import builtin_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.dto import StepTypeVersionDTO
from main import app


@pytest.mark.anyio
async def test_catalog_is_stable_searchable_and_bounded(monkeypatch) -> None:
    handler = builtin_registry().catalog()[0]
    step_type = StepTypeVersionDTO(**handler.model_dump(), ref_id="step-version", number=1)

    async def catalog(*_args, **_kwargs):
        return [step_type]

    monkeypatch.setattr(StepTypeService, "catalog", catalog)
    service = DesignerService(Mock())
    first = await service.catalog(DesignerQuery(size=100))
    second = await service.catalog(DesignerQuery(size=100))

    assert first.items == second.items
    assert [(item.category, item.key) for item in first.items] == sorted(
        (item.category, item.key) for item in first.items
    )
    assert {
        "step_type",
        "form_component",
        "renderer",
        "form_operator",
        "form_function",
        "expression_function",
        "expression_operator",
        "conversion",
        "process_status",
        "outcome",
    } <= {item.category for item in first.items}
    assert any(
        item.key == "version_in_range" and item.category == "expression_function"
        for item in first.items
    )
    running = next(item for item in first.items if item.key == "RUNNING")
    assert running.model_dump(mode="json")["metadata"]["compatible_next_values"] == [
        "WAITING",
        "PAUSED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    filtered = await service.catalog(DesignerQuery(search="date", size=2))
    assert len(filtered.items) <= 2
    assert filtered.total > len(filtered.items)


def test_completion_contract_uses_snake_case_and_type_metadata() -> None:
    schema = CompletionItemDTO.model_json_schema()
    assert set(schema["properties"]) == {
        "path",
        "source",
        "type_schema",
        "nullable",
        "cardinality",
        "source_step",
    }


def test_designer_routes_are_protected_and_bounded() -> None:
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/designer/catalog"]
    assert "post" in paths["/api/v1/designer/selectors/{kind}"]
    assert "post" in paths["/api/v1/designer/completion"]


@pytest.mark.anyio
async def test_enum_selectors_localize_labels_and_filter_before_paging() -> None:
    from apps.users.domain.entity import UserEntity
    from core.i18n import use_language

    service = DesignerService(Mock())
    actor = UserEntity(username="designer", hashed_password="hash")
    with use_language("fa"):
        page = await service.selector("process_status", DesignerQuery(search="تکمیل"), actor)
    assert [item.model_dump() for item in page.items] == [{"key": "COMPLETED", "value": "تکمیل‌شده"}]
    assert page.total == 1
    with use_language("en"):
        page = await service.selector("process_status", DesignerQuery(search="completed"), actor)
    assert page.items[0].model_dump() == {"key": "COMPLETED", "value": "Completed"}
    with use_language("unsupported"):
        page = await service.selector("process_status", DesignerQuery(size=2, page=2), actor)
    assert page.total == 6 and len(page.items) == 2
    assert all(item.key != item.value for item in page.items)


def test_select_openapi_uses_key_value_and_enum_selector_kinds() -> None:
    from apps.work_groups.domain.dto import WorkGroupSelectDTO
    from utils.select import SelectOption

    assert set(SelectOption[str].model_json_schema()["properties"]) == {"key", "value"}
    assert set(WorkGroupSelectDTO.model_json_schema()["properties"]) == {"key", "value"}
    operation = app.openapi()["paths"]["/api/v1/designer/selectors/{kind}"]["post"]
    parameter = next(item for item in operation["parameters"] if item["name"] == "kind")
    assert {"process_status", "request_status", "definition_status", "outcome"} <= set(
        parameter["schema"]["enum"]
    )


@pytest.mark.anyio
async def test_selector_route_returns_same_bounded_items_in_both_formats() -> None:
    from fastapi import Request

    from apps.designer.presentation.routes import selector
    from apps.users.domain.entity import UserEntity

    actor = UserEntity(username="designer", hashed_password="hash")
    request = Request({"type": "http", "headers": []})
    query = DesignerQuery(size=2)
    page = await selector(request, "process_status", query, actor, Mock(), response_format="page")
    items = await selector(request, "process_status", query, actor, Mock(), response_format="items")
    assert isinstance(items, list)
    assert not isinstance(page, list)
    assert [item.model_dump() for item in items] == [
        item.model_dump() for item in page.result.items
    ]
    assert len(items) == 2 and page.result.total == 6
