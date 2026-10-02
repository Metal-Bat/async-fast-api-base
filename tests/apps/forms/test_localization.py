"""Public form catalog and client conformance behavior."""

import hashlib
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from apps.clients.domain.contracts import ClientContext
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments


def catalog_documents():
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[2] / "fixtures/forms/localization-v1.json"
    return json.loads(fixture.read_text())["form"]


def test_localized_resolution_preserves_canonical_data_and_design_revision():
    doc = FormDocuments.model_validate(catalog_documents())
    before = deepcopy(doc.model_dump())
    fa = resolve_form_documents(doc, ClientContext.legacy(), locale="fa-IR")
    en = resolve_form_documents(doc, ClientContext.legacy(), locale="en-US")
    assert fa.render_schema["root"]["label"] == "ایمیل"
    assert en.render_schema["root"]["label"] == "Email"
    assert fa.localization is not None
    assert fa.localization.resolved_locale == "fa"
    assert fa.render_schema["root"]["formatting"]["direction"] == "ltr"
    assert fa.revision == en.revision
    assert doc.model_dump() == before
    assert FormValidator().validate(doc, {"email": "ada@example.test"}).valid


def test_draft_gaps_are_reported_but_publication_requires_translations():
    payload = catalog_documents()
    payload["localization"]["catalogs"]["fa"] = {}
    doc = FormDocuments.model_validate(payload)
    draft = FormValidator().validate(doc)
    assert draft.valid
    assert draft.warnings[0].code == "localization.missing"
    published = FormValidator().validate(doc, publication=True)
    assert not published.valid
    assert published.issues[0].pointer == "/localization/catalogs/fa/email"
    resolved = resolve_form_documents(doc, ClientContext.legacy(), locale="fa")
    assert resolved.localization is not None
    assert resolved.localization.messages["email"].locale == "en"
    assert resolved.render_schema["root"]["label"] == "Email"


def test_source_changes_mark_translation_stale_without_rewriting_it():
    payload = catalog_documents()
    payload["localization"]["catalogs"]["en"]["email"]["text"] = "Work email"
    doc = FormDocuments.model_validate(payload)
    assert FormValidator().validate(doc).warnings[0].code == "localization.stale"
    assert not FormValidator().validate(doc, publication=True).valid
    result = resolve_form_documents(doc, ClientContext.legacy(), locale="fa")
    assert result.render_schema["root"]["label"] == "Work email"
    assert doc.localization is not None
    assert doc.localization.catalogs["fa"]["email"].text == "ایمیل"


@pytest.mark.parametrize(
    "text",
    [
        "{user.name}",
        "{name!r}",
        "{name:100000}",
        "{missing}",
        {"one": "One"},
        {"one": "One", "other": "{count}", "few": "Few"},
    ],
)
def test_invalid_message_profile_is_rejected(text):
    payload = catalog_documents()
    payload["localization"]["catalogs"]["en"]["email"]["text"] = text
    with pytest.raises(ValidationError):
        FormDocuments.model_validate(payload)


def test_incompatible_parameter_shapes_are_not_draft_warnings():
    payload = catalog_documents()
    payload["localization"]["catalogs"]["fa"]["email"].update(
        text="{count}", parameters={"count": "integer"}
    )
    result = FormValidator().validate(FormDocuments.model_validate(payload))
    assert not result.valid
    assert result.issues[0].code == "localization.parameters"


def test_legacy_checksum_does_not_gain_null_catalog():
    payload = {
        "data_schema": {"type": "object"},
        "render_schema": {"root": {"component": "vertical"}},
    }
    doc = FormDocuments.model_validate(payload)
    original = {"data_dialect": doc.data_dialect, "render_dialect": doc.render_dialect, **payload}
    checksum = hashlib.sha256(
        json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert FormValidator().validate(doc).checksum == checksum


@pytest.mark.parametrize(
    ("formatting", "value", "canonical", "display"),
    [
        ({"kind": "date", "numbering": "arabext"}, "۲۰۲۶-۱۰-۰۱", "2026-10-01", "۲۰۲۶-۱۰-۰۱"),
        (
            {"kind": "datetime", "timezone": "Asia/Tehran", "numbering": "arabext"},
            "۲۰۲۶-۱۰-۰۱T۱۲:۳۰:۰۰+۰۳:۳۰",
            "2026-10-01T09:00:00Z",
            "۲۰۲۶-۱۰-۰۱T۱۲:۳۰:۰۰+۰۳:۳۰",
        ),
        (
            {"kind": "decimal", "numbering": "arabext", "decimal_places": 3, "currency": "IRR"},
            "۱۲۳۴٫۵۶۷",
            "1234.567",
            "۱۲۳۴٫۵۶۷ IRR",
        ),
        (
            {"kind": "decimal"},
            "9007199254740993.001",
            "9007199254740993.001",
            "9007199254740993.001",
        ),
        (
            {"kind": "text", "direction": "ltr"},
            "ada@example.test",
            "ada@example.test",
            "ada@example.test",
        ),
    ],
)
def test_field_formatting_is_exact(formatting, value, canonical, display):
    from apps.forms.application.formatting import format_value
    from apps.forms.domain.localization import FieldFormatting

    result = format_value(value, FieldFormatting.model_validate(formatting))
    assert result == (canonical, display)


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("date", "1405/07/09"),
        ("date", "2026-02-30"),
        ("datetime", "2026-10-01T12:30:00"),
        ("decimal", "1,234.56"),
        ("decimal", "NaN"),
        ("decimal", "1.001"),
    ],
)
def test_ambiguous_or_lossy_input_is_rejected(kind, value):
    from apps.forms.application.formatting import format_value
    from apps.forms.domain.localization import FieldFormatting

    with pytest.raises(ValueError):
        format_value(
            value, FieldFormatting(kind=kind, decimal_places=2 if kind == "decimal" else None)
        )


