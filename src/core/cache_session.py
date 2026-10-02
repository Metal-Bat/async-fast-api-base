"""Invalidate cached read models after successful ORM transactions."""

from itertools import chain
from typing import cast, override

import structlog
from sqlalchemy import event
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm.session import ORMExecuteState
from sqlmodel import Session as SQLModelSession
from sqlmodel.ext.asyncio.session import AsyncSession

from core.base_entity import BaseEntity
from core.cache_repository import BaseCacheRepository

logger = structlog.get_logger(__name__)
_CACHED_MODELS: dict[type[BaseEntity], str] = {}
_PENDING_KEY = "read_cache_pending_namespaces"


def register_cached_model(model: type[BaseEntity], namespace: str) -> None:
    """Register one ORM model whose committed changes invalidate a namespace."""
    _CACHED_MODELS[model] = namespace


def _pending_namespaces(session: SQLAlchemySession) -> set[object]:
    pending = session.info.setdefault(_PENDING_KEY, set())
    return _require_pending_set(pending)


def _require_pending_set(value: object) -> set[object]:
    if not isinstance(value, set):
        raise TypeError("Cache pending namespace state must be a set")
    return cast(set[object], value)


class CacheTrackingSession(SQLModelSession):
    """Record cache namespaces touched by ORM flushes."""


@event.listens_for(CacheTrackingSession, "after_flush")
def _mark_changed_models(session: SQLAlchemySession, _flush_context: object) -> None:
    pending = _pending_namespaces(session)
    for entity in chain(session.new, session.dirty, session.deleted):
        for model, namespace in _CACHED_MODELS.items():
            if isinstance(entity, model):
                pending.add(namespace)


@event.listens_for(CacheTrackingSession, "do_orm_execute")
def _mark_bulk_changes(state: ORMExecuteState) -> None:
    if not (state.is_update or state.is_delete) or state.bind_mapper is None:
        return
    namespace = _CACHED_MODELS.get(state.bind_mapper.class_)
    if namespace is not None:
        _pending_namespaces(state.session).add(namespace)


class CacheInvalidatingSession(AsyncSession):
    """Invalidate committed model caches before returning from commit."""

    sync_session_class = CacheTrackingSession

    @override
    async def commit(self) -> None:
        await super().commit()
        pending_value = self.sync_session.info.pop(_PENDING_KEY, set())
        pending_value = _require_pending_set(pending_value)
        pending = {value for value in pending_value if isinstance(value, str)}
        for namespace in pending:
            if not await BaseCacheRepository(namespace).invalidate():
                await logger.awarning("read_cache.invalidation_failed", namespace=namespace)

    @override
    async def rollback(self) -> None:
        await super().rollback()
        self.sync_session.info.pop(_PENDING_KEY, None)
