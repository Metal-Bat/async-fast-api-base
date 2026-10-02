---
tags: [testing]
---

# Saved purchase-request conformance scenario

The portable vector is [`tests/fixtures/scenarios/purchase-request-v1.json`](../../tests/fixtures/scenarios/purchase-request-v1.json). It contains the exact form documents, actor and client context, English and Persian locales, starting canonical data, user actions, fake host-navigation result, expected resolved views, dependency/rule trace, validation path and canonical submission. The `reuse` section contains one versioned address component and two bindings. The `workflow` and `corrections` sections contain the expected runtime outcomes. The version string `bpms.conformance/1` identifies this fixture format; it does not change any published form or workflow dialect.

Run the backend form replay with:

```sh
uv --cache-dir /tmp/uv-cache run pytest -q tests/apps/forms/test_conformance_scenarios.py
```

The replay calls the actual `compile_instances`, `resolve_form_documents`, `edit_collection`, `evaluate_behavior`, `FormValidator`, `OptionService`, `navigation_plan`, `apply_navigation_result` and manual-override application. It compares the resulting report with `expected`. Dynamic UUIDv7 item keys are translated to stable row labels only for the portable report; identity behavior is still exercised by the backend. The source race uses local custom option rows in the saved definition. A client should discard the older generation or fingerprint after changing the country; backend results expose both fields. Navigation uses a saved fake host response and confirms an old data revision cannot overwrite newer input. No external notification or provider call occurs during this replay.

Run the PostgreSQL runtime checks on a migrated **disposable** database with `RUN_INTEGRATION=1`:

```sh
env LOG_OUTPUTS='["console"]' POSTGRES_HOST=localhost POSTGRES_DB=DISPOSABLE_DB RUN_INTEGRATION=1 uv --cache-dir /tmp/uv-cache run --env-file .envs/.backend pytest -q tests/integration/test_full_workflow.py::test_full_purchase_request_flow_preserves_pins_and_human_approvals tests/integration/test_task_corrections.py::test_repeated_correction_rounds_pin_data_feedback_and_reject_stale_writes
```

The first test creates one request, calls a reusable manager approval child twice, publishes successor parent and child versions while the first call is active, and checks both child executions remain on the pinned version. It checks distinct manager assignments, authorized view projection, duplicate submission and settlement, and the completed timeline. The correction test checks two return/correction rounds, feedback and attachment visibility, stale writes, duplicate return, and reviewer redaction. The two PostgreSQL tests use separate requests; the fixture groups them as related runtime scenarios, not as a single transaction.

The backend replay proves canonical JSON, validation, version pinning and durable runtime behavior. It does not prove Angular or Flutter rendering, accessibility, gestures, browser request timing, local storage, or visual direction. BPMS-017 owns those client implementations and must run these vectors in the clients before claiming web/Flutter parity. Clients must compare canonical keys and values, validation paths, resolved labels, generation/fingerprint behavior and outcome status; they must not substitute localized labels for canonical data. The fixture has no live external option source or notifications. Authorization and redaction are checked through the PostgreSQL work-item service, not inferred from fixture metadata.

The canonical core journey also runs with `mise run flow-test`, which creates and removes a disposable local PostgreSQL database. See the [full workflow regression guide](full-workflow-regression.md) for its coverage and extension rule.
