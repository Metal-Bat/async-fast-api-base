"""Tests for the synchronous-to-asynchronous Celery runtime bridge."""

import asyncio
import threading
from unittest.mock import AsyncMock, Mock

import pytest

import core.celery_runtime as runtime
from core import deps


def test_timeout_waits_for_coroutine_cleanup_and_loop_remains_usable(monkeypatch) -> None:
    cleaned = threading.Event()
    engine = Mock(dispose=AsyncMock())
    monkeypatch.setattr(deps, "engine", engine)

    async def blocked():
        try:
            await asyncio.sleep(60)
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    async def next_call():
        return "ready"

    try:
        with pytest.raises(TimeoutError):
            runtime.run_async(blocked(), timeout=0.05)
        assert cleaned.is_set()
        assert runtime.run_async(next_call()) == "ready"
    finally:
        runtime.close_runtime()
    engine.dispose.assert_awaited_once()
    assert runtime._loop is None and runtime._thread is None


def test_close_stops_loop_even_when_connection_disposal_fails(monkeypatch) -> None:
    monkeypatch.setattr(deps, "engine", Mock(dispose=AsyncMock(side_effect=ConnectionError())))
    runtime.run_async(asyncio.sleep(0))
    with pytest.raises(ConnectionError):
        runtime.close_runtime()
    assert runtime._loop is None and runtime._thread is None
