"""Tests for core observability configuration."""

import logging
from typing import cast
from unittest.mock import Mock

import structlog
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from core import observability


def test_scheduler_exports_application_logs_without_telemetry_diagnostics(monkeypatch) -> None:
    from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor

    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setenv("OTEL_LOGS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "none")
    monkeypatch.setattr(observability.settings, "LOG_OUTPUTS", ["otel"])
    exporter = InMemoryLogRecordExporter()
    monkeypatch.setattr(observability, "OTLPLogExporter", Mock(return_value=exporter))
    monkeypatch.setattr(observability, "BatchLogRecordProcessor", SimpleLogRecordProcessor)
    monkeypatch.setattr(observability, "_instrument_logging", Mock())
    monkeypatch.setattr(observability, "_instrument_clients", Mock())
    monkeypatch.setattr(observability, "SQLAlchemyInstrumentor", Mock())
    monkeypatch.setattr(observability.trace, "set_tracer_provider", Mock())
    monkeypatch.setattr(observability.metrics, "set_meter_provider", Mock())
    monkeypatch.setattr(observability, "set_logger_provider", Mock())
    local_handler = logging.Handler()
    local_handler.emit = Mock()
    root = logging.getLogger()
    json_logger = logging.getLogger("json_logger")
    monkeypatch.setattr(root, "handlers", [local_handler])
    monkeypatch.setattr(json_logger, "handlers", [])
    monkeypatch.setattr(json_logger, "propagate", False)
    providers = observability.configure_scheduler_observability(Mock())
    try:
        for name in (
            "application",
            "json_logger",
            "opentelemetry_application",
            "opentelemetry",
            "opentelemetry.exporter.otlp.proto.grpc.exporter",
            "opentelemetry.exporter.otlp.proto.http._log_exporter",
            "opentelemetry.sdk._shared_internal",
        ):
            logging.getLogger(name).warning("diagnostic from %s", name)

        exported_names = [log.log_record.body for log in exporter.get_finished_logs()]
        assert exported_names == [
            "diagnostic from application",
            "diagnostic from json_logger",
            "diagnostic from opentelemetry_application",
        ]
        assert local_handler.emit.call_count == 6

        json_logger.addHandler(local_handler)
        structured = structlog.wrap_logger(
            json_logger,
            processors=[structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
            wrapper_class=structlog.stdlib.BoundLogger,
        )
        structured.warning("REQUEST", request_id="request-123", method="GET")
        exported = exporter.get_finished_logs()[-1].log_record
        assert exported.attributes is not None
        assert "_logger" not in exported.attributes
        assert "_name" not in exported.attributes
        assert "request-123" in str(exported.body)
        # Other handlers still need these fields for ProcessorFormatter.
        original = local_handler.emit.call_args.args[0]
        assert original._logger is json_logger
        assert original._name == "warning"
    finally:
        providers.shutdown()
        for handler in root.handlers:
            if handler is not local_handler:
                handler.close()


def test_exporters_use_grpc() -> None:
    for exporter_type in (
        observability.OTLPSpanExporter,
        observability.OTLPMetricExporter,
        observability.OTLPLogExporter,
    ):
        assert ".proto.grpc." in exporter_type.__module__


def test_scheduler_uses_one_configured_endpoint_for_all_signals(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    for signal in ("TRACES", "METRICS", "LOGS"):
        monkeypatch.setenv(f"OTEL_{signal}_EXPORTER", "otlp")
    endpoint = "http://collector.test:4317"
    monkeypatch.setattr(observability.settings, "OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
    monkeypatch.setattr(observability.settings, "LOG_OUTPUTS", ["console"])
    for name in (
        "TracerProvider",
        "MeterProvider",
        "LoggerProvider",
        "BatchSpanProcessor",
        "BatchLogRecordProcessor",
        "PeriodicExportingMetricReader",
        "set_logger_provider",
        "_instrument_logging",
        "_instrument_clients",
        "SQLAlchemyInstrumentor",
    ):
        monkeypatch.setattr(observability, name, Mock())
    monkeypatch.setattr(observability.trace, "set_tracer_provider", Mock())
    monkeypatch.setattr(observability.metrics, "set_meter_provider", Mock())
    exporters = [Mock(), Mock(), Mock()]
    for name, exporter in zip(
        ("OTLPSpanExporter", "OTLPMetricExporter", "OTLPLogExporter"), exporters, strict=True
    ):
        monkeypatch.setattr(observability, name, exporter)

    observability.configure_scheduler_observability(Mock())

    for exporter in exporters:
        exporter.assert_called_once_with(endpoint=endpoint, insecure=True)


def test_resource_identifies_service_and_environment() -> None:
    attributes = observability._resource().attributes
    assert attributes["service.name"] == observability.settings.PROJECT_NAME
    assert attributes["service.version"] == observability.settings.VERSION
    assert attributes["deployment.environment.name"] == observability.settings.ENVIRONMENT


def test_resource_accepts_a_process_specific_service_name(monkeypatch) -> None:
    monkeypatch.setenv("HOSTNAME", "scheduler-1")

    attributes = observability._resource("sample-scheduler").attributes

    assert attributes["service.name"] == "sample-scheduler"
    assert attributes["service.instance.id"] == "scheduler-1"


def test_disabled_sdk_does_not_create_exporters(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    span_exporter = Mock()
    metric_exporter = Mock()
    log_exporter = Mock()
    monkeypatch.setattr(observability, "OTLPSpanExporter", span_exporter)
    monkeypatch.setattr(observability, "OTLPMetricExporter", metric_exporter)
    monkeypatch.setattr(observability, "OTLPLogExporter", log_exporter)

    providers = observability._providers()

    span_exporter.assert_not_called()
    metric_exporter.assert_not_called()
    log_exporter.assert_not_called()
    providers.shutdown()


def test_none_exporter_configuration_does_not_create_exporters(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "none")
    monkeypatch.setenv("OTEL_LOGS_EXPORTER", "none")
    span_exporter = Mock()
    metric_exporter = Mock()
    log_exporter = Mock()
    monkeypatch.setattr(observability, "OTLPSpanExporter", span_exporter)
    monkeypatch.setattr(observability, "OTLPMetricExporter", metric_exporter)
    monkeypatch.setattr(observability, "OTLPLogExporter", log_exporter)

    providers = observability._providers()

    span_exporter.assert_not_called()
    metric_exporter.assert_not_called()
    log_exporter.assert_not_called()
    providers.shutdown()


def test_telemetry_provider_shutdown_closes_every_signal() -> None:
    tracer = Mock()
    meter = Mock()
    logger = Mock()
    providers = observability.TelemetryProviders(
        cast(TracerProvider, tracer),
        cast(MeterProvider, meter),
        cast(LoggerProvider, logger),
    )

    providers.shutdown()

    logger.shutdown.assert_called_once_with()
    meter.shutdown.assert_called_once_with()
    tracer.shutdown.assert_called_once_with()


def test_scheduler_instruments_database_cache_and_s3(monkeypatch) -> None:
    providers = Mock()
    providers.tracer = Mock()
    providers.meter = Mock()
    monkeypatch.setattr(observability, "_providers", Mock(return_value=providers))
    database = Mock()
    redis = Mock()
    botocore = Mock()
    monkeypatch.setattr(observability, "SQLAlchemyInstrumentor", Mock(return_value=database))
    monkeypatch.setattr(observability, "RedisInstrumentor", Mock(return_value=redis), raising=False)
    monkeypatch.setattr(
        observability, "BotocoreInstrumentor", Mock(return_value=botocore), raising=False
    )
    engine = Mock()

    result = observability.configure_scheduler_observability(engine)

    assert result is providers
    database.instrument.assert_called_once()
    redis.instrument.assert_called_once_with(tracer_provider=providers.tracer)
    botocore.instrument.assert_called_once_with(tracer_provider=providers.tracer)


def test_logging_instrumentation_is_enabled(monkeypatch) -> None:
    instrumentor = Mock()
    monkeypatch.setattr(observability, "LoggingInstrumentor", Mock(return_value=instrumentor))

    observability._instrument_logging()
    instrumentor.instrument.assert_called_once_with(
        set_logging_format=False,
        inject_trace_context=True,
        enable_log_auto_instrumentation=False,
    )


def test_authenticated_user_is_added_to_active_trace_and_log_context(monkeypatch) -> None:
    from uuid import uuid7

    from structlog.contextvars import clear_contextvars, get_contextvars

    user_id = uuid7()
    span = Mock()
    monkeypatch.setattr(observability.trace, "get_current_span", Mock(return_value=span))
    try:
        observability.annotate_authenticated_user(user_id, "ada")

        assert get_contextvars()["username"] == "ada"
        span.set_attribute.assert_any_call("enduser.id", str(user_id))
        span.set_attribute.assert_any_call("app.user.id", str(user_id))
        span.set_attribute.assert_any_call("app.user.username", "ada")
    finally:
        clear_contextvars()


def test_application_lifespan_does_not_install_http_exporters(monkeypatch) -> None:
    from contextlib import asynccontextmanager

    from fastapi.testclient import TestClient
    from opentelemetry.exporter.otlp.proto.http import (
        _log_exporter,
        metric_exporter,
        trace_exporter,
    )

    from main import app

    @asynccontextmanager
    async def without_infrastructure(_app):
        yield

    monkeypatch.setattr(app.router, "lifespan_context", without_infrastructure)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.test:4317")
    exporters = []
    for module, name, signal in (
        (trace_exporter, "OTLPSpanExporter", "TRACES"),
        (metric_exporter, "OTLPMetricExporter", "METRICS"),
        (_log_exporter, "OTLPLogExporter", "LOGS"),
    ):
        monkeypatch.setenv(f"OTEL_{signal}_EXPORTER", "otlp")
        exporter = Mock(side_effect=AssertionError("Unexpected HTTP exporter"))
        monkeypatch.setattr(module, name, exporter)
        exporters.append(exporter)
    with TestClient(app):
        pass
    for exporter in exporters:
        exporter.assert_not_called()
