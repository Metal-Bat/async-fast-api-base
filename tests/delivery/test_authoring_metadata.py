"""Inspector contracts come from the deployed registry, without executing handlers."""

import pytest
from pydantic import ValidationError

from apps.designer.application.inspector import inspector_contract
from apps.designer.domain.inspector import InspectorContract
from apps.forms.domain.fields import FIELD_DEFINITIONS
from apps.step_types.application.registry import get_registry
from core.i18n import use_language


def test_every_deployed_handler_and_primitive_has_a_versioned_contract() -> None:
    registry = get_registry()
    before = [item.fingerprint for item in registry.definitions()]
    contract = inspector_contract()
    assert contract.schema_version == 1
    assert {(item.handler_key, item.handler_version) for item in contract.handlers} == {
        (item.handler_key, item.handler_version) for item in registry.definitions()
    }
    assert {item.key for item in contract.fields} == set(FIELD_DEFINITIONS)
    assert len(contract.fields) == 20
    assert InspectorContract.model_validate_json(contract.model_dump_json()) == contract
    assert before == [item.fingerprint for item in registry.definitions()]
    human = next(item for item in contract.handlers if item.handler_key == "human_task")
    binding = next(item for item in human.bindings if item.pointer == "/form_version_ref")
    assert binding.selector_kind == "form_versions"
    assert binding.pinned is True
    assert binding.secret_reference is False
    service = next(item for item in contract.handlers if item.handler_key == "service_task")
    assert next(
        item for item in service.bindings if item.pointer == "/connection_ref"
    ).secret_reference


def test_metadata_has_no_execution_or_unknown_event_payload() -> None:
    document = inspector_contract().model_dump(mode="json")
    document["handlers"][0]["credential"] = "must-not-be-accepted"
    with pytest.raises(ValidationError):
        InspectorContract.model_validate(document)
    with use_language("en"):
        english = inspector_contract()
    with use_language("fa"):
        persian = inspector_contract()
    assert [item.config_schema for item in english.handlers] == [
        item.config_schema for item in persian.handlers
    ]
    assert [item.key for item in english.fields] == [item.key for item in persian.fields]


def test_inspector_configuration_diagnostics_never_echo_input_values():
    from apps.designer.application.inspector import validate_configuration
    from apps.designer.domain.inspector import InspectorValidationQuery

    bad = InspectorValidationQuery(
        handler_key="transform",
        handler_version="2",
        config={
            "conversion_key": "decimal",
            "null_behavior": None,
            "credential": "never-echo-input",
        },
    )
    result = validate_configuration(bad)
    assert result.valid is False
    assert {item.pointer for item in result.diagnostics} >= {"/", "/null_behavior"}
    assert "never-echo-input" not in result.model_dump_json()
    unknown = validate_configuration(
        InspectorValidationQuery(handler_key="unknown", handler_version="1", config={})
    )
    assert unknown.valid is False and unknown.diagnostics[0].code == "handler_unavailable"
