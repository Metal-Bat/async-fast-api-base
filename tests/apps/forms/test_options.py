"""Versioned option sources preserve canonical keys and reject stale selections."""

from unittest.mock import Mock

import pytest

from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments


def dependent_document():
    return FormDocuments(
        data_schema={
            "type": "object",
            "properties": {
                "country": {"type": "string", "enum": ["IR", "GB"]},
                "city": {"type": "integer"},
            },
        },
        render_schema={
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "choice",
                        "scope": "/properties/country",
                        "source": {"kind": "schema"},
                    },
                    {
                        "component": "choice",
                        "scope": "/properties/city",
                        "source": {
                            "kind": "custom",
                            "dependencies": {"country": "/properties/country"},
                            "items": [
                                {"key": 1, "value": "Tehran", "matches": {"country": "IR"}},
                                {"key": 2, "value": "London", "matches": {"country": "GB"}},
                            ],
                        },
                    },
                ],
            }
        },
    )


def test_dependent_keys_are_validated_against_current_parent():
    doc = dependent_document()
    assert FormValidator().validate(doc, {"country": "IR", "city": 1}).valid
    result = FormValidator().validate(doc, {"country": "GB", "city": 1})
    assert not result.valid
    assert result.issues[0].code == "source.membership"
    assert result.issues[0].pointer == "/data/city"


def test_unknown_source_dependency_is_rejected_before_save():
    doc = dependent_document()
    doc.render_schema["root"]["children"][1]["source"]["dependencies"]["country"] = (
        "/properties/secret"
    )
    result = FormValidator().validate(doc)
    assert not result.valid
    assert result.issues[0].code == "source.dependency"


@pytest.mark.anyio
async def test_options_filter_selected_keys_and_preserve_scalar_types():
    from apps.forms.application.options import OptionService, decode_choice_key
    from apps.forms.domain.options import OptionQuery
    from apps.users.domain.entity import UserEntity

    result = await OptionService(Mock()).resolve(
        dependent_document(),
        OptionQuery(node_pointer="/root/children/1", data={"country": "IR"}, generation=3),
        UserEntity(username="test", hashed_password="hash"),
    )
    assert result.generation == 3 and result.state == "READY"
    assert result.items[0].model_dump() == {"key": "json:1", "value": "Tehran"}
    assert decode_choice_key(result.items[0].key) == 1
    assert result.dependencies == {"country": "IR"}
    empty = await OptionService(Mock()).resolve(
        dependent_document(),
        OptionQuery(node_pointer="/root/children/1", data={}, generation=4),
        UserEntity(username="test", hashed_password="hash"),
    )
    assert empty.state == "BLOCKED" and empty.items == []


@pytest.mark.parametrize("value", [1, True, "1", "json:1", 1.5])
def test_wire_key_encoding_is_reversible_and_type_preserving(value):
    from apps.forms.application.options import decode_choice_key, encode_choice_key

    decoded = decode_choice_key(encode_choice_key(value))
    assert type(decoded) is type(value) and decoded == value


@pytest.mark.anyio
async def test_response_fingerprint_covers_locale_rows_and_predicate_data(monkeypatch):
    from apps.forms.application.options import OptionService
    from apps.forms.domain.options import OptionQuery
    from apps.users.domain.entity import UserEntity
    from core.i18n import use_language

    doc = dependent_document()
    doc.data_schema["properties"]["enabled"] = {"type": "boolean"}
    doc.render_schema["root"]["children"][1]["source"]["enabled_when"] = "request.enabled"
    actor = UserEntity(username="test", hashed_password="hash")
    service = OptionService(Mock())

    async def resolve(data, rows=None):
        return await service.resolve(
            doc,
            OptionQuery(node_pointer="/root/children/1", data=data, row_indices=rows or []),
            actor,
        )

    with use_language("en"):
        ready = await resolve({"country": "IR", "enabled": True})
        blocked = await resolve({"country": "IR", "enabled": False})
        missing = await resolve({"country": "IR"})
        row = await resolve({"country": "IR", "enabled": True}, [1])
    with use_language("fa"):
        localized = await resolve({"country": "IR", "enabled": True})
    assert ready.state == "READY" and blocked.state == missing.state == "BLOCKED"
    assert len({x.dependency_fingerprint for x in [ready, blocked, missing, row, localized]}) == 5
    assert localized.locale == "fa"


@pytest.mark.anyio
async def test_revoked_remote_host_is_rejected_without_fetch(monkeypatch):
    from apps.forms.application.options import OptionService
    from apps.forms.domain.options import OptionQuery
    from apps.users.domain.entity import UserEntity
    from core.settings import settings
    from utils.exceptions import ValidationDetailsException

    doc = dependent_document()
    doc.render_schema["root"]["children"][0]["source"] = {
        "kind": "remote",
        "url": "https://options.example/countries",
    }
    monkeypatch.setattr(settings, "FORM_CLIENT_OPTION_URLS", ["https://options.example/countries"])
    assert FormValidator().validate(doc).valid
    monkeypatch.setattr(settings, "FORM_CLIENT_OPTION_URLS", [])
    with pytest.raises(ValidationDetailsException):
        await OptionService(Mock()).resolve(
            doc,
            OptionQuery(node_pointer="/root/children/0"),
            UserEntity(username="test", hashed_password="hash"),
        )


def test_nullable_schema_choice_preserves_missing_and_null_without_default_insertion():
    doc = FormDocuments(
        data_schema={
            "type": "object",
            "properties": {
                "choice": {"type": ["string", "null"], "enum": ["a", None], "default": "a"}
            },
        },
        render_schema={
            "root": {
                "component": "choice",
                "scope": "/properties/choice",
                "source": {"kind": "schema"},
            }
        },
    )
    for data in [{}, {"choice": None}, {"choice": "a"}]:
        before = data.copy()
        assert FormValidator().validate(doc, data).valid
        assert data == before


