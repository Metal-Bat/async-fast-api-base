"""Strict per-logical-task budget reservations."""

from decimal import Decimal

import pytest

from apps.ai.domain.budget import BudgetAmounts, BudgetLedger
from apps.ai.domain.contracts import AITaskLimits


def limits() -> AITaskLimits:
    return AITaskLimits(
        requests=2,
        tool_calls=1,
        input_tokens=100,
        output_tokens=50,
        total_tokens=120,
        elapsed_seconds=60,
        spend_usd=Decimal("0.40"),
    )


def test_reservations_count_against_budget_before_dispatch() -> None:
    ledger = BudgetLedger(limits=limits())
    first = BudgetAmounts(
        requests=1, input_tokens=50, output_tokens=20, total_tokens=70, spend_usd=Decimal("0.20")
    )
    ledger.reserve(first)
    with pytest.raises(ValueError, match="exhausted"):
        ledger.reserve(first)
    ledger.settle(
        first,
        BudgetAmounts(
            requests=1,
            input_tokens=30,
            output_tokens=10,
            total_tokens=40,
            spend_usd=Decimal("0.15"),
        ),
    )
    ledger.reserve(first)
    assert ledger.remaining().requests == 0
    assert ledger.remaining().spend_usd == Decimal("0.05")


def test_unknown_usage_keeps_reservation_and_overrun_blocks_future_calls() -> None:
    ledger = BudgetLedger(limits=limits())
    upper = BudgetAmounts(
        requests=1, input_tokens=80, output_tokens=40, total_tokens=120, spend_usd=Decimal("0.30")
    )
    ledger.reserve(upper)
    ledger.mark_unknown(upper)
    with pytest.raises(ValueError, match="exhausted"):
        ledger.reserve(upper)
    assert ledger.unknown


def test_negative_or_inconsistent_usage_is_rejected() -> None:
    with pytest.raises(ValueError):
        BudgetAmounts(requests=1, input_tokens=4, output_tokens=5, total_tokens=2)
    with pytest.raises(ValueError):
        BudgetAmounts(spend_usd=Decimal("-0.01"))
