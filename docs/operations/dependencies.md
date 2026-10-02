---
tags: [operations, dependencies, deployment]
---

# Dependency and installation policy

`pyproject.toml` declares the package requirements. `uv.lock` fixes the resolved versions for reproducible installs. Commit both files together when dependencies change.

| Environment | Command | Installed groups | Purpose |
| --- | --- | --- | --- |
| Local development | `uv sync --locked` | Runtime and default `dev` group | API work, tests, lint, docs generation and pre-commit. |
| Local quality gate | `mise run check` | Same local environment | Lock, formatting, lint, docstrings, type, security, doctest, unit tests, a disposable PostgreSQL workflow regression and pre-commit, run sequentially. |
| Production image | `uv sync --locked --no-default-groups --no-install-project --active` | Runtime dependencies only | Builder creates `/opt/venv`; runtime stage copies that environment. |

The image then runs `uv pip check --python /opt/venv/bin/python` to detect missing or incompatible installed distributions. `--no-default-groups` is explicit because uv normally includes the default `dev` group. `--no-install-project` is intentional: the image copies `src/` into the runtime stage and launches from there; this project is not installed as a distribution. Do not use `uv sync` without group exclusion in the production Dockerfile.

The `dev` group contains Bandit, detect-secrets, Ruff, Ty, pytest/coverage/benchmark tools, pre-commit, debugpy, factory-boy and Commitizen. The runtime dependency list contains FastAPI, PostgreSQL, broker/cache/storage, BPMS, AI, telemetry and export libraries used by the application. The exact dependency tree is in `uv.lock`; `uv tree --only-group dev` and `uv tree --no-default-groups` help inspect each view. The Docker dry-run `uv sync --locked --no-default-groups --no-install-project --dry-run` shows which local dev packages would be removed when switching environments.

## Upgrade procedure

1. Edit direct requirements in `pyproject.toml`, then run `uv lock --upgrade` for a compatible refresh. This repository permits required prerelease OpenTelemetry instrumentation packages. Keep the direct Pydantic bound below `2.14` until a stable compatible release exists and its API behavior is checked.
2. Run `uv sync --locked` locally and `mise run check`. Verify `uv lock --check` succeeds after the change.
3. Build the backend image and run `uv pip check` inside it. Smoke-test startup, migrations, API schema and representative workflows against disposable services before deployment.
4. Commit `pyproject.toml` and `uv.lock` together. A changed lockfile requires rebuilding the backend, worker, reporting worker and scheduler images before they share one dependency set.

Integration tests are opt-in and require migrated disposable services. The local `mise run check` also requires PostgreSQL for the disposable core workflow regression; use the other integration commands in the [README](../../README.md#testing) for database, broker and storage behavior. Never point migration round-trip tests at a persistent database.
