"""The workflow gate provisions only its local database and always cleans up."""

import subprocess
from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest
from scripts import run_flow_test as runner


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setenv("FLOW_TEST_POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("FLOW_TEST_AUTOSTART", "1")


@pytest.mark.anyio
async def test_ready_database_needs_no_docker(environment, monkeypatch):
    probe = AsyncMock()
    docker = Mock()
    monkeypatch.setattr(runner, "_probe_postgres", probe, raising=False)
    monkeypatch.setattr(runner.subprocess, "run", docker)
    await runner._ensure_postgres()
    probe.assert_awaited_once()
    docker.assert_not_called()


@pytest.mark.anyio
async def test_stopped_database_starts_compose_and_waits(environment, monkeypatch):
    probe = AsyncMock(side_effect=[ConnectionRefusedError(), ConnectionRefusedError(), None])
    docker = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(runner, "_probe_postgres", probe, raising=False)
    monkeypatch.setattr(runner.subprocess, "run", docker)
    monkeypatch.setattr(runner.asyncio, "sleep", AsyncMock())
    await runner._ensure_postgres()
    assert probe.await_count == 3
    assert docker.call_args.args[0] == ["docker", "compose", "up", "-d", "postgres"]


@pytest.mark.anyio
@pytest.mark.parametrize("setting,value", [("POSTGRES_PORT", "5544"), ("FLOW_TEST_AUTOSTART", "0")])
async def test_unavailable_custom_or_opt_out_database_does_not_start_docker(
    environment, monkeypatch, setting, value
):
    monkeypatch.setenv(setting, value)
    monkeypatch.setattr(
        runner, "_probe_postgres", AsyncMock(side_effect=ConnectionRefusedError()), raising=False
    )
    docker = Mock()
    monkeypatch.setattr(runner.subprocess, "run", docker)
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        await runner._ensure_postgres()
    docker.assert_not_called()


@pytest.mark.anyio
async def test_authentication_error_never_starts_docker(environment, monkeypatch):
    monkeypatch.setattr(
        runner,
        "_probe_postgres",
        AsyncMock(side_effect=asyncpg.InvalidPasswordError()),
        raising=False,
    )
    docker = Mock()
    monkeypatch.setattr(runner.subprocess, "run", docker)
    with pytest.raises(asyncpg.InvalidPasswordError):
        await runner._ensure_postgres()
    docker.assert_not_called()


@pytest.mark.anyio
async def test_startup_wait_is_bounded(environment, monkeypatch):
    probe = AsyncMock(side_effect=ConnectionRefusedError())
    monkeypatch.setattr(runner, "_probe_postgres", probe, raising=False)
    monkeypatch.setattr(
        runner.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0))
    )
    monkeypatch.setattr(runner.asyncio, "sleep", AsyncMock())
    with pytest.raises(RuntimeError, match="ready"):
        await runner._ensure_postgres()
    assert probe.await_count == 16


def test_setup_error_is_safe_and_does_not_create_or_drop(environment, monkeypatch, capsys):
    monkeypatch.setattr(
        runner,
        "_ensure_postgres",
        AsyncMock(side_effect=asyncpg.InvalidPasswordError("private credential")),
        raising=False,
    )
    commands = AsyncMock()
    monkeypatch.setattr(runner, "_database_command", commands)
    assert runner.main() == 2
    assert "private credential" not in capsys.readouterr().err
    commands.assert_not_awaited()


@pytest.mark.parametrize("migration_code,test_code", [(1, 0), (0, 1), (0, 0)])
def test_database_is_dropped_after_migration_or_test_result(
    environment, monkeypatch, migration_code, test_code
):
    monkeypatch.setattr(runner, "_ensure_postgres", AsyncMock(), raising=False)
    commands = AsyncMock()
    monkeypatch.setattr(runner, "_database_command", commands)
    run = Mock(
        side_effect=[
            subprocess.CompletedProcess([], migration_code),
            subprocess.CompletedProcess([], test_code),
        ]
    )
    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main() == (migration_code or test_code)
    assert [call.args[1] for call in commands.await_args_list] == ["create", "drop"]
    assert run.call_count == (1 if migration_code else 2)


def test_remote_host_is_rejected_before_startup(environment, monkeypatch):
    monkeypatch.setenv("FLOW_TEST_POSTGRES_HOST", "remote.invalid")
    startup = AsyncMock()
    monkeypatch.setattr(runner, "_ensure_postgres", startup, raising=False)
    assert runner.main() == 2
    startup.assert_not_awaited()


def test_missing_test_process_is_failure_and_still_cleans_up(environment, monkeypatch):
    monkeypatch.setattr(runner, "_ensure_postgres", AsyncMock())
    commands = AsyncMock()
    monkeypatch.setattr(runner, "_database_command", commands)
    monkeypatch.setattr(
        runner.subprocess, "run", Mock(side_effect=[subprocess.CompletedProcess([], 0), OSError()])
    )
    assert runner.main() == 2
    assert commands.await_args_list[-1].args[1] == "drop"


@pytest.mark.parametrize("test_code,expected", [(0, 2), (1, 1)])
def test_cleanup_failure_is_reported_without_masking_test_failure(
    environment, monkeypatch, capsys, test_code, expected
):
    monkeypatch.setattr(runner, "_ensure_postgres", AsyncMock())
    monkeypatch.setattr(runner, "_database_command", AsyncMock(side_effect=[None, OSError()]))
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        Mock(
            side_effect=[
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], test_code),
            ]
        ),
    )
    assert runner.main() == expected
    assert "Cleanup failed" in capsys.readouterr().err


@pytest.mark.anyio
async def test_failed_compose_does_not_continue(environment, monkeypatch):
    probe = AsyncMock(side_effect=ConnectionRefusedError())
    monkeypatch.setattr(runner, "_probe_postgres", probe)
    monkeypatch.setattr(
        runner.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 1))
    )
    with pytest.raises(RuntimeError, match="Compose"):
        await runner._ensure_postgres()
    probe.assert_awaited_once()
