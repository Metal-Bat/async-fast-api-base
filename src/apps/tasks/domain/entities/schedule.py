from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.i18n import _


class PeriodicTaskEntity(BaseEntity, table=True):
    __tablename__ = "PERIODIC_TASK"

    name: str = Field(
        sa_column=Column(
            "NAME",
            String(255),
            unique=True,
            nullable=False,
            comment="UNIQUE SCHEDULE NAME.",
        ),
        description=_("Unique schedule name."),
    )
    task_name: str = Field(
        sa_column=Column(
            "TASK_NAME",
            String(255),
            nullable=False,
            comment="REGISTERED CELERY TASK NAME.",
        ),
        description=_("Registered Celery task name."),
    )
    queue: str = Field(
        sa_column=Column(
            "QUEUE",
            String(255),
            nullable=False,
            comment="DESTINATION QUEUE.",
        ),
        description=_("Destination queue."),
    )
    schedule_type: str = Field(
        sa_column=Column(
            "SCHEDULE_TYPE",
            String(32),
            nullable=False,
            comment="INTERVAL, CRONTAB, OR CLOCKED.",
        ),
        description=_("Schedule type."),
    )
    interval_seconds: float | None = Field(
        default=None,
        sa_column=Column(
            "INTERVAL_SECONDS",
            Float,
            nullable=True,
            comment="INTERVAL IN SECONDS.",
        ),
        description=_("Interval in seconds."),
    )
    cron_minute: str | None = Field(
        default=None,
        sa_column=Column(
            "CRON_MINUTE",
            String(64),
            nullable=True,
            comment="CRON MINUTE EXPRESSION.",
        ),
    )
    cron_hour: str | None = Field(
        default=None,
        sa_column=Column(
            "CRON_HOUR",
            String(64),
            nullable=True,
            comment="CRON HOUR EXPRESSION.",
        ),
    )
    cron_day_of_week: str | None = Field(
        default=None,
        sa_column=Column(
            "CRON_DAY_OF_WEEK",
            String(64),
            nullable=True,
            comment="CRON WEEKDAY EXPRESSION.",
        ),
    )
    cron_day_of_month: str | None = Field(
        default=None,
        sa_column=Column(
            "CRON_DAY_OF_MONTH",
            String(64),
            nullable=True,
            comment="CRON DAY-OF-MONTH EXPRESSION.",
        ),
    )
    cron_month_of_year: str | None = Field(
        default=None,
        sa_column=Column(
            "CRON_MONTH_OF_YEAR",
            String(64),
            nullable=True,
            comment="CRON MONTH EXPRESSION.",
        ),
    )
    clocked_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "CLOCKED_AT",
            DateTime(timezone=True),
            nullable=True,
            comment="ONE-OFF EXECUTION TIMESTAMP.",
        ),
    )
    args: list[object] = Field(
        default_factory=list,
        sa_column=Column(
            "ARGS",
            JSON,
            nullable=False,
            default=list,
            comment="POSITIONAL TASK ARGUMENTS.",
        ),
    )
    kwargs: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(
            "KWARGS",
            JSON,
            nullable=False,
            default=dict,
            comment="KEYWORD TASK ARGUMENTS.",
        ),
    )
    headers: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(
            "HEADERS",
            JSON,
            nullable=False,
            default=dict,
            comment="AMQP MESSAGE HEADERS.",
        ),
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(
            "ENABLED",
            Boolean,
            nullable=False,
            default=True,
            index=True,
            comment="WHETHER THIS SCHEDULE IS ACTIVE.",
        ),
    )
    one_off: bool = Field(
        default=False,
        sa_column=Column(
            "ONE_OFF",
            Boolean,
            nullable=False,
            default=False,
            comment="DISABLE AFTER ONE EXECUTION.",
        ),
    )
    start_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "START_AT",
            DateTime(timezone=True),
            nullable=True,
            comment="EARLIEST EXECUTION TIMESTAMP.",
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "EXPIRES_AT",
            DateTime(timezone=True),
            nullable=True,
            comment="LATEST EXECUTION TIMESTAMP.",
        ),
    )
    last_run_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "LAST_RUN_AT",
            DateTime(timezone=True),
            nullable=True,
            comment="MOST RECENT DISPATCH TIMESTAMP.",
        ),
    )
    total_run_count: int = Field(
        default=0,
        sa_column=Column(
            "TOTAL_RUN_COUNT",
            Integer,
            nullable=False,
            default=0,
            comment="NUMBER OF DISPATCHES.",
        ),
    )
