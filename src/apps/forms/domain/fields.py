"""Code-owned primitive field definitions shared by validation and discovery."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from core.base_dto import BaseDTO


class ComponentKind(StrEnum):
    ACTION = "action"
    ATTACHMENT_COLLECTION = "attachment_collection"
    BOOLEAN = "boolean"
    CALCULATED = "calculated"
    CHOICE = "choice"
    DATE = "date"
    DATETIME = "datetime"
    DISPLAY = "display"
    GRID = "grid"
    GROUP = "group"
    HORIZONTAL = "horizontal"
    INTEGER = "integer"
    MEDIA = "media"
    NUMBER = "number"
    REPEATER = "repeater"
    TABLE = "table"
    TEXT = "text"
    TEXTAREA = "textarea"
    USER = "user"
    VERTICAL = "vertical"


@dataclass(frozen=True)
class FieldDefinition:
    kind: ComponentKind
    node_kind: Literal["layout", "display", "control", "action"]
    description: str
    data_types: frozenset[str] = frozenset()
    options: frozenset[str] = frozenset()
    children: bool = False


def _control(
    kind: ComponentKind, description: str, types: str, options: str = "", *, children: bool = False
) -> FieldDefinition:
    return FieldDefinition(
        kind,
        "control",
        description,
        frozenset(types.split()),
        frozenset(options.split()) | {"read_only"},
        children,
    )


FIELD_DEFINITIONS = {
    item.kind: item
    for item in (
        FieldDefinition(
            ComponentKind.VERTICAL, "layout", "Arrange child fields vertically.", children=True
        ),
        FieldDefinition(
            ComponentKind.HORIZONTAL, "layout", "Arrange child fields horizontally.", children=True
        ),
        FieldDefinition(
            ComponentKind.GRID,
            "layout",
            "Arrange child fields in a bounded responsive grid.",
            options=frozenset({"columns"}),
            children=True,
        ),
        FieldDefinition(
            ComponentKind.DISPLAY, "display", "Display presentation text without writing data."
        ),
        FieldDefinition(
            ComponentKind.ACTION, "action", "Select a declared canonical form outcome."
        ),
        _control(ComponentKind.TEXT, "Edit one string value.", "string", "placeholder"),
        _control(
            ComponentKind.TEXTAREA, "Edit a multiline string value.", "string", "placeholder rows"
        ),
        _control(ComponentKind.INTEGER, "Edit an integer value.", "integer"),
        _control(ComponentKind.NUMBER, "Edit a JSON numeric value.", "number integer"),
        _control(ComponentKind.BOOLEAN, "Edit a boolean value.", "boolean"),
        _control(
            ComponentKind.CHOICE,
            "Choose canonical keys from a declared option source.",
            "string integer number boolean array",
            "multiple",
        ),
        _control(ComponentKind.DATE, "Edit a canonical Gregorian date.", "string"),
        _control(ComponentKind.DATETIME, "Edit a canonical offset datetime.", "string"),
        _control(ComponentKind.USER, "Choose a user using an opaque reference.", "string"),
        _control(ComponentKind.GROUP, "Choose a work group using an opaque reference.", "string"),
        _control(
            ComponentKind.REPEATER,
            "Edit repeated values using one item schema.",
            "array",
            "min_items max_items",
            children=True,
        ),
        _control(
            ComponentKind.TABLE,
            "Edit a collection in a table presentation.",
            "array",
            "min_items max_items",
            children=True,
        ),
        _control(
            ComponentKind.CALCULATED,
            "Display a value calculated by the registered contract.",
            "string integer number array",
        ),
        _control(ComponentKind.MEDIA, "Select a private uploaded media reference.", "string"),
        _control(
            ComponentKind.ATTACHMENT_COLLECTION,
            "Manage bounded private submission attachments.",
            "array",
            "min_items max_items allowed_kinds allowed_mime_types max_item_bytes max_total_bytes caption_required allow_duplicates preview camera allow_reorder allow_replace allow_remove",
        ),
    )
}


class FieldContract(BaseDTO):
    key: ComponentKind
    version: Literal[1] = 1
    node_kind: Literal["layout", "display", "control", "action"]
    description: str
    data_schema: dict[str, Any]
    options_schema: dict[str, Any]
    defaults: dict[str, Any]
    renderers: list[str] = Field(default_factory=lambda: ["default", "compact"])
    client_kinds: list[str] = Field(
        default_factory=lambda: ["WEB", "DESKTOP", "ANDROID", "IOS", "B2B", "SDK"]
    )
    children: bool
    validation: list[str] = Field(default_factory=lambda: ["server_submit"])
