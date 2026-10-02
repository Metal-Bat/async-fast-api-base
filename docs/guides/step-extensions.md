---
tags: [guides]
---

# Trusted step extensions

Place a Python module in `src/apps/step_types/extensions/`. API and Celery worker boot import every module in that package in sorted order and build the same immutable handler registry. Only deploy reviewed code; workflow authors cannot supply Python, SQL, URLs, or import paths. A broken import or duplicate `(handler_key, handler_version)` fails boot.

```python
from typing import override

from apps.step_types.application.invocation import StepInvocationContext, StepResult
from apps.step_types.application.registry import (
    EmptyConfig,
    PortDefinition,
    StepDefinition,
    step_definition,
)
from core.base_dto import BaseDTO


@step_definition
class RequestPriority(StepDefinition):
    code = "REQUEST_PRIORITY"
    name = "Request priority"
    handler_key = "request_priority"
    handler_version = "1"
    category = "DATA"
    execution_mode = "SYNC"
    config_model = EmptyConfig
    ports = (PortDefinition("priority", "OUTPUT", int),)
    name_key = "step.request_priority.name"
    help_key = "step.request_priority.help"
    examples = ({},)

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        return StepResult(outputs={"priority": await context.services.request_priority()})
```

Put translations for `name_key` and `help_key` in the EN/FA message catalogs, then run `mise run i18n-compile`. `config_model` must inherit `BaseDTO`; JSON field names stay `snake_case`. Declare typed input and output ports with `PortDefinition`, and optionally declare `outcomes`, `required_capabilities`, and more `examples`. The registry validates config, inputs, outputs, and declared outcomes. A class must implement `execute`. Supported custom modes are `SYNC` and `BACKGROUND`; custom `HUMAN` and `WAIT` classes are rejected until lifecycle adapters exist.

`StepInvocationContext` is created for one attempt. It contains the actor, process, request, execution and attempt IDs, a per-attempt idempotency key, validated read-only inputs, cancellation probe, and narrow application services. Keep per-attempt state in the context or local variables. Do not store it on the class. The provided services demonstrate a bounded current-request priority read, a current-permission predicate, and an approved connection call. A permission predicate returns a value; it never grants a permission.

## Deployment and publication

1. Deploy the same extension package to API and worker images. `get_registry()` caches one sorted registry per process; its fingerprint identifies the full deployed set. Both processes fail on broken imports.
2. API startup reconciles registered custom definitions into **draft** step-type versions in one transaction guarded by a PostgreSQL advisory transaction lock. Concurrent boots create one version. Reconciliation never changes a published contract.
3. A user with `workflows.manage` can inspect `/api/v1/step-types/search` and `/api/v1/step-types/{ref_id}`, publish a matching draft with `/api/v1/step-types/{ref_id}/publish`, and obtain published executable choices from `/api/v1/step-types/select`.
4. Publish a workflow referring to the exact step-type version. Publication validates its config, ports, and required connection access. Background invocations use the existing outbox and pinned connection. Worker dispatch verifies the handler fingerprint and persisted version before invoking the class; mismatches fail the attempt rather than switching code silently.

To change metadata or port/config schemas, introduce a new `handler_version` and publish the newly reconciled draft. Keep the old implementation installed while old workflows or queued attempts may run. Removing a version leaves its published catalog record inspectable with `is_available=false`, but it cannot be selected for new work or executed. Retire old versions when new authoring should stop. Restore the old code version to resume historical execution. Ordinary implementation changes that do not alter metadata require a coordinated API/worker deployment; registry fingerprints describe contracts, not source-code hashes.

`CONNECTION_STATUS` in `examples.py` shows `BACKGROUND` execution. Its `connection_ref` must point to an active, verified SERVICE connection that the workflow publisher may use. The worker rechecks the pinned connection and actor at delivery. API calls must go through the approved provider and connection service; do not add network clients or arbitrary endpoint fields to a step config.
