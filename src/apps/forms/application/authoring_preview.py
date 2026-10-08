"""Author-only simulated contexts use the actual runtime projection."""

import json
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from apps.forms.application.behavior import evaluate_behavior
from apps.forms.application.collections import initialize_identity
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.runtime import display_page, render_scopes, runtime_projection
from apps.forms.application.validation import FormValidator, _bounded, _Invalid
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.runtime import RuntimeFormStateDTO
from core.base_dto import BaseDTO
from utils.exceptions import ValidationDetailsException


class SimulatedRuntimePreviewRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    documents: FormDocuments
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Bounded synthetic sample values; this endpoint never persists a submission.",
    )
    purpose: Literal["edit", "summary", "print", "correction"] = "edit"
    policy: dict[str, list[str]] | None = Field(
        default=None,
        description="Explicit simulated read/write/required/hidden scopes; not real actor entitlements. Null previews all declared scopes.",
    )
    before_data: dict[str, Any] | None = Field(
        default=None, description="Optional synthetic prior correction values."
    )
    item_identity: dict[str, list[str]] = Field(
        default_factory=dict,
        max_length=256,
        description="Optional synthetic UUIDv7 row keys, validated against sample values. Omit to generate fresh preview identities.",
    )
    before_item_identity: dict[str, list[str]] = Field(
        default_factory=dict,
        max_length=256,
        description="Explicit synthetic prior keys for correction comparisons; never assume row indices identify the same item.",
    )
    locale: Literal["en", "fa"] = "en"

    @field_validator("data", "before_data", "item_identity", "before_item_identity")
    @classmethod
    def bounded_sample(cls, value):
        if value is not None:
            try:
                _bounded(value, "/data")
                if len(json.dumps(value, allow_nan=False).encode()) > 262144:
                    raise ValueError("Sample is too large")
            except _Invalid as exc:
                raise ValueError("Invalid sample data") from exc
        return value

    @field_validator("policy")
    @classmethod
    def bounded_policy(cls, value):
        if value is not None and (
            set(value) - {"read", "write", "required", "hidden"}
            or any(
                len(items) > 256
                or any(len(scope) > 512 or not scope.startswith("/properties/") for scope in items)
                for items in value.values()
            )
        ):
            raise ValueError("Invalid simulated policy")
        return value


def runtime_preview(payload, context):
    structure = FormValidator().validate(payload.documents)
    if not structure.valid:
        raise ValidationDetailsException([issue.model_dump() for issue in structure.issues])
    design = resolve_form_documents(payload.documents, context, locale=payload.locale)
    documents = payload.documents.model_copy(
        update={
            "render_schema": {"dialect": payload.documents.render_dialect, **design.render_schema},
            "page_settings": design.page_settings,
        }
    )
    data = (
        evaluate_behavior(documents, payload.data, initialize=True, enforce_required=False).data
        if documents.behavior_dialect
        else payload.data
    )
    identity = initialize_identity(data, payload.item_identity, documents.data_schema)
    declared = render_scopes(documents.render_schema)
    policy = (
        payload.policy
        if payload.policy is not None
        else {
            "read": sorted(declared),
            "write": sorted(declared),
            "required": [],
            "hidden": [],
        }
    )
    readable = set(policy.get("read", [])) | set(policy.get("write", []))
    writable = set(policy.get("write", [])) if payload.purpose in {"edit", "correction"} else set()
    projected = runtime_projection(
        data,
        identity,
        {},
        documents.data_schema,
        documents.render_schema,
        policy,
        readable,
        writable,
        set(policy.get("required", [])),
    )
    before = None
    before_identity = None
    if payload.before_data is not None:
        previous = runtime_projection(
            payload.before_data,
            initialize_identity(
                payload.before_data, payload.before_item_identity, documents.data_schema
            ),
            {},
            documents.data_schema,
            documents.render_schema,
            policy,
            readable,
            set(),
            set(),
        )
        before = previous["data"]
        before_identity = previous["item_identity"]
    return RuntimeFormStateDTO(
        resource_kind="REQUEST",
        resource_ref_id="simulated-preview",
        form_version_ref_id="simulated-form",
        form_version_number=1,
        submission_ref_id="simulated-submission",
        design_key=design.key,
        view_key="simulated-" + payload.purpose,
        purpose=payload.purpose,
        resolved_locale=payload.locale,
        direction="rtl" if payload.locale == "fa" else "ltr",
        data=projected["data"],
        item_identity=projected["item_identity"],
        render_schema=projected["render_schema"],
        readable_scopes=projected["readable_scopes"],
        writable_scopes=projected["writable_scopes"],
        required_scopes=projected["required_scopes"],
        field_metadata=projected["field_metadata"],
        before_data=before,
        before_item_identity=before_identity,
        page_settings=display_page(design.page_settings, set(projected["readable_scopes"])),
    )
