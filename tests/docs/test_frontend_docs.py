"""Check documentation against the API contract rather than prose snapshots."""

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from docs.tools.generate_response_dtos import note, render_pages
from jsonschema import Draft202012Validator, FormatChecker

from apps.requests.domain.dto import BusinessRequestCreateDTO, BusinessRequestSubmitDTO
from apps.work_items.domain.dto import WorkItemCompleteDTO

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def schema():
    from main import app

    return app.openapi()


def test_curated_requests_and_responses_match_actual_operations(schema) -> None:
    fixture = json.loads((ROOT / "docs/examples/frontend-journey.json").read_text())
    for step in fixture["steps"]:
        operation = schema["paths"][step["path"]][step["method"]]
        if "request" in step:
            request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
            Draft202012Validator(
                {**request_schema, "components": schema["components"]},
                format_checker=FormatChecker(),
            ).validate(step["request"])
        response_schema = operation["responses"][str(step["status"])]["content"][
            "application/json"
        ]["schema"]
        Draft202012Validator(
            {**response_schema, "components": schema["components"]}, format_checker=FormatChecker()
        ).validate(step["response"])


def test_journey_values_follow_dto_and_error_contracts() -> None:
    from apps.forms.application.validation import FormValidator
    from apps.forms.domain.dto import FormDocuments
    from utils.errors import CommonError

    fixture = json.loads((ROOT / "docs/examples/frontend-journey.json").read_text())
    steps = {step["key"]: step for step in fixture["steps"]}
    documents = FormDocuments.model_validate(fixture["form_contract"])
    BusinessRequestCreateDTO.model_validate(steps["create"]["request"])
    BusinessRequestSubmitDTO.model_validate(steps["submit"]["request"])
    completed = WorkItemCompleteDTO.model_validate(steps["complete"]["request"])
    view = steps["view"]["response"]["data"]
    assert completed.outcome_key == view["actions"][0]["outcome_key"]
    assert view["actions"][0]["kind"] == "complete"
    assert steps["stale"]["response"]["code"] == CommonError.VERSION_CONFLICT.number
    assert steps["invalid"]["response"]["code"] == CommonError.VALIDATION_FAILED.number
    # The sample form used by the process integration fixtures declares amount as a string.
    for key in ("create", "save", "complete"):
        assert isinstance(steps[key]["request"]["data"]["amount"], str)
        assert FormValidator().validate(documents, steps[key]["request"]["data"]).valid
    invalid = FormValidator().validate(documents, {})
    assert not invalid.valid
    assert steps["invalid"]["response"]["data"]["issues"] == [
        issue.model_dump(mode="json") for issue in invalid.issues
    ]


def test_response_scenarios_match_their_dtos() -> None:
    from apps.ai.domain.dto import AIToolApprovalDTO
    from apps.processes.domain.dto import ProcessDTO
    from apps.work_items.domain.dto import WorkItemDTO
    from utils.pagination import Page
    from utils.presenter import PageResponse, SuccessResponse
    from utils.select import SelectOption

    examples = re.findall(
        r"```json\n(.*?)\n```", (ROOT / "docs/api/response-scenarios.md").read_text(), re.DOTALL
    )
    models = [
        SuccessResponse[WorkItemDTO],
        SuccessResponse[ProcessDTO],
        SuccessResponse[ProcessDTO],
        SuccessResponse[AIToolApprovalDTO],
        PageResponse[Page[SelectOption[str]]],
    ]
    for model, example in zip(models, examples, strict=True):
        model.model_validate_json(example)


def test_generated_references_are_current(schema) -> None:
    for filename, expected in render_pages(schema).items():
        assert (ROOT / "docs/reference/responses" / filename).read_text() == expected, filename


def test_documentation_links_are_portable_and_targets_exist() -> None:
    failures = []
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
        text = re.sub(r"```.*?```", "", path.read_text(), flags=re.DOTALL)
        assert "[[" not in text, f"Obsidian-only link in {path.relative_to(ROOT)}"
        for target in re.findall(r"\[[^\]\n]+\]\(([^)]+)\)", text):
            url = urlsplit(target.strip("<>"))
            if url.scheme or url.netloc or not url.path:
                continue
            destination = (path.parent / unquote(url.path)).resolve()
            if not destination.exists():
                failures.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not failures, "\n".join(failures)


def test_reference_does_not_invent_business_examples() -> None:
    rendered = note(
        "UnreviewedResource",
        {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
        ["GET /resource"],
        {},
    )

    assert '"status": "example"' not in rendered
    assert "No reviewed business example" in rendered
