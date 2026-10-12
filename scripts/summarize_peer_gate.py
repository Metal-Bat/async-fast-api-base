"""Publish frontend gate scope and counts without raw browser or business diagnostics."""

import argparse
import json
import re
from pathlib import Path

REQUIRED = (
    "format:check",
    "api:check",
    "delivery:check",
    "typecheck",
    "lint",
    "test:ci",
    "test:boundary",
    "test:deployment",
    "test:diagnostics",
    "build",
    "test:browser-quality",
    "release:evidence",
)


def summarize(manifest: dict) -> dict:
    """A source change, tool diagnostic or missing mandatory command prevents a pass."""
    commands = [
        {
            "name": row["name"],
            "exit_code": row["exitCode"],
            "diagnostic_count": row["diagnosticCount"],
        }
        for row in manifest["commands"]
        if row.get("name") in REQUIRED
    ]
    not_run = [name for name in REQUIRED if name not in {row["name"] for row in commands}]
    failed = bool(
        manifest["exitCode"]
        or manifest["sourceChangedDuringCheck"]
        or not_run
        or any(row["exit_code"] or row["diagnostic_count"] for row in commands)
    )
    identity = {}
    for key in ("commit", "treeSha256", "finalTreeSha256", "lockSha256", "openapiSha256"):
        value = manifest.get(key, "")
        if value and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is None:
            raise ValueError("Invalid gate identity")
        identity[key] = value
    failed |= not all(identity.values()) or identity["treeSha256"] != identity["finalTreeSha256"]
    return {
        "status": "FAILED" if failed else "VERIFIED_LOCAL",
        "identity": identity,
        "commands": commands,
        "not_run": not_run,
        "source_changed_during_check": manifest["sourceChangedDuringCheck"],
        "live_backend_browser": "SEPARATE_REQUIRED_EVIDENCE",
        "deployed": "NOT_ATTESTED",
        "user_accepted": "NOT_ATTESTED",
    }


def main() -> int:
    """Create a fresh sanitized artifact from actual gate evidence, including failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.source.is_symlink() or args.report.exists() or args.report.is_symlink():
        parser.error("Compare existing evidence; links and overwrites are refused")
    report = summarize(json.loads(args.source.read_text()))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    print("Frontend sanitized gate status: " + report["status"])
    return 0 if report["status"] == "VERIFIED_LOCAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
