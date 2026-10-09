# Verification through APP-BE-020

Status: VERIFIED_WITH_EXCEPTION — the complete fourteen-stage gate passed. The exact D07 SDK exceptions and
prior ten-entry baseline approval remain accepted; no exception expansion is authorized.

Observed focused results: support/calendar/reminder/visual PostgreSQL profile 9 passed;
actual scheduler/Redis broker/Celery/private transfer worker profile 6 passed; foundation
migration/seed/authority profile 16 passed; focused unit contracts 38 passed; ty passed.
The analytics fixture initially attempted to mutate immutable submitted_at and was
corrected to use the actual submission lifecycle with a controlled clock. The twenty-control
fixture found two production bugs (canonical attachment synchronization and partial-format
argument order), both fixed and exercised through published review/correction.

The final report will record exact source hashes, tools, per-stage counts, services,
required skips, default exclusions and limitations. See through-020-handoff.md.

The first full gate stopped at security with seven synthetic fixture findings. The hidden
form field now uses the accurate name private_note. New synthetic users use per-test
UUID placeholders instead of a constant password-hash literal, matching existing test
practice; these direct service tests do not authenticate those placeholders. No baseline
entry, scanner rule or suppression was added. The unchanged scanner now reports no findings.

The next full gate passed security/doctest but exposed a pytest module-name collision
between the new support test_contract.py and the existing work-group module. The support
module was renamed test_support_contract.py; collection uses the unchanged pytest policy.

The next complete gate passed the 29-case application profile but stopped in the paired
private transfer profile (5 passed/1 failed): HTTPX observed ReadError while sending an
11 MiB invalid multipart body after the peer's early declared-size rejection. The pinned
peer emits 413 without consuming that declared-oversized body; early rejection races
client transmission. The test now separately verifies declared-size rejection by sending
only actual HTTP headers, while retaining complete maximum-size upload/download and
maximum-plus-one backend rejection. This does not attest graceful peer handling of every
oversized streaming upload. That frontend transport gap remains in later paired acceptance.
The reminder broker test was also strengthened from injected publication failure to an
actual refused Redis connection followed by dispatch to the real owned Redis/Celery worker.
The owned runner uses Redis as its broker; no RabbitMQ verification is claimed.

The first refused-connection fixture was ineffective because CELERY_BROKER_URL overrides
the Celery constructor URL; the real live broker published one message and the test failed.
The fixture now sets and asserts its separate broker_write_url before dispatch. This
preserves the live worker's configuration and validates an actual refused connection.

Corrected final owned transfer/worker profile: 6 passed (23.64 seconds), including the
real refused write connection, retained occurrence identity and live worker recovery.
Declared-size preflight rejection, maximum private upload/download, backend oversize
rejection and current session/outsider protections also passed. Applicable final hooks
passed on changed transfer/worker and renamed support tests.

## Final closure — 2026-10-08

Command: `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check`, exit 0. Private report: `/tmp/app-be-check-faib6zqz/report.json`.
Public summary: [through-020-gate.json](through-020-gate.json).
Tested tree digest: `1f079ec71dcbcf83a51c5ea66da7497d4882103f4226516086fae8ffb5f23c02`.
Code/configuration/fixture digest: `b026d9b694019736a9162857aba2a8e515bce9ce850fdd21c88b712f8af2ab4e`.

| Stage | Result | Passed | Skipped |
|---|---|---:|---:|
| lock-check | PASSED | 0 | 0 |
| fmt-check | PASSED | 0 | 0 |
| lint | PASSED | 0 | 0 |
| docstrings | PASSED | 0 | 0 |
| typecheck | PASSED | 0 | 0 |
| security | PASSED | 0 | 0 |
| doctest | PASSED | 1 | 0 |
| test | PASSED | 805 | 167 |
| flow-test | PASSED | 4 | 0 |
| delivery-foundation-test | PASSED | 16 | 0 |
| delivery-wave-four-test | PASSED | 29 | 0 |
| delivery-transfer-test | PASSED | 6 | 0 |
| delivery-through-020-test | PASSED | 9 | 0 |
| precommit-check | PASSED | 0 | 0 |

All required profiles executed without skips or diagnostics. Default opt-in exclusions
are enumerated by module/reason in the public summary. Native warnings-as-errors remains
active with exactly D07's two accepted SDK filters. The ten approved baseline additions,
original baseline entries and scanner settings were verified; no new exception was added.
Both applied original migrations remain byte-identical. Fresh installation, populated
upgrade, round trip and Alembic drift checks passed at j016_calendar_events. Required
worker tests used actual owned Redis broker/Celery, cache/storage and TLS gateway resources;
runner cleanup succeeded. Graphify AST refresh completed at 15445 nodes/36399 edges.
All tracked and new files passed applicable repository hooks
before the final gate; the final tracked precommit stage also passed. No-suitable-file
hook exclusions are distinct from required pytest scenario skips.

APP-BE-001–020 are complete. The newly closed scopes are 015/016/017/018/020; 019 was
already verified. Unfinished 021–032 dependencies were reviewed: 021/026/027/030 remain
READY, 023 still requires 022, 028 still requires 024/025/026/027, and 029/031 still
require 028. No later task was marked complete. Only completion documentation/evidence
changed after the successful gate; tested production code, tests, fixtures, configuration,
lockfile and security controls retain the recorded digest. No commit or deployment.

Frontend/calendar rendering, peer work, rebuilt/deployed images, production-scale metrics,
live vendors, downstream SMTP, paid AI and full-demo/reset acceptance remain separate.
Analytics query plans are controlled four-row evidence, not production performance.

Completion documentation check: `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pytest -q tests/docs` — 6 passed, no skips. No implementation changed.
