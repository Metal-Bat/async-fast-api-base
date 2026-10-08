"""Migrate, test, and remove a fresh local PostgreSQL workflow database."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]


async def _probe_postgres() -> None:
    connection = await asyncpg.connect(
        host=os.getenv("FLOW_TEST_POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        database="postgres",
        timeout=2,
    )
    await connection.close()


async def _ensure_postgres() -> None:
    try:
        await _probe_postgres()
        return
    except OSError:
        if (
            os.getenv("FLOW_TEST_AUTOSTART", "1") != "1"
            or os.getenv("POSTGRES_PORT", "5432") != "5432"
        ):
            raise RuntimeError(
                "Start PostgreSQL at the configured local port before flow-test"
            ) from None
    print("Starting local PostgreSQL with Docker Compose...", flush=True)
    result = await asyncio.to_thread(
        subprocess.run,
        ["docker", "compose", "up", "-d", "postgres"],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Unable to start PostgreSQL; check Docker Compose")
    for _ in range(15):
        try:
            await _probe_postgres()
            return
        except OSError:
            await asyncio.sleep(1)
    raise RuntimeError("PostgreSQL did not become ready; check the service and configured port")


async def _database_command(name: str, action: str) -> None:
    connection = await asyncpg.connect(
        host=os.getenv("FLOW_TEST_POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        database="postgres",
        timeout=5,
    )
    try:
        if action == "create":
            await connection.execute(f'CREATE DATABASE "{name}"')
        else:
            await connection.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    finally:
        await connection.close()


def main() -> int:
    host = os.getenv("FLOW_TEST_POSTGRES_HOST", "localhost")
    if host not in {"localhost", "127.0.0.1", "::1"}:
        print("Flow tests require a local PostgreSQL host", file=sys.stderr)
        return 2
    name = f"bpms_flow_{uuid4().hex}"
    environment = os.environ.copy()
    environment.update(
        POSTGRES_DB=name,
        POSTGRES_HOST=host,
        LOG_OUTPUTS='["console"]',
        OTEL_TRACES_EXPORTER="none",
        OTEL_METRICS_EXPORTER="none",
        OTEL_LOGS_EXPORTER="none",
        RUN_INTEGRATION="1",
        PYTHONPATH="src",
    )
    try:
        asyncio.run(_ensure_postgres())
        asyncio.run(_database_command(name, "create"))
    except (
        OSError,
        asyncpg.PostgresError,
        RuntimeError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
    ):
        print(
            "Flow test setup failed. Check local PostgreSQL, Docker Compose, and the "
            "POSTGRES_* settings in .envs/.backend. Start the service with "
            "`docker compose up -d postgres`; custom ports require a manually started service.",
            file=sys.stderr,
        )
        return 2
    status = 2
    try:
        print(f"Migrating disposable database {name}", flush=True)
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=environment,
            check=False,
        )
        status = migration.returncode
        if status == 0:
            status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "--tb=short",
                    "--show-capture=no",
                    "tests/integration/test_full_workflow.py",
                    "tests/integration/test_frontend_journey.py",
                    "tests/integration/test_platform_foundation.py",
                ],
                env=environment,
                check=False,
            ).returncode
    except OSError:
        print("Unable to execute migration or tests", file=sys.stderr)
        status = 2
    finally:
        try:
            asyncio.run(_database_command(name, "drop"))
            print(f"Removed disposable database {name}", flush=True)
        except OSError, asyncpg.PostgresError:
            print(
                f"Cleanup failed; remove disposable database {name} after restoring PostgreSQL",
                file=sys.stderr,
            )
            status = status or 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
