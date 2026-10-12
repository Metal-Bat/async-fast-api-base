"""Internal persisted contract for one background execution attempt."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from apps.ai.domain.contracts import AIDecisionContract
from apps.integrations.domain.contracts import ConnectionPin
from apps.integrations.domain.orders import ProtectedApprovalEvidence, SandboxOrderReceipt
from core.base_dto import BaseDTO

type OrderDispatchState = Literal["PREPARED", "DISPATCHING", "UNKNOWN", "CONFIRMED"]


class OrderDispatchEvidence(BaseDTO):
    operation_id: UUID
    payload_hash: str
    state: OrderDispatchState = "PREPARED"
    receipt: SandboxOrderReceipt | None = None
    dispatched_at: datetime | None = None


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
    protected_approval: ProtectedApprovalEvidence | None = None
    order_dispatch: OrderDispatchEvidence | None = None


class AutomationResult(BaseDTO):
    attempt_id: UUID
    disposition: str
