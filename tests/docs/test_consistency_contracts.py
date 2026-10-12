"""Current producer contracts and deliberately adversarial drift checks."""

from copy import deepcopy
from typing import Any

import pytest
from scripts.entity_inventory import entity_inventory, field_format_violations

from apps.support.domain.dto import ClientFailure, IncidentDTO, IncidentHistoryDTO
from apps.tasks.domain.dtos.schedules import (
    PeriodicTaskCreateDTO,
    PeriodicTaskDTO,
    PeriodicTaskUpdateDTO,
)
from main import app
from utils.localized_docs import localized_openapi


def machine_contract(value):
    if isinstance(value, dict):
        return {
            key: machine_contract(item)
            for key, item in value.items()
            if key not in {"description", "summary", "title", "x-docs-language"}
        }
    if isinstance(value, list):
        return [machine_contract(item) for item in value]
    return value


def test_localization_preserves_machine_contract_and_detects_enum_drift():
    english = localized_openapi(app, "en")
    persian = localized_openapi(app, "fa")
    assert machine_contract(english) == machine_contract(persian)
    changed = deepcopy(persian)
    changed["components"]["schemas"]["PeriodicTaskCreateDTO"]["properties"]["schedule_type"][
        "enum"
    ].append("invented")
    assert machine_contract(english) != machine_contract(changed)


@pytest.mark.parametrize(
    "model",
    [
        ClientFailure,
        IncidentDTO,
        IncidentHistoryDTO,
        PeriodicTaskCreateDTO,
        PeriodicTaskDTO,
        PeriodicTaskUpdateDTO,
    ],
)
def test_touched_fixed_fields_have_actionable_descriptions(model):
    for mode in ("validation", "serialization"):
        schema = model.model_json_schema(mode=mode)
        for name, field in schema["properties"].items():
            assert field.get("description"), f"{model.__name__}.{name} lacks an explanation"


def test_storage_inventory_covers_all_tables_without_granting_crud():
    inventory = entity_inventory()
    assert len(inventory) == 103
    assert all(
        item["owner"] and item["mutability"] and item["public_exposure"].startswith("none-implied")
        for item in inventory.values()
    )
    assert any(item["mutability"] == "append-only-audit" for item in inventory.values())


def test_entity_formatter_detects_collapsed_nested_declarations():
    assert field_format_violations(
        'value = Field(sa_column=Column("VALUE", String(64), nullable=False))'
    )
    assert not field_format_violations(
        'value = Field(\n    sa_column=Column(\n        "VALUE",\n        String(64),\n        nullable=False,\n    ),\n)'
    )


def test_current_producer_artifacts_regenerate_without_drift():
    import json
    from pathlib import Path

    from scripts.contract_inventory import check_authorities
    from scripts.export_wave_four_contracts import DESTINATION, build_documents

    active = []
    for path in Path("docs/delivery").rglob("manifest.json"):
        manifest = json.loads(path.read_text())
        if manifest.get("authority") == "current-producer":
            active.append(str(path))
    check_authorities(active)
    assert active == [str(DESTINATION.relative_to(Path.cwd()) / "manifest.json")]
    for name, document in build_documents().items():
        assert json.loads((DESTINATION / name).read_text()) == document, (
            f"{name} needs regeneration"
        )


def test_schedule_examples_validate_in_the_declared_input_mode():
    from jsonschema import Draft202012Validator, FormatChecker

    schema = PeriodicTaskCreateDTO.model_json_schema(mode="validation")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for example in schema["examples"]:
        validator.validate(example)
        PeriodicTaskCreateDTO.model_validate(example)
    with pytest.raises(ValueError, match="timezone"):
        PeriodicTaskCreateDTO.model_validate(
            schema["examples"][2] | {"clocked_at": "2026-12-01T12:00:00"}
        )


def test_effective_openapi_has_no_unresolved_local_references():
    schema = localized_openapi(app, "en")
    pending: list[Any] = [schema]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            reference = current.get("$ref", "")
            if reference.startswith("#/"):
                target = schema
                for part in reference[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
