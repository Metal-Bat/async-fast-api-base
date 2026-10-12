"""Actual peer browser, ordinary authentication and real worker receipt acknowledgment."""

import json
import os
import secrets
from pathlib import Path

import anyio
import pytest
from scripts.verify_release_pair import assert_contract_equal
from sqlmodel import col, select

from apps.processes.domain.entity import ProcessInstanceEntity
from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.entity import UserEntity
from apps.users.domain.preferences import PreferencesPatch
from apps.work_items.domain.entity import WorkItemEntity
from core.deps import SessionFactory, engine
from core.history import audit_context
from tests.integration.test_connected_fixture import connected_profile
from tests.integration.test_connected_workflow import _complete_parallel_reviews
from tests.integration.test_connected_workflow import scripted_model as connected_scripted_model
from tests.integration.test_notification_push import dispatching, owned_api
from tests.integration.test_required_human_approval import waiting_order
from utils.security import hash_password

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_PRIVATE_TRANSFERS") != "1",
        reason="requires disposable paired transfer services",
    ),
]

scripted_model = connected_scripted_model


@pytest.mark.anyio
@pytest.mark.usefixtures("scripted_model")
@pytest.mark.parametrize("language", ["en", "fa", "ar"])
@pytest.mark.parametrize("lose_approval_reply", [False, True])
async def test_actual_browser_approves_and_acknowledges_worker_receipt(
    tmp_path, language, lose_approval_reply
):
    assert os.environ["POSTGRES_DB"] == os.environ["FLOW_TEST_OWNED_DATABASE"]
    peer = Path(
        os.getenv("TRANSFER_FRONTEND_ROOT", "/home/erfan/Project/js/async-fast-api-base-frontend")
    )
    assert (peer / "server/receipt-browser-journey.mjs").is_file(), (
        "Actual peer receipt harness is required"
    )
    password = secrets.token_urlsafe(32)
    digest = await hash_password(password)
    tmp_path.chmod(0o700)
    try:
        with audit_context():
            async with SessionFactory() as session:
                item_id, reviewer_id, _ = await waiting_order(
                    session, receipt_view=True, connected=True
                )
                item_id = await _complete_parallel_reviews(
                    session, item_id, reviewer_id, claim_final=False
                )
                reviewer = await session.get(UserEntity, reviewer_id)
                item = await session.get(WorkItemEntity, item_id)
                assert reviewer is not None and item is not None
                reviewer.hashed_password = digest
                username, case_id = reviewer.username, item.business_request_id
                personal = PersonalSettingsService(session)
                current = await personal.read(reviewer)
                await personal.apply(
                    reviewer, PreferencesPatch(ref_id=current.ref_id, locale={"language": language})
                )
                await session.commit()
        credentials = tmp_path / "accounts.json"
        credentials.touch(mode=0o600)
        credentials.write_text(
            json.dumps(
                {
                    "users": [username],
                    "password": password,
                    "language": language,
                    "scenario": connected_profile(),
                    "lose_approval_reply": lose_approval_reply,
                }
            )
        )
        report = tmp_path / "browser-report.json"
        async with owned_api(lifespan="on") as api, dispatching():
            live = await api.get("/api/v1/openapi.json", headers={"Accept-Language": language})
            assert live.status_code == 200
            frozen = json.loads(
                (peer / "docs/reference/app-be-001" / f"openapi-{language}.json").read_text()
            )
            assert_contract_equal(frozen, live.json())
            with (tmp_path / "browser-private.log").open("w") as log:
                (tmp_path / "browser-private.log").chmod(0o600)
                process = await anyio.open_process(
                    ["mise", "exec", "--", "node", "server/browser-backend.spec.mjs"],
                    cwd=peer,
                    env={
                        **os.environ,
                        "BACKEND_BROWSER_ACCOUNTS": str(credentials),
                        "BACKEND_BROWSER_ORIGIN": str(api.base_url).rstrip("/"),
                        "BROWSER_APP_DIR": str(peer / "dist/ng-architect/browser"),
                        "BROWSER_REPORT_PATH": str(report),
                        "RECEIPT_BROWSER_CHECKS": "1",
                        "RECEIPT_DROP_APPROVAL_RESPONSE": "1" if lose_approval_reply else "0",
                    },
                    stdout=log,
                    stderr=log,
                )
                try:
                    with anyio.fail_after(120):
                        assert await process.wait() == 0, (
                            "Actual peer receipt journey failed; private diagnostics retained"
                        )
                finally:
                    if process.returncode is None:
                        process.terminate()
                        await process.wait()
                    await process.aclose()
        evidence = json.loads(report.read_text())
        assert evidence["status"] == "passed"
        assert evidence["diagnostics"] == []
        assert evidence.get("receiptDrops", 0) == int(lose_approval_reply)
        assert {
            "human-approve",
            "actual-worker-order",
            "readonly-receipt",
            "acknowledge",
            language,
        } <= set(evidence["scenarios"])
        async with SessionFactory() as session:
            roots = (
                await session.exec(
                    select(ProcessInstanceEntity).where(
                        ProcessInstanceEntity.business_request_id == case_id,
                        col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                    )
                )
            ).all()
            assert len(roots) == 1 and roots[0].status == "COMPLETED"
    finally:
        await engine.dispose()
