"""Audit fixed public JSON boundaries without constraining dynamic business keys."""

import inspect
from typing import Any, TypeAliasType, get_args

from pydantic import BaseModel

from core.base_dto import BaseDTO


def nested_models(annotation: Any, seen: set[int] | None = None) -> set[type[BaseModel]]:
    """Resolve typed models through containers, unions, Annotated and recursive aliases."""
    seen = set() if seen is None else seen
    if id(annotation) in seen:
        return set()
    seen.add(id(annotation))
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return {annotation}
    if isinstance(annotation, TypeAliasType):
        return nested_models(annotation.__value__, seen)
    models: set[type[BaseModel]] = set()
    for argument in get_args(annotation):
        models.update(nested_models(argument, seen))
    return models


def assert_public_dto(model: type[BaseModel]) -> None:
    """Reject entity/plain-model leakage and unexplained whole-model serialization."""
    pending = [(model, model.__name__)]
    checked: set[type[BaseModel]] = set()
    while pending:
        current, path = pending.pop()
        if current in checked:
            continue
        checked.add(current)
        if not issubclass(current, BaseDTO):
            raise TypeError(f"{path}: {current.__name__} is not a BaseDTO public JSON model")
        if not current.__pydantic_complete__:
            current.model_rebuild()
        if current.__pydantic_decorators__.model_serializers:
            raise TypeError(
                f"{path}: custom model serializer needs an explicit fixed wire contract"
            )
        if current.__pydantic_decorators__.field_serializers:
            raise TypeError(
                f"{path}: custom field serializer needs an explicit fixed wire contract"
            )
        for name, field in current.model_fields.items():
            pending.extend((child, f"{path}.{name}") for child in nested_models(field.annotation))
        for name, field in current.model_computed_fields.items():
            pending.extend((child, f"{path}.{name}") for child in nested_models(field.return_type))
