"""Small invalidation events; persisted inbox DTOs retain all private details."""

from dataclasses import dataclass
from typing import Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO

LIFETIME_SECONDS = 300
HEARTBEAT_SECONDS = 15
RESYNC_SECONDS = 60
MAX_SIGNALS = 256
MAX_SIGNAL_BYTES = 1024
MAX_RECIPIENT_CONNECTIONS = 3
MAX_CONNECTIONS = 200
SEND_TIMEOUT = 5


class InboxChanged(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    notification_ref_id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class InboxResync(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    reason: Literal["connected", "reconnected", "periodic", "event_limit", "lifetime"]


@dataclass(frozen=True)
class InboxLiveEvent:
    """Transport-independent invalidation frame with a typed public data payload."""

    event: str | None = None
    data: InboxChanged | InboxResync | None = None
    id: str | None = None
    retry: int | None = None
    comment: str | None = None
