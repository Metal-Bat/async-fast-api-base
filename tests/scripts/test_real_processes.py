"""Business seed contracts differ from lifecycle/load demonstrations."""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker
from scripts.demo.real_processes import real_form, real_graph, real_sample
from scripts.demo.templates import CATALOG, DETAILS

from apps.forms.application.validation import FormValidator
from core.ref_id import create_ref_id


def reference(key):
    return create_ref_id(uuid5(NAMESPACE_URL, key), 1)


def test_business_forms_keep_domain_inputs_without_forcing_a_budget_for_nonfinancial_work():
    for template in CATALOG:
        form = real_form(template)
        validation = FormValidator().validate(form, publication=True)
        assert validation.valid, (template.key, validation.issues)
        sample = real_sample(template, 0, datetime(2026, 10, 27, tzinfo=UTC))
        errors = list(
            Draft202012Validator(form.data_schema, format_checker=FormatChecker()).iter_errors(
                sample
            )
        )
        assert not errors, [(error.json_path, error.message) for error in errors]
        assert all(key in form.data_schema["properties"] for key, *_ in DETAILS[template.key])
        if template.key in {
            "leave",
            "service",
            "onboarding",
            "access",
            "incident",
            "equipment",
            "quality",
        }:
            assert "amount" not in form.data_schema["properties"]
            assert "line_items" not in sample
        else:
            assert isinstance(sample["amount"], str)
            assert form.data_schema["properties"]["amount"]["type"] == "string"
            assert "currency" in form.data_schema["required"]
    quality = next(item for item in CATALOG if item.key == "quality")
    assert "inspection_note" not in real_sample(quality, 0, datetime(2026, 10, 27, tzinfo=UTC))


def test_business_routing_uses_responsible_people_and_invoice_identity_without_fake_waits():
    refs = {
        (code, "1"): reference(code)
        for code in ["START", "FINISH", "HUMAN_TASK", "SUBPROCESS", "EVENT_WAIT"]
    }
    actors = {
        department + ".reviewer": reference(department)
        for department in [
            "people",
            "finance",
            "operations",
            "technology",
            "legal",
            "support",
            "quality",
        ]
    }
    for template in CATALOG:
        graph = real_graph(
            template,
            refs,
            reference("form"),
            actors,
            reference("requester"),
            reference("legal-child"),
        )
        targets = [target.user_ref for target in graph.targets if target.step != "correction"]
        assert reference("requester") not in targets
        if len(targets) > 1:
            assert len(set(targets)) > 1
        assert not any(step.type_code in {"TRANSFORM", "TIMER"} for step in graph.steps)
        assert not any(
            edge.condition and "process.priority" in edge.condition for edge in graph.transitions
        )
        if template.key == "invoice":
            assert (
                next(
                    binding
                    for binding in graph.bindings
                    if binding.target_port == "correlation_key"
                ).source_path
                == "/invoice_number"
            )
