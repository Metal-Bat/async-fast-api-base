"""Additive inspector metadata; schema documents describe data, never execute it."""

import json
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, field_validator

from apps.forms.domain.fields import FieldContract
from apps.step_types.domain.dto import HandlerDTO
from core.base_dto import BaseDTO
from core.i18n import _ as gettext_


class InspectorBinding(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    pointer: str = Field(description=gettext_("JSON pointer within the handler configuration."))
    selector_kind: Literal["form_versions", "connections", "agent_versions"] = Field(
        description=gettext_(
            "Existing authorized selector; selection does not grant use permission."
        )
    )
    pinned: bool = Field(
        description=gettext_("Whether the field selects an exact immutable version.")
    )
    secret_reference: bool = Field(
        description=gettext_("Selects a protected resource; never enter or return credentials.")
    )
    scope: Literal["published_form", "connection_use", "published_agent"] = Field(
        description=gettext_("Owning service eligibility policy applied again at publication.")
    )


class HandlerInspector(HandlerDTO):
    model_config = ConfigDict(extra="forbid")

    contract_fingerprint: str
    config_dialect: Literal["json-schema-2020-12"] = "json-schema-2020-12"
    config_schema: dict[str, JsonValue]
    bindings: list[InspectorBinding] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    outcome_source: Literal["handler", "graph"]
    required_capabilities: list[str] = Field(default_factory=list)
    name_key: str | None = None
    help_key: str | None = None
    help_text: str | None = None
    examples: list[dict[str, JsonValue]] = Field(default_factory=list)


class InspectorContract(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    handlers: list[HandlerInspector] = Field(max_length=256)
    fields: list[FieldContract] = Field(max_length=64)
    diagnostic_pointer_format: Literal["json-pointer"] = "json-pointer"
    preview_policy: Literal["bounded-pure-synthetic-only"] = "bounded-pure-synthetic-only"


class InspectorValidationQuery(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    handler_key: str = Field(min_length=1, max_length=64)
    handler_version: str = Field(min_length=1, max_length=32)
    config: dict[str, JsonValue] = Field(max_length=128)

    @field_validator("config")
    @classmethod
    def bounded_config(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if len(json.dumps(value, allow_nan=False).encode()) > 16_384:
            raise ValueError("Inspector configuration exceeds 16 KiB")
        return value


class InspectorDiagnostic(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    pointer: str
    code: Literal["handler_unavailable", "invalid_config", "unknown_field"]


class InspectorValidationResult(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    valid: bool
    diagnostics: list[InspectorDiagnostic] = Field(default_factory=list, max_length=128)
