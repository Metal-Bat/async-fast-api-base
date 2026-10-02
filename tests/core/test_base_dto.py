"""Tests for the shared JSON DTO contract."""

import ast
import re
from pathlib import Path

import pytest
from pydantic import Field

from core.base_dto import BaseDTO

_CAMEL_CASE = re.compile(r"[a-z][A-Z]")


def schema_property_names(value: object) -> set[str]:
    if isinstance(value, dict):
        properties = value.get("properties", {})
        names: set[str] = set()
        if isinstance(properties, dict):
            for name in properties:
                if isinstance(name, str):
                    names.add(name)
        for nested in value.values():
            names.update(schema_property_names(nested))
        return names
    if isinstance(value, list):
        names: set[str] = set()
        for nested in value:
            names.update(schema_property_names(nested))
        return names
    return set()


def test_all_json_models_use_the_snake_case_dto_contract() -> None:
    root = Path(__file__).parents[2] / "src"
    direct_base_model_classes: list[tuple[Path, str]] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in (item for item in ast.walk(tree) if isinstance(item, ast.ClassDef)):
            bases = {base.id for base in node.bases if isinstance(base, ast.Name)}
            if "BaseModel" in bases:
                direct_base_model_classes.append((path.relative_to(root), node.name))

    assert sorted(direct_base_model_classes) == [
        (Path("core/base_dto.py"), "BaseDTO"),
        (Path("utils/base_schema.py"), "BaseHeaders"),
    ]

    from main import app

    assert not {name for name in schema_property_names(app.openapi()) if _CAMEL_CASE.search(name)}


def test_base_dto_rejects_non_snake_case_output_aliases() -> None:
    with pytest.raises(TypeError, match="must serialize snake_case"):

        class InvalidDTO(BaseDTO):
            field_name: str = Field(alias="fieldName")
