"""Build a local production image from an explicit source-only context; never publish it."""

import argparse
import json
import re
import shutil
import subprocess
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def build(image: str) -> dict:
    """Keep private workspace files outside Docker's context and report exact build inputs."""
    if re.fullmatch(r"app-be-runtime:[a-z0-9][a-z0-9_.-]{0,63}", image) is None:
        raise ValueError("Use an app-be-runtime local verification tag")
    with TemporaryDirectory(prefix="app-be-runtime-context-") as directory:
        context = Path(directory)
        for name in ("pyproject.toml", "uv.lock", "alembic.ini"):
            source = ROOT / name
            if source.is_symlink():
                raise ValueError("Build inputs must be regular repository files")
            shutil.copy2(source, context / name)
        for name in ("src", "compose/backend"):
            source = ROOT / name
            if source.is_symlink() or any(path.is_symlink() for path in source.rglob("*")):
                raise ValueError("Inspect source symlinks before building a runtime image")
            shutil.copytree(
                source,
                context / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.mo"),
            )
        hashes = {
            str(path.relative_to(context)): sha256(path.read_bytes()).hexdigest()
            for path in sorted(context.rglob("*"))
            if path.is_file()
        }
        subprocess.run(
            [
                "docker",
                "build",
                "--progress=plain",
                "--file",
                str(context / "compose/backend/Dockerfile"),
                "--tag",
                image,
                str(context),
            ],
            check=True,
        )
        digest = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {
            "image": image,
            "image_id": digest,
            "context_sha256": sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "context_files": hashes,
            "build_policy": "existing locked production Dockerfile; no environment/private workspace files",
            "runtime_acceptance": "NOT_RUN",
            "publication": "NOT_PERFORMED",
        }


def main() -> int:
    """Write only an explicitly requested evidence file; building does not attest startup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="app-be-runtime:" + uuid4().hex)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Evidence path already exists; compare it before choosing a fresh path")
    report = build(args.image)
    with args.report.open("x") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    print("Built local runtime image; startup and query acceptance remain separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
