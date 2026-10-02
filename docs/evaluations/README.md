---
tags: [evaluations]
---

# BPMS-018 Jev evaluation

`jev-triage-sample.json` contains synthetic English tickets and provisional labels. It is a
reproducible smoke benchmark for the pinned `jev-1.13.0` decision schema, not evidence of
production quality. Replace or supplement it with representative, human-adjudicated cases before
calibrating the review threshold. Keep case files in access-controlled storage when they contain
real user data; do not commit those files or a credential.

Preflight the case count, pinned versions and quote without calling a provider:

```sh
PYTHONPATH=src uv run --env-file .envs/.backend python -m apps.ai.application.jev_evaluation docs/evaluations/jev-triage-sample.json
```

The sample has 12 cases and a $0.20 configured quote cap. Its current calculated quote is $0.1332.
The quote is based on the configured token prices and limits; it cannot guarantee an exact
provider bill. The CLI stops before another call when reported usage leaves too little quote and
stops after reported usage exceeds the cap, but an individual provider call may exceed its quote.

Live evaluation uses the published agent and approved connection stored in the database. The
connection's secret reference is resolved through the existing integration secret store; no
separate `TYPESAFE_API_KEY` is needed. Prepare a cases-only JSON file containing `cases` and
`max_quote_usd` (the same fields as the sample, without `spec`). Configuration, prices, thresholds,
and model version are injected from the published database agent:

```sh
PYTHONPATH=src uv run --env-file .envs/.backend python -m apps.ai.application.jev_evaluation cases.json --live --agent-ref "$AGENT_REF" --actor-ref "$ACTOR_REF"
```

The actor must be authorized for both the agent and its verified connection. Authorization,
agent integrity, model allowlisting and credential version are rechecked before each request.
Revocation stops subsequent calls. The live run makes paid calls sequentially. It emits aggregate accuracy,
automatic and review counts, unsafe automatic decisions on labeled ambiguous cases, a Brier score
for the reported confidence, and reported usage. It does not emit case text, individual
predictions, response bodies or the credential. A provider or schema error ends the run with a
redacted failure type. The operator should record the model version, prompt version, schema hash,
threshold, case provenance and aggregate results in this directory before BPMS-018 is accepted.

No live Jev evaluation result has been recorded yet.
