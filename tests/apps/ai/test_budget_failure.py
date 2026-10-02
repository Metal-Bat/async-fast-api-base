"""Worker failures distinguish exhausted logical-task budgets from other failures."""

from uuid import uuid7

import pytest

from apps.ai.application.errors import AIBudgetExhausted


def test_worker_records_stable_ai_budget_failure(monkeypatch) -> None:
    from apps.processes.application import automation
    from apps.tasks.tasks import BackgroundExecutionFailed, execute_bpms_background

    recorded = []

    async def execute(attempt_id):
        raise AIBudgetExhausted("task budget exhausted")

    async def fail(attempt_id, code):
        recorded.append(code)

    monkeypatch.setattr(automation, "execute_background", execute)
    monkeypatch.setattr(automation, "fail_background", fail)
    with pytest.raises(BackgroundExecutionFailed):
        execute_bpms_background.run(attempt_id=str(uuid7()))
    assert recorded == ["ai.budget.exhausted"]
