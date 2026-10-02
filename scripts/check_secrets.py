"""Fail the quality gate when detect-secrets reports potential secrets."""

import json
import subprocess
import sys
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1] / ".secrets.baseline"


def main() -> int:
    result = subprocess.run(
        [
            "detect-secrets",
            "scan",
            "--all-files",
            "src",
            "tests",
            "scripts",
            "compose",
            ".envs/examples",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        print(result.stderr or result.stdout, file=sys.stderr)
        return result.returncode
    try:
        findings = json.loads(result.stdout)["results"]
    except json.JSONDecodeError, KeyError, TypeError:
        print("detect-secrets did not return a valid results object", file=sys.stderr)
        return 1
    try:
        reviewed = json.loads(BASELINE.read_text())["results"]
        allowed = {
            (filename, item["type"], item["hashed_secret"])
            for filename, items in reviewed.items()
            for item in items
            if item.get("is_secret") is False
        }
        findings = {
            filename: [
                item
                for item in items
                if (filename, item["type"], item["hashed_secret"]) not in allowed
            ]
            for filename, items in findings.items()
        }
        findings = {filename: items for filename, items in findings.items() if items}
    except OSError, ValueError, KeyError, TypeError, AttributeError:
        print("Secret baseline is missing or invalid", file=sys.stderr)
        return 1
    count = sum(len(items) for items in findings.values())
    if count:
        print(f"detect-secrets found {count} potential secrets in {len(findings)} files:")
        for filename, items in sorted(findings.items()):
            lines = ", ".join(str(item["line_number"]) for item in items)
            print(f"  {filename}: lines {lines}")
        return 1
    print("detect-secrets: no findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
