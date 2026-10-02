from datetime import datetime
from typing import Any
from uuid import UUID

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
