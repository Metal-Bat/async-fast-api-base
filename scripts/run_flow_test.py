"""Migrate, test, and remove a fresh local PostgreSQL workflow database."""

import asyncio
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
FLOW_TESTS = (
    "tests/integration/test_full_workflow.py",
    "tests/integration/test_frontend_journey.py",
    "tests/integration/test_platform_foundation.py",
)
PROFILES = {
    "delivery-completion": (
        "tests/integration/test_workflow_defaults.py",
        "tests/integration/test_studio_workspace.py",
        "tests/integration/test_definition_library.py",
    ),
    "delivery-through-020": (
        "tests/integration/test_support_failures.py",
        "tests/integration/test_calendar_events.py",
        "tests/integration/test_calendar_reminders.py",
        "tests/integration/test_visual_runtime_conformance.py",
    ),
    "flow": FLOW_TESTS,
    "delivery-transfers": (
        "tests/integration/test_owned_report_worker.py",
        "tests/integration/test_owned_notification_worker.py",
        "tests/integration/test_owned_calendar_worker.py",
        "tests/integration/test_private_transfers.py",
        "tests/integration/test_demo_assets.py",
    ),
    "delivery-wave-four": (
        *FLOW_TESTS,
        "tests/integration/test_demo_seed.py",
        "tests/integration/test_demo_groups.py",
        "tests/integration/test_personal_preferences.py",
        "tests/integration/test_help_state.py",
        "tests/integration/test_resource_links.py",
        "tests/integration/test_business_analytics.py",
        "tests/integration/test_wave_four_http.py",
        "tests/integration/test_saved_views_favorites.py",
        "tests/integration/test_setup_dependency_readiness.py",
        "tests/integration/test_unified_notifications.py",
        "tests/integration/test_processes.py::test_notifications_are_atomic_owned_retryable_and_idempotent",
        "tests/integration/test_task_corrections.py::test_repeated_correction_rounds_pin_data_feedback_and_reject_stale_writes",
    ),
    "delivery-foundation": (
        "tests/integration/test_migrations.py",
        *FLOW_TESTS,
        "tests/integration/test_live_query_policy.py",
        "tests/integration/test_application_seed.py",
    ),
}


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
    profile = os.getenv("FLOW_TEST_PROFILE", "flow")
    if profile not in PROFILES:
        print("Unknown flow profile; use " + ", ".join(PROFILES), file=sys.stderr)
        return 2
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
        FLOW_TEST_OWNED_DATABASE=name,
    )
    if profile == "delivery-foundation":
        environment["RUN_MIGRATION_INTEGRATION"] = "1"
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
            if profile == "delivery-transfers":
                sys.path.insert(0, str(ROOT))
                from scripts.transfer_services import transfer_services

                resources = transfer_services(environment)
            else:
                resources = nullcontext(environment)
            with resources as test_environment:
                status = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "--tb=short",
                        *([] if profile == "delivery-foundation" else ["--show-capture=no"]),
                        *PROFILES[profile],
                    ],
                    env=test_environment,
                    check=False,
                ).returncode
    except OSError, RuntimeError, subprocess.TimeoutExpired:
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
