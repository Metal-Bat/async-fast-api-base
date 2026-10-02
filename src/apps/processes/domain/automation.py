"""Internal persisted contract for one background execution attempt."""

from uuid import UUID

from apps.ai.domain.contracts import AIDecisionContract
from apps.integrations.domain.contracts import ConnectionPin
from core.base_dto import BaseDTO


class AutomationSnapshot(BaseDTO):
    handler_key: str
    handler_version: str
    operation_key: str
    actor_id: UUID
    connection: ConnectionPin | None = None
    handler_fingerprint: str | None = None
    ai_agent_ref: str | None = None
    ai_agent_checksum: str | None = None
    ai_decision: AIDecisionContract | None = None


class AutomationResult(BaseDTO):
    attempt_id: UUID
    disposition: str
