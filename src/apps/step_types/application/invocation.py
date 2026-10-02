"""Per-attempt context and result for trusted step classes."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class StepServices(Protocol):
    """Only approved application operations exposed to a step invocation."""

    async def request_priority(self) -> int: ...
    async def has_permission(self, permission: str) -> bool: ...
    async def connection_status(self) -> int: ...
    async def ai_decision(
        self, agent_ref: str, execution_id: UUID, attempt_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class StepInvocationContext:
    actor_id: UUID
    process_id: UUID
    request_id: UUID
    execution_id: UUID
    attempt_id: UUID
    idempotency_key: str
    inputs: Mapping[str, Any]
    services: StepServices
    cancelled: Callable[[], bool]
    client_id: str | None = None


@dataclass(frozen=True, slots=True)
class StepResult:
    outputs: dict[str, Any]
    outcome: str | None = None
