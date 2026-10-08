"""Server-resolved behavior flags do not disclose authored expressions."""

from typing import Any, cast

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.runtime import runtime_projection
from apps.users.domain.entity import UserEntity


def test_runtime_flags_use_canonical_dependencies_and_keep_hidden_bindings_private():
    """Public flags follow the pinned rule while hidden data remains undisclosed."""
    render = {
        "dialect": "bpms.render/1",
        "root": {
            "component": "vertical",
            "children": [
                {
                    "component": "text",
                    "scope": "/properties/amount",
                    "rules": [
                        {
                            "scope": "/properties/secret",
                            "operator": "eq",
                            "value": True,
                            "effect": "disable",
                        },
                        {
                            "scope": "/properties/secret",
                            "operator": "eq",
                            "value": True,
                            "effect": "require",
                        },
                    ],
                },
                {
                    "component": "calculated",
                    "scope": "/properties/total",
                    "calculation": {
                        "function": "sum",
                        "scopes": ["/properties/amount"],
                        "override_permission": "forms.override",
                    },
                },
            ],
        },
    }
    schema = {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "total": {"type": "number"},
            "secret": {"type": "boolean"},
        },
    }
    scopes = {"/properties/amount", "/properties/total"}
    result = runtime_projection(
        {"amount": 2, "total": 2, "secret": True},
        {},
        {},
        schema,
        render,
        {"read": list(scopes), "write": list(scopes), "hidden": ["/properties/secret"]},
        scopes,
        scopes,
        set(),
        {"forms.override"},
    )
    nodes = result["render_schema"]["root"]["children"]
    assert nodes[0]["runtime_state"]["enabled"] is False
    assert nodes[0]["runtime_state"]["required"] is True
    assert nodes[1]["runtime_state"]["overridable"] is True
    assert "rules" not in nodes[0]
    assert "calculation" not in nodes[1]
    assert "secret" not in result["data"]


def test_readonly_actor_has_no_override_affordance_and_hidden_rule_hides_control():
    """Read-only display cannot infer calculation override permission."""
    render = {
        "dialect": "bpms.render/1",
        "root": {
            "component": "calculated",
            "scope": "/properties/total",
            "rules": [
                {"scope": "/properties/flag", "operator": "eq", "value": True, "effect": "hide"}
            ],
            "calculation": {"override_permission": "forms.override"},
        },
    }
    result = runtime_projection(
        {"total": 5, "flag": True},
        {},
        {},
        {"properties": {"total": {"type": "number"}}},
        render,
        None,
        {"/properties/total"},
        set(),
        set(),
        {"forms.override"},
    )
    state = result["render_schema"]["root"]["runtime_state"]
    assert state["visible"] is False
    assert state["overridable"] is False


def test_named_task_options_select_the_authorized_view_contract():
    """The optional named-view selector is represented in the generated contract."""
    from main import app

    app.openapi_schema = None
    operation = app.openapi()["paths"]["/api/v1/work-items/{ref_id}/options"]["post"]
    key = next(parameter for parameter in operation["parameters"] if parameter["name"] == "key")
    assert key["in"] == "query" and not key["required"]


@pytest.mark.anyio
async def test_task_runtime_uses_pinned_rules_after_display_metadata_is_filtered(monkeypatch):
    """An ordinary task read resolves rules without leaking the hidden dependency."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid7

    from apps.forms.application.runtime import display_render
    from apps.forms.domain.dto import FormDocuments
    from apps.work_items.application.service import WorkItemService

    scope = "/properties/amount"
    render = {
        "dialect": "bpms.render/1",
        "root": {
            "component": "number",
            "scope": scope,
            "rules": [
                {
                    "scope": "/properties/secret",
                    "operator": "eq",
                    "value": True,
                    "effect": "disable",
                }
            ],
        },
    }
    documents = FormDocuments(
        data_schema={
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "secret": {"type": "boolean"},
            },
        },
        render_schema=render,
    )
    form = SimpleNamespace(**documents.model_dump(), id=uuid7(), version=1, number=1)
    actor = SimpleNamespace(id=uuid7())
    item = SimpleNamespace(id=uuid7(), version=1, status="CLAIMED", claimed_by_user_id=actor.id)
    submission = SimpleNamespace(
        id=uuid7(),
        version=1,
        form_version_id=form.id,
        data={"amount": 5, "secret": True},
        item_identity={},
        override_provenance={},
        design_snapshot={"render_schema": render},
        correction_source_submission_id=None,
    )
    policy = {"read": [scope], "write": [scope], "hidden": ["/properties/secret"]}
    view = SimpleNamespace(
        view_key="review",
        purpose="edit",
        before_data=None,
        before_item_identity=None,
        render_schema=display_render(render, policy, {scope}),
        actions=[],
    )
    assert "rules" not in view.render_schema["root"]
    session = SimpleNamespace(get=AsyncMock(return_value=form))
    service = WorkItemService(cast(AsyncSession, cast(Any, session)))
    service.get = AsyncMock(return_value=item)
    service.task_view = AsyncMock(return_value=view)
    service.submission = AsyncMock(return_value=submission)
    service._step = AsyncMock(return_value=SimpleNamespace(field_policy=policy, task_contract=None))
    monkeypatch.setattr(
        "apps.users.application.authorization.user_permissions", AsyncMock(return_value=set())
    )
    runtime = await service.runtime_state(
        "opaque/task", cast(UserEntity, cast(Any, actor)), "review"
    )
    assert runtime.render_schema["root"]["runtime_state"]["enabled"] is False
    assert runtime.data == {"amount": 5}
    assert "rules" not in runtime.render_schema["root"]
