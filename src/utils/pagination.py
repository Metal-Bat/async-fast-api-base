from datetime import date, datetime
from enum import StrEnum
from types import UnionType
from typing import Annotated, Any, ClassVar, Union, get_args, get_origin

from pydantic import (
    AliasChoices,
    ConfigDict,
    EmailStr,
    Field,
    TypeAdapter,
    computed_field,
    create_model,
    model_validator,
)
from sqlalchemy import Select
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.base_dto import BaseDTO


class FilterOperation(StrEnum):
    """Filter operators exposed by the shared search contract."""

    EQUAL = "equal"
    NOT_EQUAL = "notEqual"
    START_WITH = "startWith"
    ENDS_WITH = "endsWith"
    CONTAINS = "contains"
    NOT_CONTAINS = "notContains"
    BETWEEN = "between"
    IS_NULL = "isNull"
    IS_NOT_NULL = "isNotNull"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "nin"


class SortOperation(StrEnum):
    """Sort direction for one field or a sequence of fields."""

    ASC = "asc"
    DESC = "desc"


class FilterCriteria(BaseDTO):
    """One filter in the shared search wire format."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    field_name: str = Field(validation_alias=AliasChoices("field_name", "fieldName"), min_length=1)
    operation: FilterOperation
    value: Any = None


class SortOrder(BaseDTO):
    """Sort one field or multiple fields using the same direction."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    multi_field: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("multi_field", "multiField"),
    )
    field_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("field_name", "fieldName"),
    )
    operation: SortOperation = SortOperation.ASC

    @model_validator(mode="after")
    def validate_fields(self) -> SortOrder:
        """Require exactly one of field_name and a nonempty multi_field."""
        if bool(self.field_name) == bool(self.multi_field):
            raise ValueError("Supply either field_name or multi_field")
        if any(not name for name in self.multi_field):
            raise ValueError("Sort fields must not be empty")
        return self


class PageRequest(BaseDTO):
    """Page-number pagination shared by bounded in-memory collections."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class SearchRequest(PageRequest):
    """Validated filter, sort, and page parameters shared by search endpoints."""

    filters: list[FilterCriteria] = Field(default_factory=list)
    sort_orders: list[SortOrder] = Field(
        default_factory=list,
        validation_alias=AliasChoices("sort_orders", "sortOrders"),
    )
    __query_fields__: ClassVar[dict[str, Any] | None] = None

    @model_validator(mode="after")
    def validate_query(self) -> SearchRequest:
        """Validate names, type-specific operations, and filter values before SQL."""
        fields = self.__query_fields__
        if fields is None:
            return self
        for sort in self.sort_orders:
            for name in sort.multi_field or ([sort.field_name] if bool(sort.field_name) else []):
                if name not in fields:
                    raise ValueError(f"Invalid sort field: {name}")
        for criterion in self.filters:
            name, operation = criterion.field_name, criterion.operation
            if name not in fields:
                raise ValueError(f"Invalid filter field: {name}")
            annotation = fields[name]
            base = _unwrap_type(annotation)
            if operation in {FilterOperation.IS_NULL, FilterOperation.IS_NOT_NULL}:
                if criterion.value is not None:
                    raise ValueError("Null checks do not accept a value")
                continue
            allowed = {
                FilterOperation.EQUAL,
                FilterOperation.NOT_EQUAL,
                FilterOperation.IN,
                FilterOperation.NOT_IN,
            }
            if base in {str, EmailStr}:
                allowed |= {
                    FilterOperation.START_WITH,
                    FilterOperation.ENDS_WITH,
                    FilterOperation.CONTAINS,
                    FilterOperation.NOT_CONTAINS,
                }
            if base in {int, float, date, datetime}:
                allowed |= {
                    FilterOperation.LT,
                    FilterOperation.LTE,
                    FilterOperation.GT,
                    FilterOperation.GTE,
                    FilterOperation.BETWEEN,
                }
            if operation not in allowed:
                raise ValueError(f"Operation {operation} is not allowed for {name}")
            value = criterion.value
            if operation in {FilterOperation.IN, FilterOperation.NOT_IN, FilterOperation.BETWEEN}:
                if not isinstance(value, list) or not value:
                    raise ValueError("This operation requires a nonempty list")
                if operation == FilterOperation.BETWEEN and len(value) != 2:
                    raise ValueError("The between operator requires a two-item list")
                criterion.value = [TypeAdapter(base).validate_python(item) for item in value]
            else:
                criterion.value = TypeAdapter(annotation).validate_python(value)
        return self


class Page[T](BaseDTO):
    """One search result page using the shared snake_case contract."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    items: list[T] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(ge=0)

    @computed_field
    @property
    def total_pages(self) -> int:
        """Return the number of nonempty pages in the full result set."""
        return (self.total + self.size - 1) // self.size


