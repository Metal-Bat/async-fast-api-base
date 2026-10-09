"""Security contract for the step-type catalog seed."""

import importlib
import json
from unittest.mock import Mock

from sqlalchemy.dialects import postgresql


def test_step_type_seed_passes_catalog_as_bound_json(monkeypatch) -> None:
    migration = importlib.import_module("migrations.versions.0002_required_data")
    execute = Mock()
    monkeypatch.setattr(migration.op, "execute", execute)

    migration._seed_catalog()

    assert len(execute.call_args_list) == 2
    for call in execute.call_args_list:
        statement = call.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        assert "%(payload)s" in str(compiled)
        assert compiled.params["payload"] == json.dumps(migration._INITIAL_CATALOG)
        assert compiled.params["payload"] not in str(compiled)


def test_deployed_catalog_seeds_match_current_registered_contracts() -> None:
    from apps.step_types.application.registry import builtin_registry, get_registry

    migration = importlib.import_module("migrations.versions.0002_required_data")
    builtins = {
        (item.handler_key, item.handler_version) for item in builtin_registry().definitions()
    }
    expected = [
        item.metadata().model_dump(mode="json")
        for item in get_registry().definitions()
        if (item.handler_key, item.handler_version) not in builtins
    ]
    seeded = migration._deployed_catalog()
    assert len(seeded) == len(expected)
    for stored, metadata in zip(seeded, expected, strict=True):
        definition = get_registry().resolve(metadata["handler_key"], metadata["handler_version"])
        schema = stored["config_schema"]
        assert schema["x-step-definition-fingerprint"] == definition.fingerprint
        assert schema["x-step-definition"] == {
            "category": definition.category,
            "name_key": definition.name_key,
            "help_key": definition.help_key,
            "outcomes": list(definition.outcomes),
            "examples": list(definition.examples),
            "required_capabilities": list(definition.required_capabilities),
        }
        clean = dict(
            stored,
            config_schema={
                key: value
                for key, value in schema.items()
                if not key.startswith("x-step-definition")
            },
        )
        assert clean == metadata
