"""Inspect effective public routes without opening database or external connections."""

import inspect
import sys
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from core.dto_contract import assert_public_dto, nested_models

METHODS = frozenset({"get", "post", "put", "patch", "delete"})


def effective_routes(app: Any) -> Iterable[Any]:
    """Isolate the pinned FastAPI lazy-router inspection seam."""
    for route in app.routes:
        included = getattr(route, "effective_route_contexts", None)
        if included is not None:
            yield from included()
        else:
            yield route


def dependency_names(dependant: Any) -> list[str]:
    """Record authorization dependencies, including callable permission objects."""
    found: set[str] = set()
    pending = [dependant]
    while pending:
        current = pending.pop()
        call = getattr(current, "call", None)
        if call is not None:
            permission = getattr(call, "permission", None)
            name = getattr(call, "__qualname__", type(call).__name__)
            module = getattr(call, "__module__", type(call).__module__)
            found.add(f"{module}.{name}" + (f":{permission}" if permission else ""))
        pending.extend(getattr(current, "dependencies", ()))
    return sorted(found)


def response_family(operation: dict[str, Any], schemas: dict[str, Any]) -> str:
    """Keep SSE, private binary, selector arrays and JSON envelopes distinct."""
    content = {
        media: detail
        for status, response in operation.get("responses", {}).items()
        if status.startswith("2")
        for media, detail in response.get("content", {}).items()
    }
    if "text/event-stream" in content:
        return "sse"
    if "application/json" not in content:
        return "binary-or-empty"
    schema = content["application/json"].get("schema", {})
    if "anyOf" in schema or "oneOf" in schema:
        return "typed-union"
    root = schemas.get(schema.get("$ref", "").split("/")[-1], schema)
    properties = root.get("properties", {})
    if "result" in properties:
        return "page-result"
    if "data" in properties and "success" in properties:
        return "success-data"
    if root.get("type") == "array":
        return "plain-items"
    return "native-json"


def operation_inventory(app: Any) -> dict[str, dict[str, Any]]:
    """Account for every effective OpenAPI operation by identity, owner and authority."""
    schema = app.openapi()
    contexts = {
        (route.path_format, method.lower()): route
        for route in effective_routes(app)
        if getattr(route, "include_in_schema", False)
        for method in getattr(route, "methods", ()) or ()
    }
    inventory = {}
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in METHODS:
                continue
            route = contexts[(path, method)]
            endpoint = route.endpoint
            module = endpoint.__module__
            owner = module.split(".")[1] if module.startswith("apps.") else module
            dependencies = dependency_names(route.dependant)
            permissions = [
                name for name in dependencies if "Permission" in name or "current_user" in name
            ]
            # Shared CRUD closures retain the concrete DTO owner through their annotations.
            if module.startswith("utils."):
                owners = sorted(
                    {
                        model.__module__.split(".")[1]
                        for model in model_tree(route_models(route)).values()
                        if model.__module__.startswith("apps.")
                    }
                )
                if owners:
                    owner = ",".join(owners)
            disposition = "domain-ui"
            if any("admin." in name for name in permissions):
                disposition = "advanced-administration"
            elif "/auth/" in path or "/login" in path:
                disposition = "session-boundary"
            elif not module.startswith("apps."):
                disposition = "shared-infrastructure"
            inventory[f"{method.upper()} {path}"] = {
                "operation_id": operation["operationId"],
                "owner": owner,
                "endpoint": f"{module}.{endpoint.__qualname__}",
                "disposition": disposition,
                "tags": operation.get("tags", []),
                "permission_dependencies": permissions,
                "dependencies": dependencies,
                "security": operation.get("security", []),
                "response_family": response_family(operation, schema["components"]["schemas"]),
                "models": sorted(model_name(model) for model in route_models(route)),
            }
    return dict(sorted(inventory.items()))


def model_name(model: type[BaseModel]) -> str:
    """Use qualified identities rather than potentially colliding short class names."""
    return f"{model.__module__}.{model.__name__}"


def annotation_models(annotation: Any) -> set[type[BaseModel]]:
    """Find typed models through Annotated, unions and generic collection arguments."""
    return nested_models(annotation)


