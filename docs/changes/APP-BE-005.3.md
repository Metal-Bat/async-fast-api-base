# APP-BE-005.3 — Executable business seed profile

Backlog: APP-BE-005.3
Date: 2026-10-27
Area: scripts/demo, requests/processes/work_items

## Summary

The thirteen legacy catalog templates are useful lifecycle/load fixtures, not thirteen
absent implementations. Their forms already contain domain fields and en/fa/ar
catalogs. The primitive library already publishes and executes ordinary workflows.
Neither is replaced. Disabled AI/integration configurations remain configuration
examples; they are not evidence of provider execution.

## Why

The audit found irrelevant required budgets in seven nonfinancial templates,
repeated same-person approvals, priority-based financial branching, a no-op legal
child, a discarded incident transform, a fixed equipment timer unrelated to the
requested reservation, invoice correlation by title, and readonly inspection data.
There is no defensible single percentage of “wrong seeds”: technical execution and
business meaning are different acceptance criteria.

## What Changed

| Process | v3 business behavior |
| --- | --- |
| Procurement | Finance budget review, then operations fulfillment review. |
| Leave | Operations manager, then People review; no mandatory money fields. |
| Expenses | Operations authorization, then Finance receipt review; sample claims zero receipts. |
| Service | Technology triage, then Support resolution review. |
| Onboarding | People, Technology account setup confirmation, Operations workspace confirmation. |
| Access | Business owner, Technology security and Legal compliance reviews. |
| Travel | Manager and Finance funding review; no priority-as-budget rule. |
| Contract | Actual Legal human child and explicit approved/rejected outcomes, then owner review. |
| Incident | Support triage, then Technology records required workaround. |
| Equipment | Operations reviews reservation request; no claim of automatic booking/capacity control. |
| Invoice | Actual EVENT_WAIT by invoice number, then Finance verification. |
| Quality | Quality records sample count and inspection note, then Operations accepts. |
| Showcase | Finance funding and Operations rollout readiness reviews. |

`scripts/demo/real_processes.py` installs the additive installation-owned
`real.<installation>.v3.` profile through existing form/workflow/request owners.
Financial declarations use decimal strings with existing canonical formatting and
explicit currency; this is review data, not a payment/accounting engine. Required
domain inputs are retained. Inspection/resolution evidence is absent until entered
by its responsible actor. All reviewer dispositions require comments.

## Compatibility

Contract subprocess lifecycle options are intentionally limited by the existing
backend. After legal disposition, owner review allows approval/rejection; amendment
requires a new request rather than pretending the child can be reset/replayed.
Other profiles retain ordinary requester correction and rereview paths. Provider
calls, payments, inventory booking and account provisioning are not fabricated.

The installer creates one draft and one genuinely submitted waiting request per
process by default. It performs zero human approvals. Versions/pins and legacy v2
cases remain intact. Reinstallation preserves cases and operator edits, checks
source provenance and refuses conflicting immutable definitions. The recipe digest
covers module bytes, the shared graph helper, form and stage data. Credentials stay
in the existing private installation export and are never printed.

Commands: `mise run real-process-seed`; inspect using
`mise run demo-seed -- --inspect --with-real-processes`. Existing local services and
current migrations are prerequisites; this command never migrates/resets a database.
`mise run real-process-test` owns disposable database, broker and worker resources.
The scenario is also required by the full delivery-transfer gate.

## Architecture

No architecture change. Existing service-owned publication, request submission, work-item
commands, transactional outbox and Celery subprocess settlement remain the owners.
No new engine, queue, schema, applied migration, dependency or permission is added.

## Validation

Initial attempts: actual form validator and sample schema checks pass for all 13;
routing assertions pass. Initial database acceptance caught an unsupported schema
keyword, duplicate currency requirements and unsupported subprocess lifecycle options;
all were repaired using supported contracts. A repeat-export test incorrectly assumed
credentials were omitted on rerun; the assertion was corrected without changing the
existing private export behavior. Final execution, preservation, full gates and source
identity receipts remain required; no integrated/demo readiness is claimed here.

Actual acceptance continuation: the owned PostgreSQL/broker/worker scenario passes
all thirteen approval paths, both actual Legal child outcomes, exact invoice matching
and unrelated-event denial, requester correction followed by rejection, unauthorized
claim privacy, repeated installation and preservation of an ordinarily edited draft.
The isolated final branch run passed in 65.11 seconds and removed its owned database.

The local development CLI was then run twice successfully. Inspection proves the
same 26 current references/statuses: 13 DRAFT and 13 RUNNING requests waiting on
actual work/events. No request was auto-approved. The existing frontend boundary
was restarted with the profile's public registered client release; weakening the
request's pinned-client checks was unnecessary. An actual seeded requester opens
and edits the leave form, sees no irrelevant budget, and reloads the unchanged saved
data without submitting/saving/approving any request. Safe receipts and full logs are
under the frontend `artifacts/seed-processes-2026-10-27/`; credentials remain private
at `.demo-seed/fd8798e8b92b1482/credentials.json` in the backend checkout.


Commands executed:

- `rtk proxy env FLOW_TEST_PROFILE=real-processes UV_CACHE_DIR=/tmp/uv-cache uv run --env-file .envs/.backend python scripts/run_flow_test.py` — final focused branch scenario passed.
- `rtk proxy env PYTHONPATH=src:. .venv/bin/python -m scripts.demo_seed --with-real-processes` — actual local installation and repeated installation passed.
- `rtk proxy env PYTHONPATH=src:. .venv/bin/python -m scripts.demo_seed --inspect --with-real-processes` — same 26 current refs/statuses after repeat.
- Full `mise run check`, explicit hooks on new files and AST graph refresh have separate native logs and final source comparisons in the completion receipt.

Result: focused and local-service acceptance PASS. Full documentation-qualified
completion remains conditional on the final receipt; no strict/demo readiness is
implied by D07's exact accepted SDK exceptions.

## Backlog Impact

Enabled: APP-BE-005 ordinary business examples; APP-BE-038 bounded showcase preparation.

Blocked: Live provider configuration, paid execution, deployment and actual human acceptance
retain their original owners. Frontend Agent authoring consumers remain APP-FE-025/030.

Superseded: None. Legacy v2 lifecycle/load fixtures and primitive-library history remain.

Conflicts: None. All unfinished backlog owners were reviewed; no parent is closed.

## References

Commit: None.

Pull Request: None.

Additional notes: `docs/guides/demo-seed.md`, `docs/changes/APP-BE-005.2.md`.


## Full-gate completion candidate — 2026-10-27

The preliminary sixteen-stage `mise run check` completed with native exit 0 and
VERIFIED_WITH_EXCEPTION: 1,039 default tests plus 234 documented opt-in exclusions,
one doctest and 146 mandatory service scenarios, zero required skips and zero emitted
diagnostics. Only documentation changed during that run. The final documentation-qualified
full run and exact source comparison are recorded separately in the frontend checkout's
`artifacts/seed-processes-2026-10-27/completion.json`; missing/failed evidence keeps the
candidate incomplete. D07's two exact accepted SDK exceptions remain unchanged and do
not establish strict/demo readiness. All failed/partial attempts are retained separately.
