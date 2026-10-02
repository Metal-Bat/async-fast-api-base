---
tags: [architecture]
---

# Media security boundary

File and image objects are private. Download routes require authentication and
the default access policy permits only the user who created the upload. An
opaque `ref_id` identifies a row; possession of it never grants access. Product
code may supply an `UploadAccessPolicy` implementation when a BPMS feature has
an explicit, tested relationship rule. Public links are not supported.

Generic files use an allowlist of passive formats: signature-checked PDF and
valid UTF-8 text, CSV, or JSON. Images are decoded with Pillow, constrained by
byte and pixel limits, and re-encoded as WebP without source metadata. Stored
objects remain private and carry their SHA-256 digest as object metadata.
Downloads compare the database size, content type, and digest with trusted S3
metadata before opening a bounded-memory stream.

The private user-media download routes accept one optional request Content-Disposition mode.
Generic files permit `attachment` only; normalized WebP images permit `inline` or `attachment`.
The server derives and encodes filenames, rejects duplicate or parameterized preferences, and
always emits `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.
Request Cache-Control never changes the response policy. See the
[private media download contract](../api/private-media-downloads.md).

Content validation is not malware detection. A malware scanner belongs between
format validation and `UserUploadService._store`; it must reject or quarantine
content before S3 persistence and database commit. Until a scanner is connected,
deployments must keep the passive-format allowlist, serve generic files as
attachments with `nosniff`, and must not describe uploads as malware-free.

Rate limits are per authenticated user. If database persistence fails after an
object upload, the service rolls back and deletes the orphaned object. Operators
should alert on `upload.orphan_cleanup_failed` because that event requires an
object-store reconciliation pass.
