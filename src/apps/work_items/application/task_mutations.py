"""Actor-filtered patches and a shared safe mutation response projection."""

from copy import deepcopy
from typing import Any

from apps.work_items.application.task_views import _data_path, filter_identity, project_data
from utils.exceptions import ValidationDetailsException

_MISSING = object()


def _covers(path: tuple[str, ...], scope: str) -> bool:
    bound = _data_path(scope)
    return len(path) >= len(bound) and all(
        part == expected or expected == "*" for part, expected in zip(path, bound)
    )


def _related(path: tuple[str, ...], scope: str) -> bool:
    bound = _data_path(scope)
    return all(part == expected or expected == "*" for part, expected in zip(path, bound))


def _pointer(path: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)


def _instance_path(pointer: str) -> tuple[str, ...]:
    if not pointer.startswith("/") or pointer == "/":
        raise ValueError("A non-root instance pointer is required")
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:])


def visible_scopes(
    policy: dict[str, list[str]] | None, view_scopes: set[str] | None = None
) -> set[str] | None:
    if not bool(policy) or not any(policy.values()):
        return view_scopes
    scopes = set(policy.get("read", [])) | set(policy.get("write", []))
    if view_scopes is not None:
        scopes &= view_scopes
    return {
        scope
        for scope in scopes
        if not any(_covers(_data_path(scope), hidden) for hidden in policy.get("hidden", []))
    }


def _erase(value: Any, path: tuple[str, ...]) -> None:
    if not path:
        return
    head, *tail = path
    if isinstance(value, list) and head == "*":
        for child in value:
            _erase(child, tuple(tail))
    elif isinstance(value, dict) and head in value:
        if tail:
            _erase(value[head], tuple(tail))
        else:
            del value[head]


