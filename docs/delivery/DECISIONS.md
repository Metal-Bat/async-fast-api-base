# Current delivery decisions

The [approved decision record](approved-decisions.json) is authoritative. Task history
and superseded plans belong in Git; they do not override current implementation.

## Recorded decisions

- **Migration baseline:** DB-002 separates schema and required data. Its two applied baseline files are preserved; the Arabic feature adds `0003_arabic`. No shared reset or blind stamp is authorized. See [migration policy](migration-verification.md).
- **D07:** only the two exact approved Cohere/Google GenAI warning filters apply. Backend results retain `VERIFIED_WITH_EXCEPTION`; new diagnostics are failures.
- **Secret review:** only the [ten reviewed file/type/hash tuples](secret-baseline-review.json) are approved. Scanner rules and unrelated findings remain enforced.
- **D04 / protected effects:** retain publisher-bound authority with a dedicated non-superuser publisher, current grants and pinned connections/secrets. The [protected-effect policy](protected-effect-policy.md) requires committed human approval bound to the exact payload and immutable workflow version.
- **Locale and dates:** English, Persian and Arabic are supported. Backend dates remain canonical Gregorian/UTC; display text, calendars and digits must not alter canonical values.
- **Session boundary:** retain same-origin server-held tokens and empty browser token storage. A multi-replica session design requires separate implementation and verification.

## Remaining acceptance and design decisions

- Named vendor access and an explicitly approved live AI model/data/cost cap are required for live-provider claims. Local HTTPS sandbox and scripted AI checks remain labeled.
- Actual hosted, deployed, device/performance and product-owner acceptance remain separate from local tests. A workflow file or fixture pass is not that evidence.
- Assistant conversation/proposal/scheduling contracts require the policies and schema approach recorded by the eight unfinished tasks in [BACKLOG](../../BACKLOG.md). No generic executor, parallel scheduler or permission system is inferred.
- No tenancy, staffing, compliance, production capacity or RPO/RTO commitments are assumed. Quorum, self-approval restrictions, currencies and holiday policy require domain requirements.
