"""Real owned Swagger browser and PostgreSQL schedule conflict evidence."""

import base64
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid7

import anyio
import httpx
import pytest
from websockets.asyncio.client import connect

from apps.tasks.application.schedules import ScheduleService
from apps.tasks.domain.dtos.schedules import PeriodicTaskCreateDTO, PeriodicTaskUpdateDTO
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from core.settings import settings
from tests.integration.test_notification_push import owned_api
from utils.exceptions import VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_REPORT_WORKER") != "1",
        reason="requires disposable reporting worker and storage",
    ),
]


@pytest.fixture(autouse=True)
async def dispose_connections():
    yield
    await engine.dispose()


def require_owned():
    assert os.environ["POSTGRES_DB"].startswith("bpms_flow_")
    assert os.environ["POSTGRES_DB"] == os.environ["FLOW_TEST_OWNED_DATABASE"]


@pytest.mark.anyio
async def test_schedule_concurrent_write_and_noop():
    require_owned()
    async with SessionFactory() as session:
        row = await ScheduleService(session).create(
            PeriodicTaskCreateDTO(
                name=f"cons-{uuid7()}",
                task_name="system.ping",
                schedule_type="interval",
                interval_seconds=60,
            )
        )
        ref = create_ref_id(row.id, row.version)
    async with SessionFactory() as first, SessionFactory() as second:
        one, two = ScheduleService(first), ScheduleService(second)
        await one.get(ref)
        retained = await two.get(ref)
        assert retained.name.startswith("cons-")
        changed = await one.update(ref, PeriodicTaskUpdateDTO(interval_seconds=30))
        with pytest.raises(VersionConflictException):
            await two.update(ref, PeriodicTaskUpdateDTO(interval_seconds=40))
        current = create_ref_id(changed.id, changed.version)
        noop = await one.update(current, PeriodicTaskUpdateDTO(interval_seconds=30))
        assert create_ref_id(noop.id, noop.version) == current
        await one.delete(current)


