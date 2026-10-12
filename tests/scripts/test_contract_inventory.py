"""The authoritative contract inventory detects new routes and competing authorities."""

from copy import deepcopy

import pytest


def test_effective_routes_include_lazy_routers_and_live_stream():
    from scripts.contract_inventory import operation_inventory

    from main import app

    inventory = operation_inventory(app)
    declared = {
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert set(inventory) == declared
    assert inventory["GET /api/v1/inbox/events"]["response_family"] == "sse"
    assert all(item["owner"] and item["disposition"] for item in inventory.values())
    assert inventory["PATCH /api/v1/me/preferences"]["permission_dependencies"]


def test_new_route_is_not_silently_accepted_by_a_frozen_inventory():
    from scripts.contract_inventory import check_operation_inventory

    frozen = {"GET /known": {"owner": "example", "operation_id": "known"}}
    changed = deepcopy(frozen)
    changed["GET /unclassified"] = {"owner": "example", "operation_id": "new"}
    with pytest.raises(ValueError, match="unclassified"):
        check_operation_inventory(changed, frozen)


def test_competing_contract_authority_is_rejected():
    from scripts.contract_inventory import check_authorities

    with pytest.raises(ValueError, match="authority"):
        check_authorities(["producer-a", "producer-b"])
    check_authorities(["producer-a"])


def test_every_actual_fixed_json_model_obeys_the_recursive_wire_contract():
    from scripts.contract_inventory import audit_public_models

    from main import app

    audit_public_models(app)


def test_inventory_definition_sources_are_real_repository_paths():
    from pathlib import Path

    from scripts.contract_inventory import field_inventory

    from main import app

    for model, row in field_inventory(app).items():
        assert row["source"].startswith("transport-generated:") or Path(row["source"]).is_file(), (
            model
        )


def test_declared_error_and_sse_json_models_are_in_the_inventory():
    from scripts.contract_inventory import reachable_models

    from main import app

    names = reachable_models(app)
    assert "utils.presenter.ErrorResponse" in names
    assert "apps.notifications.domain.live.InboxChanged" in names
    assert "apps.notifications.domain.live.InboxResync" in names
