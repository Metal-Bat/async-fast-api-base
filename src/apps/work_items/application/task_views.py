"""Pure policy, projection and action validation for pinned human tasks."""

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.validators import extend

from apps.forms.application.behavior import BehaviorError, evaluate_behavior
from apps.forms.application.validation import FormValidator, _compile
from apps.forms.domain.dto import FormDocuments
from apps.work_items.domain.task_contract import HumanTaskContract, TaskAction, TaskView
from apps.workflows.application.validation import GraphValidator
from utils.exceptions import ValidationDetailsException


class TaskPolicyError(ValueError):
    pass


def _data_path(scope: str) -> tuple[str, ...]:
    parts = scope.split("/")[1:]
    path: list[str] = []
    index = 0
    while index < len(parts):
        if parts[index] == "properties" and index + 1 < len(parts):
            path.append(parts[index + 1].replace("~1", "/").replace("~0", "~"))
            index += 2
        elif parts[index] == "items":
            path.append("*")
            index += 1
        else:
            raise TaskPolicyError("task.scope")
    return tuple(path)


def _matches(path: tuple[str, ...], scope: str) -> bool:
    allowed = _data_path(scope)
    return len(path) == len(allowed) and all(
        part == bound or bound == "*" for part, bound in zip(path, allowed, strict=True)
    )


def validate_contract(
    contract: HumanTaskContract,
    policy: dict[str, list[str]],
    schema: dict[str, Any],
    outcomes: set[str],
    transitions: set[str],
) -> None:
    readable = set(policy.get("read", [])) | set(policy.get("write", []))
    writable = set(policy.get("write", []))
    if not readable or not writable:
        raise TaskPolicyError("task.policy.empty")
    if not set(policy.get("required", [])) <= readable:
        raise TaskPolicyError("task.policy.required_scope")
    for view in contract.views:
        if not view.scopes or any(scope not in readable for scope in view.scopes):
            raise TaskPolicyError("task.view.scope")
    pairs: set[tuple[str, str]] = set()
    for action in contract.actions:
        if action.outcome_key not in outcomes or action.outcome_key not in transitions:
            raise TaskPolicyError("task.action.outcome")
        pair = (action.kind, action.outcome_key)
        if pair in pairs:
            raise TaskPolicyError("task.action.duplicate")
        pairs.add(pair)
        if action.kind in {"reject", "return"} and not action.require_comment:
            raise TaskPolicyError("task.action.reason")
        if any(scope not in readable for scope in action.required_scopes):
            raise TaskPolicyError("task.action.required_scope")
        if any(
            GraphValidator._schema_at(schema, scope) is None for scope in action.required_scopes
        ):
            raise TaskPolicyError("task.action.required_scope")
    for scope in readable:
        field = GraphValidator._schema_at(schema, scope)
        if field is None or not isinstance(field, dict) or field.get("type") == "object":
            raise TaskPolicyError("task.policy.scope")
        if (
            field.get("type") == "array"
            and isinstance(field.get("items"), dict)
            and field["items"].get("type") == "object"
            and any(
                _data_path(hidden)[: len(_data_path(scope))] == _data_path(scope)
                for hidden in policy.get("hidden", [])
            )
        ):
            raise TaskPolicyError("task.policy.array_hidden")


def changed_paths(before: Any, after: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if isinstance(before, dict) and isinstance(after, dict):
        result: set[tuple[str, ...]] = set()
        for key in before.keys() | after.keys():
            if key not in before or key not in after:
                result.add((*prefix, key))
            else:
                result |= changed_paths(before[key], after[key], (*prefix, key))
        return result
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        result = set()
        for index, (left, right) in enumerate(zip(before, after, strict=True)):
            result |= changed_paths(left, right, (*prefix, str(index)))
        return result
    return {prefix} if before != after else set()


def enforce_writes(
    before: dict[str, Any], after: dict[str, Any], policy: dict[str, list[str]] | None
) -> None:
    if not bool(policy) or not any(policy.values()):
        return  # Published legacy steps had empty advisory policies.
    writable = policy.get("write", [])
    for path in changed_paths(before, after):
        if not any(_matches(path, scope) for scope in writable):
            raise ValidationDetailsException(
                [{"pointer": "/data/" + "/".join(path), "code": "task.field.read_only"}]
            )


def _project(value: Any, path: tuple[str, ...], scopes: set[str]) -> Any:
    if any(_matches(path, scope) for scope in scopes):
        return deepcopy(value)
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            next_path = (*path, key)
            if any(
                len(_data_path(scope)) >= len(next_path)
                and all(
                    part == bound or bound == "*"
                    for part, bound in zip(next_path, _data_path(scope))
                )
                for scope in scopes
            ):
                result[key] = _project(child, next_path, scopes)
        return result
    if isinstance(value, list):
        return [_project(child, (*path, str(index)), scopes) for index, child in enumerate(value)]
    return None


def project_data(data: dict[str, Any], scopes: set[str]) -> dict[str, Any]:
    return _project(data, (), scopes)


def filter_identity(
    identity: dict[str, list[str]] | None, scopes: set[str]
) -> dict[str, list[str]] | None:
    if identity is None:
        return None
    visible = {}
    for path, keys in identity.items():
        parts = tuple(part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:])
        if any(
            len(pattern := _data_path(scope)) >= len(parts)
            and all(part == bound or bound == "*" for part, bound in zip(parts, pattern))
            for scope in scopes
        ):
            visible[path] = list(keys)
    return visible


