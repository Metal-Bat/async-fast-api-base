"""Public behavior of the bounded workflow expression language."""

from typing import Any

import pytest

from apps.expressions.application.language import (
    EvaluationError,
    ExpressionCompiler,
    ExpressionContext,
    ExpressionError,
    ExpressionLimits,
)


def context_schema() -> dict[str, dict[str, Any]]:
    return {
        "request": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer"},
                "name": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        "process": {
            "type": "object",
            "properties": {"priority": {"type": "integer"}},
            "additionalProperties": False,
        },
        "current_user": {
            "type": "object",
            "properties": {"is_superuser": {"type": "boolean"}},
            "additionalProperties": False,
        },
        "steps": {
            "type": "object",
            "properties": {
                "lookup": {
                    "type": "object",
                    "properties": {
                        "outputs": {
                            "type": "object",
                            "properties": {"score": {"type": "number"}},
                            "additionalProperties": False,
                        }
                    },
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
        },
    }


def test_compile_and_evaluate_typed_namespaces_without_python_eval() -> None:
    compiler = ExpressionCompiler()
    expression = compiler.compile(
        'request.amount >= 10 and starts_with(lower(request.name), "a") '
        "and steps.lookup.outputs.score < 9.5",
        context_schema(),
        expected_schema={"type": "boolean"},
    )
    result = expression.evaluate(
        ExpressionContext(
            request={"amount": 12, "name": "Ada", "tags": []},
            process={"priority": 2},
            current_user={"is_superuser": False},
            steps={"lookup": {"outputs": {"score": 8.25}}},
        )
    )
    assert result.value is True
    assert result.record.input_summary["request"]["type"] == "object"
    assert "Ada" not in str(result.record)
    assert result.record.error is None


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("request.missing == 1", "expression.path.unknown"),
        ('request.amount + "1"', "expression.type.incompatible"),
        ('__import__("os")', "expression.function.unknown"),
        ("request.__class__", "expression.path.forbidden"),
        ("[item for item in request.tags]", "expression.syntax.unsupported"),
    ],
)
def test_compile_rejects_unknown_unsafe_and_incompatible_expressions(
    source: str, code: str
) -> None:
    with pytest.raises(ExpressionError) as captured:
        ExpressionCompiler().compile(source, context_schema())
    assert captured.value.code == code
    assert captured.value.line == 1
    assert captured.value.column >= 0


def test_limits_fail_deterministically_at_compile_and_runtime() -> None:
    compiler = ExpressionCompiler(ExpressionLimits(max_nodes=8, max_work=3))
    with pytest.raises(ExpressionError, match="limit") as first:
        compiler.compile("1 + 2 + 3 + 4 + 5", context_schema())
    with pytest.raises(ExpressionError) as second:
        compiler.compile("1 + 2 + 3 + 4 + 5", context_schema())
    assert (first.value.code, first.value.line, first.value.column) == (
        second.value.code,
        second.value.line,
        second.value.column,
    )

    compiled = compiler.compile("request.amount + 1", context_schema())
    with pytest.raises(EvaluationError) as exhausted:
        compiled.evaluate(
            ExpressionContext(request={"amount": 1}, process={}, current_user={}, steps={})
        )
    assert exhausted.value.code == "expression.work.exhausted"


def test_null_array_and_supported_operator_semantics_are_stable() -> None:
    schemas = context_schema()
    schemas["request"]["properties"]["optional"] = {"type": ["string", "null"]}
    context = ExpressionContext(
        request={"amount": 2, "name": "x", "tags": ["a", "b"], "optional": None},
        process={"priority": 1},
        current_user={"is_superuser": False},
        steps={"lookup": {"outputs": {"score": 1.0}}},
    )
    compiler = ExpressionCompiler()
    assert compiler.compile("request.optional is null", schemas).evaluate(context).value is True
    assert compiler.compile('contains(request.tags, "b")', schemas).evaluate(context).value is True
    assert (
        compiler.compile("request.amount * 3 + process.priority", schemas).evaluate(context).value
        == 7
    )


def test_integer_property_and_repeat_invariants() -> None:
    compiler = ExpressionCompiler()
    compiled = compiler.compile("request.amount * 2 - process.priority", context_schema())
    for amount in range(-100, 101):
        context = ExpressionContext(
            request={"amount": amount, "name": "x", "tags": []},
            process={"priority": 3},
            current_user={"is_superuser": False},
            steps={"lookup": {"outputs": {"score": 1.0}}},
        )
        first = compiled.evaluate(context).value
        second = compiled.evaluate(context).value
        assert first == second == amount * 2 - 3


def test_unreachable_step_output_is_absent_from_the_compilation_schema() -> None:
    schemas = context_schema()
    schemas["steps"]["properties"] = {}
    with pytest.raises(ExpressionError) as captured:
        ExpressionCompiler().compile("steps.lookup.outputs.score > 0", schemas)
    assert captured.value.code == "expression.path.unknown"
