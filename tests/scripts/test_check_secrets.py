"""Secret checks must reject new findings even beside reviewed fixtures."""

import json
import subprocess

from scripts import check_secrets


def test_secret_gate_allows_only_reviewed_fingerprints(monkeypatch, tmp_path, capsys):
    baseline = tmp_path / "baseline.json"
    known = {"type": "Secret Keyword", "hashed_secret": "reviewed", "is_secret": False}
    baseline.write_text(json.dumps({"results": {"tests/example.py": [known]}}))
    monkeypatch.setattr(check_secrets, "BASELINE", baseline, raising=False)
    findings = {"tests/example.py": [{**known, "line_number": 10}]}
    calls = []

    def scan(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, json.dumps({"results": findings}), "")

    monkeypatch.setattr(check_secrets.subprocess, "run", scan)
    assert check_secrets.main() == 0
    assert "--all-files" in calls[0]
    findings["tests/example.py"].append(
        {"type": "Secret Keyword", "hashed_secret": "new", "line_number": 11}
    )
    assert check_secrets.main() == 1
    assert "tests/example.py: lines 11" in capsys.readouterr().out
    findings.clear()
    findings["src/copied.py"] = [{**known, "line_number": 5}]
    assert check_secrets.main() == 1


def test_secret_gate_fails_when_scanner_fails(monkeypatch):
    monkeypatch.setattr(
        check_secrets.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 2, "", "scan failed"),
    )
    assert check_secrets.main() == 2
