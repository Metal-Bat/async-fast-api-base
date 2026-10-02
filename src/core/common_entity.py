from typing import ClassVar

from sqlalchemy import Column, Index, Integer, String, Text, text
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.i18n import _


class SlugEntity(BaseEntity):
    title: str = Field(
        description=_("Human-readable title."),
        sa_column=Column(
            "TITLE",
            String(255),
            nullable=False,
            comment="HUMAN-READABLE TITLE.",
        ),
    )
    slug: str = Field(
        description=_("URL-safe identifier, unique among rows that are not soft-deleted."),
        sa_column=Column(
            "SLUG",
            String(255),
            nullable=False,
            comment="URL-SAFE IDENTIFIER, UNIQUE AMONG ROWS THAT ARE NOT SOFT-DELETED.",
        ),
    )
    description: str | None = Field(
        default=None,
        description=_("Optional long-form description."),
        sa_column=Column(
            "DESCRIPTION",
            Text,
            nullable=True,
            comment="OPTIONAL LONG-FORM DESCRIPTION.",
        ),
    )

    @classmethod
    def active_slug_index(cls, table_name: str) -> Index:
        return Index(
            f"uq_{table_name}_active_slug",
            text('"SLUG"'),
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        )


class OrderEntity(BaseEntity):
    __default_ordering__: ClassVar[tuple[str, ...]] = ("order_id", "id")

    title: str = Field(
        description=_("Human-readable title."),
        sa_column=Column(
            "TITLE",
            String(255),
            nullable=False,
            comment="HUMAN-READABLE TITLE.",
        ),
    )
    description: str | None = Field(
        default=None,
        description=_("Optional long-form description."),
        sa_column=Column(
            "DESCRIPTION",
            Text,
            nullable=True,
            comment="OPTIONAL LONG-FORM DESCRIPTION.",
        ),
    )
    order_id: int = Field(
        description=_("User-controlled position used as the primary default sort key."),
        sa_column=Column(
            "ORDER_ID",
            Integer,
            nullable=False,
            index=True,
            comment="USER-CONTROLLED POSITION USED AS THE PRIMARY DEFAULT SORT KEY.",
        ),
    )
