"""New field projections preserve old wire identity and reject ambiguous instructions."""

import pytest
from pydantic import ValidationError

from apps.workflows.domain.dto import GraphBinding


def binding(**changes):
    return GraphBinding.model_validate(
        {
            "step": "review",
            "target_port": "data",
            "target_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "source_kind": "CONSTANT",
            "constant_value": "Example",
        }
        | changes
    )


def test_optional_projection_does_not_change_existing_canonical_binding_payload():
    old = binding().model_dump(mode="json")
    assert "target_projection" not in old
    assert binding(target_projection=None).model_dump(mode="json") == old


def test_versioned_object_field_is_explicit_and_round_trips():
    row = binding(target_projection={"dialect": "bpms.binding.object/1", "path": "/name"})
    assert row.model_dump(mode="json")["target_projection"] == {
        "dialect": "bpms.binding.object/1",
        "path": "/name",
    }
    assert GraphBinding.model_validate(row.model_dump()).target_projection == row.target_projection


@pytest.mark.parametrize(
    "projection",
    [
        {"dialect": "bpms.binding.object/2", "path": "/name"},
        {"dialect": "bpms.binding.object/1", "path": "name"},
        {"dialect": "bpms.binding.object/1", "path": "/bad~escape"},
        {"dialect": "bpms.binding.object/1", "path": "/__proto__/name"},
        {"dialect": "bpms.binding.object/1", "path": "/" + "/".join(["deep"] * 13)},
    ],
)
def test_unsupported_projection_is_rejected(projection):
    with pytest.raises(ValidationError):
        binding(target_projection=projection)
