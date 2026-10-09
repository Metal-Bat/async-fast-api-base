"""Versioned private presets and favorites; no result bodies or actor assignment."""

import json
from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, JsonValue, model_validator

from apps.designer.domain.resource_links import ResourceLink, ResourceReference
from core.base_dto import BaseDTO
from utils.pagination import FilterCriteria, SearchRequest, SortOrder

type ViewScope = Literal["forms", "workflows", "business_requests", "work_items"]


class SavedViewInput(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "My active requests",
                    "resource_kind": "business_requests",
                    "schema_version": 1,
                    "command_key": "preset-create-1",
                    "query": {
                        "scope": "mine",
                        "filters": [
                            {"field_name": "status", "operation": "equal", "value": "RUNNING"}
                        ],
                    },
                    "column_keys": ["title", "status"],
                    "page_size": 20,
                }
            ]
        },
    )
    name: str = Field(min_length=1, max_length=120)
    resource_kind: ViewScope
    schema_version: Literal[1] = 1
    command_key: str = Field(min_length=1, max_length=128)
    query: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Version-one query document validated against the named list DTO. No page/size, result bodies, credentials, actor identifiers or reference-valued filters. At most 8 KiB, 20 filters and 10 sort orders. Cartable scopes retain only their supported typed query fields.",
    )
    column_keys: list[str] = Field(default_factory=list, max_length=30)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def bounded_document(self):
        if not self.name.strip() or len(set(self.column_keys)) != len(self.column_keys):
            raise ValueError("Name and distinct column keys are required")
        if len(json.dumps(self.query, allow_nan=False).encode()) > 8192:
            raise ValueError("Saved query exceeds 8 KiB")
        if any(key in self.query for key in ("page", "size")):
            raise ValueError("Page offset and size belong outside the saved query")
        for key, limit in (("filters", 20), ("sort_orders", 10)):
            supplied = self.query.get(key, [])
            if not isinstance(supplied, list) or len(supplied) > limit:
                raise ValueError("Saved filters and ordering must be bounded lists")
        return self


class SavedViewDTO(BaseDTO):
    ref_id: str
    name: str
    resource_kind: ViewScope
    schema_version: int
    query: dict[str, JsonValue]
    column_keys: list[str]
    page_size: int
    is_default: bool
    compatible: bool
    reason: Literal["compatible", "schema_changed"]


class AppliedView(BaseDTO):
    compatible: bool
    reason: Literal["compatible", "schema_changed"]
    resource_kind: ViewScope
    query: dict[str, JsonValue] | None = None
    column_keys: list[str] = Field(default_factory=list)


class FavoriteInput(ResourceReference):
    """Only existing resource-link kinds; work items retain their own pin state."""


class FavoriteDTO(BaseDTO):
    ref_id: str
    target: ResourceLink


class PersonalItemQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {
        "name": str,
        "scope": str,
        "created_at": datetime,
    }
    filters: list[FilterCriteria] = Field(default_factory=list, max_length=20)
    sort_orders: list[SortOrder] = Field(default_factory=list, max_length=10)


class PersonalHistoryQuery(SearchRequest):
    """Bounded metadata only; historical private queries and identities are not exposed."""

    __query_fields__: ClassVar[dict[str, Any]] = {"changed_at": datetime, "operation": str}
    filters: list[FilterCriteria] = Field(default_factory=list, max_length=20)
    sort_orders: list[SortOrder] = Field(default_factory=list, max_length=10)


class PersonalHistoryDTO(BaseDTO):
    changed_at: datetime
    operation: str


class DefaultCommand(BaseDTO):
    model_config = ConfigDict(extra="forbid")