def filter_render(render: dict[str, Any], scopes: set[str]) -> dict[str, Any]:
    result = deepcopy(render)

    def filter_node(node: dict[str, Any]) -> bool:
        node["children"] = [child for child in node.get("children", []) if filter_node(child)]
        scope = node.get("scope")
        return scope is None or scope in scopes

    filter_node(result["root"])
    return result


def allowed_view_scopes(view: TaskView, policy: dict[str, list[str]]) -> set[str]:
    readable = set(policy.get("read", [])) | set(policy.get("write", []))
    return set(view.scopes) & readable - set(policy.get("hidden", []))


def action_for(contract: HumanTaskContract, kind: str, outcome: str) -> TaskAction:
    action = next(
        (item for item in contract.actions if item.kind == kind and item.outcome_key == outcome),
        None,
    )
    if action is None:
        raise ValidationDetailsException(
            [{"pointer": "/outcome_key", "code": "task.action.unavailable"}]
        )
    return action


def validate_action_data(
    documents: FormDocuments,
    data: dict[str, Any],
    action: TaskAction | None,
    overrides: dict[str, dict[str, Any]] | None,
    *,
    partial: bool = False,
    policy_required: list[str] | None = None,
) -> dict[str, Any]:
    if not partial and (action is None or action.validation == "complete"):
        result = FormValidator().validate(documents, data, overrides=overrides)
        if not result.valid:
            raise ValidationDetailsException([issue.model_dump() for issue in result.issues])
        canonical = result.evaluated_data if result.evaluated_data is not None else data
    else:
        structure = FormValidator().validate(documents)
        if not structure.valid:
            raise ValidationDetailsException([issue.model_dump() for issue in structure.issues])
        try:
            canonical = (
                evaluate_behavior(
                    documents,
                    data,
                    authoritative=True,
                    overrides=overrides,
                    enforce_required=False,
                ).data
                if documents.behavior_dialect
                else data
            )
        except BehaviorError as exc:
            raise ValidationDetailsException([{"pointer": "/data", "code": str(exc)}]) from None
        schema = _compile(documents.data_schema)

        PartialValidator = extend(
            Draft202012Validator,
            {"required": lambda validator, required, instance, schema: iter(())},
        )
        issues = [
            {"pointer": "/data/" + "/".join(map(str, error.absolute_path)), "code": "data.invalid"}
            for error in PartialValidator(schema, format_checker=FormatChecker()).iter_errors(
                canonical
            )
        ]
        if issues:
            raise ValidationDetailsException(issues[:32])
        from apps.forms.application.formatting import canonical_value_issues
        from apps.forms.application.option_validation import static_membership_issues

        for validator in (static_membership_issues, canonical_value_issues):
            field_issues = validator(documents.render_schema, schema, canonical)
            if field_issues:
                raise ValidationDetailsException(
                    [{"pointer": path, "code": code} for path, code in field_issues[:32]]
                )
    from apps.forms.application.behavior import _MISSING, _get_concrete, _locations

    required_scopes = [*(policy_required or []), *(action.required_scopes if action else [])]
    for scope in required_scopes:
        for concrete, _ in _locations(canonical, scope):
            value = _get_concrete(canonical, concrete)
            if value is _MISSING or value is None or value == "":
                raise ValidationDetailsException(
                    [{"pointer": "/data" + concrete, "code": "task.action.required"}]
                )
    return canonical
