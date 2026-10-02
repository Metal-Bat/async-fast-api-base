from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, DateTime, String, Uuid
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.i18n import _


class SchedulerLeaseEntity(BaseEntity, table=True):
    __tablename__ = "SCHEDULER_LEASE"

    name: str = Field(
        description=_("Unique scheduler lease name."),
        sa_column=Column(
            "NAME",
            String(255),
            unique=True,
            nullable=False,
            index=True,
            comment="UNIQUE SCHEDULER LEASE NAME.",
        ),
    )
    owner_id: UUID = Field(
        description=_("UUIDv7 of the scheduler process holding the lease."),
        sa_column=Column(
            "OWNER_ID",
            Uuid,
            nullable=False,
            index=True,
            comment="UUIDV7 OF THE SCHEDULER PROCESS HOLDING THE LEASE.",
        ),
    )
    expires_at: datetime = Field(
        description=_("UTC deadline after which another scheduler may claim the lease."),
        sa_column=Column(
            "EXPIRES_AT",
            DateTime(timezone=True),
            nullable=False,
            index=True,
            comment="UTC DEADLINE AFTER WHICH ANOTHER SCHEDULER MAY CLAIM THE LEASE.",
        ),
    )
