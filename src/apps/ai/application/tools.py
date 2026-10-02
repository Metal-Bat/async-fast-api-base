"""Trusted, versioned read-only AI tools; workflow JSON never supplies Python code."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Tool
from pydantic_ai.messages import ToolCallPart

from apps.ai.domain.contracts import AIPermittedData


@dataclass(frozen=True, slots=True)
class TrustedAITool:
    key: str
    version: str
    description: str
    function: Callable[..., Any]
    retrieval_source: str | None = None
    read_only: bool = True

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", self.key) is None:
            raise ValueError("Tool key is invalid")
        if not self.version or len(self.version) > 128:
            raise ValueError("A bounded tool version is required")
        if not self.description or len(self.description) > 512:
            raise ValueError("A bounded tool description is required")
        if (
            self.retrieval_source is not None
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", self.retrieval_source) is None
        ):
            raise ValueError("Retrieval source key is invalid")
        if not self.read_only:
            raise ValueError("Effectful AI tools require a separate idempotent adapter")

    def validate_call(self, call: ToolCallPart) -> dict[str, Any]:
        """Revalidate a model-proposed call before showing it for approval."""
        if call.tool_name != self.key or not call.tool_call_id:
            raise ValueError("AI tool call differs from the pinned tool")
        try:
            raw = call.args_as_dict(raise_if_invalid=True)
            if len(json.dumps(raw, sort_keys=True, separators=(",", ":"))) > 8192:
                raise ValueError("Tool arguments exceed the bounded approval payload")
            return self.pydantic_tool().function_schema.validator.validate_python(raw)
        except TypeError, ValueError:
            raise ValueError("AI tool arguments are invalid") from None

    def pydantic_tool(self) -> Tool[Any]:
        return Tool(
            self.function,
            name=self.key,
            description=self.description,
            max_retries=0,
            sequential=True,
            requires_approval=True,
        )


_TOOLS: dict[str, TrustedAITool] = {}


def register_trusted_tool(tool: TrustedAITool) -> None:
    """Only deployed Python code can register a tool; a duplicate key cannot replace it."""
    if tool.key in _TOOLS:
        raise ValueError("Trusted AI tool key already registered")
    _TOOLS[tool.key] = tool


def resolve_trusted_tools(
    policy: AIPermittedData, pinned_versions: dict[str, str]
) -> tuple[TrustedAITool, ...]:
    """Reject missing, changed or unauthorized tools before a provider request."""
    from apps.ai.application import query_lookup  # noqa: F401 -- register deployed query adapter

    if set(pinned_versions) != policy.allowed_tools:
        raise ValueError("Pinned tools differ from the agent allowlist")
    resolved = []
    for key, version in sorted(pinned_versions.items()):
        tool = _TOOLS.get(key)
        if tool is None or tool.version != version:
            raise ValueError("Trusted AI tool is unavailable or changed")
        if tool.retrieval_source is not None and not policy.permits_retrieval(
            tool.retrieval_source
        ):
            raise ValueError("Trusted AI retrieval source is not allowed")
        resolved.append(tool)
    return tuple(resolved)


def pin_trusted_tools(policy: AIPermittedData) -> dict[str, str]:
    from apps.ai.application import query_lookup  # noqa: F401 -- register deployed adapter

    versions = {key: _TOOLS[key].version for key in policy.allowed_tools if key in _TOOLS}
    resolve_trusted_tools(policy, versions)
    return versions
