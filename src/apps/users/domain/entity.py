from pydantic import EmailStr
from sqlalchemy import Boolean, Column, String
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table
from core.i18n import _


class UserEntity(BaseEntity, table=True):
    __tablename__ = "USER"

    username: str = Field(
        description=_("Unique username used to identify the user."),
        sa_column=Column(
            "USERNAME",
            String(255),
            nullable=False,
            unique=True,
            index=True,
            comment="UNIQUE USERNAME USED TO IDENTIFY THE USER.",
        ),
    )
    email: EmailStr | None = Field(
        default=None,
        description=_("Unique email address for the user."),
        sa_column=Column(
            "EMAIL",
            String(255),
            nullable=True,
            unique=True,
            comment="UNIQUE EMAIL ADDRESS FOR THE USER.",
        ),
    )
    is_superuser: bool = Field(
        default=False,
        description=_("Whether the user has administrative privileges."),
        sa_column=Column(
            "IS_SUPERUSER",
            Boolean,
            nullable=False,
            default=False,
            comment="WHETHER THE USER HAS ADMINISTRATIVE PRIVILEGES.",
        ),
    )
    first_name: str | None = Field(
        default=None,
        description=_("User's given name."),
        sa_column=Column(
            "FIRST_NAME",
            String(255),
            nullable=True,
            comment="USER'S GIVEN NAME.",
        ),
    )
    last_name: str | None = Field(
        default=None,
        description=_("User's family name."),
        sa_column=Column(
            "LAST_NAME",
            String(255),
            nullable=True,
            comment="USER'S FAMILY NAME.",
        ),
    )
    hashed_password: str = Field(
        description=_("One-way password hash; a plaintext password is never stored."),
        sa_column=Column(
            "HASHED_PASSWORD",
            String,
            nullable=False,
            comment="ONE-WAY PASSWORD HASH; A PLAINTEXT PASSWORD IS NEVER STORED.",
        ),
    )


UserHistoryTable = create_history_table(getattr(UserEntity, "__table__"))  # noqa: B009
