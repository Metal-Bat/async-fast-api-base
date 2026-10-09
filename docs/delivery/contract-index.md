# Backend contract index

Producer: APP-BE-001. Consumer: APP-FE-001 and owning feature tasks.
This is a repository-local handoff, not evidence that the peer has consumed it.

- [Manifest](contract-manifest.json): exact commits, versions, hashes, permissions and head.
- [English OpenAPI](openapi-en.json) and [Farsi OpenAPI](openapi-fa.json): generated with
  `utils.localized_docs.localized_openapi`, preserving operation IDs and wire field names.
- [API inventory](api-inventory.json): all 314 operations, source functions, security,
  input media, status codes and 425 reachable schemas/2,219 fields.
- [Shared contracts C01–C14](CONTRACTS-AND-ACCEPTANCE.md): proposed deltas, not invented APIs.
- [Existing frontend contracts](../guides/frontend-contract.md) and
  [response schemas](../reference/responses/index.md): current envelopes and wire examples.

Actual success envelopes are `SuccessResponse` with `data` and `PageResponse` with `result`;
selectors support bounded `page|items` where documented. Downloads and streaming operations
are identified by media in OpenAPI and must not be decoded as JSON envelopes. Current opaque
refs must be replaced from mutation responses. Existing operation-specific command keys,
published checksums and process pins are retained.

Permission definitions are only one authorization layer: notifications/media/report ownership,
workflow/library grants, current eligibility and superuser-only recovery checks remain in the
owning service. Appearance in a selector does not confer mutation/dispatch authority.

Peer comparison: the current platform snapshot has identical shared schemas and paths,
while its manifest still describes an uncommitted patch. The base snapshot is older and
lacks 12 operations. Full API equality, translations and generated-source hashes must be
rechecked when implementation changes; APP-BE-031 owns live pairing and deployment evidence.

No new public API is frozen by this intake. C01–C14 producer tasks freeze their deltas
against these existing paths, envelopes, permission checks and examples before peer changes.