@pytest.mark.anyio
async def test_owned_swagger_browser():
    require_owned()
    executable = os.getenv(
        "CONS_BROWSER_EXECUTABLE",
        "/tmp/cons-be-browser/chrome-headless-shell-linux64/chrome-headless-shell",
    )
    assert Path(executable).is_file(), "Required Swagger browser executable is unavailable"
    with TemporaryDirectory(prefix="cons-swagger-") as directory:
        profile = Path(directory) / "profile"
        profile.mkdir(mode=0o700)
        with (Path(directory) / "browser.log").open("w") as log:
            process = await anyio.open_process(
                [
                    executable,
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--remote-debugging-port=0",
                    f"--user-data-dir={profile}",
                    "about:blank",
                ],
                stdout=log,
                stderr=log,
            )
            try:
                with anyio.fail_after(30):
                    while not (profile / "DevToolsActivePort").exists():
                        assert process.returncode is None, "Required browser exited"
                        await anyio.sleep(0.1)
                port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
                async with httpx.AsyncClient(trust_env=False) as client:
                    pages = (await client.get(f"http://127.0.0.1:{port}/json/list")).json()
                async with (
                    owned_api(lifespan="on") as api,
                    connect(pages[0]["webSocketDebuggerUrl"]) as websocket,
                ):
                    identity = 0
                    browser_errors = []

                    async def command(method, params=None):
                        nonlocal identity
                        identity += 1
                        await websocket.send(
                            json.dumps({"id": identity, "method": method, "params": params or {}})
                        )
                        with anyio.fail_after(30):
                            while True:
                                result = json.loads(await websocket.recv())
                                if result.get("method") == "Runtime.exceptionThrown":
                                    browser_errors.append(
                                        result["params"]["exceptionDetails"].get(
                                            "text", "JavaScript exception"
                                        )
                                    )
                                if (
                                    result.get("method") == "Runtime.consoleAPICalled"
                                    and result.get("params", {}).get("type") == "error"
                                ):
                                    browser_errors.append(str(result["params"].get("args", [])))
                                if result.get("id") == identity:
                                    assert "error" not in result, result
                                    return result.get("result", {})

                    await command(
                        "Emulation.setDeviceMetricsOverride",
                        {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False},
                    )
                    await command("Runtime.enable")
                    await command("Network.enable")
                    for language in ("en", "fa"):
                        await command(
                            "Network.setExtraHTTPHeaders",
                            {"headers": {"Accept-Language": language}},
                        )
                        await command(
                            "Page.navigate",
                            {"url": f"{str(api.base_url).rstrip('/')}{settings.DOCS_URL}"},
                        )
                        specification = (
                            await api.get(
                                settings.OPENAPI_URL, headers={"Accept-Language": language}
                            )
                        ).json()
                        assert specification["x-docs-language"] == language
                        with anyio.fail_after(60):
                            while (
                                not (
                                    await command(
                                        "Runtime.evaluate",
                                        {
                                            "expression": "typeof ui !== 'undefined' && Boolean(document.querySelector('.operation-filter-input')) && ui.specSelectors.specJson().get('x-docs-language') === "
                                            + json.dumps(language),
                                            "returnByValue": True,
                                        },
                                    )
                                )
                                .get("result", {})
                                .get("value")
                            ):
                                await anyio.sleep(0.2)
                        for required in (
                            "schedules",
                            "preferences",
                            "inspector",
                            "restore",
                            "inbox/events",
                            "download",
                        ):
                            matches = [
                                (path, operation)
                                for path, operations in specification["paths"].items()
                                if required in path
                                for method, operation in operations.items()
                                if method in {"get", "post", "put", "delete", "patch"}
                            ]
                            assert matches, required
                            tag = matches[0][1]["tags"][0]
                            expression = (
                                "(()=>{const input=document.querySelector('.operation-filter-input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,"
                                + json.dumps(tag)
                                + "); input.dispatchEvent(new Event('input',{bubbles:true}));})()"
                            )
                            await command("Runtime.evaluate", {"expression": expression})
                            with anyio.fail_after(30):
                                while True:
                                    state = await command(
                                        "Runtime.evaluate",
                                        {
                                            "expression": "JSON.stringify(Array.from(document.querySelectorAll('.opblock-tag')).map(x=>x.textContent))",
                                            "returnByValue": True,
                                        },
                                    )
                                    tags = json.loads(state["result"]["value"])
                                    if any(text.startswith(tag) for text in tags):
                                        break
                                    await anyio.sleep(0.1)
                            await command(
                                "Runtime.evaluate",
                                {
                                    "expression": "Array.from(document.querySelectorAll('.opblock-tag')).find(x=>x.textContent.startsWith("
                                    + json.dumps(tag)
                                    + ")).click()"
                                },
                            )
                            with anyio.fail_after(30):
                                while True:
                                    state = await command(
                                        "Runtime.evaluate",
                                        {
                                            "expression": "JSON.stringify(Array.from(document.querySelectorAll('.opblock-summary-path')).map(x=>x.textContent))",
                                            "returnByValue": True,
                                        },
                                    )
                                    paths = json.loads(state["result"]["value"])
                                    assert not browser_errors, browser_errors
                                    if any(required in path for path in paths):
                                        break
                                    await anyio.sleep(0.1)
                            await command(
                                "Runtime.evaluate",
                                {
                                    "expression": "Array.from(document.querySelectorAll('.opblock')).find(x=>x.querySelector('.opblock-summary-path').textContent === "
                                    + json.dumps(matches[0][0])
                                    + ").querySelector('.opblock-summary-control').click()"
                                },
                            )
                            await command(
                                "Runtime.evaluate",
                                {
                                    "expression": "Array.from(document.querySelectorAll('.opblock')).find(x=>x.querySelector('.opblock-summary-path').textContent === "
                                    + json.dumps(matches[0][0])
                                    + ").scrollIntoView()"
                                },
                            )
                            await anyio.sleep(0.2)
                            details = await command(
                                "Runtime.evaluate",
                                {
                                    "expression": "Array.from(document.querySelectorAll('.opblock')).find(x=>x.querySelector('.opblock-summary-path').textContent === "
                                    + json.dumps(matches[0][0])
                                    + ").innerText",
                                    "returnByValue": True,
                                },
                            )
                            assert "Responses" in details["result"]["value"]
                            assert not browser_errors, browser_errors
                            screenshot = await command("Page.captureScreenshot", {"format": "png"})
                            destination = Path(os.getenv("APP_BE_ARTIFACT_DIR", directory))
                            destination.mkdir(mode=0o700, parents=True, exist_ok=True)
                            (
                                destination
                                / f"cons-swagger-{language}-{required.replace('/', '-')}.png"
                            ).write_bytes(base64.b64decode(screenshot["data"]))
            finally:
                process.terminate()
                with anyio.CancelScope(shield=True):
                    await process.wait()
                    await process.aclose()


