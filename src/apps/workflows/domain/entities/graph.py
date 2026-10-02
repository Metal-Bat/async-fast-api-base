"""Persisted workflow definitions, immutable versions, and graph snapshots."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from core.base_entity import BaseEntity
from utils.date_utils import get_datetime_utc


class WorkflowStepEntity(BaseEntity, table=True):
    __tablename__ = "WORKFLOW_STEP"
    __table_args__ = (
        UniqueConstraint("WORKFLOW_VERSION_ID", "STEP_KEY", name="uq_WORKFLOW_STEP_key"),
        UniqueConstraint("WORKFLOW_VERSION_ID", "ID", name="uq_WORKFLOW_STEP_version_id"),
        Index("ix_WORKFLOW_STEP_version_order", "WORKFLOW_VERSION_ID", "DISPLAY_ORDER"),
        Index("ix_WORKFLOW_STEP_type", "STEP_TYPE_VERSION_ID"),
        Index("ix_WORKFLOW_STEP_form", "FORM_VERSION_ID"),
        CheckConstraint('length("STEP_KEY") > 0', name="ck_WORKFLOW_STEP_key"),
        CheckConstraint(
            '"DEFAULT_PRIORITY" IS NULL OR "DEFAULT_PRIORITY" BETWEEN 0 AND 9',
            name="ck_WORKFLOW_STEP_priority",
        ),
        CheckConstraint(
            '"TIMEOUT_SECONDS" IS NULL OR "TIMEOUT_SECONDS" > 0', name="ck_WORKFLOW_STEP_timeout"
        ),
        CheckConstraint('"DISPLAY_ORDER" >= 0', name="ck_WORKFLOW_STEP_order"),
        CheckConstraint(
            '("FORM_VERSION_ID" IS NULL AND "FIELD_POLICY" IS NULL) OR ("FORM_VERSION_ID" IS NOT NULL AND "FIELD_POLICY" IS NOT NULL)',
            name="ck_WORKFLOW_STEP_form_policy",
        ),
    )

    workflow_version_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_VERSION_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_VERSION.ID",
                ondelete="CASCADE",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    step_type_version_id: UUID = Field(
        sa_column=Column(
            "STEP_TYPE_VERSION_ID",
            Uuid,
            ForeignKey(
                "STEP_TYPE_VERSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    step_key: str = Field(
        sa_column=Column(
            "STEP_KEY",
            String(64),
            nullable=False,
        ),
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "CONFIG",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    flow: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "FLOW",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    form_version_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "FORM_VERSION_ID",
            Uuid,
            ForeignKey(
                "FORM_VERSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    field_policy: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "FIELD_POLICY",
            JSONB(none_as_null=True),
        ),
    )
    task_contract: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "TASK_CONTRACT",
            JSONB(none_as_null=True),
        ),
    )
    subprocess_call: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "SUBPROCESS_CALL",
            JSONB(none_as_null=True),
        ),
    )
    default_priority: int | None = Field(
        default=None,
        sa_column=Column(
            "DEFAULT_PRIORITY",
            Integer,
        ),
    )
    timeout_seconds: int | None = Field(
        default=None,
        sa_column=Column(
            "TIMEOUT_SECONDS",
            Integer,
        ),
    )
    display_order: int = Field(
        default=0,
        sa_column=Column(
            "DISPLAY_ORDER",
            Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )


class WorkflowStepInputBindingEntity(SQLModel, table=True):
    __tablename__ = "WORKFLOW_STEP_INPUT_BINDING"
    __table_args__ = (
        UniqueConstraint(
            "WORKFLOW_STEP_ID",
            "TARGET_PORT_ID",
            "ORDINAL",
            name="uq_WORKFLOW_BINDING_target_ordinal",
        ),
        CheckConstraint(
            "\"SOURCE_KIND\" IN ('REQUEST', 'CONTEXT', 'CONSTANT', 'STEP_OUTPUT')",
            name="ck_WORKFLOW_BINDING_kind",
        ),
        CheckConstraint(
            '("SOURCE_KIND" = \'STEP_OUTPUT\') = ("SOURCE_STEP_ID" IS NOT NULL AND "SOURCE_PORT_ID" IS NOT NULL)',
            name="ck_WORKFLOW_BINDING_step_source",
        ),
        CheckConstraint(
            '("SOURCE_KIND" = \'CONSTANT\') = ("CONSTANT_VALUE" IS NOT NULL)',
            name="ck_WORKFLOW_BINDING_constant",
        ),
        CheckConstraint('"ORDINAL" >= 0', name="ck_WORKFLOW_BINDING_ordinal"),
        CheckConstraint(
            '("SOURCE_KIND" IN (\'REQUEST\', \'CONTEXT\')) = ("SOURCE_PATH" IS NOT NULL AND "SOURCE_STEP_ID" IS NULL AND "SOURCE_PORT_ID" IS NULL AND "CONSTANT_VALUE" IS NULL)',
            name="ck_WORKFLOW_BINDING_request_context",
        ),
        CheckConstraint(
            '"SOURCE_KIND" <> \'CONSTANT\' OR "SOURCE_PATH" IS NULL',
            name="ck_WORKFLOW_BINDING_constant_path",
        ),
        Index("ix_WORKFLOW_BINDING_target_port", "TARGET_PORT_ID"),
        Index("ix_WORKFLOW_BINDING_source_step", "SOURCE_STEP_ID"),
        Index("ix_WORKFLOW_BINDING_source_port", "SOURCE_PORT_ID"),
    )
    id: UUID = Field(
        default=None,
        sa_column=Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "CREATED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    workflow_step_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_STEP_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_STEP.ID",
                ondelete="CASCADE",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    target_port_id: UUID = Field(
        sa_column=Column(
            "TARGET_PORT_ID",
            Uuid,
            ForeignKey(
                "STEP_TYPE_PORT.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    ordinal: int = Field(
        default=0,
        sa_column=Column(
            "ORDINAL",
            Integer,
            nullable=False,
        ),
    )
    source_kind: str = Field(
        sa_column=Column(
            "SOURCE_KIND",
            String(16),
            nullable=False,
        ),
    )
    source_path: str | None = Field(
        default=None,
        sa_column=Column(
            "SOURCE_PATH",
            String(1024),
        ),
    )
    source_step_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "SOURCE_STEP_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_STEP.ID",
                ondelete="CASCADE",
                onupdate="RESTRICT",
            ),
        ),
    )
    source_port_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "SOURCE_PORT_ID",
            Uuid,
            ForeignKey(
                "STEP_TYPE_PORT.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    constant_value: Any | None = Field(
        default=None,
        sa_column=Column(
            "CONSTANT_VALUE",
            JSONB,
        ),
    )


class WorkflowStepTargetEntity(SQLModel, table=True):
    __tablename__ = "WORKFLOW_STEP_TARGET"
    __table_args__ = (
        CheckConstraint(
            '(num_nonnulls("USER_ID", "WORK_GROUP_ID") = 1)', name="ck_WORKFLOW_TARGET_principal"
        ),
        CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_WORKFLOW_TARGET_priority"),
        UniqueConstraint("WORKFLOW_STEP_ID", "USER_ID", name="uq_WORKFLOW_TARGET_user"),
        UniqueConstraint("WORKFLOW_STEP_ID", "WORK_GROUP_ID", name="uq_WORKFLOW_TARGET_group"),
        Index("ix_WORKFLOW_TARGET_user", "USER_ID"),
        Index("ix_WORKFLOW_TARGET_group", "WORK_GROUP_ID"),
    )
    id: UUID = Field(
        default=None,
        sa_column=Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "CREATED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    workflow_step_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_STEP_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_STEP.ID",
                ondelete="CASCADE",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    work_group_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "WORK_GROUP_ID",
            Uuid,
            ForeignKey(
                "WORK_GROUP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    condition: str | None = Field(
        default=None,
        sa_column=Column(
            "CONDITION",
            String(1024),
        ),
    )
    priority: int = Field(
        default=0,
        sa_column=Column(
            "PRIORITY",
            Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )


class WorkflowTransitionEntity(SQLModel, table=True):
    __tablename__ = "WORKFLOW_TRANSITION"
    __table_args__ = (
        ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID", "SOURCE_STEP_ID"],
            ["WORKFLOW_STEP.WORKFLOW_VERSION_ID", "WORKFLOW_STEP.ID"],
            ondelete="CASCADE",
            onupdate="RESTRICT",
            name="fk_WORKFLOW_TRANSITION_source",
        ),
        ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID", "TARGET_STEP_ID"],
            ["WORKFLOW_STEP.WORKFLOW_VERSION_ID", "WORKFLOW_STEP.ID"],
            ondelete="CASCADE",
            onupdate="RESTRICT",
            name="fk_WORKFLOW_TRANSITION_target",
        ),
        UniqueConstraint(
            "SOURCE_STEP_ID", "OUTCOME", "PRIORITY", name="uq_WORKFLOW_TRANSITION_choice"
        ),
        Index(
            "uq_WORKFLOW_TRANSITION_default",
            "SOURCE_STEP_ID",
            "OUTCOME",
            unique=True,
            postgresql_where=text('"IS_DEFAULT"'),
        ),
        CheckConstraint(
            '"SOURCE_STEP_ID" <> "TARGET_STEP_ID"', name="ck_WORKFLOW_TRANSITION_no_self"
        ),
        CheckConstraint('"PRIORITY" >= 0', name="ck_WORKFLOW_TRANSITION_priority"),
        Index("ix_WORKFLOW_TRANSITION_target", "TARGET_STEP_ID"),
        Index(
            "ix_WORKFLOW_TRANSITION_choice",
            "SOURCE_STEP_ID",
            "OUTCOME",
            text('"PRIORITY" DESC'),
            "ID",
        ),
    )
    id: UUID = Field(
        default=None,
        sa_column=Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "CREATED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    workflow_version_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_VERSION_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_VERSION.ID",
                ondelete="CASCADE",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    source_step_id: UUID = Field(
        sa_column=Column(
            "SOURCE_STEP_ID",
            Uuid,
            nullable=False,
        ),
    )
    target_step_id: UUID = Field(
        sa_column=Column(
            "TARGET_STEP_ID",
            Uuid,
            nullable=False,
        ),
    )
    outcome: str = Field(
        sa_column=Column(
            "OUTCOME",
            String(64),
            nullable=False,
        ),
    )
    condition: str | None = Field(
        default=None,
        sa_column=Column(
            "CONDITION",
            String(1024),
        ),
    )
    is_default: bool = Field(
        default=False,
        sa_column=Column(
            "IS_DEFAULT",
            Boolean,
            nullable=False,
            server_default=text("false"),
        ),
    )
    priority: int = Field(
        default=0,
        sa_column=Column(
            "PRIORITY",
            Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )
