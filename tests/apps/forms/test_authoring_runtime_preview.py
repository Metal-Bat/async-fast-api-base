"""Author previews use the same safe runtime projection without creating a case."""

from main import app


def test_author_preview_contract_is_authenticated_and_explicitly_simulated():
    operation = app.openapi()["paths"]["/api/v1/forms/runtime-preview"]["post"]
    assert operation["security"]
    assert (
        operation["responses"]["200"]["headers"]["Cache-Control"]["schema"]["const"]
        == "private, no-store"
    )
    assert "SimulatedRuntimePreviewRequest" in app.openapi()["components"]["schemas"]


def test_frontend_palette_examples_validate_against_the_code_owned_catalog():
    import json
    from pathlib import Path

    from apps.forms.application.validation import FormValidator
    from apps.forms.domain.dto import FormDocuments
    from apps.forms.domain.fields import FIELD_DEFINITIONS

    examples = json.loads(Path("docs/examples/studio-primitives.json").read_text())
    assert {example["kind"] for example in examples} == set(FIELD_DEFINITIONS)
    for example in examples:
        result = FormValidator().validate(FormDocuments.model_validate(example["documents"]))
        assert result.valid, (example["kind"], result.issues)
