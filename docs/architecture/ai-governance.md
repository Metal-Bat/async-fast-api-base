---
tags: [architecture]
---

# AI step governance (BPMS-018)

## Runtime boundary

The application pins `pydantic-ai-slim==2.50.0` on Python 3.14.7. Agent versions are authored at `/api/v1/ai-agents`, stored in `AI_AGENT`, and published only after the actor's verified AI connection, configured model, price record, data policy and effective user/admin limits pass validation. Published configuration is immutable in PostgreSQL and carries a checksum. The workflow uses the trusted `AI_DECISION` handler version 1 with an opaque agent version reference, one `data` input object, and typed `choice`, `confidence` and `needs_review` output ports. No workflow JSON imports Python or supplies a network URL.

The background dispatcher snapshots the agent checksum, connection version, decision question/options and schema hash in the existing execution attempt. It creates one `AI_TASK_BUDGET` per logical step execution in the same transaction as the outbox message. The worker rechecks the actor, connection grant, secret version, model allowlist, agent checksum and option snapshot before any model request. Input preparation includes only allowed fields with permitted classifications and applies configured field redaction. The model receives no implicit process context, tools or retrieval access. Generic process events and broker messages contain operational identifiers, never prompt or response content.

Each model call reserves request, token and USD bounds in `AI_RESERVATION` in a committed transaction before network dispatch. The reservation key is the execution attempt ID, with a distinct `:tool` key for an approved resume. A duplicate or concurrent delivery cannot authorize a second call with that key. Each dispatch permits one model request without validation retries. An agent may additionally publish one approval-required read-only tool and reserve a second request on resume. Output token settings and the logical-task elapsed-time deadline apply to both dispatches. Known actual usage settles the reservation and records the response model name; an exception after dispatch holds it as unknown. `GET /api/v1/ai-agents/processes/{process_ref}/executions/{execution_ref}/budget` exposes effective, used, reserved and remaining amounts to an authorized process viewer. Unknown completion is never charged as zero.

The AI step has explicit `next` and `review` outcomes. A low-confidence answer, or an answer from a provider with no trustworthy confidence metadata, takes `review`. Workflow validation requires that transition to lead directly to a `HUMAN_TASK`; the existing human work-item service then creates the review item. The result is revalidated against the pinned Literal schema and choice keys before process progression. The published question and each option description form the same Jev schema used for output validation. English and Farsi labels are for display, never submitted as keys. Input-bound option sets are validated and snapshotted before dispatch, and later edits cause a safe conflict.

## Deployment configuration

`AI_ADMIN_LIMITS` must contain a complete `AITaskLimits` object for publication. `AI_PRICE_CATALOG` maps `provider:model_id` to an `AIPrice` object with `version`, `input_per_million_usd`, `output_per_million_usd` and `fixed_per_request_usd`. Values are operator quotes in USD, not vendor bills; a missing or all-zero price is rejected. User task limits are pinned beneath administrator ceilings. This implementation requires the total-token cap to cover the sum of the input and output caps so one request has a reservable upper bound. All examples below are synthetic:

```json
{
  "AI_ADMIN_LIMITS": {
    "requests": 2,
    "tool_calls": 0,
    "input_tokens": 1000,
    "output_tokens": 500,
    "total_tokens": 1500,
    "elapsed_seconds": 30,
    "spend_usd": "0.50",
    "strict_spend": false
  },
  "AI_PRICE_CATALOG": {
    "typesafe:jev-1.13.0": {
      "version": "operator-example-1",
      "input_per_million_usd": "1",
      "output_per_million_usd": "1",
      "fixed_per_request_usd": "0.01"
    }
  }
}
```

