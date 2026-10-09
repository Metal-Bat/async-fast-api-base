"""Credential-free demo bootstrap results."""

from pydantic import Field

from core.base_dto import BaseDTO


class DemoSeedResult(BaseDTO):
    seed_version: int = 1
    request_types: dict[str, str] = Field(default_factory=dict)
    cases: dict[str, str] = Field(default_factory=dict)
    client_key: str
    client_release: str = "1.0.0"
