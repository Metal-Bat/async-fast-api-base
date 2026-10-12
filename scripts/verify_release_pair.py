"""Verify one current source-hashed producer against the actual consumer snapshots."""

import argparse
import json
import subprocess
from hashlib import sha256
from pathlib import Path

from scripts.producer_identity import source_hashes

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = Path("docs/delivery/consistency-2026-10-09/contracts")


def consumer_source_identity(frontend: Path) -> str:
    """Use the frontend gate's exact source inventory and compact JSON digest convention."""
    names = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=frontend,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    tree = []
    for name in sorted(names):
        if name.startswith(("artifacts/", "graphify-out/")):
            continue
        path = frontend / name
        if path.is_symlink():
            raise ValueError("Compare consumer source symlink before attesting")
        tree.append([name, sha256(path.read_bytes()).hexdigest() if path.is_file() else "deleted"])
    return sha256(json.dumps(tree, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def assert_contract_equal(producer: dict, consumer: dict) -> None:
    """Compare complete operations/components, including descriptions, headers and security."""
    changed = [
        key for key in ("paths", "components", "security") if producer.get(key) != consumer.get(key)
    ]
    if changed:
        raise ValueError("Actual paired contract drift: " + ", ".join(changed))


def verify_pair(frontend: Path) -> dict:
    """Refuse stale producer inputs and preserve historical manifests while recording current intake."""
    authority = ROOT / AUTHORITY
    manifest = json.loads((authority / "manifest.json").read_text())
    if source_hashes(ROOT) != manifest["source_files"]:
        raise ValueError("Producer source changed; regenerate and review before verifying")
    intake = json.loads((frontend / "docs/reference/app-be-001/contract-manifest.json").read_text())
    observed = {}
    for locale in ("en", "fa", "ar"):
        name = "openapi-" + locale + ".json"
        producer_bytes = (authority / name).read_bytes()
        digest = sha256(producer_bytes).hexdigest()
        if manifest["artifacts"][name] != digest:
            raise ValueError("Producer artifact differs from its frozen manifest")
        consumer_bytes = (frontend / "docs/reference/app-be-001" / name).read_bytes()
        if sha256(consumer_bytes).hexdigest() != intake["schemas"][locale]["sha256"]:
            raise ValueError("Consumer snapshot differs from its reviewed intake")
        assert_contract_equal(json.loads(producer_bytes), json.loads(consumer_bytes))
        observed[locale] = digest
    assert_contract_equal(
        json.loads((authority / "openapi-en.json").read_text()),
        json.loads((frontend / "docs/reference/platform-openapi.json").read_text()),
    )
    current = intake.get("current_intake", {})
    if current.get("producer_source_sha256") != manifest["source_sha256"]:
        raise ValueError("Consumer intake does not acknowledge this exact producer source")
    peer_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=frontend, capture_output=True, text=True, check=True
    ).stdout.strip()
    backend_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    return {
        "schema_version": 1,
        "backend_head": backend_head,
        "producer_origin_head": manifest["backend_head"],
        "backend_source_sha256": manifest["source_sha256"],
        "frontend_head": peer_head,
        "frontend_tree_sha256": consumer_source_identity(frontend),
        "contracts": observed,
        "migration_chain": manifest["migration_chain"],
        "backend_lock_sha256": sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "frontend_lock_sha256": sha256((frontend / "pnpm-lock.yaml").read_bytes()).hexdigest(),
        "scenario": "purchase-connected/1",
        "ai_mode": "scripted_no_network",
        "worktrees": "Exact dirty source identity required in final gate evidence; HEAD alone is not the candidate",
        "snapshot_comparison": "PASS",
        "live_http_browser": "NOT_ATTESTED_BY_THIS_COMMAND",
        "hosted": "NOT_RUN",
        "deployed": "NOT_ATTESTED",
        "user_accepted": "NOT_ATTESTED",
    }


def main() -> int:
    """Create a fresh reviewable pair manifest; do not overwrite differing evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected-peer-sha")
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Compare existing evidence and use a fresh report path")
    report = verify_pair(args.frontend)
    if args.expected_peer_sha is not None and report["frontend_head"] != args.expected_peer_sha:
        parser.error("Checked-out frontend does not match the reviewed peer SHA")
    with args.report.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(
        "Exact producer/consumer contract comparison passed; live and hosted acceptance separate."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
