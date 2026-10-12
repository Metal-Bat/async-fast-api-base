"""Pure limits shared by versioned form and authoring documents."""

import json
from typing import Any

from apps.forms.domain.dto import ValidationIssue


class InvalidDocument(Exception):
    def __init__(self, path: str, code: str) -> None:
        self.issue = ValidationIssue(pointer=path, code=code)


def bounded_document(value: Any, path: str) -> int:
    count = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        count += 1
        if depth > 24 or count > 2048:
            raise InvalidDocument(path, "document.limit")
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            if len(item) > 256:
                raise InvalidDocument(path, "document.limit")
            stack.extend((v, depth + 1) for v in item)
    try:
        size = len(json.dumps(value, allow_nan=False).encode())
    except ValueError, TypeError, RecursionError:
        raise InvalidDocument(path, "document.invalid") from None
    if size > 65536:
        raise InvalidDocument(path, "document.limit")
    return count
