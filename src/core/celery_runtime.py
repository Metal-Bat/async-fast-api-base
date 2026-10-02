import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_start_lock = threading.Lock()


def run_async[Result](coroutine: Coroutine[Any, Any, Result], *, timeout: float = 30) -> Result:
    """Run worker I/O, cancelling outstanding work when the caller is interrupted."""
    global _loop, _thread
    with _start_lock:
        if _loop is None:
            loop = asyncio.new_event_loop()
            _loop = loop
            _thread = threading.Thread(target=loop.run_forever, name="celery-async-io", daemon=True)
            _thread.start()
    finished = threading.Event()

    async def tracked() -> Result:
        try:
            return await coroutine
        finally:
            finished.set()

    future = asyncio.run_coroutine_threadsafe(tracked(), _loop)
    try:
        return future.result(timeout=timeout)
    except BaseException:
        future.cancel()
        if not finished.wait(timeout=5):
            logger.error("worker.async_cleanup_timeout")
        raise


def close_runtime() -> None:
    """Dispose database connections before stopping the owning event loop."""
    global _loop, _thread
    from core.deps import engine

    loop, thread = _loop, _thread
    if loop is None:
        return
    try:
        run_async(engine.dispose())
        run_async(loop.shutdown_asyncgens())
    finally:
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)
        if thread is None or not thread.is_alive():
            loop.close()
        _loop = None
        _thread = None
        logger.info("worker.resources_closed")
