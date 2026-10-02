---
tags: [api]
---

# Private user file and image downloads

The existing `/api/v1/media/files/{ref_id}` and `/api/v1/media/images/{ref_id}` endpoints
stream uploads for an authenticated user. By default, the upload owner may read the object;
trusted product code can add a tested relationship policy. A reference alone never grants
access. The server checks the reference, kind, revision and authorization before accessing
object storage, then verifies stored object size, content type and digest metadata before
streaming. A missing or unauthorized upload returns the same 404 response. See the
[media security boundary](../architecture/media-security.md).

## Disposition preference

Send at most one `Content-Disposition` **request** header. It may contain only a mode, without
`filename`, other parameters or a comma-separated list. Modes are case-insensitive and optional
surrounding HTTP whitespace is ignored.

| Route | Omitted header | Accepted header values | Response filename |
| --- | --- | --- | --- |
| `GET /api/v1/media/files/{ref_id}` | `attachment` | `attachment` | Sanitized original filename |
| `GET /api/v1/media/images/{ref_id}` | No disposition header; browser may display inline | `inline`, `attachment` | Sanitized original stem with `.webp` |

Generic files remain attachment-only under the current passive-file policy. Unsupported modes,
duplicate headers, filenames and parameterized values return 422 with public code `1002` and
an issue at `/headers/content-disposition`. The issue code is `media.disposition.invalid` or
`media.disposition.duplicate`. The server never reflects a caller-supplied filename. On a valid
request it emits an encoded `filename*=UTF-8''...` when a disposition header is present.

`Cache-Control` is **not** a preference input. Both download routes always return
`Cache-Control: private, no-store`, even if a client sends a different request Cache-Control.
They also return `X-Content-Type-Options: nosniff`. Files retain their validated stored MIME
type; normalized images return `image/webp`. Other private attachment and report routes are
outside this preference contract.

## Examples

Download a private file to disk:

```sh
curl -f -H 'Authorization: Bearer <access-token>' \
  -H 'Content-Disposition: attachment' \
  -o purchase-report.pdf \
  'http://localhost:8000/api/v1/media/files/<opaque-ref-id>'
```

The successful response streams binary content, for example:

```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename*=UTF-8''purchase-report.pdf
Cache-Control: private, no-store
X-Content-Type-Options: nosniff
```

Request an inline normalized image:

```sh
curl -f -H 'Authorization: Bearer <access-token>' \
  -H 'Content-Disposition: inline' \
  -o portrait.webp \
  'http://localhost:8000/api/v1/media/images/<opaque-ref-id>'
```

This returns `Content-Type: image/webp` and a response header such as
`Content-Disposition: inline; filename*=UTF-8''portrait.webp`. Omitting the request preference
keeps the existing image response without Content-Disposition.

For a browser on an allowed CORS origin, use `fetch()` with the bearer token and optional
Content-Disposition mode, read the response as a `Blob`, and create an object URL for display or
download. The server permits the request header and exposes response Content-Disposition and
Cache-Control through CORS. A plain `<img>` or `<iframe>` navigation cannot attach this bearer
token or the custom preference header; use an authorized fetch/blob flow. An object URL should be
revoked when the view is finished. CORS grants browser access to an allowed origin; it does not
replace server authentication or upload authorization.

## Failures and limits

| HTTP | Public code | Meaning |
| --- | ---: | --- |
| 401 | `2001` | Missing or invalid access token. |
| 404 | `1003` | Missing, stale-revision, wrong-kind or unauthorized upload. |
| 422 | `1002` | Invalid or duplicate Content-Disposition preference. |
| 503 | `4004` | Object storage is unavailable. |

Downloads are streamed after object metadata preflight. An object that fails size, content-type
or digest-metadata verification returns 404 before streaming. These checks do not make the
content malware-free. Generic files are still forced to attachment until the malware-scanning
policy changes.
