# Private transfer follow-up — APP-BE-027

Date: 2026-10-09. Status: PARTIAL; actual paired streaming rejection remains open.
Historical scope/evidence: [change record](../changes/APP-BE-027.md).

## Backend behavior

Existing authenticated media file/image and owned report download routes are reused.
No second storage owner, direct private URL, JSON success envelope or browser token store
is added. Current references and authorization precede metadata preflight. Missing and
unauthorized objects retain the same 404 behavior. Private/no-store/nosniff and existing
server-selected disposition/filename contracts remain.

Media authorization reads and report access accounting release their database session
before streaming. Reports commit an authorized start before closing; download_count is
not proof of completed delivery. Generation READY and persisted report notifications do
not depend on a browser completing a download.

Storage chunks are 1–65,536 bytes (default 65,536); invalid chunk sizes fail before storage
access. These media/report callers supply the expected metadata size. Excess data is
rejected before its chunk is forwarded; truncation fails at EOF. A late failure closes
the binary response after headers and cannot substitute a JSON success response. Client
code must discard partial files. Explicit disconnect/closure releases the storage body
and client. Metadata digest checks remain metadata checks, not a fresh streamed SHA256
computation or malware guarantee.

The [media guide](../api/private-media-downloads.md), actual localized OpenAPI and the
single [producer manifest](wave-four/manifest.json) describe these contracts. Routes,
DTO wire names, stable errors and configuration limits are preserved. No migration,
dependency, environment or shared data was changed.

## Actual Node gap and concrete repair

The actual peer rejects declared oversized inputs before forwarding. For an unknown-size
multipart body that exceeds its 11 MiB cap while still arriving, cancellation can destroy
the IncomingMessage socket. A real paired probe received 413 followed by ReadError on
session/status; this is failed recovery evidence, not successful browser acceptance.

The two-file proposed patch changes only Node transport:

- Drain excess chunked bytes without retaining them, bounded by the existing transfer
  deadline/abort signal, before returning 413. No rejected body reaches the backend.
- Advertise Connection: close when an error is emitted with unread request bytes, so
  early declared-size rejection cannot reuse a partially consumed request connection.

The patch was applied only to a temporary copy. With the actual pinned Node runtime and
owned real backend/services, a valid unknown-size multipart upload of 100 × 128 KiB chunks
was rejected with 413/uncertain=false, followed by an authenticated session/status request
using the same client. Result: 1 passed, zero warnings/skips. A header-only repair candidate
failed first and is retained as failure evidence. An initial probe invocation omitted the
project pytest config and emitted three unknown-marker warnings; it was corrected by
using the existing config, without adding filters or suppressions. A first candidate used
the wrong Node runtime and failed; the successful run uses the peer's pinned runtime.

The actual frontend checkout is unchanged. Specific permission for the cross-repository
patch is pending. Applying it requires peer regression tests, a complete frontend gate,
actual paired acceptance and appropriate peer ownership; this backend preparation does
not complete APP-FE-036 or browser/device/accessibility/performance acceptance. Draining
bounds retained memory and duration, not total inbound network traffic before deadline.

## Verification

- Focused storage/media/report/transfer tests: 44 passed before the additional report
  session-release regression and updated Swagger descriptions.
- Mandatory owned delivery-transfers profile: 14 passed, zero skips, with actual
  PostgreSQL/S3/worker/Node boundary. Disposable resources were removed by the runner.
- Extra actual-peer oversized-upload probe: FAILED; actual peer recovery remains open.
- Extra temporary-patch paired probe: 1 passed; provisional repair evidence only.
- Complete final backend gate (closure 2026-10-10): all 15 stages passed, 879 default
  tests, one doctest and 86 mandatory service tests with zero required skips. The default
  suite separately excludes 183 opt-in integration cases. The exact start/end source hash
  matches. Result: VERIFIED_WITH_EXCEPTION under the two existing D07 SDK exceptions.
  No new suppression or mandatory skip was added. See [verification](private-transfer-verification.json).

Private logs/probe evidence remain outside the repository; no credentials, bearer tokens,
private URLs or uploaded business data are copied into this handoff. Full final source
identity and gate results are recorded in the linked verification. The task remains
BLOCKED/IMPLEMENTED until actual peer acceptance; the reviewed peer files are unchanged.
