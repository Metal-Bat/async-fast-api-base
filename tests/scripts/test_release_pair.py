"""Paired verification checks DTO meaning even when operation identifiers stay fixed."""

import json
from copy import deepcopy
from typing import Any

import pytest
from scripts.verify_release_pair import assert_contract_equal


def test_unchanged_operation_id_does_not_hide_incompatible_dto():
    contract: dict[str, Any] = {
        "paths": {"/example": {"get": {"operationId": "example"}}},
        "components": {"schemas": {"Example": {"properties": {"quantity": {"type": "integer"}}}}},
    }
    consumer = deepcopy(contract)
    consumer["components"]["schemas"]["Example"]["properties"]["quantity"]["type"] = "string"
    with pytest.raises(ValueError, match="components"):
        assert_contract_equal(contract, consumer)


def test_security_scheme_drift_fails_the_pair():
    with pytest.raises(ValueError, match="components"):
        assert_contract_equal(
            {"paths": {}, "components": {"securitySchemes": {"bearer": {"type": "http"}}}},
            {"paths": {}, "components": {}},
        )


def test_new_producer_source_file_invalidates_frozen_manifest(tmp_path, monkeypatch):
    from scripts import verify_release_pair

    monkeypatch.setattr(verify_release_pair, "ROOT", tmp_path)
    authority = tmp_path / verify_release_pair.AUTHORITY
    authority.mkdir(parents=True)
    (authority / "manifest.json").write_text(json.dumps({"source_files": {}}))
    (tmp_path / "src").mkdir()
    (tmp_path / "src/new_contract.py").write_text("value = 1\n")
    with pytest.raises(ValueError, match="Producer source changed"):
        verify_release_pair.verify_pair(tmp_path / "absent-peer")
