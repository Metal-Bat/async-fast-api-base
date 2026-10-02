"""Public contracts for durable event and timer waits."""

import pytest
from pydantic import ValidationError

from apps.processes.application.waits import correlation_hash
from apps.processes.domain.dto import EventDeliveryDTO


def test_correlation_hash_is_deterministic_and_never_contains_raw_value() -> None:
    first = correlation_hash("payment.received", "customer-secret-42")

    assert first == correlation_hash("payment.received", "customer-secret-42")
    assert first != correlation_hash("payment.failed", "customer-secret-42")
    assert "customer-secret-42" not in first
    assert len(first) == 64


def test_event_delivery_contract_rejects_unbounded_or_empty_identity() -> None:
    delivery = EventDeliveryDTO(
        correlation_key="invoice-42",
        delivery_key="provider-delivery-7",
        outcome="received",
        payload={"amount": 42},
    )
    assert delivery.model_dump() == {
        "correlation_key": "invoice-42",
        "delivery_key": "provider-delivery-7",
        "outcome": "received",
        "payload": {"amount": 42},
    }
    with pytest.raises(ValidationError):
        EventDeliveryDTO(
            correlation_key="",
            delivery_key="provider-delivery-7",
            outcome="received",
        )
