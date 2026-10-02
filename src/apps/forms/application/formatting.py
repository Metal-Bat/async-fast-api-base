"""Lossless canonical conversion for the explicit bpms.format/1 profile."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from typing import Any
from zoneinfo import ZoneInfo

from apps.forms.domain.localization import FieldFormatting, FormatSample, FormattedValue

_LATIN = "0123456789."
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹٫"


def format_value(value: str, profile: FieldFormatting) -> tuple[str, str]:
    """Return exact canonical and display strings; never guess calendar or round."""
    if len(value) > 256:
        raise ValueError("Formatting input exceeds limit")
    if profile.kind == "text":
        return value, value
    raw = (
        value.translate(str.maketrans(_PERSIAN, _LATIN))
        if profile.numbering == "arabext"
        else value
    )
    if profile.kind == "date":
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
            raise ValueError("Expected Gregorian YYYY-MM-DD")
        canonical = display = date.fromisoformat(raw).isoformat()
    elif profile.kind == "datetime":
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
            raw,
        ):
            raise ValueError("Expected offset datetime with at most microsecond precision")
        if raw.endswith("-00:00"):
            raise ValueError("Unknown offset is not supported")
        if raw[-6:-5] in {"+", "-"} and (int(raw[-5:-3]) > 23 or int(raw[-2:]) > 59):
            raise ValueError("Invalid UTC offset")
        parsed = datetime.fromisoformat(raw)
        try:
            canonical = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
            display = parsed.astimezone(ZoneInfo(profile.timezone)).isoformat()
        except OverflowError, ValueError:
            raise ValueError("Datetime outside supported range") from None
    else:
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw):
            raise ValueError("Expected decimal without grouping, exponent or currency")
        amount = Decimal(raw)
        with localcontext() as context:
            context.prec = 512
            if profile.decimal_places is not None:
                scaled = amount.quantize(Decimal(1).scaleb(-profile.decimal_places))
                if scaled != amount:
                    raise ValueError("Decimal would require rounding")
                amount = scaled
            canonical = display = format(amount, "f")
    if profile.numbering == "arabext":
        display = display.translate(str.maketrans(_LATIN, _PERSIAN))
    if profile.currency:
        display += " " + profile.currency
    return canonical, display


def format_samples(render: dict[str, Any], samples: list[FormatSample]) -> list[FormattedValue]:
    results = []
    for sample in samples:
        node: Any = render
        try:
            if not sample.node_pointer.startswith("/root"):
                raise ValueError("Expected a render node pointer")
            for part in sample.node_pointer.removeprefix("/").split("/"):
                key = part.replace("~1", "/").replace("~0", "~")
                node = node[int(key)] if isinstance(node, list) else node[key]
            profile = FieldFormatting.model_validate(node["formatting"])
            canonical, display = format_value(sample.value, profile)
        except KeyError, IndexError, TypeError, ValueError:
            raise ValueError("Invalid formatting sample: " + sample.node_pointer) from None
        results.append(
            FormattedValue(node_pointer=sample.node_pointer, canonical=canonical, display=display)
        )
    return results


def canonical_value_issues(
    render: dict[str, Any], data: Any, schema: dict[str, Any]
) -> list[tuple[str, str]]:
    """Validate submitted canonical values, including repeated collection items."""
    issues: list[tuple[str, str]] = []
    stack = [render["root"]]
    while stack:
        node = stack.pop()
        stack.extend(node.get("children", []))
        if not node.get("formatting") or not node.get("scope"):
            continue
        profile = FieldFormatting.model_validate(node["formatting"])
        if profile.kind == "text":
            continue
        profile = profile.model_copy(update={"numbering": "latn", "currency": None})
        parts = node["scope"].removeprefix("/").split("/")
        candidates: list[tuple[Any, str]] = [(data, "/data")]
        schema_cursor = schema
        i = 0
        while i < len(parts):
            keyword = parts[i]
            if keyword == "properties":
                key = parts[i + 1].replace("~1", "/").replace("~0", "~")
                schema_cursor = schema_cursor["properties"][key]
                candidates = [
                    (value[key], path + "/" + parts[i + 1])
                    for value, path in candidates
                    if isinstance(value, dict) and key in value
                ]
                i += 2
            elif keyword == "items":
                prefix_count = len(schema_cursor.get("prefixItems", []))
                schema_cursor = schema_cursor["items"]
                candidates = [
                    (item, path + f"/{index}")
                    for value, path in candidates
                    if isinstance(value, list)
                    for index, item in enumerate(value)
                    if index >= prefix_count
                ]
                i += 1
            elif keyword == "prefixItems":
                index = int(parts[i + 1])
                schema_cursor = schema_cursor["prefixItems"][index]
                candidates = [
                    (value[index], path + f"/{index}")
                    for value, path in candidates
                    if isinstance(value, list) and index < len(value)
                ]
                i += 2
            else:
                raise ValueError("Invalid field scope")
        for value, path in candidates:
            if value is None:
                continue
            try:
                if not isinstance(value, str) or format_value(value, profile)[0] != value:
                    raise ValueError("Noncanonical value")
            except ValueError:
                issues.append((path, "data.canonical_format"))
                if len(issues) == 32:
                    return issues
    return issues
