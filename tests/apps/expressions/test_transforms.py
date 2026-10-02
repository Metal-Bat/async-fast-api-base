"""Explicit conversion behavior used by TRANSFORM steps."""

from decimal import Decimal

import pytest

from apps.expressions.application.transforms import (
    Conversion,
    TransformEngine,
    TransformError,
    TransformSpec,
)


@pytest.mark.parametrize(
    ("conversion", "value", "expected"),
    [
        ("string", 42, "42"),
        ("integer", "-42", -42),
        ("decimal", "12.50", Decimal("12.50")),
        ("boolean", "true", True),
        ("date", "2026-09-22", "2026-09-22"),
        ("date_time", "2026-09-22T12:30:00+03:30", "2026-09-22T09:00:00Z"),
        ("array", '[1,"two"]', [1, "two"]),
    ],
)
def test_explicit_conversion_families(
    conversion: Conversion, value: object, expected: object
) -> None:
    outcome = TransformEngine().apply(TransformSpec(conversion=conversion), value)
    assert outcome.value == expected
    assert outcome.record.error is None
    assert str(value) not in str(outcome.record.input_summary)


def test_projection_default_null_and_formatting_are_explicit() -> None:
    engine = TransformEngine()
    projected = engine.apply(
        TransformSpec(
            conversion="object",
            projection={"display_name": "/profile/name", "id": "/id"},
        ),
        {"id": 7, "profile": {"name": "Ada", "secret": "hidden"}},
    )
    assert projected.value == {"display_name": "Ada", "id": 7}
    assert (
        engine.apply(
            TransformSpec(conversion="integer", null_behavior="default", default=5), None
        ).value
        == 5
    )
    assert (
        engine.apply(TransformSpec(conversion="string", format="Value: {}"), 12).value
        == "Value: 12"
    )


@pytest.mark.parametrize("value", ["1.2", "NaN", "9999999999999999999999999", [], {}])
def test_integer_conversion_has_structured_redacted_failures(value: object) -> None:
    with pytest.raises(TransformError) as captured:
        TransformEngine().apply(TransformSpec(conversion="integer"), value)
    assert captured.value.code == "transform.integer.invalid"
    assert captured.value.record.error == "transform.integer.invalid"
    assert str(value) not in str(captured.value.record.input_summary)


def test_transform_work_and_output_limits_are_enforced() -> None:
    with pytest.raises(TransformError, match="limit") as captured:
        TransformEngine().apply(
            TransformSpec(conversion="array"), "[" + ",".join("1" for _ in range(300)) + "]"
        )
    assert captured.value.code == "transform.limit"


def test_integer_conversion_property_and_date_format_allowlist() -> None:
    engine = TransformEngine()
    for value in range(-500, 501):
        assert engine.apply(TransformSpec(conversion="integer"), str(value)).value == value
    with pytest.raises(ValueError, match="locale-dependent"):
        TransformSpec(conversion="date", format="%B %d")
