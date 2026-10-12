"""Sanitized frontend evidence cannot promote incomplete or warning-bearing checks."""

from scripts.summarize_peer_gate import summarize


def test_peer_summary_rejects_missing_mandatory_browser_stage():
    result = summarize({"exitCode": 0, "sourceChangedDuringCheck": False, "commands": []})
    assert result["status"] == "FAILED" and "test:browser-quality" in result["not_run"]


def test_peer_summary_retains_warning_failure_without_raw_output():
    result = summarize(
        {
            "exitCode": 0,
            "sourceChangedDuringCheck": False,
            "commands": [
                {
                    "name": "format:check",
                    "exitCode": 0,
                    "diagnosticCount": 1,
                    "output": "private response",
                }
            ],
        }
    )
    assert result["status"] == "FAILED"
    assert result["commands"] == [{"name": "format:check", "exit_code": 0, "diagnostic_count": 1}]
    assert "private response" not in str(result)


def test_source_changed_or_missing_identity_never_passes_complete_commands():
    from scripts.summarize_peer_gate import REQUIRED

    manifest = {
        "exitCode": 0,
        "sourceChangedDuringCheck": False,
        "commands": [{"name": name, "exitCode": 0, "diagnosticCount": 0} for name in REQUIRED],
    }
    assert summarize(manifest)["status"] == "FAILED"
    manifest.update(
        commit="a" * 40,
        treeSha256="b" * 64,
        finalTreeSha256="b" * 64,
        lockSha256="c" * 64,
        openapiSha256="d" * 64,
    )
    assert summarize(manifest)["status"] == "VERIFIED_LOCAL"
    assert summarize(manifest | {"sourceChangedDuringCheck": True})["status"] == "FAILED"
