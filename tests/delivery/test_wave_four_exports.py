"""Frozen handoff artifacts preserve authorization, private headers and wire contracts."""

import json
from hashlib import sha256
from pathlib import Path

from apps.users.domain.help_state import HelpReleaseMetadata

ARTIFACTS = Path(__file__).resolve().parents[2] / "docs/delivery/wave-four"


def test_wave_four_artifact_integrity_and_help_metadata_only():
    manifest = json.loads((ARTIFACTS / "manifest.json").read_text())
    for name, digest in manifest["artifacts"].items():
        assert sha256((ARTIFACTS / name).read_bytes()).hexdigest() == digest
    sample = HelpReleaseMetadata.model_validate_json(
        (ARTIFACTS / "help-release.synthetic.json").read_text()
    )
    assert sample.release_key == "synthetic-contract-example"
    assert set(sample.items[0].model_dump()) == {"help_key", "revision", "locales"}


def test_private_contracts_have_real_security_headers_and_localization():
    english = json.loads((ARTIFACTS / "openapi-en.json").read_text())
    persian = json.loads((ARTIFACTS / "openapi-fa.json").read_text())
    for path, method in (
        ("/me/preferences", "get"),
        ("/me/preferences", "patch"),
        ("/me/profile", "get"),
        ("/me/help-state", "get"),
        ("/resource-links/resolve", "post"),
        ("/analytics/query", "post"),
        ("/designer/inspector-contract", "get"),
        ("/designer/config-validation", "post"),
        ("/me/saved-views", "post"),
        ("/me/saved-views/search", "post"),
        ("/me/favorites", "post"),
        ("/me/favorites/search", "post"),
        ("/setup/readiness", "get"),
        ("/designer/dependency-readiness", "post"),
        ("/inbox/search", "post"),
        ("/inbox/unread", "get"),
    ):
        operation = english["paths"]["/api/v1" + path][method]
        assert operation["security"]
        assert "Cache-Control" in operation["responses"]["200"]["headers"]
        assert operation["summary"] != persian["paths"]["/api/v1" + path][method]["summary"]
    patch = english["components"]["schemas"]["PreferencesPatch"]
    assert patch["additionalProperties"] is False
    assert patch["required"] == ["ref_id"]
    assert "actor_id" not in patch["properties"]
