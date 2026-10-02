# Keeping documentation useful

Audience: maintainers and reviewers. Status: documentation workflow. Reviewed: 2026-10-02.

[Documentation home](../Home.md) · [Frontend walkthrough](frontend-journey.md)

## Ownership and source of truth

The person changing a feature updates its guide and examples in the same change. A reviewer checks
business meaning, not just spelling. The owning application's routes, DTOs, service and tests are
the authority; generated OpenAPI describes its wire shape. Never add a second handwritten OpenAPI
spec or silently change runtime behavior to make prose accurate.

| Artifact | Maintain by |
| --- | --- |
| User handbook | Explain affected tasks in ordinary words; link technical details elsewhere. |
| Frontend journey | Update call order, prerequisites, refs, permissions, side effects, failures and UI states. |
| `examples/frontend-journey.json` | Add realistic synthetic request/response pairs with actual method/path/status; test them. |
| Response references | Regenerate with the existing generator; do not edit its output by hand. |
| Design/roadmap notes | Label proposed versus historical versus implemented; link the current contract. |
| Operational docs | Check commands against current configuration and migration lineage. |

Each hand-authored guide should declare audience, status and review date. Record proof separately:
schema validation, service integration, HTTP integration, and browser verification are different.
Do not label a proposed UI as shipped. Screenshots should be added when an actual UI exists.

## Checks

From the repository root, using the project's development environment:

```bash
PYTHONPATH=src:. uv run python docs/tools/generate_response_dtos.py
uv run pytest -q tests/docs
tsc --strict --noEmit --target ES2022 --module ES2022 --lib ES2022,DOM docs/examples/frontend-client.ts
```

The TypeScript check requires `tsc` on PATH. The project does not add a frontend package manager or
install compiler dependencies automatically. The Python documentation checks are part of the
default pytest suite and require no database. They validate curated payloads against generated
OpenAPI, selected DTO/business contracts, reference regeneration, and local Markdown links.

Run the current full project gate from the README when changing code. Run `mise run flow-test`
against its disposable database for changes to the purchase journey or the documented HTTP steps.
It must report two passing journeys; see the [validation scope and deployment checklist](../testing/full-workflow-regression.md).
Regenerate the [coverage inventory](../api/openapi-coverage.md) when API surface changes. Its
description counts measure presence, not explanatory quality or complete frontend readiness.

## Example policy

Use synthetic, non-secret data and meaningful lifecycle values. Never invent statuses by using a
generic string generator. The reference generator includes curated business examples only where
available and explicitly states when a schema has none. Tokens and opaque references in examples
are not executable credentials; real references must come from authorized API calls.

Schema validation cannot prove a form is published, a user is eligible, a transition exists, or an
outcome is allowed. Verify those with service/integration tests and explain setup requirements.
Keep a realistic request paired with its response and include failure cases. The small amount
example is distinct from the richer saved purchase conformance fixture.

## Reader acceptance

Before calling a frontend handoff complete, ask a developer to follow the walkthrough with two
ordinary accounts without reading backend internals. Have them exercise empty work, a competing
claim, stale save, invalid submit and an expired session. Check field errors, confirmation prompts,
unsaved edits and network-failure reconciliation in the real UI.

Ask a nontechnical reader to explain how to submit, review and correct a request using only the
handbook. Record confusion as a documentation issue. Those reader/browser checks are not automated
by the current repository and must not be claimed solely from passing schema tests.
