"""Private, installation-bound inputs for the supported bootstrap command."""

from typing import Literal
from uuid import UUID, uuid7

from pydantic import ConfigDict, Field, SecretStr

from core.base_dto import BaseDTO


class BootstrapAccount(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    persona: Literal["requester", "reviewer", "designer"]
    username: str = Field(min_length=1, max_length=255)
    password: SecretStr = Field(min_length=16)


class BootstrapManifest(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    seed_version: Literal[1] = 1
    installation_id: UUID = Field(default_factory=uuid7)
    database: str = Field(min_length=1, max_length=63)
    accounts: list[BootstrapAccount] = Field(min_length=1, max_length=3)


class BootstrapSummary(BaseDTO):
    created_users: list[str] = Field(default_factory=list)
    missing_users: list[str] = Field(default_factory=list)
    preserved_users: list[str] = Field(default_factory=list)
