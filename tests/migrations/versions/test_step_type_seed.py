"""Security contract for the step-type catalog seed."""

import importlib
import json
from unittest.mock import Mock

from sqlalchemy.dialects import postgresql


def test_step_type_seed_passes_catalog_as_bound_json(monkeypatch) -> None:
    migration = importlib.import_module("migrations.versions.b13a0c7d2e44_initial_schema")
    execute = Mock()
    monkeypatch.setattr(migration.op, "execute", execute)

    migration._seed_catalog()

    statement = execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "%(payload)s" in str(compiled)
    assert compiled.params["payload"] == json.dumps(migration._INITIAL_CATALOG)
    assert compiled.params["payload"] not in str(compiled)
