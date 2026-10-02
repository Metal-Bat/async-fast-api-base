"""Behavior of the trusted workflow step catalog."""

import pytest
from pydantic import ValidationError

from apps.step_types.application.registry import builtin_registry


def test_initial_catalog_has_explicit_modes_and_zero_or_many_ports() -> None:
    registry = builtin_registry()
    catalog = {item.code: item for item in registry.catalog()}
    assert {key: item.execution_mode for key, item in catalog.items()} == {
        "START": "SYNC",
        "HUMAN_TASK": "HUMAN",
        "SERVICE_TASK": "BACKGROUND",
        "FUNCTION": "SYNC",
        "TRANSFORM": "SYNC",
        "DECISION": "SYNC",
        "NOTIFICATION": "BACKGROUND",
        "EVENT_WAIT": "WAIT",
        "TIMER": "WAIT",
        "FINISH": "SYNC",
        "SUBPROCESS": "WAIT",
    }
    assert catalog["START"].ports == []
    assert catalog["FINISH"].ports == []
    assert catalog["SUBPROCESS"].ports == []
    assert len(catalog["HUMAN_TASK"].ports) > 1
    assert catalog["SERVICE_TASK"].config_schema["additionalProperties"] is False


def test_event_and_timer_wait_contracts_are_bounded_and_typed() -> None:
    registry = builtin_registry()

    assert registry.validate_config(
        "event_wait",
        "1",
        {"event_type": "payment.received", "expires_in_seconds": 3600},
    ) == {"event_type": "payment.received", "expires_in_seconds": 3600}
    assert registry.validate_inputs(
        registry.resolve("event_wait", "1"), {"correlation_key": "invoice-42"}
    ) == {"correlation_key": "invoice-42"}
    assert registry.validate_config("timer", "1", {"delay_seconds": 30}) == {"delay_seconds": 30}
    with pytest.raises(ValidationError):
        registry.validate_config("timer", "1", {"delay_seconds": 0})
    with pytest.raises(ValidationError):
        registry.validate_config("event_wait", "1", {"event_type": "bad type"})


def test_handler_resolution_never_imports_designer_supplied_names() -> None:
    registry = builtin_registry()
    with pytest.raises(ValueError, match="registered"):
        registry.resolve("os.system", "1")
    with pytest.raises(ValueError, match="registered"):
        registry.resolve("start", "999")
    with pytest.raises(ValidationError):
        registry.validate_config("start", "1", {"callable": "os.system"})


def test_configuration_validation_and_catalog_are_isolated() -> None:
    registry = builtin_registry()
    with pytest.raises(ValidationError):
        registry.validate_config("human_task", "1", {})
    assert registry.validate_config("human_task", "1", {"form_version_ref": "opaque"}) == {
        "form_version_ref": "opaque"
    }
    catalog = registry.catalog()
    catalog[0].config_schema.clear()
    assert registry.catalog()[0].config_schema


def test_transform_v2_catalog_drives_completion_and_registered_execution() -> None:
    registry = builtin_registry()
    schema = registry.resolve("transform", "2").metadata().config_schema
    assert schema["properties"]["conversion_key"]["enum"] == [
        "string",
        "integer",
        "decimal",
        "boolean",
        "date",
        "date_time",
        "array",
        "object",
    ]
    config = {
        "conversion_key": "object",
        "projection": {"name": "/profile/name"},
    }
    result = registry.execute_transform(
        "transform", "2", config, {"profile": {"name": "Ada", "secret": "hidden"}}
    )
    assert result.value == {"name": "Ada"}
    assert "hidden" not in str(result.record)


def test_port_values_validate_cardinality_nullability_and_references() -> None:
    registry = builtin_registry()
    human = registry.resolve("human_task", "1")
    assert registry.validate_outputs(human, {"submission": {}, "outcome": "approve"}) == {
        "submission": {},
        "outcome": "approve",
    }
    with pytest.raises(ValueError, match="required"):
        registry.validate_outputs(human, {"submission": {}})
    with pytest.raises(ValidationError):
        registry.validate_outputs(human, {"submission": {}, "outcome": None})
    with pytest.raises(ValueError, match="Unknown"):
        registry.validate_outputs(human, {"submission": {}, "outcome": "ok", "extra": 1})
    notification = registry.resolve("notification", "1")
    registry.validate_inputs(notification, {"recipients": ["user-ref"], "data": {}})
    with pytest.raises(ValidationError):
        registry.validate_inputs(notification, {"recipients": "user-ref", "data": {}})


def test_extension_ports_cover_nested_arrays_references_and_explicit_nullability() -> None:
    from pydantic import JsonValue

    from apps.step_types.application.registry import (
        EmptyConfig,
        HandlerDefinition,
        HandlerRegistry,
        PortDefinition,
        Reference,
    )

    handler = HandlerDefinition(
        "EXTENSION",
        "Extension",
        "extension",
        "1",
        "WAIT",
        EmptyConfig,
        (
            PortDefinition("nested", "INPUT", dict[str, list[int]]),
            PortDefinition("media", "INPUT", Reference, reference_kind="media"),
            PortDefinition("request", "INPUT", Reference, reference_kind="request"),
            PortDefinition(
                "groups", "INPUT", Reference, cardinality="LIST", reference_kind="work_group"
            ),
            PortDefinition("optional", "OUTPUT", str, required=False, nullable=True),
            PortDefinition("value", "OUTPUT", JsonValue),
        ),
    )
    registry = HandlerRegistry((handler,))
    values = {"nested": {"items": [1, 2]}, "media": "m", "request": "r", "groups": ["g"]}
    assert registry.validate_inputs(handler, values) == values
    assert registry.validate_outputs(handler, {"value": 4, "optional": None}) == {
        "value": 4,
        "optional": None,
    }
    with pytest.raises(ValueError, match="null"):
        registry.validate_outputs(handler, {"value": None})
    with pytest.raises(ValidationError):
        registry.validate_inputs(handler, {**values, "nested": {"items": ["1"]}})
    with pytest.raises(ValueError, match="Duplicate"):
        HandlerRegistry((handler, handler))
