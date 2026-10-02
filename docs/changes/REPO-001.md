# REPO-001 — Prepare a clean, reproducible repository baseline

Backlog: REPO-001
Date: 2026-10-02
Area: repository/tooling

## Summary

Organized the previously uncommitted implementation into a connected backend baseline,
documentation handoff, and contributor tooling. Added reproducible development templates,
corrected secret-scan coverage, and documented Obsidian navigation.

## Why

The user requested clean commits and instructions for viewing the project documentation in
Obsidian. Most implementation files were untracked. Local credentials were eligible for staging,
and the existing detect-secrets invocation skipped untracked files, creating misleading clean
results. Staging vendor assets also exposed hooks that rewrote their upstream whitespace.

## What Changed

- Track `.envs/examples/` with explicit development placeholders; ignore actual runtime files.
  README documents copying only missing files and retaining credentials for existing volumes.
  Quote JSON in the backend template so both uv and Compose preserve it.
- Scan source, tests, scripts, Compose files and templates with `--all-files`. Reviewed false
  positives are matched by file, detector type and fingerprint from `.secrets.baseline`.
  New findings fail; an identical value in another file is not automatically accepted. The
  baseline contains hashes, not secret values. Scanner failures remain failures.
- Added tests that first failed against the old gate, then verified reviewed exceptions,
  new findings, moved values and scanner failure behavior.
- Preserve vendor assets by excluding `src/static/docs/` from whitespace and EOF rewriting.
- Ignore local Obsidian state and downloaded research snapshots. `docs/Home.md` explains opening
  the repository root as a vault, standard Markdown link settings, and audience entry points.

## Architecture

No application architecture change. Runtime environment files were neither rewritten nor removed.

## Compatibility

Fresh clones must copy the tracked environment templates before starting Compose. Existing
local files and data volumes retain their configuration. Templates contain development-only
credentials; production deployments must supply their own. No schema or API change.

## Validation

- `rtk proxy timeout 120s uv --cache-dir /tmp/uv-cache run --no-sync pytest -q`
  — 631 passed, 114 opt-in infrastructure tests skipped, seven dependency warnings.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pytest -q tests/scripts/test_check_secrets.py`
  — two passed; the reviewed-fixture test failed before implementation.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync python scripts/check_secrets.py`
  — no unreviewed findings across tracked and untracked files.
- Ruff check/format, ty and all-file pre-commit checks passed. Vendor bytes were restored after
  the initial whitespace hooks identified their need for exclusion.
- Loaded `.envs/examples/.backend` through `uv run --env-file` and imported Settings successfully.
  The initial unquoted JSON template failed; quoting corrected the uv parsing failure.
- Documentation contract/link tests passed. Existing runtime credentials were confirmed absent
  from the index. Diff whitespace checks pass when excluding unchanged vendor distributions.

Result: PASS for repository preparation. No remote push, history rewrite, browser acceptance,
or new infrastructure-wide integration run was performed for this packaging change.

## Backlog Impact

All tasks reviewed. Existing completed feature records remain the implementation history.

Enabled: None

Blocked: None

Superseded: None

Conflicts: None

## References

Commit: backend baseline `0604352`; documentation and tooling follow as separate commits.

Pull Request: None

Additional notes: [Documentation home and Obsidian instructions](../Home.md),
[repository setup](../../README.md).
