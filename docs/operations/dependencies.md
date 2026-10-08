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

The pytest configuration contains two exact message/module filters for Python 3.14 deprecations
inside `cohere.client` and `google.genai.types`. These are temporary test-output exceptions,
not patches to the SDKs or a guarantee of compatibility with Python 3.16/3.17. Remove them when
compatible upstream releases fix the deprecated APIs. Application deprecations and other SDK
messages remain visible; `tests/utils/test_warning_policy.py` verifies that boundary. Google
tracks its warning in [python-genai issue 1640](https://github.com/googleapis/python-genai/issues/1640).

1. Edit direct requirements in `pyproject.toml`, then run `uv lock --upgrade` for a compatible refresh. This repository permits required prerelease OpenTelemetry instrumentation packages. Keep the direct Pydantic bound below `2.14` until a stable compatible release exists and its API behavior is checked.
2. Run `uv sync --locked` locally and `mise run check`. Verify `uv lock --check` succeeds after the change.
3. Build the backend image and run `uv pip check` inside it. Smoke-test startup, migrations, API schema and representative workflows against disposable services before deployment.
4. Commit `pyproject.toml` and `uv.lock` together. A changed lockfile requires rebuilding the backend, worker, reporting worker and scheduler images before they share one dependency set.

Integration tests are opt-in and require migrated disposable services. The local `mise run check` also requires PostgreSQL for the disposable core workflow regression; use the other integration commands in the [README](../../README.md#testing) for database, broker and storage behavior. Never point migration round-trip tests at a persistent database.

## Cache startup and SQL tracing compatibility

SQLAlchemy is constrained to `>=2.0.54,<2.1` because the installed OpenTelemetry SQLAlchemy
instrumentor declares `<2.1.0`. Keep this bound until the instrumentor supports 2.1; the
observability regression executes a query and checks its emitted span instead of bypassing
the instrumentor dependency check. Keep the asyncio extra installed.

The local Dragonfly image defaults `CACHE_THREADS=2`. Dragonfly needs at least 256 MiB of
available memory per thread; automatic CPU-based sizing previously requested 3 GiB on a
12-thread machine and exited. Set `CACHE_THREADS` in `.envs/.cache` for larger deployments.
The cache restarts unless stopped, logs startup errors to stderr, and exposes an authenticated
PING health check. Backend, worker, reporting worker and scheduler wait for cache health.
This startup check does not replace runtime retries during later cache outages.

After pulling these changes, rebuild the images so both the cache command and locked Python
packages are installed:

```bash
docker compose up -d --build cache backend worker reporting-worker scheduler
```

This command preserves named volumes. Inspect `docker compose logs cache` and
`docker compose ps` if startup fails; restarting workers alone cannot repair a stopped cache.
Celery continues storing results in the configured Redis-compatible backend. Scheduler cleanup
is deferred until the current asyncio runner call unwinds when a shutdown signal arrives.
See [REPO-004](../changes/REPO-004.md) for validation and deployment details.
