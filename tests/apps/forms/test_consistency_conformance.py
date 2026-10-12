"""The peer receives the same positive/negative canonical vectors the server runs."""

import json
from pathlib import Path

import pytest

from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments
from tests.apps.forms.test_visual_control_matrix import vector

MATRIX = Path("tests/fixtures/delivery/consistency-conformance-v1.json")


def test_paired_matrix_preserves_types_units_and_null_rules():
    matrix = json.loads(MATRIX.read_text())
    fixture = vector()
    assert matrix["schema_version"] == 1
    document = FormDocuments.model_validate(fixture["documents"])
    assert FormValidator().validate(document, fixture["initial_data"], publication=True).valid
    for name, expected in matrix["invariants"].items():
        actual = fixture["initial_data"][name]
        assert actual == expected and type(actual) is type(expected)
    for negative in fixture["negative_values"]:
        result = FormValidator().validate(
            document, fixture["initial_data"] | {negative["field"]: negative["value"]}
        )
        assert not result.valid and any(issue.code == negative["code"] for issue in result.issues)


@pytest.mark.parametrize(
    "field,value",
    [("integer", "0"), ("boolean", 0), ("choice", "0"), ("money", "125.7500"), ("optional", False)],
)
def test_canonical_fixture_drift_is_rejected_by_the_actual_validator(field, value):
    fixture = vector()
    result = FormValidator().validate(
        FormDocuments.model_validate(fixture["documents"]), fixture["initial_data"] | {field: value}
    )
    assert not result.valid
