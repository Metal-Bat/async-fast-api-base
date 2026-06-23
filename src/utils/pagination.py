import enum
import types
from datetime import date, datetime
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from pydantic import BaseModel, Field, create_model
from pydantic import EmailStr
from sqlalchemy import Select

from core.types import OperatorFunc

OPERATORS: dict[str, OperatorFunc] = {
    "eq": lambda c, v: c == v,
    "neq": lambda c, v: c != v,
    "lt": lambda c, v: c < v,
    "lte": lambda c, v: c <= v,
    "gt": lambda c, v: c > v,
    "gte": lambda c, v: c >= v,
    "in": lambda c, v: c.in_(v if isinstance(v, list) else [v]),
}

# Extend this dict at module level to support additional types (e.g. custom annotated types).
TYPE_OPERATORS: dict[type, list[str]] = {
    int: ["eq", "neq", "lt", "lte", "gt", "gte", "in"],
    float: ["eq", "neq", "lt", "lte", "gt", "gte", "in"],
    datetime: ["eq", "neq", "lt", "lte", "gt", "gte"],
    date: ["eq", "neq", "lt", "lte", "gt", "gte"],
    str: ["eq", "neq", "in"],
    EmailStr: ["eq", "neq", "in"],
    UUID: ["eq", "neq", "in"],
    bool: ["eq"],
}

DEFAULT_OPERATORS: list[str] = ["eq"]


class FilterItem(BaseModel):
    field: str
    operator: str
    value: Any


def _unwrap_type(field_type: Any) -> type:
    """Recursively unwrap Annotated and Optional/Union to get the base type."""
    if get_origin(field_type) is Annotated:
        field_type = get_args(field_type)[0]

    origin = get_origin(field_type)
    is_union = origin is Union or (
        hasattr(types, "UnionType") and isinstance(field_type, types.UnionType)
    )
    if is_union:
        non_none = [a for a in get_args(field_type) if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap_type(non_none[0])

    return field_type


def auto_query_model(
    dto: type[BaseModel],
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
):
    include = include or set(dto.model_fields.keys())
    exclude = exclude or set()

    annotations = get_type_hints(dto, include_extras=True)

    # Map field_name -> allowed operators for runtime validation in apply_query.
    valid_fields: dict[str, list[str]] = {}
    for field_name, field_type in annotations.items():
        if field_name not in include or field_name in exclude:
            continue
        base_type = _unwrap_type(field_type)
        valid_fields[field_name] = TYPE_OPERATORS.get(base_type, DEFAULT_OPERATORS)

    ordering_values = {k: k for k in dto.model_fields.keys()} | {
        f"-{k}": f"-{k}" for k in dto.model_fields.keys()
    }
    OrderingEnum = enum.Enum(f"{dto.__name__}Ordering", ordering_values)

    fields: dict[str, tuple[type, Any]] = {
        "filters": (list[FilterItem], Field(default_factory=list)),
        "page": (int, Field(1, ge=1)),
        "page_size": (int, Field(20, ge=1, le=100)),
        "ordering": (OrderingEnum | None, None),
    }

    model = create_model(f"{dto.__name__}Query", **fields)
    model.__valid_filter_fields__ = valid_fields  # type: ignore[attr-defined]
    return model


def apply_query(
    query: Select,
    model: type,
    query_params: Any,
    *,
    paginate: bool = True,
) -> Select:
    """Apply filters, ordering, and optional pagination from *query_params* onto *query*.

    Args:
        query:        The base SQLAlchemy SELECT statement to modify.
        model:        The SQLModel class whose columns are referenced by filter fields.
        query_params: A Pydantic model with ``filters``, ``page``, ``page_size``, ``ordering``.
        paginate:     When ``False``, LIMIT/OFFSET are not applied (use for COUNT queries).
    """
    data = query_params.model_dump(exclude_none=True)

    page = data.get("page", 1)
    page_size = data.get("page_size", 20)
    ordering = data.get("ordering", None)
    filters: list[dict[str, Any]] = data.get("filters", [])

    valid_fields: dict[str, list[str]] = getattr(type(query_params), "__valid_filter_fields__", {})

    for f in filters:
        field_name = f["field"]
        operator = f["operator"]
        value = f["value"]

        if valid_fields and field_name not in valid_fields:
            raise ValueError(f"Invalid filter field: '{field_name}'")
        if operator not in OPERATORS:
            raise ValueError(f"Unsupported operator: '{operator}'")
        if valid_fields and operator not in valid_fields.get(field_name, []):
            raise ValueError(f"Operator '{operator}' is not allowed for field '{field_name}'")

        column = getattr(model, field_name)
        query = query.where(OPERATORS[operator](column, value))

    if ordering is not None:
        ordering_str = ordering.value if isinstance(ordering, enum.Enum) else str(ordering)
        is_desc = ordering_str.startswith("-")
        field_name = ordering_str.removeprefix("-")
        column = getattr(model, field_name)
        query = query.order_by(column.desc() if is_desc else column.asc())

    if paginate:
        query = query.offset((page - 1) * page_size).limit(page_size)

    return query
