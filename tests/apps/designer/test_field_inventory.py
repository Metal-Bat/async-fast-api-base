"""Field inventory uses exact field identity and conservative consumer evidence."""

from apps.designer.application.field_inventory import analyze_fields
from apps.workflows.domain.dto import GraphBinding, GraphSnapshot, GraphStep, GraphTransition


def _form(properties, required=(), children=()):
    return {
        "data_schema": {"type": "object", "properties": properties, "required": list(required)},
        "render_schema": {"root": {"component": "group", "children": list(children)}},
        "localization": None,
        "checksum": "form-checksum",
    }


def test_unused_optional_and_notification_binding_are_distinct():
    graph = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(key="notify", type_code="NOTIFICATION"),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        bindings=[
            GraphBinding(
                step="notify",
                target_port="recipient",
                target_schema={"type": "string"},
                source_kind="REQUEST",
                source_path="/properties/email",
            )
        ],
        transitions=[
            GraphTransition(source="start", target="notify", outcome="ok"),
            GraphTransition(source="notify", target="finish", outcome="ok"),
        ],
    )
    result = analyze_fields(
        graph,
        {"start": ("form-v1", _form({"email": {"type": "string"}, "note": {"type": "string"}}))},
        locale="en",
    )
    by_path = {row.path: row for row in result.fields}
    assert by_path["/properties/email"].classification == "OPTIONAL_USED"
    assert by_path["/properties/note"].classification == "NO_DETECTED_CONSUMER"
    assert by_path["/properties/note"].suggestions[0].code == "REVIEW_UNUSED"


def test_calculation_transitively_feeds_workflow_threshold():
    form = _form(
        {"quantity": {"type": "integer"}, "line_total": {"type": "integer"}},
        children=(
            {"component": "number", "scope": "/properties/quantity"},
            {
                "component": "number",
                "scope": "/properties/line_total",
                "calculation": {"function": "sum", "scopes": ["/properties/quantity"]},
            },
        ),
    )
    graph = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        transitions=[
            GraphTransition(
                source="start",
                target="finish",
                outcome="ok",
                condition="request.line_total > 100",
            )
        ],
    )
    result = analyze_fields(graph, {"start": ("form-v1", form)}, locale="en")
    by_path = {row.path: row for row in result.fields}
    assert by_path["/properties/line_total"].classification == "DERIVED"
    assert any(
        edge.reason == "CALCULATION" for edge in by_path["/properties/quantity"].dependencies
    )
    assert any(edge.reason == "ROUTING" for edge in by_path["/properties/quantity"].dependencies)


def test_duplicate_labels_and_nested_item_scope_are_separate():
    form = _form(
        {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"quantity": {"type": "integer"}},
                },
            },
            "quantity": {"type": "integer"},
        },
        children=(
            {"component": "number", "scope": "/properties/quantity", "label": "Quantity"},
            {
                "component": "number",
                "scope": "/properties/items/items/properties/quantity",
                "label": "Quantity",
            },
        ),
    )
    result = analyze_fields(GraphSnapshot(), {"start": ("form-v1", form)}, locale="en")
    assert len(result.fields) == 2
    assert {row.path for row in result.fields} == {
        "/properties/quantity",
        "/properties/items/items/properties/quantity",
    }


def test_conditional_required_and_human_review_are_uses():
    graph = GraphSnapshot(
        steps=[
            GraphStep(
                key="review",
                type_code="HUMAN_TASK",
                form_ref="form-v1",
                field_policy={
                    "read": ["/properties/note"],
                    "write": [],
                    "required": ["/properties/justification"],
                    "hidden": [],
                },
            )
        ],
    )
    form = _form(
        {"note": {"type": "string"}, "justification": {"type": "string"}},
    )
    result = analyze_fields(graph, {"workflow/review": ("form-v1", form)}, locale="en")
    by_path = {row.path: row for row in result.fields}
    assert by_path["/properties/note"].classification == "OPTIONAL_USED"
    assert by_path["/properties/note"].dependencies[0].reason == "REVIEW"
    assert by_path["/properties/justification"].classification == "CONDITIONALLY_REQUIRED"


def test_opaque_handler_never_reports_unused_candidate():
    graph = GraphSnapshot(steps=[GraphStep(key="custom", type_code="CUSTOM_TASK")])
    result = analyze_fields(
        graph,
        {"start": ("form-v1", _form({"note": {"type": "string"}}))},
        locale="en",
    )
    assert not result.complete
    assert result.fields[0].classification == "UNKNOWN_ANALYSIS"
    assert not result.fields[0].suggestions