def merge_task_data(
    before: dict[str, Any],
    incoming: dict[str, Any],
    policy: dict[str, list[str]] | None,
    *,
    view_scopes: set[str] | None = None,
    delete_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Patch supplied writable values; omission preserves state and delete_paths is explicit."""
    legacy = not bool(policy) or not any(policy.values())
    scopes = visible_scopes(policy, view_scopes)
    writable = set((policy or {}).get("write", []))
    hidden = (policy or {}).get("hidden", [])

    def readable(path: tuple[str, ...], *, container: bool = False) -> bool:
        return not any(_covers(path, scope) for scope in hidden) and (
            scopes is None
            or any((_related if container else _covers)(path, scope) for scope in scopes)
        )

    def allowed(path: tuple[str, ...]) -> bool:
        return readable(path) and (legacy or any(_covers(path, scope) for scope in writable))

    def deny(path: tuple[str, ...]) -> None:
        raise ValidationDetailsException(
            [{"pointer": "/data" + _pointer(path), "code": "task.field.read_only"}]
        )

    def merge(old: Any, new: Any, path: tuple[str, ...]) -> Any:
        if not readable(path, container=isinstance(new, dict | list)):
            deny(path)
        if isinstance(new, dict):
            result = deepcopy(old) if isinstance(old, dict) else {}
            for key, child in new.items():
                result[key] = merge(result.get(key, _MISSING), child, (*path, key))
            return result
        if isinstance(new, list):
            # Structural changes need authority over the entire collection and no hidden descendants.
            if allowed(path) and not any(_related(path, scope) for scope in hidden):
                return deepcopy(new)
            if not isinstance(old, list) or len(old) != len(new):
                deny(path)
            return [
                merge(left, right, (*path, str(index)))
                for index, (left, right) in enumerate(zip(old, new, strict=True))
            ]
        if any(_related(path, scope) for scope in hidden):
            deny(path)
        if not allowed(path) and old != new:
            deny(path)
        return deepcopy(new)

    result = deepcopy(incoming) if legacy and view_scopes is None else merge(before, incoming, ())
    for pointer in delete_paths or []:
        try:
            path = _instance_path(pointer)
        except ValueError:
            raise ValidationDetailsException(
                [{"pointer": "/delete_paths", "code": "task.delete.invalid"}]
            ) from None
        if not allowed(path) or any(_related(path, scope) for scope in hidden):
            deny(path)
        parent: Any = result
        for part in path[:-1]:
            if isinstance(parent, dict):
                parent = parent.get(part)
            elif (
                isinstance(parent, list)
                and part.isdigit()
                and str(int(part)) == part
                and int(part) < len(parent)
            ):
                parent = parent[int(part)]
            else:
                parent = None
                break
        if isinstance(parent, list):
            deny(
                path
            )  # Stable-row structure is changed through collection commands, never index deletion.
        if isinstance(parent, dict):
            parent.pop(path[-1], None)
    return result


def project_task_state(
    data: dict[str, Any],
    identity: dict[str, list[str]] | None,
    provenance: dict[str, dict[str, Any]] | None,
    issues: list[dict[str, Any]],
    policy: dict[str, list[str]] | None,
    view_scopes: set[str] | None = None,
) -> dict[str, Any]:
    """Filter values, identities, override metadata and error locations through one actor policy."""
    scopes = visible_scopes(policy, view_scopes)
    hidden = (policy or {}).get("hidden", [])
    values = deepcopy(data) if scopes is None else project_data(data, scopes)
    for scope in hidden:
        _erase(values, _data_path(scope))

    def visible(path: tuple[str, ...], *, ancestor: bool = False) -> bool:
        return not any(_covers(path, scope) for scope in hidden) and (
            scopes is None
            or any((_related if ancestor else _covers)(path, scope) for scope in scopes)
        )

    keys = deepcopy(identity) if scopes is None else filter_identity(identity, scopes)
    keys = {
        path: value
        for path, value in (keys or {}).items()
        if visible(_instance_path(path), ancestor=True)
    }
    overrides = {}
    for scope, entry in (provenance or {}).items():
        try:
            path = _data_path(scope) if scope.startswith("/properties/") else _instance_path(scope)
        except ValueError:
            continue
        if visible(path) and not any(_related(path, scope) for scope in hidden):
            # Checksums of hidden inputs must remain server-only.
            overrides[scope] = {
                key: deepcopy(value)
                for key, value in entry.items()
                if key in {"actor_ref_id", "reason", "value", "recorded_at"}
            }
    safe_issues = []
    for issue in issues:
        pointer = issue.get("pointer", "")
        try:
            path = (
                _data_path(pointer)
                if pointer.startswith("/properties/")
                else _instance_path(pointer.removeprefix("/data"))
            )
        except ValueError:
            continue
        if visible(path):
            safe_issues.append(
                {
                    "pointer": pointer,
                    "code": issue.get("code")
                    if issue.get("code") in {"data.invalid", "task.action.required"}
                    else "task.validation",
                }
            )
    return {
        "data": values,
        "item_identity": keys,
        "override_provenance": overrides,
        "issues": safe_issues,
    }


def normalize_task_behavior(documents, before, incoming, canonical, overrides):
    """Recompute merged calculations; reject explicitly forged derived values."""
    if not documents.behavior_dialect:
        return canonical
    from apps.forms.application.behavior import (
        _MISSING as missing,
    )
    from apps.forms.application.behavior import (
        BehaviorError,
        _get_concrete,
        _locations,
        evaluate_behavior,
    )
    from apps.forms.application.bindings import render_nodes

    try:
        normalized = evaluate_behavior(
            documents, canonical, overrides=overrides, enforce_required=False
        ).data
        for _, node in render_nodes(documents.render_schema):
            if not node.get("calculation") or not node.get("scope"):
                continue
            for concrete, _ in _locations(normalized, node["scope"]):
                supplied = _get_concrete(incoming, concrete)
                if (
                    supplied is not missing
                    and supplied != _get_concrete(before, concrete)
                    and supplied != _get_concrete(normalized, concrete)
                ):
                    raise BehaviorError("behavior.derived_tampered")
        return normalized
    except BehaviorError as exc:
        raise ValidationDetailsException([{"pointer": "/data", "code": str(exc)}]) from None
