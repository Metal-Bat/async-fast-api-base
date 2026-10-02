---
tags: [api]
---

# User-Agent request metadata

Every versioned application route declares optional `User-Agent` in generated OpenAPI.
It identifies caller software for request logs, authentication sessions/audit and entity
history. It is caller-controlled text and is never used for authorization or trusted
client identity. The same value is captured at ingress for those uses: absence or an
empty value becomes `null`, and values longer than 1024 characters are truncated to
the first 1024 characters so they fit existing storage. Header names are case-insensitive.
No new validation error or database column is introduced.

Native/API clients can set a value, for example `User-Agent: MyNativeClient/2.3` or
`User-Agent: python-httpx/0.28.1`. Browsers generate their own User-Agent, often with
privacy reduction. Swagger UI runs in a browser, so editing its displayed header input
does not guarantee a manual override is transmitted; check the browser network request
when testing. This header is optional even when a client library supplies a default.

The global API dependency exposes the optional input in OpenAPI and copies its bounded
value to request state. Middleware captures it before route execution, including for
unauthorized requests. Standalone routes that omit the middleware still get the same
normalization when they attach the dependency. Existing CORS origin and authentication
rules are unchanged.
