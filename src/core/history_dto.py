from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import Field

from core.base_dto import BaseDTO
from utils.pagination import SearchRequest, auto_query_model


class HistoryRecordDTO(BaseDTO):
    id: UUID
    entity_id: UUID
    modifier_type: str
    modifier_id: str
    changed_at: datetime
    operation: str
    request_id: str | None = None
    trace_id: str | None = None
    reason: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    from_values: dict[str, Any]
    to_values: dict[str, Any]


class HistoryQuery(SearchRequest):
    __query_fields__ = auto_query_model(
        HistoryRecordDTO, exclude={"from_values", "to_values"}
    ).__query_fields__


class ResourceHistoryDTO(BaseDTO):
    """Authorized timeline metadata; no canonical values or actor identifiers.

    فرادادهٔ مجاز تاریخچه؛ بدون مقادیر فرم یا شناسهٔ کاربران.
    """

    changed_at: datetime = Field(description="UTC change timestamp. / زمان تغییر به UTC.")
    operation: str = Field(description="Persisted lifecycle action. / رخداد ذخیره‌شده.")
    version: int | None = Field(
        default=None,
        description="Recorded revision when available; null otherwise. / نسخه در صورت موجود بودن؛ در غیر این صورت null.",
    )


class ResourceHistoryQuery(SearchRequest):
    """Bounded metadata search with no arbitrary entity or canonical-value selectors."""

    __query_fields__: ClassVar[dict[str, Any]] = {"changed_at": datetime, "operation": str}
