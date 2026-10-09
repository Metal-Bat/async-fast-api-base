"""Run the unchanged quality stages with native strict diagnostics and private evidence."""

import importlib.metadata
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
STAGES = (
    "lock-check",
    "fmt-check",
    "lint",
    "docstrings",
    "typecheck",
    "security",
    "doctest",
    "test",
    "flow-test",
    "delivery-foundation-test",
    "delivery-wave-four-test",
    "delivery-transfer-test",
    "delivery-through-020-test",
    "delivery-completion-test",
    "precommit-check",
)
_DIAGNOSTIC = re.compile(r"^(?:WARN(?:ING)?\b|.*\b\w+Warning:|.*\bwarning\[)", re.IGNORECASE)


def approved_warning_filters(root: Path) -> list[str]:
    """Reject any policy expansion beyond the two expressly accepted SDK exceptions."""
    decision = json.loads((root / "docs/delivery/approved-decisions.json").read_text())["D07"]
    approved = decision["warning_filters"]
    policy = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"][
        "filterwarnings"
    ]
    if (
        len(approved) != 2
        or policy != approved
        or decision["verification_label"] != "VERIFIED_WITH_EXCEPTION"
    ):
        raise ValueError("Warning policy differs from the recorded owner approval")
    return approved


def _test_results(path: Path) -> dict:
    if not path.exists():
        return {"passed": 0, "failed": 0, "skipped": [], "missing": True}
    root = ElementTree.parse(path).getroot()
    cases = list(root.iter("testcase"))
    skipped = [
        {
            "name": case.get("name"),
            "classname": case.get("classname", ""),
            "type": skip.get("type", ""),
            "reason": skip.get("message", skip.text or ""),
        }
        for case in cases
        if (skip := case.find("skipped")) is not None
    ]
    failed = sum(
        case.find("failure") is not None or case.find("error") is not None for case in cases
    )
    return {
        "passed": len(cases) - len(skipped) - failed,
        "failed": failed,
        "skipped": skipped,
        "missing": not cases,
    }


def permitted_default_exclusions(rows: list[dict]) -> bool:
    """Allow only documented opt-in integration exclusions, never xfail or unit skips."""
    reasons = {
        "uses PostgreSQL",
        "uses PostgreSQL and S3",
        "uses isolated PostgreSQL",
        "requires disposable Celery test infrastructure",
        "requires disposable reporting worker and storage",
        "requires owned worker and HTTPS email gateway",
        "requires disposable paired transfer services",
        "requires disposable PostgreSQL/S3 and Docker CLI",
        "loads disposable PostgreSQL volume fixtures",
        "requires disposable worker infrastructure",
        "uses the configured disposable integration database",
    }
    return all(
        row["classname"].startswith("tests.integration.")
        and row["type"] == "pytest.skip"
        and (
            row["reason"] in reasons
            or (
                row["classname"] == "tests.integration.test_services"
                and row["reason"] == "set RUN_INTEGRATION=1 with Docker Compose services running"
            )
        )
        for row in rows
    )


def run_step(
    name: str,
    command: list[str],
    directory: Path,
    environment: dict[str, str],
    *,
    required_tests: bool = False,
) -> dict:
    """Retain command status, categorized diagnostics and individual test exclusions."""
    started = datetime.now(UTC).isoformat()
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=os.environ | environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    (directory / f"{name}.log").write_text(result.stdout)
    print(result.stdout, end="", flush=True)
    diagnostics = [line for line in result.stdout.splitlines() if _DIAGNOSTIC.match(line)]
    tests = _test_results(directory / f"{name}.xml")
    failed = bool(result.returncode or diagnostics)
    if required_tests:
        failed |= bool(tests["missing"] or tests["failed"] or tests["skipped"])
    return {
        "stage": name,
        "command": command,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "returncode": result.returncode,
        "status": "FAILED" if failed else "PASSED",
        "diagnostics": diagnostics,
        "tests": tests,
        "log": f"{name}.log",
    }


def _source_state() -> dict:
    """Hash tracked and new nonignored files without collecting private environment contents."""
    paths = (
        subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    digests = {
        name: sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(paths))
        if name and not name.startswith("graphify-out/") and (ROOT / name).is_file()
    }
    return {
        "files": digests,
        "sha256": sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest(),
    }


def _tool_state() -> dict:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    pins = tomllib.loads((ROOT / ".mise.toml").read_text())["tools"]
    packages = ("ruff", "ty", "pre-commit")
    locked = {item["name"]: item["version"] for item in lock["package"] if item["name"] in packages}
    installed = {name: importlib.metadata.version(name) for name in packages}
    mismatches = [name for name in packages if not pins[name] == locked[name] == installed[name]]
    return {
        "python": sys.version,
        "installed": installed,
        "locked": locked,
        "mismatches": mismatches,
    }


def main() -> int:
    """Produce an inspectable report and stop at the first actual failed stage."""
    directory = Path(tempfile.mkdtemp(prefix="app-be-check-"))
    tools = _tool_state()
    warning_filters = approved_warning_filters(ROOT)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "lock_sha256": sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "working_diff_sha256": sha256(
            subprocess.run(
                ["git", "diff", "--binary", "HEAD"], cwd=ROOT, capture_output=True, check=True
            ).stdout
        ).hexdigest(),
        "tools": tools,
        "source_state": _source_state(),
        "stages": [],
        "not_run": list(STAGES),
        "status": "FAILED",
        "approved_warning_exceptions": warning_filters,
        "approval_record": "docs/delivery/approved-decisions.json#D07",
    }
    print(f"Private gate evidence: {directory}", flush=True)
    try:
        if tools["mismatches"]:
            print("Tool/lock/mise mismatch: " + ", ".join(tools["mismatches"]), file=sys.stderr)
            return 1
        for name in STAGES:
            environment = {}
            if name in {
                "test",
                "doctest",
                "flow-test",
                "delivery-foundation-test",
                "delivery-wave-four-test",
                "delivery-transfer-test",
                "delivery-through-020-test",
                "delivery-completion-test",
            }:
                environment["PYTEST_ADDOPTS"] = (
                    os.getenv("PYTEST_ADDOPTS", "")
                    + f" -ra --junitxml={directory / (name + '.xml')}"
                    + " -o "
                    + shlex.quote("filterwarnings=error\n" + "\n".join(warning_filters))
                )
            row = run_step(
                name,
                ["mise", "run", name],
                directory,
                environment,
                required_tests=name
                in {
                    "test",
                    "doctest",
                    "flow-test",
                    "delivery-foundation-test",
                    "delivery-wave-four-test",
                    "delivery-transfer-test",
                    "delivery-through-020-test",
                    "delivery-completion-test",
                },
            )
            # Default opt-in exclusions are reported, not represented as integrated passes.
            if name == "test" and row["returncode"] == 0 and not row["diagnostics"]:
                row["status"] = (
                    "PASSED"
                    if row["tests"]["passed"]
                    and not row["tests"]["failed"]
                    and permitted_default_exclusions(row["tests"]["skipped"])
                    else "FAILED"
                )
            report["stages"].append(row)
            report["not_run"].remove(name)
            if row["status"] != "PASSED":
                return row["returncode"] or 1
        report["status"] = "VERIFIED_WITH_EXCEPTION"
        return 0
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
