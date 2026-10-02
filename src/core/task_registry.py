from collections.abc import Callable
from dataclasses import dataclass
from inspect import signature
from typing import Any

from celery import Task

from core.celery_app import celery_app
from core.settings import settings


@dataclass(frozen=True, slots=True)
class TaskPolicy:
    """Reusable execution policy applied by :func:`register_task`."""

    queue: str = settings.CELERY_DEFAULT_QUEUE
    retry_for: tuple[type[Exception], ...] = (ConnectionError, TimeoutError)
    max_retries: int = 5
    retry_backoff: bool = True
    retry_jitter: bool = True
    soft_time_limit: int = settings.CELERY_TASK_SOFT_TIME_LIMIT
    time_limit: int = settings.CELERY_TASK_TIME_LIMIT

    def __post_init__(self) -> None:
        """Keep task overrides bounded with time available for soft-limit cleanup."""
        if not 0 < self.soft_time_limit < self.time_limit:
            raise ValueError("Task limits must satisfy 0 < soft_time_limit < time_limit")


DEFAULT_TASK_POLICY = TaskPolicy()


@dataclass(frozen=True, slots=True)
class TaskRegistration:
    """Inspectable metadata for one explicitly registered application task."""

    name: str
    module: str
    callable_name: str
    signature: str
    description: str | None
    bind: bool
    policy: TaskPolicy


_TASK_REGISTRATIONS: dict[str, TaskRegistration] = {}


def registered_tasks() -> dict[str, TaskRegistration]:
    """Return the application task catalog without Celery's internal tasks."""
    return _TASK_REGISTRATIONS.copy()


def register_task(
    name: str,
    *,
    policy: TaskPolicy = DEFAULT_TASK_POLICY,
    bind: bool = False,
) -> Callable[[Callable[..., Any]], Task]:
    """Register a task with the project's queue, retries, limits, and idempotency.

    Example:
        @register_task("billing.issue_invoice")
        def issue_invoice(invoice_id: str) -> dict[str, str]:
            return {"invoice_id": invoice_id}
    """

    def decorator(function: Callable[..., Any]) -> Task:
        registered = celery_app.task(
            name=name,
            queue=policy.queue,
            bind=bind,
            autoretry_for=policy.retry_for,
            retry_backoff=policy.retry_backoff,
            retry_jitter=policy.retry_jitter,
            retry_kwargs={"max_retries": policy.max_retries},
            soft_time_limit=policy.soft_time_limit,
            time_limit=policy.time_limit,
        )(function)
        if not isinstance(registered, Task):
            raise TypeError("Celery returned an invalid registered task")
        _TASK_REGISTRATIONS[name] = TaskRegistration(
            name=name,
            module=function.__module__,
            callable_name=getattr(function, "__qualname__", type(function).__qualname__),
            signature=str(signature(function)),
            description=function.__doc__,
            bind=bind,
            policy=policy,
        )
        return registered

    return decorator