These are environment setting values encoded as JSON, not one combined application setting. Strict spend is rejected for every currently shipped native execution adapter: the pinned SDK cannot give a defensible pre-call billing bound for each one, including Jev. In non-strict mode the service reserves a configured quote and stops later dispatch when limits are consumed, but provider-side billing may exceed a quote before actual usage arrives. Custom trusted adapters may declare strict support only when their own implementation enforces that bound. A provider can report missing usage; the hold then remains for operator reconciliation.

AI connections use `AIConnectionConfig`: a model allowlist, optional region/account, operator-declared provider retention, a secret reference/version, and an `endpoint_key`. `hosted` selects the provider's hosted endpoint. A custom endpoint key must occur in administrator-owned `INTEGRATION_HTTP_ENDPOINTS`, be HTTPS with no embedded credentials/query/fragment, and be supported by the adapter. OpenAI-compatible and Ollama transports support this path. No arbitrary user URL or live model discovery is accepted. `verify` confirms that the secret reference resolves; it does not prove a live provider credential or independently verify the operator's retention declaration. Rotate or revoke the connection to prevent new calls. Retention remains a provider/operator contract outside the application.

## Capability matrix

`known_model_names()` supplies library suggestions. The API keeps those suggestions distinct from authorized connection-scoped configured IDs; library suggestions are not executable. Provider metadata reports import availability, optional SDK failure, custom endpoint capability, governed execution capability and strict-spend support. The `/select` endpoints return bounded `key`/`value` pages or plain item arrays; the metadata and suggestion endpoints provide richer source/capability details without secrets.

| Adapter family | Installed/construction evidence | Governed execution | Endpoint and retry policy |
| --- | --- | --- | --- |
| TypeSafe/Jev | `typesafe` extra; fake-backed typed test and import/construction tests | Yes, with a configured pinned Jev ID | Hosted; TypeSafe SDK retries disabled |
| OpenAI Chat/Responses | `openai` extra; construction tests | Yes | Hosted or allowlisted HTTPS; OpenAI SDK retries disabled |
| Ollama/OpenAI-compatible | `openai` transport; construction tests | Yes | Allowlisted HTTPS only; OpenAI SDK retries disabled |
| Anthropic, Cohere, Groq and Mistral | Native SDK clients with zero retries, fake construction tests | Yes, with configured connections and prices | Hosted; SDK retries disabled |
| Google | SDK HTTP retry attempts set to one, fake construction test | Yes, with configured connection and price | Hosted; one outbound attempt configured |
| Cerebras, Crusoe, OpenRouter, Snowflake and ZAI | Importable, fake-constructed and checked for zero SDK retries | Yes, with configured connections and prices | Hosted fixed HTTPS API origins; OpenAI SDK retries disabled. Snowflake account is restricted to a safe host component |
| AWS Bedrock | Botocore bearer client with one total attempt; fake construction test | Yes, with configured connection, region and price | Hosted AWS region; no implicit SDK retry |
| Bedrock Mantle | OpenAI SDK client with zero retries; fake construction test | Yes, with configured connection, region and price | Fixed region-derived HTTPS origin |
| Hugging Face | HTTPX-backed inference client with one outbound POST in pinned source; fake construction test | Yes, with configured allowlisted endpoint and price | Administrator allowlisted HTTPS inference endpoint only; automatic model/provider discovery disabled |
| GitHub Copilot and OpenAI Codex | Native adapters with injected access-token clients; construction tests | Yes with configured connection secrets | Fixed hosted endpoints; zero SDK retries; Codex requires a safe account ID |
| Trusted custom Model/Provider | Registered in deployed Python with explicit capability flags | Only if registration declares governed execution | Factory receives an approved connection endpoint, never workflow-supplied imports/URLs |

The default profile includes the supported native SDKs, including TypeSafe/Jev. xAI was
removed from this deployment profile because its SDK conflicted with the development dependency
group. It is absent from the provider catalog; configurations referencing `xai` fail closed as an
unavailable adapter. Native construction tests do not establish live credentials, account access,
provider retention or business accuracy.

