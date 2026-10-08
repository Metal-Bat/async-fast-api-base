---
tags: [testing, bpms, workflow]
---

# Full workflow regression

[`tests/integration/test_full_workflow.py`](../../tests/integration/test_full_workflow.py) is the canonical end-to-end backend journey for a purchase request. It uses the saved [`purchase-request-v1.json`](../../tests/fixtures/scenarios/purchase-request-v1.json) vector and real application services against a newly migrated PostgreSQL database. Add a stage and observable assertion here whenever a new workflow feature becomes part of this core journey. Keep focused tests for boundary cases and failure modes; the flow test verifies that their pieces still work together.

## Run it

```sh
mise run flow-test
```

This command needs `.envs/.backend` and local PostgreSQL. It first probes an authenticated connection. If the default local port 5432 is unavailable, it runs `docker compose up -d postgres` with a 60-second command timeout, then tries up to 15 readiness probes with two-second connection timeouts and one-second pauses. Configure matching credentials in `.envs/.backend` and `.envs/.postgres`. An already available server needs no Docker access. Set `FLOW_TEST_AUTOSTART=0` to disable automatic startup; custom ports always require manual startup. Authentication errors never trigger Compose startup. Setup failures return a nonzero status and safe configuration guidance.

The runner creates a database named `bpms_flow_<random>`, applies every Alembic migration, runs the service and HTTP journey tests, and attempts to drop that database even when a migration or assertion fails. It refuses non-local PostgreSQL hosts and does not modify the configured application database. Cleanup failure reports the disposable database name and fails the gate without hiding a prior test failure. A service started by the runner remains running. `mise run check` includes this command. The default `uv run pytest` suite skips these integration cases unless `RUN_INTEGRATION=1` is set.

## Journey covered now

1. Replay the saved user form interaction through production form services: localization, collection reorder/removal, behavior calculation, dependent option generations, validation pointers, stale navigation and authorized manual override.
2. Create and publish the purchase form and manager approval form; resolve English and Farsi from the saved published document.
3. Create and publish a child approval workflow with an explicit localized human task contract, typed subprocess interface and per-manager assignment.
4. Create and publish a parent workflow with a typed `TRANSFORM` stage and two pinned child approval calls. Create a request type pointing at the roots.
5. Create a draft, submit it, replay the same submit key, and verify one request, canonical submitted data and exact form/workflow pins.
6. Publish child and parent successor versions while the first child is active. Verify the in-flight process and both calls keep version 1.
7. Reject forged parent/child resumes and wrong-manager claims. Claim each work item as its eligible manager, read its declared approval action and authorized fields, complete it, and settle the child exactly once.
8. Verify completed root/children, the executed graph path and transitions, no active positions, and the safe process timeline.

This single journey covers the integration of forms, graph authoring, typed bindings, requests, idempotency, subprocesses, human approval, authorization, version pinning and timeline projection. Separate integration tests still own corrections, parallel branches, waits, background work, AI tools, service calls, notifications, compensation, private attachments and failure recovery. Add those to this journey as stable deterministic stages when their dependencies and expected outcomes can be expressed through the shared fixture. The [full workflow roadmap](../roadmap/full-workflow.md) tracks the broader frontend target; this test does not claim an AI or external delivery occurred.

## How to extend the flow

1. Extend `tests/fixtures/scenarios/purchase-request-v1.json` with a new input and a literal expected outcome. Keep those values independent of the implementation under test.
2. Add the resource or graph stage to `test_full_purchase_request_flow_preserves_pins_and_human_approvals`. Use the owning application service and the same disposable session; keep one request and process where the feature belongs in that journey.
3. Assert user-observable state through the service response, authorized work-item view, process status or timeline. Query persistence only for invariants the public projection cannot show, such as exact pinned IDs and candidate rows.
4. Run `mise run flow-test` while developing, then `mise run check`. If the feature needs a broker, cache, S3 or external provider, use a deterministic local adapter or a separately isolated service and document the requirement before making it a required stage.

Do not replace the flow with a chain of independent tests: one request should traverse the added stages so version pins, state handoff and authorization remain exercised across boundaries.

## HTTP walkthrough regression

[`test_frontend_journey.py`](../../tests/integration/test_frontend_journey.py) validates the
[frontend walkthrough](../guides/frontend-journey.md) using HTTPX against the real ASGI application,
real PostgreSQL transactions, ordinary accounts and actual bearer-token sessions. Setup alone
uses application services/ORM to provision published definitions and grants; all user actions
use HTTP. No authentication dependency is replaced.

It checks invalid login; missing permission; requester ownership; draft creation and save;
required-field rejection; stale-save conflict; submit replay; reviewer discovery, claim replay,
view projection and approval; changed-payload replay rejection; final request completion;
closed-task actions; refresh rotation, reuse revocation and logout.

The setup explicitly creates `requests.start`, uses `/properties/amount` field-policy scopes,
and sets `inherit_previous: true` so the reviewer receives the submitted amount. These are
configuration requirements, not consequences of merely applying migrations.

## What a passing result means

Expected output from `mise run flow-test`: **2 passed**, followed by removal of the disposable
database. A skip is not a successful runtime check. The default unit/contract suite intentionally
skips infrastructure tests; always run the separate flow command for this evidence.

These tests do not enter application lifespan, execute the TypeScript in a browser, or validate
a deployed network stack. Before accepting a deployment:

1. Start the intended Compose environment using the README, confirm service health, and confirm
   Alembic is at the expected head. Do not reset an existing database to perform this check.
2. Use ordinary requester and reviewer accounts with the explicit prerequisites above; repeat
   the frontend walkthrough against the deployed URL. Check CORS and browser network responses.
3. Confirm saved data survives refresh, validation preserves edits, stale edits prompt reconciliation,
   and completion is visible to the requester. Test an expired session and an unavailable task.
4. Exercise any features that deployment actually uses: upload/download with private S3 access,
   worker and scheduler delivery, and trace/log collection. The synchronous approval test cannot
   certify those dependencies.
5. Record environment/revision, date, tester, results and request IDs without passwords or tokens.
   Have an ordinary user complete the handbook's tasks without developer assistance; record unclear
   steps. Automated API checks cannot certify usability.
