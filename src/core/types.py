from collections.abc import Callable
from typing import Any, Literal, TypeVar

from pydantic import BaseModel
from sqlalchemy.sql.elements import ColumnElement

DTOType = TypeVar("DTOType", bound=BaseModel)

OperatorFunc = Callable[[ColumnElement[Any], Any], ColumnElement[bool]]

PlatformTypes = Literal[
    "ANDROID",
    "IOS",
    "PWA",
    None,
]


LanguagesTypes = Literal[
    "ENGLISH",
    "PERSIAN",
    None,
]
