"""Deterministic client presentation selection and bounded page JSON."""

from uuid import uuid4

import pytest

from apps.clients.domain.contracts import ClientContext
from apps.forms.application.designs import (
    DesignVariant,
    merge_page_settings,
    resolve_design,
    validate_variants,
)


def test_targeted_design_and_shared_fallback() -> None:
    client_id = uuid4()
    variants = [
        DesignVariant(
            key="desktop",
            priority=10,
            client_id=client_id,
            minimum_release="2.10",
            render_schema={"root": "desktop"},
            page_settings={"toolbar": {"color": "blue"}, "panels": ["wide"]},
        )
    ]
    defaults = {"toolbar": {"size": "large", "color": "black"}, "panels": ["narrow"]}
    context = ClientContext(client_id=client_id, release="2.10", trusted=True)
    selected = resolve_design({"root": "shared"}, defaults, variants, context)
    assert selected.key == "desktop"
    assert selected.page_settings == {
        "toolbar": {"size": "large", "color": "blue"},
        "panels": ["wide"],
        "schema_version": "bpms.page/1",
    }
    assert (
        resolve_design({"root": "shared"}, defaults, variants, ClientContext.legacy()).key
        == "shared"
    )


def test_overlapping_equal_priority_rejected_and_version_order_numeric() -> None:
    client_id = uuid4()
    one = DesignVariant(
        key="one",
        priority=5,
        client_id=client_id,
        minimum_release="2.9",
        maximum_release_exclusive="2.11",
        render_schema={},
    )
    two = DesignVariant(
        key="two", priority=5, client_id=client_id, minimum_release="2.10", render_schema={}
    )
    with pytest.raises(ValueError, match="overlap"):
        validate_variants([one, two])
    assert (
        resolve_design({}, {}, [one], ClientContext(client_id=client_id, release="2.10")).key
        == "one"
    )


def test_opaque_page_merge_and_limits() -> None:
    assert merge_page_settings({"x": {"a": 1}, "y": [1]}, {"x": {"a": None}, "y": []}) == {
        "x": {"a": None},
        "y": [],
        "schema_version": "bpms.page/1",
    }
    with pytest.raises(ValueError, match="size"):
        merge_page_settings({}, {"large": "x" * 70000})


def test_unsupported_capability_is_explicit() -> None:
    variant = DesignVariant(
        key="mobile",
        priority=1,
        kind="ANDROID",
        required_capabilities=frozenset({"camera"}),
        render_schema={},
    )
    with pytest.raises(ValueError, match="capabilit"):
        resolve_design({}, {}, [variant], ClientContext(kind="ANDROID", release="1.0"))


@pytest.mark.parametrize(
    ("kind", "release", "expected"),
    [
        ("DESKTOP", "2.9", "shared"),
        ("DESKTOP", "2.10", "modern"),
        ("DESKTOP", "2.10-rc.1", "shared"),
        ("ANDROID", "1.0", "android"),
        ("B2B", None, "shared"),
        (None, None, "shared"),
    ],
)
def test_predicate_variants_choose_first_match_and_shared_else(kind, release, expected):
    variants = [
        DesignVariant(
            key="modern",
            priority=20,
            render_schema={},
            condition='client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)',
        ),
        DesignVariant(
            key="also_modern",
            priority=10,
            render_schema={},
            condition='client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)',
        ),
        DesignVariant(
            key="android", priority=5, render_schema={}, condition='client.kind == "ANDROID"'
        ),
    ]
    assert (
        resolve_design({}, {}, variants, ClientContext(kind=kind, release=release)).key == expected
    )


def test_predicate_variants_short_circuit_and_cannot_claim_shared_identity():
    variants = [
        DesignVariant(key="first", priority=20, render_schema={}, condition="True"),
        DesignVariant(
            key="later",
            priority=10,
            render_schema={},
            condition='version_in_range(client.release, "2.10", null)',
        ),
    ]
    assert resolve_design({}, {}, variants, ClientContext(release="invalid")).key == "first"
    with pytest.raises(ValueError):
        DesignVariant(key="shared", priority=1, render_schema={}, condition="True")
    with pytest.raises(ValueError):
        DesignVariant(key="invalid", priority=1, render_schema={}, condition="request.secret == 1")


def test_variant_condition_errors_and_historical_checksum_compatibility():
    import hashlib
    import json

    from apps.forms.application.validation import FormValidator
    from apps.forms.domain.dto import FormDocuments

    original = {
        "data_dialect": "https://json-schema.org/draft/2020-12/schema",
        "render_dialect": "bpms.render/1",
        "data_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "render_schema": {"root": {"component": "vertical", "children": []}},
        "page_settings": {},
        "variants": [
            {
                "key": "desktop",
                "priority": 1,
                "client_ref_id": None,
                "kind": "DESKTOP",
                "minimum_release": None,
                "maximum_release_exclusive": None,
                "required_capabilities": [],
                "render_schema": {"root": {"component": "vertical", "children": []}},
                "page_settings": {},
            }
        ],
    }
    documents = FormDocuments.model_validate(original)
    result = FormValidator().validate(documents)
    assert result.valid, result.issues
    assert (
        result.checksum
        == hashlib.sha256(
            json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    modified = original | {
        "variants": [original["variants"][0] | {"condition": 'client.release >= "2.10"'}]
    }
    invalid = FormValidator().validate(FormDocuments.model_validate(modified))
    assert not invalid.valid
    assert invalid.issues[0].pointer == "/variants/0/condition"
    assert invalid.issues[0].line == 1
    assert invalid.issues[0].column == 0


def test_predicate_evaluation_error_does_not_fall_through_to_else():
    from apps.expressions.application.language import EvaluationError

    variant = DesignVariant(key="error", priority=10, render_schema={}, condition="1 / 0 > 0")
    with pytest.raises(EvaluationError):
        resolve_design({}, {}, [variant], ClientContext.legacy())