Copilot and Codex access tokens are resolved from the existing connection secret reference.
Codex also requires `AIConnectionConfig.account` for its account header. These adapters do not
read workstation OAuth files or refresh tokens implicitly. Operators rotate expiring credentials
through the integration connection lifecycle.

## Human approval for important AI-assisted jobs

For the initial supervised pilot, the AI decision prepares a typed recommendation and cannot
complete an important business action by itself. Author the published workflow so both the
normal `next` and low-confidence `review` outcomes reach an assigned `HUMAN_TASK`; only the
human task's approved outcome may continue to the business action. Rejection or return follows
an explicit correction/stop path. The current publication validator enforces a human `review`
route, but does not automatically enforce this stricter normal-path rule. Verify each pilot graph
and execution before use. This approval is separate from the approval below for a read-only AI
tool call. A human-supervised pilot is not a claim that Jev is calibrated for production.

## Durable read-only tool approval

Publication supports one trusted tool with a pinned deployed version, a tool-call limit of one
and at least two model requests. OpenAI Chat and explicitly capable custom adapters support this
profile; other native adapters, including Jev, reject tool-bearing publication. Configure
`INTEGRATION_SECRET_KEYS` before publication so checkpoint encryption is available.

The first model response may request a tool. `AIToolApprovalService` seals the bounded message
history and arguments in `AI_TOOL_APPROVAL`, bound to the attempt and a form-less work item.
The execution principal is its direct candidate and must claim it using the existing cartable
API. Forwarding is rejected. GET and POST
`/api/v1/ai-agents/work-items/{work_item_ref}/tool-approval` require `requests.start` and the
currently eligible claimant. GET returns only tool identity, bounded arguments and lifecycle
metadata with `Cache-Control: no-store`; it never exposes conversation history or ciphertext.
POST accepts `approved` and a bounded `command_key`. Existing form-backed work remains valid;
work-item submission and design fields may be null for an AI approval.

Approval commits a resume outbox message. A new worker session rechecks agent, connection,
principal, tool version, arguments and data policy before consuming the checkpoint. Consumption
clears ciphertext and commits a distinct budget reservation before the lookup/model call.
Concurrent or repeated deliveries observe that durable dispatch fence. Denial, cancellation
and scheduled expiry erase the payload and cannot run the tool. The logical task deadline includes
time spent waiting for approval. Unknown dispatch usage stays reserved; it is never automatically
replayed or counted as free. Budget exhaustion records `ai.budget.exhausted` on the attempt.
Approval commands are idempotent while the attempt is waiting; requests after progression conflict.

`lookup_saved_report` reuses code-owned report definitions and database-saved `REPORT` filters.
`ReportLookupPolicy` explicitly permits a projection, classification, permission and row limit.
The users definition exposes only `username` and `is_active`, at most ten rows, with current
`admin.users.manage`, report ownership and INTERNAL classification required. Field redaction
also applies to lookup results. Changed references/definitions, expired reports and unapproved
sources fail closed. Query arguments cannot contain arbitrary SQL or choose undeclared columns.

## Remaining acceptance evidence

A live Jev evaluation on representative labeled cases remains outstanding. Deterministic tests
prove the application contract and review routing; they do not calibrate business confidence.
The configured development database lacks `AI_AGENT`; disposable migrated databases were used
for integration verification. No live paid call or production-quality result is claimed.
No general prompt/response trace store was added; encrypted pending checkpoints are cleared on
consumption or terminal approval state.

## Jev evaluation injection

The live evaluation CLI uses `--agent-ref` and `--actor-ref` to load the authorized published agent
from the database. Connection settings, model, thresholds, prices and secret references come from
that configuration. Credentials resolve through the existing encrypted integration secret store.
Authorization and connection revocation are rechecked before each case. The cases-only live input
contains labels and a quote cap; it cannot replace the published agent spec. See
[`docs/evaluations/README.md`](../evaluations/README.md) for commands.
