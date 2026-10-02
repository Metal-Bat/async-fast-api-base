import logging
import os
from copy import copy
from dataclasses import dataclass
from typing import override
from uuid import UUID

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import AsyncEngine
from structlog.contextvars import bind_contextvars

from core.settings import settings


class _TelemetryLogFilter(logging.Filter):
    """Exclude exporter diagnostics and strip formatter metadata from an isolated record."""

    @override
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        if record.name == "opentelemetry" or record.name.startswith("opentelemetry."):
            return False
        # ProcessorFormatter needs these on console/file records. Only the OTLP
        # handler receives the copy, so its attributes contain no Logger objects.
        exported = copy(record)
        exported.__dict__.pop("_logger", None)
        exported.__dict__.pop("_name", None)
        return exported


@dataclass(frozen=True, slots=True)
class TelemetryProviders:
    """Providers that share one resource identity."""

    tracer: TracerProvider
    meter: MeterProvider
    logger: LoggerProvider

    def shutdown(self) -> None:
        """Flush and stop signal processors owned by this process."""
        self.logger.shutdown()
        self.meter.shutdown()
        self.tracer.shutdown()


def _resource(service_name: str | None = None) -> Resource:
    """Describe the service consistently across every telemetry signal."""
    return Resource.create(
        {
            "service.name": service_name or os.getenv("OTEL_SERVICE_NAME") or settings.PROJECT_NAME,
            "service.instance.id": os.getenv("HOSTNAME", "local"),
            "service.version": settings.VERSION,
            "deployment.environment.name": settings.ENVIRONMENT,
        }
    )


def _providers() -> TelemetryProviders:
    """Create and globally register OTLP trace, metric, and log providers."""
    resource = _resource()
    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    sdk_disabled = os.getenv("OTEL_SDK_DISABLED", "").strip().lower() == "true"
    traces_enabled = (
        not sdk_disabled and os.getenv("OTEL_TRACES_EXPORTER", "otlp").strip().lower() != "none"
    )
    metrics_enabled = (
        not sdk_disabled and os.getenv("OTEL_METRICS_EXPORTER", "otlp").strip().lower() != "none"
    )
    logs_enabled = (
        not sdk_disabled and os.getenv("OTEL_LOGS_EXPORTER", "otlp").strip().lower() != "none"
    )

    tracer_provider = TracerProvider(resource=resource)
    if traces_enabled:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )
    trace.set_tracer_provider(tracer_provider)

    metric_readers = []
    if metrics_enabled:
        metric_readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=endpoint, insecure=True),
                export_interval_millis=settings.OTEL_METRIC_EXPORT_INTERVAL_MILLIS,
            )
        )
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    if logs_enabled:
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
        )
    set_logger_provider(logger_provider)
    if logs_enabled and "otel" in settings.LOG_OUTPUTS:
        otel_handler = LoggingHandler(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            logger_provider=logger_provider,
        )
        # Filter only this handler so console/file diagnostics remain available.
        otel_handler.addFilter(_TelemetryLogFilter())
        logging.getLogger().addHandler(otel_handler)
        logging.getLogger("json_logger").addHandler(otel_handler)
    if traces_enabled or logs_enabled:
        _instrument_logging()
    return TelemetryProviders(tracer_provider, meter_provider, logger_provider)


def _instrument_logging() -> None:
    """Bridge standard-library and structlog records into OpenTelemetry."""
    LoggingInstrumentor().instrument(
        set_logging_format=False,
        inject_trace_context=True,
        enable_log_auto_instrumentation=False,
    )


def _instrument_clients(providers: TelemetryProviders) -> None:
    """Trace calls to Dragonfly/Redis and S3 through their Python clients."""
    RedisInstrumentor().instrument(tracer_provider=providers.tracer)
    BotocoreInstrumentor().instrument(tracer_provider=providers.tracer)


def annotate_authenticated_user(user_id: UUID, username: str) -> None:
    """Make the authenticated actor searchable in logs and the active request trace."""
    user_id_text = str(user_id)
    bind_contextvars(username=username, user_id=user_id_text)
    span = trace.get_current_span()
    span.set_attribute("enduser.id", user_id_text)
    span.set_attribute("app.user.id", user_id_text)
    span.set_attribute("app.user.username", username)


def configure_observability(app: FastAPI, engine: AsyncEngine) -> TelemetryProviders:
    """Instrument the API, database, and logging with all telemetry signals."""
    providers = _providers()
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=providers.tracer,
        meter_provider=providers.meter,
    )
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=providers.tracer,
        meter_provider=providers.meter,
    )
    _instrument_clients(providers)
    return providers


def configure_worker_observability(engine: AsyncEngine) -> TelemetryProviders:
    """Instrument Celery, database calls, and logs inside each worker process."""
    providers = _providers()
    CeleryInstrumentor().instrument(
        tracer_provider=providers.tracer,
        meter_provider=providers.meter,
    )
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=providers.tracer,
        meter_provider=providers.meter,
    )
    _instrument_clients(providers)
    return providers


def configure_scheduler_observability(engine: AsyncEngine) -> TelemetryProviders:
    """Trace beat ticks, outbox publication, database work, cache, and S3 calls."""
    providers = _providers()
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=providers.tracer,
        meter_provider=providers.meter,
    )
    _instrument_clients(providers)
    return providers
