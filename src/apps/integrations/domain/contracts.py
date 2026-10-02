"""Secret and provider interfaces owned by integration application policy."""

from typing import Protocol

from pydantic import SecretStr

from core.base_dto import BaseDTO


class SecretUnavailable(Exception):
    """A requested secret cannot safely be resolved."""


class SecretStore(Protocol):
    def resolve(self, reference: str, version: str) -> SecretStr: ...


class AdapterResult(BaseDTO):
    status_code: int


class ConnectionPin(BaseDTO):
    connection_ref: str
    provider: str
    kind: str
    endpoint_key: str
    secret_ref: str
    secret_version: str