def test_repeated_dependencies_cannot_bind_an_unrelated_nested_collection():
    doc = FormDocuments(
        data_schema={
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "left": {"type": "array", "items": {"type": "string"}},
                            "right": {"type": "array", "items": {"type": "string", "enum": ["x"]}},
                        },
                    },
                }
            },
        },
        render_schema={
            "root": {
                "component": "choice",
                "scope": "/properties/rows/items/properties/right/items",
                "source": {
                    "kind": "schema",
                    "dependencies": {"parent": "/properties/rows/items/properties/left/items"},
                },
            }
        },
    )
    result = FormValidator().validate(doc)
    assert not result.valid


@pytest.mark.anyio
async def test_pydantic_enum_and_literal_use_the_canonical_schema():
    from enum import StrEnum
    from typing import Literal

    from pydantic import BaseModel

    from apps.forms.application.options import OptionService, decode_choice_key
    from apps.forms.domain.options import OptionQuery
    from apps.users.domain.entity import UserEntity

    class Country(StrEnum):
        IR = "IR"
        GB = "GB"

    class Data(BaseModel):
        country: Country
        priority: Literal[1, 2]

    doc = FormDocuments(
        data_schema=Data.model_json_schema(),
        render_schema={
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "choice",
                        "scope": f"/properties/{name}",
                        "source": {"kind": "schema"},
                    }
                    for name in ("country", "priority")
                ],
            }
        },
    )
    assert FormValidator().validate(doc, {"country": "IR", "priority": 1}).valid
    result = await OptionService(Mock()).resolve(
        doc,
        OptionQuery(node_pointer="/root/children/1"),
        UserEntity(username="test", hashed_password="hash"),
    )
    assert [decode_choice_key(x.key) for x in result.items] == [1, 2]


def test_untyped_multiple_source_rejected_before_submission():
    doc = FormDocuments(
        data_schema={"type": "object", "properties": {"values": {"type": "array", "items": {}}}},
        render_schema={
            "root": {
                "component": "choice",
                "scope": "/properties/values",
                "source": {"kind": "custom", "items": [{"key": "x", "value": "X"}]},
            }
        },
    )
    assert not FormValidator().validate(doc).valid


def test_explicit_domain_source_cannot_disagree_with_variant_implicit_source():
    from apps.forms.domain.dto import FormDesignVariantDTO

    doc = FormDocuments(
        data_schema={
            "type": "object",
            "properties": {"person": {"type": "string"}, "group": {"type": "string"}},
        },
        render_schema={
            "root": {
                "component": "user",
                "scope": "/properties/person",
                "source": {
                    "kind": "domain",
                    "selector": "users",
                    "dependencies": {"group_ref": "/properties/group"},
                },
            }
        },
        variants=[
            FormDesignVariantDTO(
                key="mobile",
                priority=1,
                kind="ANDROID",
                render_schema={"root": {"component": "user", "scope": "/properties/person"}},
            )
        ],
    )
    assert not FormValidator().validate(doc).valid


@pytest.mark.anyio
async def test_shared_client_conformance_fixture():
    import json
    from pathlib import Path

    from apps.clients.domain.contracts import ClientContext
    from apps.forms.application.designs import resolve_form_documents
    from apps.forms.application.options import OptionService
    from apps.forms.domain.options import OptionQuery
    from apps.users.domain.entity import UserEntity

    fixture = json.loads(Path("tests/fixtures/forms/field-sources-v1.json").read_text())
    doc = FormDocuments.model_validate(fixture["documents"])
    actor = UserEntity(username="fixture", hashed_password="hash")
    for kind in ("WEB", "DESKTOP", "ANDROID", "IOS", "B2B", "SDK"):
        view = resolve_form_documents(doc, ClientContext(kind=kind))
        assert view.key == kind.lower()
        for case in fixture["cases"]:
            assert FormValidator().validate(doc, case["data"]).valid == case["valid"]
            query = OptionQuery(
                node_pointer="/root/children/1", data=case["data"], generation=case["generation"]
            )
            result = await OptionService(Mock()).resolve(
                doc, query, actor, render=view.render_schema
            )
            assert result.state == case["state"] and result.generation == case["generation"]
            assert [item.key for item in result.items] == case["keys"]


@pytest.mark.anyio
async def test_dependent_sources_bind_to_the_same_repeated_row():
    from apps.forms.application.options import OptionService
    from apps.forms.domain.options import OptionQuery
    from apps.users.domain.entity import UserEntity

    doc = dependent_document()
    properties = doc.data_schema["properties"]
    doc.data_schema = {
        "type": "object",
        "properties": {
            "rows": {"type": "array", "items": {"type": "object", "properties": properties}}
        },
    }
    for node in doc.render_schema["root"]["children"]:
        node["scope"] = "/properties/rows/items" + node["scope"]
    source = doc.render_schema["root"]["children"][1]["source"]
    source["dependencies"]["country"] = "/properties/rows/items/properties/country"
    data = {"rows": [{"country": "IR", "city": 1}, {"country": "GB", "city": 2}]}
    assert FormValidator().validate(doc, data).valid
    actor = UserEntity(username="rows", hashed_password="hash")
    result = await OptionService(Mock()).resolve(
        doc, OptionQuery(node_pointer="/root/children/1", data=data, row_indices=[1]), actor
    )
    assert result.items[0].key == "json:2"
    data["rows"][1]["city"] = 1
    result = FormValidator().validate(doc, data)
    assert not result.valid and result.issues[0].pointer == "/data/rows/1/city"
