"""Public connection metadata excludes secret references and all credential material."""

from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from utils.pagination import SearchRequest

type SecretIdentifier = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]


class ConnectionConfig(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    endpoint_key: SecretIdentifier


class AIConnectionConfig(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    endpoint_key: SecretIdentifier = "hosted"
    models: list[str] = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=64)
    account: str | None = Field(
        default=None,
        max_length=128,
        description="Required account identifier for Snowflake or OpenAI Codex connections. ASCII letters, digits, underscores and hyphens only; never credentials.",
    )
    provider_retention: str = Field(min_length=1, max_length=256)
    transport_attempts: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def valid_models(self) -> AIConnectionConfig:
        if any(not value.strip() or len(value) > 255 for value in self.models):
            raise ValueError("Model IDs must be nonempty and at most 255 characters")
        if len(set(self.models)) != len(self.models):
            raise ValueError("Duplicate model ID")
        return self


class ConnectionCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    code: SecretIdentifier
    name: str = Field(min_length=1, max_length=255)
    provider: str = Field(min_length=1, max_length=64)
    kind: Literal["SERVICE", "NOTIFICATION", "AI"]
    non_secret_config: ConnectionConfig | AIConnectionConfig
    secret_ref: SecretIdentifier
    secret_version: SecretIdentifier


class ConnectionUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    status: Literal["ACTIVE", "DISABLED"]


class SecretRotationDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    secret_ref: SecretIdentifier
    secret_version: SecretIdentifier


class ConnectionDTO(BaseDTO):
    ref_id: str
    code: str
    name: str
    provider: str
    kind: str
    non_secret_config: ConnectionConfig | AIConnectionConfig
    status: str
    verification_status: str
    created_at: datetime


class ConnectionQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {
        "code": str,
        "name": str,
        "provider": str,
        "kind": str,
        "status": str,
        "verification_status": str,
        "created_at": datetime,
    }


class GrantDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    user_ref_id: str | None = None
    work_group_ref_id: str | None = None
    can_use: bool = True
    can_manage: bool = False

    @model_validator(mode="after")
    def target_and_capabilities(self) -> GrantDTO:
        if (self.user_ref_id is None) == (self.work_group_ref_id is None) or not (
            self.can_use or self.can_manage
        ):
            raise ValueError("Exactly one target and at least one capability are required")
        return self


class ConnectionGrantViewDTO(GrantDTO):
    ref_id: str


class ConnectionGrantQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {"can_use": bool, "can_manage": bool}