def route_models(route: Any) -> set[type[BaseModel]]:
    """Discover actual JSON/query roots; authorization ORM dependencies are not payloads."""
    roots = annotation_models(getattr(route, "response_model", None))
    for field in getattr(route, "response_fields", {}).values():
        roots.update(annotation_models(field.field_info.annotation))
    event_schemas = (getattr(route, "openapi_extra", None) or {}).get("x-sse-event-schemas")
    if event_schemas is not None:
        event_models = getattr(sys.modules[route.endpoint.__module__], "EVENT_MODELS", {})
        if set(event_models) != set(event_schemas) or any(
            event_models[name].model_json_schema(mode="serialization") != schema
            for name, schema in event_schemas.items()
        ):
            raise ValueError(
                "SSE event schemas need matching typed models from their transport owner"
            )
        roots.update(event_models.values())
    dependant = getattr(route, "dependant", None)
    pending = [dependant]
    while pending:
        current = pending.pop()
        for family in ("body_params", "query_params"):
            for field in getattr(current, family, ()):
                roots.update(annotation_models(field.field_info.annotation))
        pending.extend(getattr(current, "dependencies", ()))
    body = getattr(route, "body_field", None)
    if body is not None:
        roots.update(annotation_models(body.field_info.annotation))
    return roots


def reachable_models(app: Any) -> dict[str, type[BaseModel]]:
    """Traverse nested and computed model types instead of guessing from DTO filenames."""
    return model_tree(model for route in effective_routes(app) for model in route_models(route))


def model_tree(roots: Iterable[type[BaseModel]]) -> dict[str, type[BaseModel]]:
    """Return one transitive typed-model graph for routes and shared CRUD projections."""
    pending = list(roots)
    found = {}
    while pending:
        model = pending.pop()
        name = model_name(model)
        if name in found:
            continue
        found[name] = model
        for field in model.model_fields.values():
            pending.extend(annotation_models(field.annotation))
        for field in model.model_computed_fields.values():
            pending.extend(annotation_models(field.return_type))
    return dict(sorted(found.items()))


def check_operation_inventory(actual: dict, frozen: dict) -> None:
    """Fail closed on a newly unclassified, removed or changed effective operation."""
    differences = sorted(
        key for key in actual.keys() | frozen.keys() if actual.get(key) != frozen.get(key)
    )
    if differences:
        raise ValueError(f"Unclassified or changed operation inventory: {differences}")


def check_authorities(authorities: list[str]) -> None:
    """Reject competing active producer manifests; historical snapshots are separate."""
    if len(authorities) != 1:
        raise ValueError("Exactly one active contract authority is required")


def field_inventory(app: Any) -> dict[str, dict[str, Any]]:
    """Describe fixed fields and explicit flexible boundaries from actual DTO metadata."""
    inventory = {}
    consumers: dict[str, set[str]] = {}
    for route in effective_routes(app):
        if not getattr(route, "include_in_schema", False):
            continue
        operations = {
            f"{method} {route.path_format}" for method in getattr(route, "methods", ()) or ()
        }
        for name in model_tree(route_models(route)):
            consumers.setdefault(name, set()).update(operations)
    for name, model in reachable_models(app).items():
        serialization = model.model_json_schema(mode="serialization")
        fields = {}
        for field_name, schema in serialization.get("properties", {}).items():
            field = model.model_fields.get(field_name)
            computed = model.model_computed_fields.get(field_name)
            fields[field_name] = {
                "schema": schema,
                "required_output": field_name in serialization.get("required", []),
                "computed": computed is not None,
                "required_input": field.is_required() if field is not None else False,
                "validation_alias": str(field.validation_alias)
                if field is not None and field.validation_alias is not None
                else None,
                "definition_owner": model.__module__,
                "flexible_document": bool(schema.get("additionalProperties")),
            }
        inventory[name] = {
            "definition_owner": model.__module__,
            "operations": sorted(consumers.get(name, set())),
            "source": (
                "src/" + inspect.getfile(model).split("/src/")[-1]
                if model.__module__.startswith(("apps.", "core.", "utils."))
                else "transport-generated:" + model.__module__
            ),
            "extra_policy": model.model_config.get("extra", "ignore"),
            "fields": fields,
            "mapping_policy": "Purpose-specific application projection; from_attributes is not authorization.",
        }
    return inventory


def audit_public_models(app: Any) -> None:
    """Audit every JSON root; FastAPI form/multipart transport models are explicit exceptions."""
    for route in effective_routes(app):
        for model in route_models(route):
            if model.__module__.startswith("fastapi."):
                body = getattr(route, "body_field", None)
                media = getattr(getattr(body, "field_info", None), "media_type", None)
                if media in {"multipart/form-data", "application/x-www-form-urlencoded"}:
                    continue
            assert_public_dto(model)