def test_inventory_route_is_documented_and_requires_login():
    from httpx import ASGITransport, AsyncClient

    from main import app

    app.openapi_schema = None
    operation = app.openapi()["paths"]["/api/v1/designer/field-inventory"]["post"]
    assert operation["security"]
    assert (
        "workflow_version_ref_id"
        in app.openapi()["components"]["schemas"]["FieldInventoryQuery"]["required"]
    )
    assert "200" in operation["responses"]
    assert "Cache-Control" in operation["responses"]["200"]["headers"]
    from apps.designer.domain.field_inventory import FieldInventoryResult
    from utils.presenter import SuccessResponse

    example = operation["responses"]["200"]["content"]["application/json"]["example"]
    assert SuccessResponse[FieldInventoryResult].model_validate(example).data.total == 0
    from utils.localized_docs import localized_openapi

    translated = localized_openapi(app, "fa")
    translated_operation = translated["paths"]["/api/v1/designer/field-inventory"]["post"]
    assert translated_operation["summary"] == "توضیح وابستگی فیلدها در نسخه دقیق گردش‌کار"
    assert "نسخه دقیق گردش‌کار" in translated_operation["description"]

    async def exercise():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.post("/api/v1/designer/field-inventory", json={})

    import anyio

    response = anyio.run(exercise)
    assert response.status_code == 401


def test_variant_rules_and_localized_labels_are_included():
    form = _form(
        {"approve": {"type": "boolean"}, "reason": {"type": "string"}},
    )
    form["localization"] = {
        "default_locale": "en",
        "catalogs": {
            "en": {"reason_label": {"text": "Reason"}},
            "fa": {"reason_label": {"text": "دلیل"}},
        },
    }
    form["variants"] = [
        {
            "key": "desktop",
            "render_schema": {
                "root": {
                    "component": "group",
                    "children": [
                        {
                            "component": "text",
                            "scope": "/properties/reason",
                            "messages": {"label": {"key": "reason_label"}},
                            "rules": [
                                {
                                    "scope": "/properties/approve",
                                    "effect": "require",
                                    "operator": "eq",
                                    "value": True,
                                }
                            ],
                        },
                    ],
                }
            },
        }
    ]
    result = analyze_fields(GraphSnapshot(), {"start": ("form-v1", form)}, locale="fa")
    by_path = {row.path: row for row in result.fields}
    assert by_path["/properties/reason"].label == "دلیل"
    assert by_path["/properties/reason"].classification == "CONDITIONALLY_REQUIRED"
    assert any(
        "/variants/0/render_schema" in item.location
        for item in by_path["/properties/approve"].dependencies
    )


def test_reused_human_form_does_not_inherit_start_request_binding():
    graph = GraphSnapshot(
        steps=[
            GraphStep(
                key="review",
                type_code="HUMAN_TASK",
                form_ref="form-v1",
                field_policy={"read": [], "write": [], "required": [], "hidden": []},
            )
        ],
        bindings=[
            GraphBinding(
                step="review",
                target_port="input",
                target_schema={"type": "string"},
                source_kind="REQUEST",
                source_path="/properties/code",
            )
        ],
    )
    form = _form({"code": {"type": "string"}})
    result = analyze_fields(
        graph,
        {"start": ("form-v1", form), "workflow/review": ("form-v1", form)},
        locale="en",
    )
    by_point = {row.collection_point: row for row in result.fields}
    assert any(item.reason == "STEP_PORT" for item in by_point["start"].dependencies)
    assert not any(item.reason == "STEP_PORT" for item in by_point["workflow/review"].dependencies)


def test_branch_only_human_requirement_is_conditional():
    graph = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(key="review", type_code="HUMAN_TASK", form_ref="review-form"),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        transitions=[
            GraphTransition(
                source="start",
                target="review",
                outcome="ok",
                condition="request.amount > 100",
            ),
            GraphTransition(source="start", target="finish", outcome="ok", is_default=True),
            GraphTransition(source="review", target="finish", outcome="ok"),
        ],
    )
    form = _form({"decision": {"type": "string"}}, required=("decision",))
    result = analyze_fields(graph, {"workflow/review": ("review-form", form)}, locale="en")
    assert result.fields[0].classification == "CONDITIONALLY_REQUIRED"


