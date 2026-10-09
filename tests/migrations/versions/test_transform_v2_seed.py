"""The additive transform seed must match immutable registry metadata."""

import importlib

from apps.step_types.application.registry import builtin_registry


def test_transform_v2_seed_matches_registered_contract() -> None:
    migration = importlib.import_module("migrations.versions.0002_required_data")
    metadata = builtin_registry().resolve("transform", "2").metadata()
    assert migration._CONFIG_SCHEMA == metadata.config_schema
    assert all(port.value_schema == migration._VALUE_SCHEMA for port in metadata.ports)
