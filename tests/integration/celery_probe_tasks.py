"""Celery tasks used only by worker integration tests."""

import signal
from time import sleep
from typing import cast

from celery.exceptions import SoftTimeLimitExceeded
from redis import Redis

from core.settings import settings
from core.task_registry import TaskPolicy, register_task


@register_task("probe.count", bind=True)
def count(self, key: str, fail_first: bool = False) -> int:
    """Retry once if requested, then record a visible side effect."""
    if fail_first and self.request.retries == 0:
        raise ConnectionError("transient probe failure")
    with Redis.from_url(str(settings.CACHE_DSN)) as cache:
        return cast(int, cache.incr(key))


@register_task("probe.soft", policy=TaskPolicy(soft_time_limit=1, time_limit=3))
def soft_timeout() -> None:
    """Let Celery interrupt the body with its actual soft-limit signal."""
    sleep(10)


@register_task("probe.hard", policy=TaskPolicy(soft_time_limit=1, time_limit=3))
def hard_timeout() -> None:
    """Ignore soft timeout and SIGTERM so Celery must use an uncatchable SIGKILL."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    try:
        sleep(10)
    except SoftTimeLimitExceeded:
        sleep(10)


@register_task("probe.drain")
def drain(key: str) -> int:
    """Expose a started marker, then finish during Celery's warm shutdown."""
    with Redis.from_url(str(settings.CACHE_DSN)) as cache:
        cache.set(f"{key}:started", "1", ex=60)
        sleep(2)
        return cast(int, cache.incr(key))