@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_integer_message_arguments_reject_coercion(value):
    payload = catalog_documents()
    payload["localization"]["catalogs"] = {
        "en": {
            "email": {
                "text": {"one": "One item", "other": "{count} items"},
                "parameters": {"count": "integer"},
            }
        }
    }
    payload["localization"]["required_locales"] = ["en"]
    payload["render_schema"]["root"]["messages"]["label"]["arguments"] = {"count": value}
    try:
        doc = FormDocuments.model_validate(payload)
    except ValidationError:
        return
    assert not FormValidator().validate(doc).valid


def test_decimal_submission_requires_canonical_string_without_rounding():
    doc = FormDocuments(
        data_schema={"type": "object", "properties": {"amount": {"type": "string"}}},
        render_schema={
            "root": {
                "component": "text",
                "scope": "/properties/amount",
                "formatting": {"kind": "decimal", "decimal_places": 2, "numbering": "arabext"},
            }
        },
    )
    assert FormValidator().validate(doc, {"amount": "1234.56"}).valid
    for value in ("۱۲۳۴٫۵۶", "1,234.56", "1234.567", "NaN"):
        result = FormValidator().validate(doc, {"amount": value})
        assert not result.valid
        assert result.issues[0].pointer == "/data/amount"


@pytest.mark.anyio
async def test_authorized_preview_resolves_locale_and_normalizes_samples(monkeypatch):
    from uuid import uuid7

    from httpx import ASGITransport, AsyncClient

    from apps.users.domain.entity import UserEntity
    from core.deps import get_current_client_context, get_current_user
    from main import app

    user = UserEntity(
        id=uuid7(), username="localization-designer", hashed_password="hash", is_superuser=True
    )
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)
    monkeypatch.setitem(app.dependency_overrides, get_current_client_context, ClientContext.legacy)
    payload = catalog_documents()
    payload["format_values"] = [{"node_pointer": "/root", "value": "ada@example.test"}]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post(
            "/api/v1/forms/preview", json=payload, headers={"Accept-Language": "fa-IR"}
        )
        assert result.status_code == 200
        data = result.json()["data"]
        assert data["localization"]["resolved_locale"] == "fa"
        assert data["render_schema"]["root"]["label"] == "ایمیل"
        assert data["formatted_values"][0]["canonical"] == "ada@example.test"
        assert result.headers["cache-control"] == "private, no-store"
        payload["format_values"][0]["node_pointer"] = "/root/missing"
        invalid = await client.post("/api/v1/forms/preview", json=payload)
        assert invalid.status_code == 200
        assert invalid.json()["data"]["issues"][0]["code"] == "localization.format_value"


def test_runtime_read_relocalizes_pinned_snapshot_without_changing_interaction():
    from apps.forms.application.localization import localize_snapshot
    from core.i18n import use_language

    doc = FormDocuments.model_validate(catalog_documents())
    design = resolve_form_documents(doc, ClientContext.legacy(), locale="en")
    snapshot = {
        "variant_key": "shared",
        "design_revision": design.revision,
        "render_schema": design.render_schema,
        "page_settings": design.page_settings,
        "interaction_revision": 7,
        "client": {"kind": "DESKTOP"},
    }
    before = deepcopy(snapshot)
    with use_language("fa-IR"):
        translated = localize_snapshot(snapshot, doc)
    assert translated is not None
    assert translated["render_schema"]["root"]["label"] == "ایمیل"
    assert translated["interaction_revision"] == 7
    assert translated["design_revision"] == snapshot["design_revision"]
    assert translated["client"] == snapshot["client"]
    assert snapshot == before


def test_shared_client_conformance_vectors():
    from pathlib import Path

    from apps.forms.application.formatting import format_value
    from apps.forms.application.localization import render_message
    from apps.forms.domain.localization import FieldFormatting, ResolvedMessage

    fixture = json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures/forms/localization-v1.json").read_text()
    )
    for case in fixture["format_cases"]:
        assert format_value(case["input"], FieldFormatting.model_validate(case["profile"])) == (
            case["canonical"],
            case["display"],
        )
    for case in fixture["plural_cases"]:
        message = ResolvedMessage(
            locale=case["locale"],
            text=case["text"],
            parameters={"count": "integer"},
            source_revision="0" * 64,
        )
        assert render_message(message, {"count": case["count"]}) == case["expected"]


