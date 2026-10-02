---
tags: [architecture]
---

# Client identity and release targeting

BPMS-022 uses a registered application/channel identity rather than a user agent or physical device. A client has a stable key, kind (`ANDROID`, `IOS`, `DESKTOP`, `WEB`, `B2B`, `SDK`), platform and authentication mode. A release belongs to one client and declares an application version, API contract version and renderer capability set. User identity and workflow grants remain separate checks.

## Trust and session binding

A confidential client presents its registered key and secret when the user session is created. The server stores only a secret hash and binds the resolved client and exact release IDs to `AUTH_SESSION`; access tokens carry the session ID, not caller-supplied client claims. Requests resolve context through that session on every protected action. HTTP `User-Agent`, device labels and optional platform/version headers are presentation hints only and cannot satisfy a restricted workflow policy. Changing headers after login cannot change session identity. Revoking the session or client denies subsequent protected actions.

A public desktop/mobile/web app cannot keep an embedded secret private, and this contract does not claim device attestation. Public registrations may select a presentation view, but `trusted=false` means they cannot satisfy a client-restricted start or action. Confidential desktop deployments, B2B integrations and server-side SDK callers can use server-provisioned credentials. Missing client fields produce `legacy` context and preserve unrestricted historical behavior. Unknown client or release assertions fail login; they never silently fall back to legacy. A verified user session does not by itself verify a public app's claimed platform or version.

## Version and range semantics

Versions have `major.minor[.patch][-prerelease][+build]` form. Major, minor and patch are numeric, so `2.9 < 2.10`; omitted patch is zero. Prereleases sort before the corresponding release; numeric prerelease identifiers compare numerically and before text identifiers. Build metadata does not affect ordering. Lower range bounds are inclusive and upper bounds exclusive. Missing/unknown versions match only an unbounded target. Invalid versions fail before persistence. No lexical string comparison or “latest” alias is used. B2B/SDK callers can have a release without a renderer; data-only submission does not require view support.

## Origin and interaction

The request snapshots the credential-free client context that started it. Workflow decisions consume that origin snapshot across workers/retries. A form interaction pins a form version plus the selected render variant/page revision and the current client context. A later device cannot silently replace a pinned interaction. A compatible client may explicitly open a new presentation interaction and receive a newly selected view while the canonical data schema, form version, request origin and completed workflow decisions stay fixed. Saved submissions retain the variant reference used to collect their data. Background workers use stored origin/attempt snapshots, never request headers.

Client variants select presentation only. They do not alter user/group access, required server validation, action permissions or business control flow. Variant targeting chooses the most specific eligible registered client and release range; equal-priority overlapping targets are invalid at publication. If no target matches, the default view applies if capability requirements are met. Unsupported capabilities produce an explicit unsupported-client result. Shared page settings merge recursively with a targeted override: maps merge by key, arrays replace, and `null` replaces the inherited value. The merged envelope is validated and byte/depth bounded before it is returned. Client options are inert JSON and cannot authorize actions, execute scripts or carry secrets.

The existing `bpms.render/1` records and checksums remain as issued. BPMS-022 adds an immutable variant snapshot to new form versions without rewriting old published documents. The future `bpms.form/2` package contract in `form-package-v2.md` keeps one canonical data schema across named views; BPMS-027/024 own later locale and field expansion.
