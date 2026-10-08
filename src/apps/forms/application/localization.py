"""Validate and resolve immutable form message catalogs and presentation copies."""

import hashlib
import json
from copy import deepcopy
from typing import Any

from babel import Locale

from apps.forms.application.formatting import format_value
from apps.forms.domain.dto import FormDocuments, RenderDocument, ValidationIssue
from apps.forms.domain.localization import (
    CatalogMessage,
    FieldFormatting,
    FormLocalization,
    MessageReference,
    PluralMessage,
    ResolvedLocalization,
    ResolvedMessage,
)
from apps.forms.domain.options import CustomSource


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def source_revision(message: CatalogMessage) -> str:
    return _digest(message.model_dump(exclude={"source_revision"}))


def _arguments(
    message: CatalogMessage | ResolvedMessage, arguments: dict[str, str | int], locale: str
) -> dict[str, str]:
    if arguments.keys() != message.parameters.keys():
        raise ValueError("Message argument names do not match")
    result = {}
    for name, kind in message.parameters.items():
        value = arguments[name]
        if kind == "integer":
            if type(value) is not int or abs(value) > 9007199254740991:
                raise ValueError("Integer parameter must be a safe JSON integer")
            text = str(value)
        elif not isinstance(value, str) or len(value) > 2048:
            raise ValueError("Parameter must be a bounded canonical string")
        elif kind == "string":
            text = value
        else:
            canonical, _ = format_value(value, FieldFormatting(kind=kind))
            if canonical != value:
                raise ValueError("Parameter must use canonical representation")
            _, text = format_value(
                value, FieldFormatting(kind=kind, numbering="arabext" if locale == "fa" else "latn")
            )
        if kind == "integer" and locale == "fa":
            text = text.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        result[name] = text
    return result


def render_message(message: ResolvedMessage, arguments: dict[str, str | int]) -> str:
    values = _arguments(message, arguments, message.locale)
    text = message.text
    if isinstance(text, PluralMessage):
        count = arguments["count"]
        if type(count) is not int:
            raise ValueError("Plural count must be an integer")
        branch = Locale.parse(message.locale).plural_form(count)
        text = text.one if branch == "one" else text.other
    # Output is plain text; clients must use text nodes, never HTML interpolation.
    return text.format_map(values)


def validate_localization(
    documents: FormDocuments,
) -> tuple[list[ValidationIssue], list[ValidationIssue], dict[str, str]]:
    catalog = documents.localization
    errors: list[ValidationIssue] = []
    gaps: list[ValidationIssue] = []
    if catalog:
        errors.extend(
            ValidationIssue(pointer=f"/variants/{index}/key", code="localization.reserved_variant")
            for index, variant in enumerate(documents.variants)
            if variant.key == "shared"
        )
    source = catalog.catalogs.get(catalog.default_locale, {}) if catalog else {}
    keys = (
        set().union(*(messages.keys() for messages in catalog.catalogs.values()))
        if catalog
        else set()
    )
    refs: list[tuple[str, MessageReference]] = []
    for prefix, raw in [
        ("/render_schema", documents.render_schema),
        *(
            (f"/variants/{i}/render_schema", item.render_schema)
            for i, item in enumerate(documents.variants)
        ),
    ]:
        render = RenderDocument.model_validate(raw)
        stack = [(prefix + "/root", render.root)]
        while stack:
            path, node = stack.pop()
            refs.extend((path + "/messages/" + role, ref) for role, ref in node.messages.items())
            refs.extend(
                (path + f"/option_messages/{i}/message", option.message)
                for i, option in enumerate(node.option_messages)
            )
            if isinstance(node.source, CustomSource):
                refs.extend(
                    (path + f"/source/items/{i}/message", item.message)
                    for i, item in enumerate(node.source.items)
                    if item.message is not None
                )
            if catalog and bool(node.localization_key):
                refs.append(
                    (path + "/localization_key", MessageReference(key=node.localization_key))
                )
            stack.extend((path + f"/children/{i}", child) for i, child in enumerate(node.children))
    if refs and catalog is None:
        return [ValidationIssue(pointer="/localization", code="localization.required")], [], {}
    keys.update(ref.key for _, ref in refs)
    if catalog is None:
        return [], [], {}
    revisions = {key: source_revision(message) for key, message in source.items()}
    for key in sorted(keys):
        original = source.get(key)
        if original is None:
            gaps.append(
                ValidationIssue(
                    pointer=f"/localization/catalogs/{catalog.default_locale}/{key}",
                    code="localization.missing",
                )
            )
        for locale in catalog.supported_locales:
            if locale == catalog.default_locale:
                continue
            translation = catalog.catalogs.get(locale, {}).get(key)
            path = f"/localization/catalogs/{locale}/{key}"
            if translation is None:
                gaps.append(ValidationIssue(pointer=path, code="localization.missing"))
            elif original is not None:
                if translation.parameters != original.parameters or isinstance(
                    translation.text, PluralMessage
                ) != isinstance(original.text, PluralMessage):
                    errors.append(ValidationIssue(pointer=path, code="localization.parameters"))
                elif translation.source_revision != revisions[key]:
                    gaps.append(ValidationIssue(pointer=path, code="localization.stale"))
    for path, ref in refs:
        original = source.get(ref.key)
        if original is not None:
            try:
                _arguments(original, ref.arguments, catalog.default_locale)
            except ValueError:
                errors.append(ValidationIssue(pointer=path, code="localization.arguments"))
    return errors, gaps, revisions


