from typing import Any, override

from celery import Celery, Task, signals
from kombu import Exchange, Queue
from sqlalchemy.exc import SQLAlchemyError

from apps.step_types.application.registry import get_registry
from core.celery_runtime import close_runtime
from core.deps import engine
from core.observability import configure_scheduler_observability, configure_worker_observability
from core.settings import settings
from core.task_lifecycle import TaskAlreadyRunning, task_lifecycle
from utils.logging_config import setup_logging

get_registry()  # Fail worker import when a deployed step extension is broken.

celery_app = Celery(settings.CELERY_APP_NAME, broker=settings.CELERY_BROKER_URL)
default_exchange = Exchange(settings.CELERY_DEFAULT_QUEUE, type="direct", durable=True)
dead_letter_exchange = Exchange(
    f"{settings.CELERY_DEFAULT_QUEUE}.dead", type="direct", durable=True
)
automation_exchange = Exchange(settings.CELERY_AUTOMATION_QUEUE, type="direct", durable=True)
automation_dead_letter_exchange = Exchange(
    f"{settings.CELERY_AUTOMATION_QUEUE}.dead", type="direct", durable=True
)
report_exchange = Exchange(settings.CELERY_REPORT_QUEUE, type="direct", durable=True)
report_dead_letter_exchange = Exchange(
    f"{settings.CELERY_REPORT_QUEUE}.dead", type="direct", durable=True
)
celery_app.conf.update(
    result_backend=settings.CELERY_RESULT_BACKEND or str(settings.CACHE_DSN),
    redis_socket_connect_timeout=5,
    redis_socket_timeout=5,
    result_backend_transport_options={"retry_policy": {"max_retries": 3, "interval_max": 2}},
    task_default_queue=settings.CELERY_DEFAULT_QUEUE,
    task_default_exchange=settings.CELERY_DEFAULT_QUEUE,
    task_default_routing_key=settings.CELERY_DEFAULT_QUEUE,
    task_queues=(
        Queue(
            settings.CELERY_DEFAULT_QUEUE,
            exchange=default_exchange,
            routing_key=settings.CELERY_DEFAULT_QUEUE,
            queue_arguments={
                "x-dead-letter-exchange": f"{settings.CELERY_DEFAULT_QUEUE}.dead",
                "x-dead-letter-routing-key": f"{settings.CELERY_DEFAULT_QUEUE}.dead",
            },
        ),
        Queue(
            f"{settings.CELERY_DEFAULT_QUEUE}.dead",
            exchange=dead_letter_exchange,
            routing_key=f"{settings.CELERY_DEFAULT_QUEUE}.dead",
        ),
        Queue(
            settings.CELERY_AUTOMATION_QUEUE,
            exchange=automation_exchange,
            routing_key=settings.CELERY_AUTOMATION_QUEUE,
            queue_arguments={
                "x-max-priority": settings.CELERY_MAX_PRIORITY,
                "x-dead-letter-exchange": f"{settings.CELERY_AUTOMATION_QUEUE}.dead",
                "x-dead-letter-routing-key": f"{settings.CELERY_AUTOMATION_QUEUE}.dead",
            },
        ),
        Queue(
            f"{settings.CELERY_AUTOMATION_QUEUE}.dead",
            exchange=automation_dead_letter_exchange,
            routing_key=f"{settings.CELERY_AUTOMATION_QUEUE}.dead",
        ),
        Queue(
            settings.CELERY_REPORT_QUEUE,
            exchange=report_exchange,
            routing_key=settings.CELERY_REPORT_QUEUE,
            queue_arguments={
                "x-max-priority": settings.CELERY_MAX_PRIORITY,
                "x-dead-letter-exchange": f"{settings.CELERY_REPORT_QUEUE}.dead",
                "x-dead-letter-routing-key": f"{settings.CELERY_REPORT_QUEUE}.dead",
            },
        ),
        Queue(
            f"{settings.CELERY_REPORT_QUEUE}.dead",
            exchange=report_dead_letter_exchange,
            routing_key=f"{settings.CELERY_REPORT_QUEUE}.dead",
        ),
    ),
    task_serializer="json",
    result_serializer="json",
    accept_content=("json",),
    result_extended=True,
    task_track_started=True,
    task_send_sent_event=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    worker_send_task_events=True,
    control_queue_exclusive=True,
    event_queue_exclusive=True,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    worker_max_memory_per_child=settings.CELERY_WORKER_MAX_MEMORY_PER_CHILD,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    worker_soft_shutdown_timeout=30.0,
    worker_enable_soft_shutdown_on_idle=True,
    broker_transport_options={"confirm_publish": True},
    broker_connection_timeout=5,
    task_acks_on_failure_or_timeout=True,
    timezone="UTC",
    enable_utc=True,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    result_expires=settings.CELERY_RESULT_RETENTION_DAYS * 86_400,
    task_routes={
        "system.*": {"queue": settings.CELERY_DEFAULT_QUEUE},
        "bpms.*": {"queue": settings.CELERY_AUTOMATION_QUEUE},
        "reporting.*": {"queue": settings.CELERY_REPORT_QUEUE},
    },
)
celery_app.conf.include = ("apps.tasks.tasks", "apps.reporting.tasks")


class IdempotentTask(Task):
    """Run each attempt inside the managed lifecycle, preserving Celery's retry request."""

    abstract = True
    autoretry_for = (ConnectionError, TimeoutError)
    max_retries = 5
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    @override
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if not self.request.id:
            return super().__call__(*args, **kwargs)
        try:
            with task_lifecycle(self, args, kwargs) as lifecycle:
                if not lifecycle.duplicate:
                    lifecycle.result = self.run(*args, **kwargs)
                return lifecycle.result
        except TaskAlreadyRunning as exc:
            raise self.retry(exc=exc, countdown=exc.retry_after, max_retries=100)
        except (SQLAlchemyError, ConnectionError, TimeoutError) as exc:
            raise self.retry(exc=exc, countdown=min(600, 2 ** min(self.request.retries + 1, 9)))


celery_app.Task = IdempotentTask


@signals.setup_logging.connect  # ty: ignore[dynamic-function-decorator-return]
def configure_celery_logging(loglevel: int | str | None = None, **_: Any) -> None:
    """Apply the same structured logging destinations in worker and scheduler processes."""
    engine.echo = False
    setup_logging(log_level=loglevel)


@signals.worker_process_init.connect  # ty: ignore[dynamic-function-decorator-return]
def instrument_worker(**_: Any) -> None:
    """Discard inherited database connections before instrumenting a prefork child."""
    engine.sync_engine.dispose(close=False)
    configure_worker_observability(engine)


@signals.beat_init.connect  # ty: ignore[dynamic-function-decorator-return]
def instrument_scheduler(**_: Any) -> None:
    """Initialize tracing in the scheduler process before it publishes tasks."""
    configure_scheduler_observability(engine)


@signals.worker_process_shutdown.connect  # ty: ignore[dynamic-function-decorator-return]
def shutdown_worker(**_: Any) -> None:
    """Close the process-local I/O loop and its database connections."""
    close_runtime()
