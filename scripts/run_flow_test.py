"""Migrate, test, and remove a fresh local PostgreSQL workflow database."""

import asyncio
import os
import subprocess
import sys
from uuid import uuid4

import asyncpg


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
    asyncio.run(_database_command(name, "create"))
    try:
        print(f"Migrating disposable database {name}", flush=True)
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=environment,
            check=True,
        )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/integration/test_full_workflow.py",
                "tests/integration/test_frontend_journey.py",
            ],
            env=environment,
            check=False,
        ).returncode
    finally:
        asyncio.run(_database_command(name, "drop"))
        print(f"Removed disposable database {name}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
