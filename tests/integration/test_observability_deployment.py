"""Deployment contract for application and infrastructure telemetry."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parents[2]


def test_collector_scrapes_supported_infrastructure_metrics() -> None:
    config = yaml.safe_load(
        (PROJECT_ROOT / "compose/otel-collector/otel-collector-config.yaml").read_text()
    )

    assert {"postgresql", "redis", "rabbitmq"} <= config["receivers"].keys()
    metric_receivers = config["service"]["pipelines"]["metrics"]["receivers"]
    assert {"otlp", "postgresql", "redis", "rabbitmq"} <= set(metric_receivers)
    assert config["service"]["pipelines"]["traces"]["receivers"] == ["otlp"]


def test_each_traced_process_has_a_distinct_service_identity() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    expected = {
        "backend": "sample-api",
        "worker": "sample-worker",
        "reporting-worker": "sample-reporting-worker",
        "scheduler": "sample-scheduler",
    }
    for service, name in expected.items():
        assert f"OTEL_SERVICE_NAME={name}" in services[service]["environment"]
        assert "otel-collector" in services[service]["depends_on"]
