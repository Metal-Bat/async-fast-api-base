"""Versioned form definitions and generated authoring history."""

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlmodel import Field

from core.base_entity import BaseEntity


class FormDefinitionEntity(BaseEntity, table=True):
    __tablename__ = "FORM_DEFINITION"
    __table_args__ = (
        Index(
            "uq_FORM_DEFINITION_CODE_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_FORM_DEFINITION_owner_created", "OWNER_USER_ID", "CREATED_AT"),
        CheckConstraint(
            'length("CODE") > 0 AND length("NAME") > 0', name="ck_FORM_DEFINITION_names"
        ),
    )
    code: str = Field(
        sa_column=Column(
            "CODE",
            String(64),
            nullable=False,
        ),
    )
    name: str = Field(
        sa_column=Column(
            "NAME",
            String(255),
            nullable=False,
        ),
    )
    owner_user_id: UUID = Field(
        sa_column=Column(
            "OWNER_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ACTIVE",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )
