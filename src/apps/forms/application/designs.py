"""Bounded, deterministic client presentation variants for one canonical form schema."""

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any
from uuid import UUID

from apps.clients.domain.contracts import (
    ClientContext,
    ClientKind,
    ClientVersion,
    ReleaseRange,
    client_expression_schema,
)
from apps.expressions.application.language import ExpressionCompiler, ExpressionContext
from apps.forms.domain.localization import ResolvedLocalization
from core.i18n import get_language

if TYPE_CHECKING:
    from apps.forms.domain.dto import FormDocuments


@dataclass(frozen=True)
class DesignVariant:
    key: str
    priority: int
    render_schema: dict[str, Any]
    client_id: UUID | None = None
    kind: ClientKind | None = None
    minimum_release: str | None = None
    maximum_release_exclusive: str | None = None
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    page_settings: dict[str, Any] = field(default_factory=dict)
    condition: str | None = None

    def __post_init__(self) -> None:
        if not self.key or len(self.key) > 64 or not 0 <= self.priority <= 100:
            raise ValueError("Invalid design variant key or priority")
        if self.client_id is None and self.kind is None and self.condition is None:
            raise ValueError("A targeted variant requires a client or kind")
        if self.condition is not None:
            if self.key == "shared":
                raise ValueError("Shared is the reserved fallback identity")
            ExpressionCompiler().compile(
                self.condition,
                {"client": client_expression_schema()},
                expected_schema={"type": "boolean"},
            )
        ReleaseRange(self.minimum_release, self.maximum_release_exclusive)
        _bounded_json(self.page_settings)
        _bounded_json(self.render_schema)

    def matches(self, context: ClientContext) -> bool:
        if self.condition is None and context.client_id is None and context.kind is None:
            return False
        return (
            (self.client_id is None or self.client_id == context.client_id)
            and (self.kind is None or self.kind == context.kind)
            and (
                self.condition is not None
                and self.minimum_release is None
                and self.maximum_release_exclusive is None
                or ReleaseRange(self.minimum_release, self.maximum_release_exclusive).contains(
                    context.release
                )
            )
            and (
                self.condition is None
                or ExpressionCompiler()
                .compile(
                    self.condition,
                    {"client": client_expression_schema()},
                    expected_schema={"type": "boolean"},
                )
                .evaluate(
                    ExpressionContext(
                        request={},
                        process={},
                        current_user={},
                        steps={},
                        client=context.expression_values(),
                    )
                )
                .value
                is True
            )
        )


PAGE_SCHEMA_VERSION = "bpms.page/1"


@dataclass(frozen=True)
class ResolvedDesign:
    key: str
    render_schema: dict[str, Any]
    page_settings: dict[str, Any]
    required_capabilities: frozenset[str]
    localization: ResolvedLocalization | None = None
    source_revision: str | None = None

    @property
    def revision(self) -> str:
        if self.source_revision is not None:
            return self.source_revision
        document = {
            "key": self.key,
            "render_schema": self.render_schema,
            "page_settings": self.page_settings,
        }
        return hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()


def _bounded_json(value: Any) -> None:
    stack = [(value, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if depth > 24 or count > 2048:
            raise ValueError("Page design size or depth limit exceeded")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("Page design keys must be strings")
            if any(
                any(
                    word in key.lower()
                    for word in ("secret", "password", "credential", "token", "api_key")
                )
                for key in item
            ):
                raise ValueError("Page design cannot contain credential fields")
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    try:
        size = len(json.dumps(value, allow_nan=False, separators=(",", ":")).encode())
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Page design must be finite JSON") from exc
    if size > 65536:
        raise ValueError("Page design size limit exceeded")


def _merge_maps(shared: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(shared)
    for key, value in override.items():
        old = result.get(key)
        result[key] = (
            _merge_maps(old, value) if isinstance(old, dict) and isinstance(value, dict) else value
        )
    return result


def merge_page_settings(shared: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Maps merge recursively; arrays and null replace inherited values."""
    result = _merge_maps(shared, override)
    version = result.get("schema_version", PAGE_SCHEMA_VERSION)
    if version != PAGE_SCHEMA_VERSION:
        raise ValueError("Unsupported page schema version")
    result["schema_version"] = PAGE_SCHEMA_VERSION
    _bounded_json(result)
    return result


def _ranges_overlap(left: DesignVariant, right: DesignVariant) -> bool:
    lower = [
        ClientVersion.parse(value)
        for value in (left.minimum_release, right.minimum_release)
        if value is not None
    ]
    upper = [
        ClientVersion.parse(value)
        for value in (left.maximum_release_exclusive, right.maximum_release_exclusive)
        if value is not None
    ]
    return not lower or not upper or max(lower) < min(upper)


def validate_variants(variants: list[DesignVariant]) -> None:
    if len(variants) > 32 or len({item.key for item in variants}) != len(variants):
        raise ValueError("Too many or duplicate design variants")
    for index, left in enumerate(variants):
        for right in variants[index + 1 :]:
            same_client = (
                left.client_id is None
                or right.client_id is None
                or left.client_id == right.client_id
            )
            same_kind = left.kind is None or right.kind is None or left.kind == right.kind
            if (
                left.priority == right.priority
                and same_client
                and same_kind
                and _ranges_overlap(left, right)
            ):
                raise ValueError("Equal-priority design variant targets overlap")


def resolve_design(
    shared_render: dict[str, Any],
    shared_page: dict[str, Any],
    variants: list[DesignVariant],
    context: ClientContext,
) -> ResolvedDesign:
    validate_variants(variants)
    selected = next(
        (
            item
            for item in sorted(variants, key=lambda item: item.priority, reverse=True)
            if item.matches(context)
        ),
        None,
    )
    if selected is None:
        page = merge_page_settings(shared_page, {})
        return ResolvedDesign("shared", shared_render, page, frozenset())
    if not selected.required_capabilities <= context.renderer_capabilities:
        raise ValueError("Client lacks required renderer capabilities")
    return ResolvedDesign(
        selected.key,
        selected.render_schema,
        merge_page_settings(shared_page, selected.page_settings),
        selected.required_capabilities,
    )


def resolve_form_documents(
    documents: FormDocuments, context: ClientContext, *, locale: str | None = None
) -> ResolvedDesign:
    """Select one published view while retaining the form's canonical data schema."""
    from apps.forms.domain.dto import FormDocuments
    from core.ref_id import open_ref_id

    if not isinstance(documents, FormDocuments):
        raise TypeError("Form documents are required")
    variants = [
        DesignVariant(
            key=item.key,
            priority=item.priority,
            client_id=open_ref_id(item.client_ref_id)[0] if bool(item.client_ref_id) else None,
            kind=item.kind,
            minimum_release=item.minimum_release,
            maximum_release_exclusive=item.maximum_release_exclusive,
            required_capabilities=frozenset(item.required_capabilities),
            render_schema=item.render_schema,
            page_settings=item.page_settings,
            condition=item.condition,
        )
        for item in documents.variants
    ]
    design = resolve_design(documents.render_schema, documents.page_settings, variants, context)
    from apps.forms.application.fields import apply_field_capabilities

    design = replace(
        design,
        render_schema=apply_field_capabilities(design.render_schema, context.renderer_capabilities),
    )
    if documents.localization is None:
        return design
    from apps.forms.application.localization import localize_render, resolve_catalog

    resolved = resolve_catalog(
        documents.localization, locale if locale is not None else get_language()
    )
    revision = hashlib.sha256((design.revision + resolved.catalog_revision).encode()).hexdigest()
    return replace(
        design,
        render_schema=localize_render(design.render_schema, resolved),
        localization=resolved,
        source_revision=revision,
    )
