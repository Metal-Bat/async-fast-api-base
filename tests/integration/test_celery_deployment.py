"""Deployment contract tests for isolated Celery worker queues."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_reporting_worker_is_the_only_worker_consuming_reporting_queue() -> None:
    """Run reports on one dedicated process instead of the general worker pool."""
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert services["worker"]["command"] == "/start-worker"
    assert services["reporting-worker"]["command"] == "/start-reporting-worker"

    default_start = (PROJECT_ROOT / "compose/backend/start-worker").read_text()
    reporting_start = (PROJECT_ROOT / "compose/backend/start-reporting-worker").read_text()

    assert "CELERY_REPORT_QUEUE" not in default_start
    assert (
        '--queues="${CELERY_DEFAULT_QUEUE:-sample.default},${CELERY_AUTOMATION_QUEUE:-bpms.automation}"'
        in default_start
    )
    assert '--queues="${CELERY_REPORT_QUEUE:-reporting}"' in reporting_start
    assert "--concurrency=1" in reporting_start


def test_worker_consumes_durable_bpms_automation_queue() -> None:
    startup = (PROJECT_ROOT / "compose/backend/start-worker").read_text()
    assert "${CELERY_AUTOMATION_QUEUE:-bpms.automation}" in startup


def test_cache_readiness_blocks_application_startup() -> None:
    services = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())["services"]
    cache = services["cache"]
    assert cache["restart"] == "unless-stopped"
    assert "redis-cli ping" in cache["healthcheck"]["test"][1]
    assert "grep -qx PONG" in cache["healthcheck"]["test"][1]
    for name in ("backend", "worker", "reporting-worker", "scheduler"):
        assert services[name]["depends_on"]["cache"]["condition"] == "service_healthy"
