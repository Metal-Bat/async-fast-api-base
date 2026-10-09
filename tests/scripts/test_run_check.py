"""The delivery gate retains failures and rejects warnings and skipped required tests."""

import json
import sys
from pathlib import Path

from scripts.run_check import approved_warning_filters, permitted_default_exclusions, run_step


def test_gate_retains_failed_command_and_stderr(tmp_path: Path) -> None:
    row = run_step(
        "failure",
        [sys.executable, "-c", "import sys; print('failed', file=sys.stderr); sys.exit(7)"],
        tmp_path,
        {},
    )
    assert row["returncode"] == 7
    assert row["status"] == "FAILED"
    assert "failed" in (tmp_path / "failure.log").read_text()


def test_gate_rejects_emitted_tool_warning_even_when_exit_zero(tmp_path: Path) -> None:
    row = run_step(
        "warning", [sys.executable, "-c", "print('WARN invalid dependency metadata')"], tmp_path, {}
    )
    assert row["returncode"] == 0
    assert row["status"] == "FAILED"
    assert row["diagnostics"] == ["WARN invalid dependency metadata"]


def test_gate_rejects_missing_or_skipped_required_suite(tmp_path: Path) -> None:
    command = [sys.executable, "-c", "print('ok')"]
    assert run_step("required", command, tmp_path, {}, required_tests=True)["status"] == "FAILED"
    (tmp_path / "required.xml").write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="1">'
        '<testcase name="required"><skipped message="Postgres missing"/></testcase>'
        "</testsuite></testsuites>"
    )
    row = run_step("required", command, tmp_path, {}, required_tests=True)
    assert row["status"] == "FAILED"
    assert row["tests"]["skipped"] == [
        {"name": "required", "classname": "", "type": "", "reason": "Postgres missing"}
    ]
    json.dumps(row)


def test_gate_accepts_actual_passing_required_suite(tmp_path: Path) -> None:
    (tmp_path / "required.xml").write_text(
        '<testsuites><testsuite tests="1"><testcase name="scenario"/></testsuite></testsuites>'
    )
    row = run_step(
        "required", [sys.executable, "-c", "print('passed')"], tmp_path, {}, required_tests=True
    )
    assert row["status"] == "PASSED"
    assert row["tests"]["passed"] == 1


def test_default_exclusions_reject_unexpected_skip_and_xfail():
    assert permitted_default_exclusions(
        [
            {
                "name": "db",
                "classname": "tests.integration.test_forms",
                "reason": "uses PostgreSQL",
                "type": "pytest.skip",
            }
        ]
    )
    assert not permitted_default_exclusions(
        [
            {
                "name": "required",
                "classname": "tests.core.test_policy",
                "reason": "uses PostgreSQL",
                "type": "pytest.skip",
            }
        ]
    )


def test_default_legacy_service_exclusion_is_limited_to_its_module():
    row = {
        "name": "test_postgresql_and_dragonfly_are_available",
        "classname": "tests.integration.test_services",
        "reason": "set RUN_INTEGRATION=1 with Docker Compose services running",
        "type": "pytest.skip",
    }
    assert permitted_default_exclusions([row])
    assert not permitted_default_exclusions([row | {"classname": "tests.integration.test_forms"}])
    assert not permitted_default_exclusions([row | {"type": "pytest.xfail"}])


def test_only_owner_approved_filters_can_enter_the_gate(tmp_path):
    import pytest

    root = Path(__file__).resolve().parents[2]
    assert len(approved_warning_filters(root)) == 2
    (tmp_path / "docs/delivery").mkdir(parents=True)
    (tmp_path / "docs/delivery/approved-decisions.json").write_text(
        (root / "docs/delivery/approved-decisions.json").read_text()
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nfilterwarnings = ["ignore"]\n'
    )
    with pytest.raises(ValueError, match="approval"):
        approved_warning_filters(tmp_path)
    assert not permitted_default_exclusions(
        [
            {
                "name": "db",
                "classname": "tests.integration.test_forms",
                "reason": "unexpected failure",
                "type": "pytest.xfail",
            }
        ]
    )
