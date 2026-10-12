"""Bounded local sandbox order contracts; no monetary or live-vendor semantics."""

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO

PROTECTED_ORDER_OPERATION = "sandbox.order.create/1"
ORDER_CANCELLATION_OPERATION = "sandbox.order.cancel/1"
APPROVAL_POLICY = "purchase-human-approval/1"


class SandboxOrderPayload(BaseDTO):
    model_config = ConfigDict(extra="forbid", strict=True)
    item_code: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        description="Sandbox item identifier; no production catalog or monetary semantics.",
    )
    quantity: int = Field(ge=1, le=1000, description="Positive sandbox quantity, bounded to 1000.")
    note: str | None = Field(
        default=None,
        max_length=512,
        description="Optional approved note; never copied into public receipt or timeline.",
    )


class SandboxOrderReceipt(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID = Field(
        description="Stable external create identity, unchanged across duplicate delivery and lookup."
    )
    receipt_id: UUID = Field(
        description="Durable sandbox receipt identity, not a private backend row reference."
    )
    state: Literal["CREATED", "CANCELLED"] = Field(
        description="Actual provider order state; cancellation is separate from database rollback."
    )
    payload_hash: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 of canonical typed sandbox payload including default note; no payload values.",
    )


class SandboxCancellationReceipt(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID = Field(
        description="Stable reversal identity, distinct from the original create operation."
    )
    order_operation_id: UUID = Field(
        description="Original order identity being deliberately reversed."
    )
    receipt_id: UUID = Field(description="Durable cancellation receipt identity from the sandbox.")
    state: Literal["CANCELLED"] = Field(
        description="Provider-confirmed cancellation; queued or unknown reversal is not success."
    )
    payload_hash: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="Original canonical order payload hash; reversal cannot substitute inputs.",
    )


class ProtectedApprovalEvidence(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    policy_key: Literal["purchase-human-approval/1"] = APPROVAL_POLICY
    workflow_version_id: UUID
    graph_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval_step_id: UUID
    approval_execution_id: UUID
    work_item_id: UUID
    action_id: UUID
    actor_id: UUID
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


def payload_hash(value: object) -> str:
    """Hash canonical JSON without persisting a second business payload copy."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(encoded.encode()).hexdigest()
