---
tags: [api]
---

# Optional client Date diagnostics

An API client may send a fresh standard HTTP `Date` for each transmission:

```http
POST /api/v1/auth/login HTTP/1.1
Date: Mon, 28 Sep 2026 12:00:00 GMT
User-Agent: MyNativeClient/2.3
Content-Type: application/json
```

Python clients can generate it with `email.utils.format_datetime(datetime.now(UTC),
usegmt=True)`. Regenerate Date on a retry while preserving the command's idempotency key.
Browser JavaScript cannot set Date; the Swagger UI Date input is therefore informative,
and a browser request commonly has no Date. No companion timestamp is required.

The middleware records one UTC server receipt instant and accepts the three RFC 9110
HTTP-date forms (preferred IMF-fixdate plus obsolete RFC 850 and asctime forms). It
ignores a missing value and marks malformed, more than 128 characters, or duplicate
values invalid. Date diagnostics never reject a request. Existing HTTP parser protections
can still reject malformed transport framing before the application receives it.

For responses without a shared-cache policy, the following headers are available and
exposed through configured CORS origins:

| Header | Meaning |
| --- | --- |
| `X-Client-Date-Status` | `available`, `unavailable`, or `invalid` |
| `X-Server-Received-At` | Server receipt UTC in RFC 3339 form |
| `X-Client-Date-Delta-Seconds` | Signed receipt minus client Date; present only when valid |
| `X-Client-Date-Advisory` | `check-device-time` when absolute delta reaches the threshold |

The advisory threshold is `HTTP_CLIENT_DATE_ADVISORY_SECONDS` (default 300; positive
integer seconds). A client can localize “check device time” when the advisory is present.
No advisory is emitted for absent or invalid dates. A delta is an **apparent difference**:
it combines clock offset, transit time and delay between generating Date and sending the
request. It is neither proven clock skew nor one-way network latency. HTTP Date has
second precision; subsecond accuracy is not claimed.

Responses carrying diagnostics gain `Cache-Control: private` so per-request receipt
metadata cannot enter a shared cache. Existing `private`/`no-store` policies remain in
effect, and other directives such as `max-age` remain alongside `private`. Responses
explicitly marked `public` or with `s-maxage` retain their policy and
omit the diagnostic response headers, while ingress logging still records the reading.
The application never reflects the request Date into the response Date. The ASGI server
or reverse proxy may set or replace response Date; duplicate values and intermediary
clock behavior must be checked at deployment. Proxies can also strip or rewrite request
Date, so the observation is of what reached this application, not necessarily what the
device originally sent.

Structured request logs include request ID, server receipt time, parsed client time,
status and signed delta; unchecked raw Date is not logged. Response logs measure server
processing with a monotonic clock from ingress until the final response body chunk is
consumed, including streaming. This duration is separate from the apparent Date delta.
Authentication expiry, audit timestamps, workflow timers and idempotency remain based on
trusted server state and do not use the client Date.

See [RFC 9110 HTTP-date](https://www.rfc-editor.org/rfc/rfc9110.html#name-date-time-formats)
and the [Fetch forbidden request-header rules](https://fetch.spec.whatwg.org/#forbidden-request-header).
