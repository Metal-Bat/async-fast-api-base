"""Generate inspector discovery from code-owned types without mutating stored versions."""

from pydantic import ValidationError

from apps.designer.domain.inspector import (
    HandlerInspector,
    InspectorBinding,
    InspectorContract,
    InspectorDiagnostic,
    InspectorValidationQuery,
    InspectorValidationResult,
)
from apps.forms.application.fields import field_catalog
from apps.step_types.application.registry import get_registry
from core.i18n import translate

_BINDINGS = {
    "form_version_ref": InspectorBinding(
        pointer="/form_version_ref",
        selector_kind="form_versions",
        pinned=True,
        secret_reference=False,
        scope="published_form",
    ),
    "connection_ref": InspectorBinding(
        pointer="/connection_ref",
        selector_kind="connections",
        pinned=False,
        secret_reference=True,
        scope="connection_use",
    ),
    "agent_ref": InspectorBinding(
        pointer="/agent_ref",
        selector_kind="agent_versions",
        pinned=True,
        secret_reference=True,
        scope="published_agent",
    ),
}


def inspector_contract() -> InspectorContract:
    """Expose every deployed handler, including versions not yet operator-published."""
    handlers = []
    for definition in sorted(
        get_registry().definitions(),
        key=lambda item: (
            item.handler_key,
            item.handler_version,
        ),
    ):
        metadata = definition.metadata()
        handlers.append(
            HandlerInspector(
                **metadata.model_dump(exclude={"name"}),
                name=translate(definition.name_key or definition.name),
                contract_fingerprint=definition.fingerprint,
                bindings=[
                    binding.model_copy(deep=True)
                    for key, binding in _BINDINGS.items()
                    if key in metadata.config_schema.get("properties", {})
                ],
                outcomes=list(definition.outcomes),
                outcome_source="handler" if definition.outcomes else "graph",
                required_capabilities=list(definition.required_capabilities),
                name_key=definition.name_key,
                help_key=definition.help_key,
                help_text=translate(definition.help_key)
                if definition.help_key is not None
                else None,
                examples=list(definition.examples),
            )
        )
    return InspectorContract(handlers=handlers, fields=field_catalog())


def validate_configuration(query: InspectorValidationQuery) -> InspectorValidationResult:
    """Validate code-owned DTOs only; return no input values, exception messages or credentials."""
    try:
        handler = get_registry().resolve(query.handler_key, query.handler_version)
    except ValueError:
        return InspectorValidationResult(
            valid=False, diagnostics=[InspectorDiagnostic(pointer="/", code="handler_unavailable")]
        )
    try:
        handler.config_model.model_validate(query.config)
    except ValidationError as error:
        diagnostics = []
        for item in error.errors(include_input=False, include_context=False, include_url=False)[
            :128
        ]:
            unknown = item["type"] == "extra_forbidden"
            # Only schema-owned top-level names are safe; nested dictionary keys are input.
            location = item["loc"][0] if item["loc"] else None
            trusted = location in handler.config_model.model_fields
            pointer = (
                "/" + str(location).replace("~", "~0").replace("/", "~1")
                if not unknown and trusted
                else "/"
            )
            diagnostics.append(
                InspectorDiagnostic(
                    pointer=pointer, code="unknown_field" if unknown else "invalid_config"
                )
            )
        return InspectorValidationResult(valid=False, diagnostics=diagnostics)
    return InspectorValidationResult(valid=True)
