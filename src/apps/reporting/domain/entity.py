from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table
from core.i18n import _


class ReportStatus:
    """Stable report lifecycle values persisted in the database."""

    PENDING: ClassVar[str] = "PENDING"
    PROCESSING: ClassVar[str] = "PROCESSING"
    READY: ClassVar[str] = "READY"
    FAILED: ClassVar[str] = "FAILED"
    CANCELLED: ClassVar[str] = "CANCELLED"
    EXPIRED: ClassVar[str] = "EXPIRED"


class ReportEntity(BaseEntity, table=True):
    """One owned asynchronous report request and its generated artifact metadata."""

    __tablename__ = "REPORT"
    __table_args__ = (
        CheckConstraint(
            "\"STATUS\" IN ('PENDING', 'PROCESSING', 'READY', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="ck_report_status",
        ),
        CheckConstraint('"ROW_COUNT" IS NULL OR "ROW_COUNT" >= 0', name="ck_report_row_count"),
        CheckConstraint('"EXPORTED_ROW_COUNT" >= 0', name="ck_report_exported_row_count"),
        CheckConstraint('"MAX_ROWS" > 0', name="ck_report_max_rows"),
        CheckConstraint('"CHUNK_SIZE" > 0', name="ck_report_chunk_size"),
        CheckConstraint('"PARALLELISM" > 0', name="ck_report_parallelism"),
        CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_report_priority"),
        Index("ix_REPORT_OWNER_CREATED_AT", "OWNER_ID", "CREATED_AT"),
        Index("ix_REPORT_OWNER_STATUS", "OWNER_ID", "STATUS"),
    )
    __default_ordering__: ClassVar[tuple[str, ...]] = ("-created_at", "id")

    owner_id: UUID = Field(
        description=_("User that requested and owns the report."),
        sa_column=Column(
            "OWNER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
            comment="USER THAT REQUESTED AND OWNS THE REPORT.",
        ),
    )
    definition_key: str = Field(
        sa_column=Column(
            "DEFINITION_KEY",
            String(100),
            nullable=False,
            index=True,
        ),
    )
    definition_version: int = Field(
        default=1,
        sa_column=Column(
            "DEFINITION_VERSION",
            Integer,
            nullable=False,
        ),
    )
    status: str = Field(
        default=ReportStatus.PENDING,
        sa_column=Column(
            "STATUS",
            String(20),
            nullable=False,
            index=True,
            comment="REPORT LIFECYCLE STATUS.",
        ),
    )
    filters: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(
            "FILTERS",
            JSON,
            nullable=False,
            default=list,
        ),
    )
    sort_orders: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(
            "SORT_ORDERS",
            JSON,
            nullable=False,
            default=list,
        ),
    )
    language: str = Field(
        default="en",
        sa_column=Column(
            "LANGUAGE",
            String(10),
            nullable=False,
        ),
    )
    row_count: int | None = Field(
        default=None,
        sa_column=Column(
            "ROW_COUNT",
            Integer,
            nullable=True,
        ),
    )
    exported_row_count: int = Field(
        default=0,
        sa_column=Column(
            "EXPORTED_ROW_COUNT",
            Integer,
            nullable=False,
            default=0,
        ),
    )
    max_rows: int = Field(
        sa_column=Column(
            "MAX_ROWS",
            Integer,
            nullable=False,
        ),
    )
    chunk_size: int = Field(
        sa_column=Column(
            "CHUNK_SIZE",
            Integer,
            nullable=False,
        ),
    )
    parallelism: int = Field(
        sa_column=Column(
            "PARALLELISM",
            Integer,
            nullable=False,
        ),
    )
    priority: int = Field(
        sa_column=Column(
            "PRIORITY",
            Integer,
            nullable=False,
        ),
    )
    task_id: str = Field(
        sa_column=Column(
            "TASK_ID",
            String(255),
            nullable=False,
            unique=True,
            index=True,
        ),
    )
    storage_key: str | None = Field(
        default=None,
        sa_column=Column(
            "STORAGE_KEY",
            String(1024),
            nullable=True,
            unique=True,
        ),
    )
    file_name: str | None = Field(
        default=None,
        sa_column=Column(
            "FILE_NAME",
            String(255),
            nullable=True,
        ),
    )
    content_type: str | None = Field(
        default=None,
        sa_column=Column(
            "CONTENT_TYPE",
            String(255),
            nullable=True,
        ),
    )
    file_size: int | None = Field(
        default=None,
        sa_column=Column(
            "FILE_SIZE",
            BigInteger,
            nullable=True,
        ),
    )
    checksum_sha256: str | None = Field(
        default=None,
        sa_column=Column(
            "CHECKSUM_SHA256",
            String(64),
            nullable=True,
        ),
    )
    zip_password: str | None = Field(
        default=None,
        sa_column=Column(
            "ZIP_PASSWORD",
            String(255),
            nullable=True,
            comment="PASSWORD FOR THE AES-ENCRYPTED ARCHIVE; REDACTED FROM HISTORY.",
        ),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "STARTED_AT",
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "COMPLETED_AT",
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    expires_at: datetime = Field(
        sa_column=Column(
            "EXPIRES_AT",
            DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
    )
    error_code: str | None = Field(
        default=None,
        sa_column=Column(
            "ERROR_CODE",
            String(255),
            nullable=True,
        ),
    )
    error_message: str | None = Field(
        default=None,
        sa_column=Column(
            "ERROR_MESSAGE",
            Text,
            nullable=True,
        ),
    )
    attempt_count: int = Field(
        default=0,
        sa_column=Column(
            "ATTEMPT_COUNT",
            Integer,
            nullable=False,
            default=0,
        ),
    )
    download_count: int = Field(
        default=0,
        sa_column=Column(
            "DOWNLOAD_COUNT",
            Integer,
            nullable=False,
            default=0,
        ),
    )
    last_downloaded_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "LAST_DOWNLOADED_AT",
            DateTime(timezone=True),
            nullable=True,
        ),
    )


ReportHistoryTable = create_history_table(getattr(ReportEntity, "__table__"))  # noqa: B009