def test_action_required_field_and_summary_view_are_consumers():
    from apps.work_items.domain.task_contract import HumanTaskContract

    contract = HumanTaskContract.model_validate(
        {
            "default_view": "edit",
            "views": [
                {
                    "key": "edit",
                    "purpose": "edit",
                    "title": {"en": "Edit"},
                    "scopes": ["/properties/note"],
                }
            ],
            "actions": [
                {
                    "key": "approve",
                    "kind": "complete",
                    "outcome_key": "approved",
                    "title": {"en": "Approve"},
                    "required_scopes": ["/properties/reason"],
                }
            ],
        }
    )
    graph = GraphSnapshot(
        steps=[
            GraphStep(
                key="review", type_code="HUMAN_TASK", form_ref="form-v1", task_contract=contract
            ),
        ]
    )
    result = analyze_fields(
        graph,
        {
            "workflow/review": (
                "form-v1",
                _form(
                    {
                        "note": {"type": "string"},
                        "reason": {"type": "string"},
                    }
                ),
            )
        },
        locale="en",
    )
    by_path = {row.path: row for row in result.fields}
    assert by_path["/properties/note"].dependencies[0].reason == "REVIEW"
    assert by_path["/properties/reason"].classification == "CONDITIONALLY_REQUIRED"
    assert by_path["/properties/reason"].dependencies[0].reason == "ACTION_REQUIRED"


def test_prior_value_inheritance_prompts_repeat_review_without_removal_claim():
    from apps.work_items.domain.task_contract import HumanTaskContract

    contract = HumanTaskContract.model_validate(
        {
            "default_view": "edit",
            "inherit_previous": True,
            "views": [
                {
                    "key": "edit",
                    "purpose": "edit",
                    "title": {"en": "Edit"},
                    "scopes": ["/properties/code"],
                }
            ],
            "actions": [
                {"key": "done", "kind": "complete", "outcome_key": "done", "title": {"en": "Done"}}
            ],
        }
    )
    graph = GraphSnapshot(
        steps=[
            GraphStep(
                key="review", type_code="HUMAN_TASK", form_ref="form-v1", task_contract=contract
            ),
        ]
    )
    form = _form({"code": {"type": "string"}})
    result = analyze_fields(
        graph,
        {"start": ("form-v1", form), "workflow/review": ("form-v1", form)},
        locale="en",
    )
    review = next(row for row in result.fields if row.collection_point == "workflow/review")
    assert any(item.code == "REVIEW_REPEATED_ENTRY" for item in review.suggestions)
    assert "Confirm" in review.suggestions[-1].caveat
    assert result.summary.unique_field_definitions == 1
    assert result.summary.user_entry_occurrences == 2


def test_purchase_request_review_keeps_quantity_and_threshold_dependencies():
    form = _form(
        {
            "items": {
                "type": "array",
                "items": {"type": "object", "properties": {"quantity": {"type": "integer"}}},
            },
            "total": {"type": "integer"},
            "internal_note": {"type": "string"},
        },
        children=(
            {"component": "number", "scope": "/properties/items/items/properties/quantity"},
            {
                "component": "number",
                "scope": "/properties/total",
                "calculation": {
                    "function": "sum",
                    "scopes": ["/properties/items/items/properties/quantity"],
                },
            },
        ),
    )
    graph = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(
                key="approve", type_code="DECISION", config={"expression": "request.total > 1000"}
            ),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        transitions=[
            GraphTransition(source="start", target="approve", outcome="ok"),
            GraphTransition(source="approve", target="finish", outcome="ok"),
        ],
    )
    result = analyze_fields(graph, {"start": ("purchase-form", form)}, locale="en")
    by_path = {row.path: row for row in result.fields}
    quantity = by_path["/properties/items/items/properties/quantity"]
    assert quantity.classification == "OPTIONAL_USED"
    assert any(item.reason == "ROUTING" and item.via for item in quantity.dependencies)
    assert by_path["/properties/total"].classification == "DERIVED"
    assert by_path["/properties/internal_note"].suggestions[0].code == "REVIEW_UNUSED"
    assert result.summary.repeated_collection == 1


