"""Trusted AI tool registration rejects policy drift before model construction."""

from typing import Any, cast

import pytest

from apps.ai.application.tools import TrustedAITool, register_trusted_tool, resolve_trusted_tools
from apps.ai.domain.contracts import AIPermittedData


def policy(*, retrieval: bool = True) -> AIPermittedData:
    return AIPermittedData(
        allowed_fields={"ticket"},
        allowed_classifications={"INTERNAL"},
        allowed_tools={"lookup_reference_test"},
        allowed_retrieval_sources={"approved_documents"} if retrieval else set(),
    )


def lookup_reference(document_id: str) -> str:
    return f"Reference {document_id}"


def test_registered_tool_requires_approval_and_pinned_retrieval_source() -> None:
    tool = TrustedAITool(
        key="lookup_reference_test",
        version="1",
        description="Look up one approved reference document",
        function=lookup_reference,
        retrieval_source="approved_documents",
    )
    register_trusted_tool(tool)
    resolved = resolve_trusted_tools(policy(), {tool.key: tool.version})
    assert resolved == (tool,)
    adapter = tool.pydantic_tool()
    assert adapter.requires_approval
    assert adapter.max_retries == 0
    assert adapter.sequential
    from pydantic_ai.messages import ToolCallPart

    assert tool.validate_call(
        ToolCallPart(tool_name=tool.key, args={"document_id": "DOC-1"}, tool_call_id="call-1")
    ) == {"document_id": "DOC-1"}
    with pytest.raises(ValueError, match="arguments are invalid"):
        tool.validate_call(
            ToolCallPart(tool_name=tool.key, args={"wrong": "DOC-1"}, tool_call_id="call-2")
        )
    with pytest.raises(ValueError, match="arguments are invalid"):
        tool.validate_call(
            ToolCallPart(
                tool_name=tool.key,
                args={"document_id": "X" * 9000},
                tool_call_id="call-large",
            )
        )
    with pytest.raises(ValueError, match="differs from the pinned"):
        tool.validate_call(
            ToolCallPart(tool_name="other", args={"document_id": "DOC-1"}, tool_call_id="call-3")
        )
    with pytest.raises(ValueError, match="already registered"):
        register_trusted_tool(tool)
    with pytest.raises(ValueError, match="source is not allowed"):
        resolve_trusted_tools(policy(retrieval=False), {tool.key: tool.version})
    with pytest.raises(ValueError, match="unavailable or changed"):
        resolve_trusted_tools(policy(), {tool.key: "2"})
    with pytest.raises(ValueError, match="differ from the agent allowlist"):
        resolve_trusted_tools(policy(), {})


def test_effectful_or_invalid_tool_registration_is_refused() -> None:
    with pytest.raises(ValueError, match="Effectful"):
        TrustedAITool(
            key="write_request_test",
            version="1",
            description="Write a request",
            function=lookup_reference,
            read_only=False,
        )
    with pytest.raises(ValueError, match="key is invalid"):
        TrustedAITool(
            key="../../import", version="1", description="Invalid", function=lookup_reference
        )


@pytest.mark.anyio
async def test_pydantic_tool_call_defers_before_read_only_execution() -> None:
    from pydantic_ai import Agent, DeferredToolRequests
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    called = False

    def lookup_document(document_id: str) -> str:
        nonlocal called
        called = True
        return f"Document {document_id}"

    tool = TrustedAITool(
        key="lookup_approval_test",
        version="1",
        description="Look up an approved document",
        function=lookup_document,
    )

    def model_response(messages, info):
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="lookup_approval_test",
                    args={"document_id": "DOC-1"},
                    tool_call_id="call-1",
                )
            ]
        )

    agent = Agent(
        FunctionModel(model_response),
        output_type=cast(Any, [str, DeferredToolRequests]),
        tools=[cast(Any, tool.pydantic_tool())],
        retries=0,
    )
    result = await agent.run("Look up DOC-1")
    assert isinstance(result.output, DeferredToolRequests)
    assert len(result.output.approvals) == 1
    assert result.output.approvals[0].tool_call_id == "call-1"
    assert not called
