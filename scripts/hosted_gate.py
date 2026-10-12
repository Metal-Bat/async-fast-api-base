"""Provision fresh GitHub-hosted configuration and run the unchanged backend gate."""

import argparse
import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def validate_hosted_environment(root: Path, environment: dict[str, str]) -> None:
    """Refuse local/self-hosted configuration, mutable refs and existing private files."""
    workspace = Path(environment.get("GITHUB_WORKSPACE", "/nonexistent"))
    if (
        environment.get("GITHUB_ACTIONS") != "true"
        or environment.get("RUNNER_ENVIRONMENT") != "github-hosted"
        or re.fullmatch(r"[0-9a-f]{40}", environment.get("PEER_SHA", "")) is None
        or root.resolve() not in {workspace.resolve(), (workspace / "backend").resolve()}
        or (root / ".envs").is_symlink()
        or any(
            (root / ".envs" / name).exists() or (root / ".envs" / name).is_symlink()
            for name in (".backend", ".postgres", ".cache", ".s3", ".broker", ".pgadmin")
        )
    ):
        raise ValueError("Hosted setup requires a fresh GitHub-hosted checkout and exact peer SHA")


def provision(root: Path, environment: dict[str, str]) -> dict[str, str]:
    """Create private synthetic settings exclusively; never modify an operator file."""
    validate_hosted_environment(root, environment)
    overrides = {
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "INITIAL_ADMIN_PASSWORD": secrets.token_urlsafe(32),
        "SWAGGER_CLIENT_SECRET": secrets.token_urlsafe(32),
        "CACHE_PASSWORD": secrets.token_urlsafe(32),
        "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(32),
        "RABBITMQ_DEFAULT_PASS": secrets.token_urlsafe(32),
        "PGADMIN_DEFAULT_PASSWORD": secrets.token_urlsafe(32),
        "LOG_OUTPUTS": '["console"]',
        "LOG_FILE": "/tmp/hosted-services.log",
        "ENVIRONMENT": "local",
        "PROJECT_NAME": "test",
        "OTEL_TRACES_EXPORTER": "none",
        "OTEL_METRICS_EXPORTER": "none",
        "OTEL_LOGS_EXPORTER": "none",
    }
    backend = {}
    for name in (".backend", ".postgres", ".cache", ".s3", ".broker", ".pgadmin"):
        values = {
            key: value
            for key, value in dotenv_values(root / ".envs/examples" / name).items()
            if value is not None
        }
        values.update(
            {key: value for key, value in overrides.items() if key in values or name == ".backend"}
        )
        path = root / ".envs" / name
        with path.open("x") as stream:
            path.chmod(0o600)
            stream.write("".join(f"{key}={json.dumps(value)}\n" for key, value in values.items()))
        if name == ".backend":
            backend = values
    return backend


def main() -> int:
    """Keep raw evidence private and publish only structured non-business gate results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Use a fresh report path")
    environment = os.environ.copy()
    environment.update(provision(ROOT, environment))
    os.environ.update(environment)
    sys.path.insert(0, str(ROOT / "src"))
    # Import application-owned helpers only after settings have been provisioned.
    from scripts import run_flow_test
    from scripts.run_check import _source_state
    from scripts.transfer_services import transfer_services

    for service in ("postgres", "cache", "s3"):
        subprocess.run(["docker", "compose", "build", service], cwd=ROOT, check=True)
    asyncio.run(run_flow_test._ensure_postgres())
    database = f"bpms_flow_{uuid4().hex}"
    asyncio.run(run_flow_test._database_command(database, "create"))
    environment.update(POSTGRES_DB=database, FLOW_TEST_OWNED_DATABASE=database)
    code = 1
    report = {"status": "FAILED", "peer_sha": environment["PEER_SHA"], "hosted": True}
    try:
        subprocess.run(
            ["uv", "run", "--env-file", ".envs/.backend", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
        )
        with transfer_services(environment) as configured:
            # Ordinary test exclusions remain ordinary exclusions; each mandatory
            # flow profile enables its own flags and owns its own worker/database.
            configured = {
                key: value for key, value in configured.items() if not key.startswith("RUN_")
            }
            configured["TRANSFER_FRONTEND_ROOT"] = str(ROOT.parent / "frontend")
            start_source = _source_state()
            with tempfile.TemporaryFile(mode="w+") as output:
                code = subprocess.run(
                    ["mise", "run", "check"],
                    cwd=ROOT,
                    env=configured,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    check=False,
                ).returncode
                output.seek(0)
                match = re.search(
                    r"Private gate evidence: (/tmp/app-be-check-[a-z0-9_]+)", output.read()
                )
            if match:
                gate = json.loads((Path(match[1]) / "report.json").read_text())
                report.update(
                    status=gate["status"],
                    stages=[
                        {
                            "name": stage["stage"],
                            "status": stage["status"],
                            "returncode": stage["returncode"],
                            "passed": stage.get("tests", {}).get("passed"),
                            "failed": stage.get("tests", {}).get("failed"),
                            "skipped_count": len(stage.get("tests", {}).get("skipped", [])),
                        }
                        for stage in gate["stages"]
                    ],
                    not_run=gate["not_run"],
                    source_state=gate["source_state"],
                    approved_warning_exceptions=gate["approved_warning_exceptions"],
                )
                end_source = _source_state()
                report["source_start_sha256"] = start_source["sha256"]
                report["source_end_sha256"] = end_source["sha256"]
                report["backend_head"] = gate["git_head"]
                report["lock_sha256"] = gate["lock_sha256"]
                if start_source != end_source or gate["git_head"] != environment.get("GITHUB_SHA"):
                    report["status"] = "FAILED_SOURCE_IDENTITY"
                    code = code or 1
    finally:
        asyncio.run(run_flow_test._database_command(database, "drop"))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
    print(f"Hosted gate status: {report['status']}; sanitized report: {args.report}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