def resolve_catalog(catalog: FormLocalization, requested: str | None) -> ResolvedLocalization:
    requested_base = (requested or catalog.default_locale).lower().split("-", 1)[0]
    locale = (
        requested_base if requested_base in catalog.supported_locales else catalog.default_locale
    )
    order = list(dict.fromkeys([locale, catalog.default_locale, "en"]))
    source = catalog.catalogs.get(catalog.default_locale, {})
    keys = set().union(*(messages.keys() for messages in catalog.catalogs.values()))
    messages = {}
    for key in sorted(keys):
        original = source.get(key)
        if original is None:
            continue
        revision = source_revision(original)
        for candidate in order:
            message = catalog.catalogs.get(candidate, {}).get(key)
            if message is not None and (
                candidate == catalog.default_locale or message.source_revision == revision
            ):
                messages[key] = ResolvedMessage(
                    locale=candidate,
                    text=message.text,
                    parameters=message.parameters,
                    source_revision=revision,
                )
                break
    return ResolvedLocalization(
        resolved_locale=locale,
        direction="rtl" if locale == "fa" else "ltr",
        catalog_revision=_digest(catalog.model_dump(mode="json")),
        messages=messages,
    )


def localize_render(render: dict[str, Any], resolved: ResolvedLocalization) -> dict[str, Any]:
    result = deepcopy(render)
    stack = [result["root"]]
    while stack:
        node = stack.pop()
        refs = dict(node.get("messages", {}))
        if node.get("localization_key") and "label" not in refs:
            refs["label"] = {"key": node["localization_key"]}
        content = {}
        for role, value in refs.items():
            ref = MessageReference.model_validate(value)
            message = resolved.messages.get(ref.key)
            if message is not None:
                content[role] = render_message(message, ref.arguments)
        if content:
            node["localized_text"] = content
            if "label" in content:
                node["label"] = content["label"]
            if "placeholder" in content:
                node.setdefault("options", {})["placeholder"] = content["placeholder"]
            for role in ("label", "description"):
                if "accessibility_" + role in content:
                    node.setdefault("accessibility", {})[role] = content["accessibility_" + role]
        node["localized_options"] = [
            {
                "value": option["value"],
                "label": render_message(resolved.messages[ref.key], ref.arguments),
            }
            for option in node.get("option_messages", [])
            if (ref := MessageReference.model_validate(option["message"])).key in resolved.messages
        ]
        formatting = node.get("formatting")
        if formatting is not None:
            formatting = FieldFormatting.model_validate(formatting).model_dump()
            if formatting["direction"] == "auto":
                formatting["direction"] = resolved.direction
            node["formatting"] = formatting
        stack.extend(node.get("children", []))
    return result


def localize_snapshot(
    snapshot: dict[str, Any] | None, documents: FormDocuments
) -> dict[str, Any] | None:
    """Resolve text for an authorized read without replacing its pinned variant or audit data."""
    if snapshot is None or documents.localization is None:
        return snapshot
    from core.i18n import get_language

    key = snapshot.get("variant_key", "shared")
    raw = (
        documents.render_schema
        if key == "shared"
        else next(
            (variant.render_schema for variant in documents.variants if variant.key == key), None
        )
    )
    if raw is None:
        raise ValueError("Pinned form variant is unavailable")
    from apps.forms.application.fields import apply_field_capabilities

    capabilities = frozenset((snapshot.get("client") or {}).get("renderer_capabilities") or [])
    raw = apply_field_capabilities(raw, capabilities)
    resolved = resolve_catalog(documents.localization, get_language())
    return {
        **snapshot,
        "render_schema": localize_render(raw, resolved),
        "localization": resolved.model_dump(mode="json"),
    }
