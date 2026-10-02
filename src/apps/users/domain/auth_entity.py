from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlmodel import Field, SQLModel

from core.base_entity import BaseEntity
from core.history import create_history_table
from core.i18n import _
from utils.date_utils import get_datetime_utc


class AuthSessionEntity(BaseEntity, table=True):
    __tablename__ = "AUTH_SESSION"

    user_id: UUID = Field(
        description=_("User that owns this device session."),
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
            ),
            nullable=False,
            index=True,
            comment="USER THAT OWNS THIS DEVICE SESSION.",
        ),
    )
    client_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "CLIENT_ID",
            Uuid,
            ForeignKey(
                "CLIENT.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            index=True,
        ),
    )
    client_release_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "CLIENT_RELEASE_ID",
            Uuid,
            ForeignKey(
                "CLIENT_RELEASE.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            index=True,
        ),
    )
    family_id: UUID = Field(
        description=_("Refresh-token rotation family identifier."),
        sa_column=Column(
            "FAMILY_ID",
            Uuid,
            nullable=False,
            index=True,
            comment="REFRESH-TOKEN ROTATION FAMILY IDENTIFIER.",
        ),
    )
    refresh_token_hash: str = Field(
        description=_("SHA-256 digest of the opaque refresh token."),
        sa_column=Column(
            "REFRESH_TOKEN_HASH",
            String(64),
            unique=True,
            nullable=False,
            index=True,
            comment="SHA-256 DIGEST OF THE OPAQUE REFRESH TOKEN.",
        ),
    )
    device_name: str | None = Field(
        default=None,
        sa_column=Column(
            "DEVICE_NAME",
            String(255),
        ),
    )
    ip_address: str | None = Field(
        default=None,
        sa_column=Column(
            "IP_ADDRESS",
            String(64),
        ),
    )
    user_agent: str | None = Field(
        default=None,
        sa_column=Column(
            "USER_AGENT",
            String(1024),
        ),
    )
    last_used_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "LAST_USED_AT",
            DateTime(timezone=True),
            nullable=False,
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
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "REVOKED_AT",
            DateTime(timezone=True),
            index=True,
        ),
    )


class PasswordResetTokenEntity(BaseEntity, table=True):
    __tablename__ = "PASSWORD_RESET_TOKEN"

    user_id: UUID = Field(
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
            ),
            nullable=False,
            index=True,
            comment="USER REQUESTING PASSWORD RECOVERY.",
        ),
    )
    token_hash: str = Field(
        sa_column=Column(
            "TOKEN_HASH",
            String(64),
            unique=True,
            nullable=False,
            index=True,
        ),
    )
    expires_at: datetime = Field(
        sa_column=Column(
            "EXPIRES_AT",
            DateTime(timezone=True),
            nullable=False,
            comment="UTC TOKEN EXPIRY.",
        ),
    )
    used_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "USED_AT",
            DateTime(timezone=True),
        ),
    )


class AuthAuditEventEntity(BaseEntity, table=True):
    __tablename__ = "AUTH_AUDIT_EVENT"

    user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
            ),
            index=True,
        ),
    )
    event_type: str = Field(
        sa_column=Column(
            "EVENT_TYPE",
            String(64),
            nullable=False,
            index=True,
        ),
    )
    success: bool = Field(
        default=True,
        sa_column=Column(
            "SUCCESS",
            Boolean,
            nullable=False,
        ),
    )
    request_id: str | None = Field(
        default=None,
        sa_column=Column(
            "REQUEST_ID",
            String(64),
        ),
    )
    ip_address: str | None = Field(
        default=None,
        sa_column=Column(
            "IP_ADDRESS",
            String(64),
        ),
    )
    user_agent: str | None = Field(
        default=None,
        sa_column=Column(
            "USER_AGENT",
            String(1024),
        ),
    )
    details: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(
            "DETAILS",
            JSON,
            nullable=False,
            default=dict,
        ),
    )


class RoleEntity(BaseEntity, table=True):
    __tablename__ = "ROLE"

    name: str = Field(
        sa_column=Column(
            "NAME",
            String(255),
            unique=True,
            nullable=False,
            index=True,
            comment="UNIQUE ROLE NAME.",
        ),
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(
            "DESCRIPTION",
            Text,
        ),
    )


class PermissionEntity(BaseEntity, table=True):
    __tablename__ = "PERMISSION"

    name: str = Field(
        sa_column=Column(
            "NAME",
            String(255),
            unique=True,
            nullable=False,
            index=True,
            comment="UNIQUE PERMISSION NAME.",
        ),
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(
            "DESCRIPTION",
            Text,
        ),
    )


class UserRoleEntity(SQLModel, table=True):
    __tablename__ = "USER_ROLE"

    user_id: UUID = Field(
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
    )
    role_id: UUID = Field(
        sa_column=Column(
            "ROLE_ID",
            Uuid,
            ForeignKey(
                "ROLE.ID",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
    )


class RolePermissionEntity(SQLModel, table=True):
    __tablename__ = "ROLE_PERMISSION"

    role_id: UUID = Field(
        sa_column=Column(
            "ROLE_ID",
            Uuid,
            ForeignKey(
                "ROLE.ID",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
    )
    permission_id: UUID = Field(
        sa_column=Column(
            "PERMISSION_ID",
            Uuid,
            ForeignKey(
                "PERMISSION.ID",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
    )


class LoginFailureEntity(BaseEntity, table=True):
    __tablename__ = "LOGIN_FAILURE"

    identifier: str = Field(
        sa_column=Column(
            "IDENTIFIER",
            String(255),
            unique=True,
            nullable=False,
            index=True,
            comment="NORMALIZED ATTEMPTED LOGIN IDENTIFIER.",
        ),
    )
    failure_count: int = Field(
        default=0,
        sa_column=Column(
            "FAILURE_COUNT",
            Integer,
            nullable=False,
        ),
    )
    locked_until: datetime | None = Field(
        default=None,
        sa_column=Column(
            "LOCKED_UNTIL",
            DateTime(timezone=True),
            index=True,
        ),
    )


RoleHistoryTable = create_history_table(getattr(RoleEntity, "__table__"))  # noqa: B009
PermissionHistoryTable = create_history_table(getattr(PermissionEntity, "__table__"))  # noqa: B009
