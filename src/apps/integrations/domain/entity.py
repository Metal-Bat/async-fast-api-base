"""Compatibility exports for the focused domain entity modules."""

from apps.integrations.domain.entities.connection import (
    ConnectionHistoryTable,
    IntegrationConnectionEntity,
)
from apps.integrations.domain.entities.grant import IntegrationConnectionGrantEntity

__all__ = [
    "ConnectionHistoryTable",
    "IntegrationConnectionEntity",
    "IntegrationConnectionGrantEntity",
]