def _unwrap_type(annotation: Any) -> Any:
    """Extract the underlying type from optional and annotated DTO fields."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap_type(get_args(annotation)[0])
    if origin in {Union, UnionType}:
        arguments = [item for item in get_args(annotation) if item is not type(None)]
        if len(arguments) == 1:
            return _unwrap_type(arguments[0])
    return annotation


def auto_query_model(
    dto: type[BaseDTO], *, include: set[str] | None = None, exclude: set[str] | None = None
) -> type[SearchRequest]:
    """Derive a validated search surface from the public DTO's permitted fields."""
    fields = {
        name: field.annotation
        for name, field in dto.model_fields.items()
        if (include is None or name in include) and name not in (exclude or set())
    }
    model = create_model(f"{dto.__name__}Query", __base__=SearchRequest)
    model.__query_fields__ = fields
    return model


OPERATORS = {
    FilterOperation.EQUAL: lambda c, v: c == v,
    FilterOperation.NOT_EQUAL: lambda c, v: c != v,
    FilterOperation.GT: lambda c, v: c > v,
    FilterOperation.GTE: lambda c, v: c >= v,
    FilterOperation.LT: lambda c, v: c < v,
    FilterOperation.LTE: lambda c, v: c <= v,
    FilterOperation.IN: lambda c, v: c.in_(v),
    FilterOperation.NOT_IN: lambda c, v: c.not_in(v),
    FilterOperation.BETWEEN: lambda c, v: c.between(v[0], v[1]),
    FilterOperation.START_WITH: lambda c, v: c.startswith(v, autoescape=True),
    FilterOperation.ENDS_WITH: lambda c, v: c.endswith(v, autoescape=True),
    FilterOperation.CONTAINS: lambda c, v: c.contains(v, autoescape=True),
    FilterOperation.NOT_CONTAINS: lambda c, v: ~c.contains(v, autoescape=True),
    FilterOperation.IS_NULL: lambda c, v: c.is_(None),
    FilterOperation.IS_NOT_NULL: lambda c, v: c.is_not(None),
}


def apply_query[SelectType: Select[*tuple[Any, ...]]](
    query: SelectType,
    model: Any,
    query_params: SearchRequest,
    *,
    paginate: bool = True,
    order: bool | None = None,
    default_ordering: tuple[str, ...] = ("id",),
    default_ordering_first: bool = False,
) -> SelectType:
    """Apply validated filters and stable ordering using SQL expression objects."""
    order = paginate if order is None else order
    if query_params.__query_fields__ is None:
        raise ValueError("Search must declare a DTO-derived field allowlist")
    for criterion in query_params.filters:
        column = getattr(model, criterion.field_name)
        query = query.where(OPERATORS[criterion.operation](column, criterion.value))
    if order:
        ordered: set[str] = set()
        if default_ordering_first:
            for ordering in default_ordering:
                name = ordering.removeprefix("-")
                column = getattr(model, name)
                query = query.order_by(column.desc() if ordering.startswith("-") else column.asc())
                ordered.add(name)
        for sort in query_params.sort_orders:
            for name in sort.multi_field or ([sort.field_name] if bool(sort.field_name) else []):
                column = getattr(model, name)
                query = query.order_by(
                    column.desc() if sort.operation == SortOperation.DESC else column.asc()
                )
                ordered.add(name)
        if not default_ordering_first:
            for ordering in default_ordering:
                name = ordering.removeprefix("-")
                if name not in ordered:
                    column = getattr(model, name)
                    query = query.order_by(
                        column.desc() if ordering.startswith("-") else column.asc()
                    )
    if paginate:
        query = query.offset((query_params.page - 1) * query_params.size).limit(query_params.size)
    return query


