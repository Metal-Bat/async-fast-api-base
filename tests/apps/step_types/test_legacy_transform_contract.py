"""Legacy Transform execution preserves its immutable generic port contract."""

import pytest

from apps.step_types.application.registry import builtin_registry


@pytest.mark.parametrize("value, expected", [("0", 0), ("42", 42), (-3, -3)])
def test_legacy_transform_executes_without_replacing_its_registered_contract(value, expected):
    registry = builtin_registry()
    definition = registry.resolve("transform", "1")
    before = definition.metadata().model_dump(mode="json")
    fingerprint = definition.fingerprint
    assert (
        registry.execute_transform("transform", "1", {"conversion_key": "integer"}, value).value
        == expected
    )
    assert definition.metadata().model_dump(mode="json") == before
    assert definition.fingerprint == fingerprint
    assert registry.transform_contract("transform", "1", {"conversion_key": "integer"}) is None


def test_legacy_transform_rejects_invalid_conversions_and_values():
    registry = builtin_registry()
    with pytest.raises(ValueError):
        registry.execute_transform("transform", "1", {"conversion_key": "unknown"}, "5")
    with pytest.raises(ValueError):
        registry.execute_transform("transform", "1", {"conversion_key": "integer"}, "invalid")
