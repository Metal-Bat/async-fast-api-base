from pydantic import AliasChoices, ConfigDict, Field

from core.base_dto import BaseDTO
from utils.pagination import SearchRequest, auto_query_model
from utils.select import SelectQuery, SelectResponseFormat


class TaskSelectQuery(SelectQuery):
    response_format: SelectResponseFormat = "page"


class TaskDefinitionDTO(BaseDTO):
    model_config = ConfigDict(populate_by_name=True)

    ref_id: str = Field(validation_alias=AliasChoices("ref_id", "refId"))
    name: str
    module: str
    callable_name: str = Field(validation_alias=AliasChoices("callable_name", "callableName"))
    signature: str
    description: str | None
    bind: bool
    queue: str
    retry_for: list[str] = Field(validation_alias=AliasChoices("retry_for", "retryFor"))
    max_retries: int
    retry_backoff: bool
    retry_jitter: bool
    soft_time_limit: int
    time_limit: int


class TaskDefinitionQuery(SearchRequest):
    __query_fields__ = auto_query_model(
        TaskDefinitionDTO, exclude={"ref_id", "retry_for"}
    ).__query_fields__