async def paginate_entities[EntityType: SQLModel](
    session: AsyncSession,
    model: type[EntityType],
    query_params: SearchRequest,
    *,
    criteria: tuple[Any, ...] = (),
    default_ordering: tuple[str, ...] = ("id",),
) -> Page[EntityType]:
    """Return a filtered page for one SQLModel entity and optional base criteria."""
    item_query = apply_query(
        select(model).where(*criteria),
        model,
        query_params,
        default_ordering=default_ordering,
    )
    count_query = apply_query(
        select(func.count()).select_from(model).where(*criteria),
        model,
        query_params,
        paginate=False,
    )
    items = list((await session.exec(item_query)).all())
    total = (await session.exec(count_query)).one()
    return Page[EntityType](
        items=items,
        page=query_params.page,
        size=query_params.size,
        total=total,
    )


def paginate_values[ValueType](values: list[ValueType], query: PageRequest) -> Page[ValueType]:
    """Return one page from an already bounded and ordered value collection."""
    start = (query.page - 1) * query.size
    return Page[ValueType](
        items=values[start : start + query.size],
        page=query.page,
        size=query.size,
        total=len(values),
    )


def paginate_models[ValueType](
    values: list[ValueType], query: SearchRequest, *, default_ordering: tuple[str, ...] = ("id",)
) -> Page[ValueType]:
    """Apply the shared search contract to a bounded in-memory catalog."""

    def matches(item: ValueType, criterion: FilterCriteria) -> bool:
        """Evaluate one already type-checked filter against one catalog item."""
        value = getattr(item, criterion.field_name)
        expected = criterion.value
        operation = criterion.operation
        if operation == FilterOperation.EQUAL:
            return bool(value == expected)
        if operation == FilterOperation.NOT_EQUAL:
            return bool(value != expected)
        if operation == FilterOperation.IS_NULL:
            return value is None
        if operation == FilterOperation.IS_NOT_NULL:
            return value is not None
        if operation == FilterOperation.IN:
            return value in expected
        if operation == FilterOperation.NOT_IN:
            return value not in expected
        if operation == FilterOperation.BETWEEN:
            return bool(expected[0] <= value <= expected[1])
        if operation == FilterOperation.START_WITH:
            return bool(value.startswith(expected))
        if operation == FilterOperation.ENDS_WITH:
            return bool(value.endswith(expected))
        if operation == FilterOperation.CONTAINS:
            return expected in value
        if operation == FilterOperation.NOT_CONTAINS:
            return expected not in value
        if operation == FilterOperation.GT:
            return bool(value > expected)
        if operation == FilterOperation.GTE:
            return bool(value >= expected)
        if operation == FilterOperation.LT:
            return bool(value < expected)
        return bool(value <= expected)

    filtered = [item for item in values if all(matches(item, rule) for rule in query.filters)]
    ordering: list[tuple[str, bool]] = []
    for sort in query.sort_orders:
        ordering.extend(
            (name, sort.operation == SortOperation.DESC)
            for name in sort.multi_field or ([sort.field_name] if bool(sort.field_name) else [])
        )
    ordered_names = {name for name, _ in ordering}
    ordering.extend(
        (item.removeprefix("-"), item.startswith("-"))
        for item in default_ordering
        if item.removeprefix("-") not in ordered_names
    )
    for name, descending in reversed(ordering):
        filtered.sort(key=lambda item: getattr(item, name), reverse=descending)
    return paginate_values(filtered, query)
