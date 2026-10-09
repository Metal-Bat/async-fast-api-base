"""Every planned notification has a real producer seam or an explicit blocked owner."""

import ast
import json
from pathlib import Path
from string import Formatter

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("map_id", [f"MAP-{number:02d}" for number in range(1, 15)])
def test_notification_row_has_safe_bilingual_contract_and_producer(map_id: str) -> None:
    manifest = json.loads((ROOT / "docs/delivery/notification-map.json").read_text())
    fixtures = json.loads((ROOT / "tests/fixtures/delivery/notification-events.json").read_text())
    rows = {row["id"]: row for row in manifest["events"]}
    assert len(rows) == len(manifest["events"]) == 14
    row, fixture = rows[map_id], fixtures[map_id]
    assert row["audience"] and row["authorization"] and row["cancellation"]
    assert row["dedupe_fields"] and "recipient_id" in row["dedupe_fields"]
    assert set(fixture["identity"]) == set(row["dedupe_fields"])
    assert row["channel_scope"] == ["IN_APP", "EMAIL"]
    assert set(row["templates"]) == {"en", "fa"}
    for translation in row["templates"].values():
        for template in translation.values():
            assert {
                field for _, field, _, _ in Formatter().parse(template) if field is not None
            } <= set(row["variables"])
            assert len(template.format_map(fixture["variables"])) <= 512
    assert fixture["expected_target_kind"] == row["target_kind"]
    source = ROOT / row["source_file"]
    assert source.exists()
    tree = ast.parse(source.read_text())
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
    }
    assert row["source_symbol"] in functions
    if row["producer_status"] == "EXISTING_EVENT":
        strings = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert set(row["source_events"]) <= strings
    elif row["producer_status"] == "EXISTING_COMMAND_HOOK":
        strings = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert row["id"] in strings and row["blocked_by"] is None
    else:
        assert row["producer_status"] == "BLOCKED_PRODUCER"
        assert row["blocked_by"].startswith("APP-BE-")
        assert row["producer_gap"]
    if row["target_kind"] in {"calendar", "report", "support", "account"}:
        assert row["requires_case"] is False


def test_notification_contract_retains_legacy_case_fields() -> None:
    from apps.notifications.domain.dto import NotificationDTO

    assert NotificationDTO.model_fields["request_ref_id"].is_required()
    assert NotificationDTO.model_fields["process_ref_id"].is_required()
    manifest = json.loads((ROOT / "docs/delivery/notification-map.json").read_text())
    assert len({row["template_key"] for row in manifest["events"]}) == 14
    assert manifest["schema_version"] == 1
    assert manifest["delivery_implemented_by"] == "APP-BE-014"
