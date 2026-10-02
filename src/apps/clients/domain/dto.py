"""Public client registration and release authoring contracts."""

from typing import Any, ClassVar

from pydantic import ConfigDict, Field, field_validator, model_validator

from apps.clients.domain.contracts import ClientKind, ClientVersion
from core.base_dto import BaseDTO
from utils.pagination import SearchRequest, auto_query_model


class ClientCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    kind: ClientKind
    platform: str = Field(min_length=1, max_length=64)
    confidential: bool = False


class ClientReleaseCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=3, max_length=64)
    api_version: str = Field(min_length=1, max_length=32)
    renderer_capabilities: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        ClientVersion.parse(value)
        return value

    @model_validator(mode="after")
    def unique_capabilities(self) -> ClientReleaseCreateDTO:
        if len(set(self.renderer_capabilities)) != len(self.renderer_capabilities):
            raise ValueError("Renderer capabilities must be unique")
        if any(not value or len(value) > 128 for value in self.renderer_capabilities):
            raise ValueError("Renderer capability is invalid")
        return self


class ClientDTO(BaseDTO):
    ref_id: str
    code: str
    name: str
    kind: ClientKind
    platform: str
    confidential: bool
    is_active: bool


class ClientCreateResultDTO(BaseDTO):
    client: ClientDTO
    secret: str | None = None


class ClientReleaseDTO(BaseDTO):
    ref_id: str
    client_ref_id: str
    version: str
    api_version: str
    renderer_capabilities: list[str]
    is_enabled: bool


class ClientUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=64)
    is_active: bool = True


class ClientQuery(SearchRequest):
    __query_fields__ = auto_query_model(
        ClientDTO, exclude={"ref_id", "confidential"}
    ).__query_fields__


class ClientReleaseCreateRequestDTO(ClientReleaseCreateDTO):
    client_ref_id: str


class ClientReleaseQuery(SearchRequest):
    client_ref_id: str
    __query_fields__: ClassVar[dict[str, Any]] = {
        "release_version": str,
        "api_version": str,
        "is_enabled": bool,
    }
