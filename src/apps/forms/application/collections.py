"""Stable UUIDv7 editing identities separate from canonical array values."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID, uuid7


class CollectionError(ValueError):
    pass


@dataclass(frozen=True)
class CollectionEdit:
    data: dict[str, Any]
    identity: dict[str, list[str]]
    index_map: dict[int, int | None]
    issues: list[dict[str, Any]] = field(default_factory=list)


def _walk(
    value: Any,
    path: str,
    identity: dict[str, list[str]],
    schema: dict[str, Any] | None = None,
) -> None:
    if isinstance(value, list):
        if schema is not None and schema.get("items", {}).get("type") != "object":
            return
        if path in identity:
            keys = identity[path]
            if len(keys) != len(value) or len(set(keys)) != len(keys):
                raise CollectionError("collection.identity")
        else:
            identity[path] = [str(uuid7()) for _ in value]
        for index, child in enumerate(value):
            _walk(child, f"{path}/{index}", identity, schema.get("items") if bool(schema) else None)
    elif isinstance(value, dict):
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            child_schema = schema.get("properties", {}).get(key) if bool(schema) else None
            _walk(child, f"{path}/{escaped}", identity, child_schema)


def initialize_identity(
    data: dict[str, Any],
    existing: dict[str, list[str]] | None = None,
    schema: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    result = deepcopy(existing) if existing is not None else {}
    _walk(data, "", result, schema)
    reachable: dict[str, list[str]] = {}
    _walk(data, "", reachable, schema)
    result = {path: result[path] for path in reachable}
    all_keys = [key for keys in result.values() for key in keys]
    if len(set(all_keys)) != len(all_keys):
        raise CollectionError("collection.duplicate_key")
    try:
        if any(UUID(key).version != 7 for key in all_keys):
            raise ValueError("not UUIDv7")
    except ValueError:
        raise CollectionError("collection.item_key") from None
    return result


def _array(data: dict[str, Any], path: str) -> list[Any]:
    if not path.startswith("/"):
        raise CollectionError("collection.path")
    node: Any = data
    for raw in path[1:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(node, list):
                if not part.isdecimal():
                    raise ValueError("not an array index")
                node = node[int(part)]
            else:
                node = node[part]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise CollectionError("collection.path") from exc
    if not isinstance(node, list):
        raise CollectionError("collection.path")
    return node


def edit_collection(
    data: dict[str, Any],
    identity: dict[str, list[str]],
    path: str,
    operation: Literal["add", "remove", "reorder", "duplicate"],
    *,
    item_key: str | None = None,
    target_index: int | None = None,
    value: Any = None,
    schema: dict[str, Any] | None = None,
) -> CollectionEdit:
    current = deepcopy(data)
    keys = initialize_identity(current, identity, schema)
    array = _array(current, path)
    if path not in keys:
        raise CollectionError("collection.path")
    old_keys = keys[path]
    if len(array) >= 256 and operation in {"add", "duplicate"}:
        raise CollectionError("collection.limit")
    if operation != "add" and (item_key is None or item_key not in old_keys):
        raise CollectionError("collection.item_key")
    if target_index is None:
        target_index = len(array) if operation == "add" else old_keys.index(item_key or "")
    if target_index < 0 or target_index > len(array):
        raise CollectionError("collection.target_index")
    entries: list[tuple[str, Any, int | None]] = [
        (key, deepcopy(item), index)
        for index, (key, item) in enumerate(zip(old_keys, array, strict=True))
    ]
    if operation == "add":
        entries.insert(target_index, (str(uuid7()), deepcopy(value), None))
    elif operation == "duplicate":
        entries.insert(
            target_index + 1, (str(uuid7()), deepcopy(array[old_keys.index(item_key or "")]), None)
        )
    elif operation == "remove":
        entries.pop(old_keys.index(item_key or ""))
    elif operation == "reorder":
        entry = entries.pop(old_keys.index(item_key or ""))
        entries.insert(min(target_index, len(entries)), entry)
    else:
        raise CollectionError("collection.operation")
    array[:] = [item for _, item, _ in entries]
    moved: dict[str, list[str]] = {}
    prefix = path + "/"
    for old_path, child_keys in keys.items():
        if not old_path.startswith(prefix):
            moved[old_path] = child_keys
    index_map: dict[int, int | None] = {index: None for index in range(len(old_keys))}
    for new_index, (key, item, old_index) in enumerate(entries):
        if old_index is None:
            item_schema = array_schema(schema, path).get("items") if bool(schema) else None
            _walk(item, f"{path}/{new_index}", moved, item_schema)
        else:
            index_map[old_index] = new_index
            old_prefix = f"{path}/{old_index}/"
            for old_path, child_keys in keys.items():
                if old_path.startswith(old_prefix):
                    moved[f"{path}/{new_index}/" + old_path[len(old_prefix) :]] = child_keys
    moved[path] = [key for key, _, _ in entries]
    moved = initialize_identity(current, moved, schema)
    return CollectionEdit(current, moved, index_map)


def issue_item_keys(pointer: str, identity: dict[str, list[str]]) -> list[str]:
    if not pointer.startswith("/data/"):
        return []
    path = ""
    keys: list[str] = []
    for raw in pointer.split("/")[2:]:
        if path in identity and raw.isdecimal() and int(raw) < len(identity[path]):
            keys.append(identity[path][int(raw)])
        path += "/" + raw
    return keys


def array_schema(schema: dict[str, Any], path: str) -> dict[str, Any]:
    node: Any = schema
    for raw in path.split("/")[1:]:
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and node.get("type") == "object":
            node = node.get("properties", {}).get(part)
        elif isinstance(node, dict) and node.get("type") == "array" and part.isdecimal():
            node = node.get("items")
        else:
            raise CollectionError("collection.path")
        if not isinstance(node, dict):
            raise CollectionError("collection.path")
    if node.get("type") != "array":
        raise CollectionError("collection.path")
    return node


async def edit_submission_collection(session, submission, form, request, actor_id):
    """Edit one declared array under the caller's locked draft submission."""
    from jsonschema import Draft202012Validator
    from sqlmodel import col, select

    from apps.forms.application.attachments import AttachmentService
    from apps.requests.domain.entity import FormSubmissionAttachmentEntity
    from utils.date_utils import get_datetime_utc

    await AttachmentService(session).materialize(submission)
    declared = array_schema(form.data_schema, request.path)
    if declared.get("items", {}).get("type") != "object":
        raise CollectionError("collection.item_schema")
    if request.operation == "add" and not Draft202012Validator(declared.get("items", {})).is_valid(
        request.value
    ):
        raise CollectionError("collection.item_schema")
    original_identity = submission.item_identity or initialize_identity(
        submission.data, schema=form.data_schema
    )
    result = edit_collection(
        submission.data,
        original_identity,
        request.path,
        request.operation,
        item_key=request.item_key,
        target_index=request.target_index,
        value=request.value,
        schema=form.data_schema,
    )
    if request.operation in {"add", "duplicate"}:
        from apps.forms.application.attachments import _collections, _set_pointer

        if request.operation == "add":
            new_index = (
                request.target_index
                if request.target_index is not None
                else len(_array(submission.data, request.path))
            )
        else:
            source_index = original_identity[request.path].index(request.item_key)
            new_index = (
                request.target_index if request.target_index is not None else source_index
            ) + 1
        new_prefix = f"{request.path}/{new_index}/"
        for field_path in _collections(form.render_schema, result.data):
            if field_path.startswith(new_prefix):
                _set_pointer(result.data, field_path, [])
    if form.behavior_dialect is not None:
        from apps.forms.application.behavior import (
            BehaviorError,
            evaluate_behavior,
            pinned_behavior_documents,
        )
        from apps.forms.domain.dto import FormDocuments

        try:
            normalized = evaluate_behavior(
                pinned_behavior_documents(
                    FormDocuments.model_validate(form, from_attributes=True),
                    submission.design_snapshot,
                ),
                result.data,
                overrides=submission.override_provenance,
                enforce_required=False,
            ).data
        except BehaviorError as exc:
            raise CollectionError(str(exc)) from None
        result = CollectionEdit(
            normalized,
            initialize_identity(normalized, result.identity, form.data_schema),
            result.index_map,
        )
    if not Draft202012Validator(declared).is_valid(_array(result.data, request.path)):
        raise CollectionError("collection.schema")
    rows = list(
        (
            await session.exec(
                select(FormSubmissionAttachmentEntity)
                .where(
                    col(FormSubmissionAttachmentEntity.form_submission_id) == submission.id,
                    col(FormSubmissionAttachmentEntity.status) == "ACTIVE",
                    col(FormSubmissionAttachmentEntity.field_path).like(request.path + "/%"),
                )
                .with_for_update()
            )
        ).all()
    )
    moving = []
    for row in rows:
        suffix = row.field_path[len(request.path) + 1 :].split("/", 1)
        if not suffix[0].isdecimal() or int(suffix[0]) not in result.index_map:
            continue
        index = result.index_map[int(suffix[0])]
        if index is None:
            row.status = "REMOVED"
            row.removed_at = get_datetime_utc()
            row.removed_by_user_id = actor_id
        else:
            tail = "/" + suffix[1] if len(suffix) == 2 else ""
            destination = f"{request.path}/{index}{tail}"
            if destination != row.field_path:
                row.field_path = f"/_moving/{row.id}"
                moving.append((row, destination))
    if moving:
        await session.flush()
        for row, destination in moving:
            row.field_path = destination
    from apps.forms.application.behavior import pinned_behavior_documents
    from apps.forms.application.validation import FormValidator
    from apps.forms.domain.dto import FormDocuments

    validation = FormValidator().validate(
        pinned_behavior_documents(
            FormDocuments.model_validate(form, from_attributes=True),
            submission.design_snapshot,
        ),
        result.data,
    )
    result = CollectionEdit(
        result.data,
        result.identity,
        result.index_map,
        [
            {
                "pointer": issue.pointer,
                "code": issue.code,
                "item_keys": issue_item_keys(issue.pointer, result.identity),
            }
            for issue in validation.issues
        ],
    )
    submission.data = result.data
    submission.item_identity = result.identity
    submission.updated_at = get_datetime_utc()
    await session.flush()
    return result
