"""Client predicates use the same release semantics as registered client targeting."""

import pytest

from apps.clients.domain.contracts import ClientContext
from apps.expressions.application.language import (
    EvaluationError,
    ExpressionCompiler,
    ExpressionContext,
    ExpressionError,
)


def compile_client(source):
    from apps.clients.domain.contracts import client_expression_schema

    return ExpressionCompiler().compile(
        source, {"client": client_expression_schema()}, expected_schema={"type": "boolean"}
    )


def evaluate(source, release=None, kind="DESKTOP"):
    client = ClientContext(kind=kind, release=release)
    return (
        compile_client(source)
        .evaluate(
            ExpressionContext(
                request={}, process={}, current_user={}, steps={}, client=client.expression_values()
            )
        )
        .value
    )


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        ("2.9", False),
        ("2.10", True),
        ("2.10.0+desktop.7", True),
        ("2.10.0-rc.1", False),
        ("3.0", False),
        (None, False),
    ],
)
def test_release_range_uses_numeric_and_prerelease_order(release, expected):
    assert evaluate('version_in_range(client.release, "2.10", "3.0")', release) is expected


def test_client_kind_and_capabilities_are_typed_and_missing_identity_is_explicit():
    assert evaluate('client.kind == "ANDROID"', kind="ANDROID") is True
    assert evaluate('client.kind == "DESKTOP"', kind=None) is False
    assert evaluate("client.release is null") is True
    assert evaluate('client.trusted or contains(client.renderer_capabilities, "table")') is False


@pytest.mark.parametrize(
    "source",
    [
        'client.release >= "2.10"',
        'client.release == "2.10"',
        'client.release is "2.10"',
        "client.release is client.kind",
        'lower(client.release) >= "2.10"',
        'client.release + "" >= "2.10"',
        'version_in_range(client.release, "3.0", "2.0")',
        "version_in_range(client.release, null, null)",
        'version_in_range(client.release, "invalid", null)',
        "version_in_range(client.release, client.release, null)",
        'version_in_range(client.kind, "2.10", null)',
        'client.secret == "x"',
        "contains(client.renderer_capabilities, 42)",
        "42 in client.renderer_capabilities",
    ],
)
def test_bad_release_predicates_fail_at_authoring_with_location(source):
    with pytest.raises(ExpressionError) as error:
        compile_client(source)
    assert error.value.line == 1
    assert error.value.column >= 0


def test_malformed_runtime_release_is_error_not_false_fallback():
    with pytest.raises(EvaluationError, match="expression.runtime.invalid"):
        evaluate('version_in_range(client.release, "2.10", null)', "invalid")