@pytest.mark.anyio
async def test_schedule_http_and_actual_scheduler_worker():
    from datetime import timedelta

    from sqlmodel import col, select

    from apps.tasks.application.outbox import dispatch_outbox
    from apps.tasks.domain.entity import TaskExecutionEntity, TaskOutboxEntity
    from apps.users.domain.entity import UserEntity
    from core.celery_app import celery_app
    from core.celery_scheduler import _claim_leader, _enqueue_due, _release_leader
    from tests.integration.test_notification_push import login
    from utils.date_utils import get_datetime_utc
    from utils.security import hash_password

    require_owned()
    password = str(uuid7())
    admin_name, outsider_name = f"cons-admin-{uuid7()}", f"cons-outsider-{uuid7()}"
    async with SessionFactory() as session:
        hashed = await hash_password(password)
        session.add(UserEntity(username=admin_name, hashed_password=hashed, is_superuser=True))
        session.add(UserEntity(username=outsider_name, hashed_password=hashed))
        await session.commit()
    async with owned_api(lifespan="on") as client:
        headers, _ = await login(client, admin_name, password)
        outsider, _ = await login(client, outsider_name, password)
        payload = {
            "name": f"cons-worker-{uuid7()}",
            "task_name": "system.ping",
            "queue": settings.CELERY_REPORT_QUEUE,
            "schedule_type": "clocked",
            "clocked_at": (get_datetime_utc() - timedelta(seconds=1)).isoformat(),
            "one_off": True,
        }
        assert (
            await client.post("/api/v1/tasks/schedules", json=payload, headers=outsider)
        ).status_code == 403
        bad = await client.post(
            "/api/v1/tasks/schedules", json=payload | {"args": [1]}, headers=headers
        )
        assert bad.status_code == 422
        response = await client.post("/api/v1/tasks/schedules", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        ref = response.json()["data"]["ref_id"]
        read = await client.get(f"/api/v1/tasks/schedules/{ref}", headers=headers)
        assert read.status_code == 200
        owner = uuid7()
        assert await _claim_leader(owner)
        try:
            entries = await _enqueue_due(owner, celery_app)
            assert payload["name"] in entries
            async with SessionFactory() as session:
                messages = (
                    await session.exec(
                        select(TaskOutboxEntity).where(
                            TaskOutboxEntity.task_name == "system.ping",
                            col(TaskOutboxEntity.published_at).is_(None),
                        )
                    )
                ).all()
                assert len(messages) == 1
                task_id = messages[0].task_id
            await dispatch_outbox(celery_app)
            with anyio.fail_after(45):
                while True:
                    async with SessionFactory() as session:
                        executions = (
                            await session.exec(
                                select(TaskExecutionEntity).where(
                                    TaskExecutionEntity.task_id == task_id,
                                    TaskExecutionEntity.status == "SUCCESS",
                                )
                            )
                        ).all()
                        if executions:
                            break
                    await anyio.sleep(0.2)
            current = await client.get(f"/api/v1/tasks/schedules/{ref}", headers=headers)
            assert current.json()["data"]["enabled"] is False
            assert current.json()["data"]["total_run_count"] == 1
            stale = await client.put(
                f"/api/v1/tasks/schedules/{ref}", json={"enabled": False}, headers=headers
            )
            assert stale.status_code == 409
        finally:
            await _release_leader(owner)