def test_read_only_review_is_use_without_new_user_entry():
    form = _form(
        {"receipt": {"type": "string"}},
        children=(
            {"component": "text", "scope": "/properties/receipt", "options": {"read_only": True}},
        ),
    )
    result = analyze_fields(GraphSnapshot(), {"start": ("form-v1", form)}, locale="en")
    row = result.fields[0]
    assert row.classification == "OPTIONAL_USED"
    assert row.dependencies[0].reason == "REVIEW"
    assert not row.user_entry
    assert result.summary.user_entry_occurrences == 0


def test_component_and_child_scope_identity_does_not_merge_same_label():
    form = _form(
        {"code": {"type": "string"}},
        children=({"component": "text", "scope": "/properties/code", "label": "Code"},),
    )
    result = analyze_fields(
        GraphSnapshot(),
        {
            "start": ("parent-form", form),
            "workflow/child/review": ("child-form", form),
        },
        locale="en",
    )
    assert len({row.identity for row in result.fields}) == 2
    assert len({row.label for row in result.fields}) == 1
    assert result.summary.unique_field_definitions == 2


def test_inventory_field_limit_returns_public_validation_issue():
    import pytest

    from utils.exceptions import ValidationDetailsException

    form = _form({f"field_{index}": {"type": "string"} for index in range(2049)})
    with pytest.raises(ValidationDetailsException) as exc:
        analyze_fields(GraphSnapshot(), {"start": ("form-v1", form)}, locale="en")
    assert exc.value.issues[0]["code"] == "field_inventory.field_limit"


def test_declared_port_sources_distinguish_constant_context_and_step_output():
    graph = GraphSnapshot(
        bindings=[
            GraphBinding(
                step="enrich",
                target_port="tenant",
                target_schema={"type": "string"},
                source_kind="CONTEXT",
                source_path="/properties/current_user/properties/id",
            ),
            GraphBinding(
                step="enrich",
                target_port="region",
                target_schema={"type": "string"},
                source_kind="CONSTANT",
                constant_value="north",
            ),
            GraphBinding(
                step="notify",
                target_port="body",
                target_schema={"type": "string"},
                source_kind="STEP_OUTPUT",
                source_step="enrich",
                source_port="summary",
                source_schema={"type": "string"},
            ),
        ]
    )
    result = analyze_fields(graph, {}, locale="en")
    inputs = {port.port: port for port in result.declared_ports if port.direction == "INPUT"}
    assert inputs["tenant"].source_kind == "CONTEXT"
    assert inputs["tenant"].source == "PROCESS_CONTEXT"
    assert inputs["region"].source_kind == "CONSTANT"
    assert inputs["region"].source == "CONSTANT"
    assert inputs["body"].source_kind == "STEP_OUTPUT"
    assert inputs["body"].source == "EARLIER_TASK_OUTPUT"
    assert any(
        port.direction == "OUTPUT" and port.port == "summary" for port in result.declared_ports
    )


def test_optional_field_validation_is_a_declared_consumer():
    result = analyze_fields(
        GraphSnapshot(),
        {
            "start": (
                "form-v1",
                _form(
                    {
                        "code": {
                            "type": "string",
                            "pattern": "^[A-Z]+$",
                        }
                    }
                ),
            )
        },
        locale="en",
    )
    assert result.fields[0].classification == "OPTIONAL_USED"
    assert result.fields[0].dependencies[0].reason == "VALIDATION"
    assert result.fields[0].dependencies[0].location.endswith("/pattern")


def test_whole_object_expression_suppresses_unused_claim():
    graph = GraphSnapshot(
        transitions=[
            GraphTransition(
                source="start", target="finish", outcome="ok", condition="request == null"
            ),
        ]
    )
    result = analyze_fields(
        graph,
        {"start": ("form-v1", _form({"note": {"type": "string"}}))},
        locale="en",
    )
    assert not result.complete
    assert result.fields[0].classification == "UNKNOWN_ANALYSIS"
    assert "whole_object_read" in result.diagnostics[0]


def test_author_business_rationale_is_separate_from_technical_reason():
    result = analyze_fields(
        GraphSnapshot(),
        {
            "start": (
                "form-v1",
                _form(
                    {
                        "purpose": {
                            "type": "string",
                            "description": "Budget owner entered this value.",
                            "x-business-rationale": "Required by purchasing policy P-12.",
                        }
                    }
                ),
            )
        },
        locale="en",
    )
    row = result.fields[0]
    assert row.author_description == "Budget owner entered this value."
    assert row.business_rationale == "Required by purchasing policy P-12."
    assert not any("purchasing policy" in item.explanation.lower() for item in row.dependencies)
