from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from core.base_dto import BaseDTO
from core.i18n import translate
from utils.pagination import PageRequest

type SelectResponseFormat = Literal["page", "items"]


class SelectQuery(PageRequest):
    """Bound and filter a page of registered select choices."""

    search: str | None = Field(default=None, min_length=1, max_length=100)


class SelectOption[T: str](BaseDTO):
    """Stable submitted key and display value for a select control."""

    key: T
    value: str


def select_options[T: str](
    *values: T, labels: Mapping[T, str] | None = None
) -> list[SelectOption[T]]:
    """Translate registered label messages at request time, preserving submitted keys.

    >>> [option.model_dump() for option in select_options("OPEN", "CLOSED")]
    [{'key': 'OPEN', 'value': 'OPEN'}, {'key': 'CLOSED', 'value': 'CLOSED'}]
    """
    return [
        SelectOption(key=value, value=translate(labels[value]) if bool(labels) else str(value))
        for value in values
    ]