def test_catalog_roles_preserve_option_values_and_action_outcomes():
    payload = catalog_documents()
    payload["data_schema"]["properties"]["choice"] = {"type": "string", "enum": ["approved"]}
    roles = [
        "label",
        "placeholder",
        "help",
        "description",
        "action",
        "confirmation",
        "loading",
        "error",
        "empty",
        "accessibility_label",
        "accessibility_description",
        "validation",
    ]
    payload["render_schema"] = {
        "outcomes": ["approve"],
        "root": {
            "component": "vertical",
            "children": [
                {
                    "component": "choice",
                    "scope": "/properties/choice",
                    "messages": {role: {"key": "email"} for role in roles},
                    "option_messages": [{"value": "approved", "message": {"key": "email"}}],
                },
                {
                    "component": "action",
                    "outcome": "approve",
                    "messages": {"action": {"key": "email"}},
                },
            ],
        },
    }
    doc = FormDocuments.model_validate(payload)
    assert FormValidator().validate(doc, publication=True).valid
    resolved = resolve_form_documents(doc, ClientContext.legacy(), locale="fa")
    choice, action = resolved.render_schema["root"]["children"]
    assert set(choice["localized_text"]) == set(roles)
    assert choice["localized_options"] == [{"value": "approved", "label": "ایمیل"}]
    assert action["outcome"] == "approve"
    assert FormValidator().validate(doc, {"choice": "approved"}).valid
    assert not FormValidator().validate(doc, {"choice": "ایمیل"}).valid


def test_missing_required_gaps_cannot_hide_behind_issue_limit():
    payload = catalog_documents()
    payload["localization"]["required_locales"] = ["en"]
    payload["localization"]["catalogs"]["en"].update(
        {f"a{i:03}": {"text": "Optional"} for i in range(40)}
    )
    payload["render_schema"]["root"]["messages"]["label"]["key"] = "zz_missing"
    doc = FormDocuments.model_validate(payload)
    assert len(FormValidator().validate(doc).warnings) == 32
    result = FormValidator().validate(doc, publication=True)
    assert not result.valid
    assert any(issue.pointer.endswith("/en/zz_missing") for issue in result.issues)


def test_localization_openapi_is_typed_and_translated():
    from main import app
    from utils.localized_docs import localized_openapi

    app.openapi_schema = None
    schema = app.openapi()
    localized = localized_openapi(app, "fa")
    operation = schema["paths"]["/api/v1/forms/preview"]["post"]
    assert any(
        p["name"] == "Accept-Language" and p["in"] == "header" for p in operation["parameters"]
    )
    assert (
        operation["responses"]["200"]["headers"]["Cache-Control"]["schema"]["const"]
        == "private, no-store"
    )
    assert operation["security"]
    models = schema["components"]["schemas"]
    assert models["FormLocalization"]["properties"]["dialect"]["const"] == "bpms.messages/1"
    from apps.forms.domain.dto import RenderDocument

    render_meta = RenderDocument.model_json_schema()
    assert render_meta["$defs"]["FieldFormatting"]["properties"]["calendar"]["const"] == "gregory"
    assert (
        localized["components"]["schemas"]["FormDocuments"]["properties"]["localization"][
            "description"
        ]
        != models["FormDocuments"]["properties"]["localization"]["description"]
    )
    assert (
        localized["paths"]["/api/v1/forms/preview"]["post"]["description"]
        != operation["description"]
    )


def test_localized_variants_cannot_alias_the_shared_snapshot_identity():
    payload = catalog_documents()
    payload["variants"] = [
        {
            "key": "shared",
            "priority": 10,
            "kind": "DESKTOP",
            "render_schema": {"root": {"component": "vertical"}},
        }
    ]
    assert not FormValidator().validate(FormDocuments.model_validate(payload)).valid


def test_canonical_formatting_respects_prefix_items_and_repeated_fields():
    doc = FormDocuments(
        data_schema={
            "type": "object",
            "properties": {
                "values": {
                    "type": "array",
                    "prefixItems": [{"type": "string"}],
                    "items": {"type": "string"},
                }
            },
        },
        render_schema={
            "root": {
                "component": "repeater",
                "scope": "/properties/values",
                "children": [
                    {
                        "component": "text",
                        "scope": "/properties/values/items",
                        "formatting": {"kind": "decimal", "decimal_places": 2},
                    }
                ],
            }
        },
    )
    assert FormValidator().validate(doc, {"values": ["header", "1.00", "2.50"]}).valid
    result = FormValidator().validate(doc, {"values": ["header", "1.00", "۲٫۵۰"]})
    assert not result.valid
    assert result.issues[0].pointer == "/data/values/2"
