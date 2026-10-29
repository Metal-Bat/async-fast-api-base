"""Trusted legacy execution schemas refine validation without rewriting pins."""

from apps.step_types.application.registry import builtin_registry
from apps.workflows.application.validation import GraphValidator
from apps.workflows.domain.dto import GraphSnapshot


def legacy_chain():
    registry = builtin_registry()
    ports = registry.resolve("transform", "1").metadata().ports
    schemas = {port.port_key: port.value_schema for port in ports}
    return GraphSnapshot.model_validate(
        {
            "steps": [
                {"key": "start", "type_code": "START"},
                {"key": "old", "type_code": "TRANSFORM", "config": {"conversion_key": "integer"}},
                {"key": "typed", "type_code": "TRANSFORM", "config": {"conversion_key": "integer"}},
                {"key": "finish", "type_code": "FINISH"},
            ],
            "transitions": [
                {"source": "start", "target": "old", "outcome": "next", "is_default": True},
                {"source": "old", "target": "typed", "outcome": "next", "is_default": True},
                {
                    "source": "typed",
                    "target": "finish",
                    "outcome": "next",
                    "condition": "steps.old.outputs.result >= 0",
                },
            ],
            "bindings": [
                {
                    "step": "old",
                    "target_port": "value",
                    "target_schema": schemas["value"],
                    "source_kind": "CONSTANT",
                    "constant_value": "0",
                },
                {
                    "step": "typed",
                    "target_port": "value",
                    "target_schema": {"type": ["string", "integer"]},
                    "source_kind": "STEP_OUTPUT",
                    "source_step": "old",
                    "source_port": "result",
                    "source_schema": schemas["result"],
                },
            ],
        }
    )


def test_registry_verified_legacy_schemas_validate_without_rewriting_graph():
    graph = legacy_chain()
    declared = graph.model_dump(mode="json")
    result = GraphValidator().validate(graph, legacy_transform_steps=frozenset({"old"}))
    assert result.valid, [issue.model_dump() for issue in result.issues]
    assert graph.model_dump(mode="json") == declared
    assert (
        GraphValidator().validate(graph, legacy_transform_steps=frozenset({"old"})).checksum
        == result.checksum
    )
    assert not GraphValidator().validate(graph).valid


def test_legacy_refinement_still_rejects_incompatible_request_values():
    graph = legacy_chain()
    binding = graph.bindings[0]
    binding.source_kind = "REQUEST"
    binding.source_path = "/value"
    binding.source_schema = {"type": "object", "properties": {"value": {"type": "boolean"}}}
    binding.constant_value = None
    result = GraphValidator().validate(graph, legacy_transform_steps=frozenset({"old"}))
    assert not result.valid
    assert ("/bindings/0/source_schema", "binding.type.incompatible") in {
        (issue.pointer, issue.code) for issue in result.issues
    }
