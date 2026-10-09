"""Validate private presets with the real list models; never broaden an incompatible query."""

from pydantic import ValidationError

from apps.forms.domain.dto import FormQuery
from apps.requests.domain.dto import BusinessRequestQuery
from apps.users.domain.saved_views import SavedViewInput
from apps.work_items.domain.dto import CartableQueryDTO
from apps.workflows.domain.dto import WorkflowQuery
from core.base_dto import BaseDTO
from utils.pagination import SearchRequest

SEARCH_MODELS: dict[str, type[SearchRequest]] = {
    "forms": FormQuery,
    "workflows": WorkflowQuery,
    "business_requests": BusinessRequestQuery,
}
QUERY_MODELS: dict[str, type[BaseDTO]] = SEARCH_MODELS | {"work_items": CartableQueryDTO}
PERMISSIONS = {
    "forms": "forms.manage",
    "workflows": "workflows.manage",
    "business_requests": "requests.start",
    "work_items": "requests.start",
}
_SCALARS = {
    "name",
    "code",
    "is_active",
    "status",
    "title",
    "priority",
    "created_at",
    "submitted_at",
    "closed_at",
}
COLUMNS = {
    scope: _SCALARS.intersection(model.__query_fields__ or {})
    for scope, model in SEARCH_MODELS.items()
}
COLUMNS["work_items"] = {"kind", "status", "priority", "due_at", "created_at", "closed_at"}


def validate_preset(data: SavedViewInput) -> SavedViewInput:
    """Reuse type/operator checks and restrict retained chips to non-reference scalar fields."""
    if not set(data.column_keys) <= COLUMNS[data.resource_kind]:
        raise ValueError("Unsupported saved-view column")
    filters = data.query.get("filters", [])
    sorts = data.query.get("sort_orders", [])
    if not isinstance(filters, list) or not isinstance(sorts, list):
        raise TypeError("Saved query filters and sorts must be lists")
    for filter_item in filters:
        if (
            not isinstance(filter_item, dict)
            or filter_item.get("field_name") not in COLUMNS[data.resource_kind]
        ):
            raise ValueError("Unsupported saved-view filter")
    for order in sorts:
        if not isinstance(order, dict):
            raise TypeError("Unsupported saved-view sort")
        names = order.get("multi_field") or [order.get("field_name")]
        if (
            not isinstance(names, list)
            or not all(isinstance(name, str) for name in names)
            or not set(names) <= COLUMNS[data.resource_kind]
        ):
            raise ValueError("Unsupported saved-view sort field")
    try:
        query = QUERY_MODELS[data.resource_kind].model_validate(
            data.query | {"page": 1, "size": data.page_size}
        )
    except ValidationError:
        raise ValueError("Saved query is incompatible with its list contract") from None
    canonical = query.model_dump(mode="json", exclude={"page", "size"})
    return data.model_copy(update={"name": data.name.strip(), "query": canonical})
