---
tags: [architecture]
---

# Integration connections and secret boundary

## Decision and threat model

Connection metadata and normalized user/group grants live in PostgreSQL. Credentials live in
operator-provisioned authenticated encrypted files, behind the `SecretStore` interface. Dedicated
Fernet keys are supplied separately from the database, ciphertext backup, and application
SECRET_KEY. The process mounts the credential directory read-only. This uses the existing
cryptography dependency and leaves a replacement seam for an external secrets manager.

This protects against a database-only disclosure, accidental credential inclusion in workflow
JSON/history/broker payloads, path traversal, symlink files, malformed ciphertext, and substitution
between secret versions. It does not protect against an operator or compromised application
process with access to both keys and files. Operators may provision credentials; workflow
designers cannot upload plaintext secrets or choose arbitrary network destinations.

`EncryptedFileSecrets` reads only bounded regular files, rejects symlinks, verifies Fernet
authentication, checks the encrypted reference/version binding, and returns `SecretStr` only
inside the provider adapter. Credentials are never returned by connection DTOs. History redacts
secret reference/version fields and configuration; audit events record operation metadata.
Provider exceptions become generic failures without their text. Do not enable HTTP header
capture/debug instrumentation for Authorization or dump process environments, locals, or vault
contents. Host-level access and diagnostics remain an operator trust boundary.

## Configuration and provisioning

- `INTEGRATION_SECRETS_DIR`: defaults to `/run/secrets/integrations`.
- `INTEGRATION_SECRET_KEYS`: JSON array of dedicated Fernet keys; empty by default.
- `INTEGRATION_HTTP_ENDPOINTS`: JSON object mapping symbolic endpoint keys to approved HTTPS URLs;
  empty by default. URLs cannot include credentials, query strings, or fragments.

Empty defaults leave provider use unavailable until provisioned. For local development set the
directory to a private local directory and use disposable credentials. Never commit keys, token
files, or environment values. Deployment operators inject keys through their protected runtime
configuration and mount a directory readable only by the service UID, for example a Compose
override with `./private/integrations:/run/secrets/integrations:ro`. Keep the source outside version
control. Endpoint allowlists and their DNS/network routes are operator-controlled; enforce egress
policy at deployment where required.

Provision an immutable file named `<reference>.<version>.enc`, using 1–64 letters/digits/underscore/
hyphen for both identifiers. Encrypt UTF-8 JSON of this shape with a dedicated Fernet key:

```json
{"connection": "status_service", "version": "v1", "token": "provider-token"}
```

Use an operator-only script with `Fernet.generate_key()` for initial key creation, `getpass()` for
credential entry, and `Fernet(key).encrypt(json.dumps(payload).encode())`. Write with exclusive
creation (`os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)`), never print the payload or
key, and arrange service UID read access. Tokens are 1–4096 characters with no CR/LF; ciphertext
files must be at most 16,384 bytes. Provision before setting the corresponding API secret reference
and version. The application deliberately has no secret-writing API.

## Rotation, revocation, and recovery

Credential rotation provisions a new immutable version file and updates the connection reference
through `/rotate`. Verification becomes UNVERIFIED. Reverify before new workflow pins are allowed.
Existing trusted pins keep the old version until completion, so retain old files while referenced.
Never overwrite a version in place. Revocation is terminal and prevents subsequent dispatch;
an already dispatched external request cannot be recalled. Group membership and grants are
rechecked at dispatch, not cached in the pin.

Encryption-key rotation adds a new key first in the keyring, retains old keys for decryption,
and reencrypts existing files with `MultiFernet.rotate` using atomic file replacement. Verify all
versions before removing old keys. Coordinate replacements with the operator-owned read-only
runtime mount. Credential-version rotation and encryption-key rotation are separate operations.

Back up PostgreSQL metadata and every retained ciphertext version consistently. Back up encryption
keys separately under restricted access, including keys needed for retained backups. Restore the
database, corresponding ciphertext files, permissions, endpoint map, and keyring; verify a test
connection before resuming workers. A database restore alone cannot restore provider access.
Loss of required keys is unrecoverable; obtain replacement credentials from the provider. Missing
files, wrong keys, and invalid envelopes fail closed with a generic unavailable result.

## Application contract

Routes require `integrations.manage`; per-connection ownership, superuser status, or direct/active
group grants further govern access. Manage implies use. Each grant targets exactly one user or
group. CRUD, search, history, report, rotate, verify, revoke, and grant operations follow the
existing snake_case/envelope/opaque-reference contracts. Public projections omit secret references
and versions as well as plaintext. Mutations use optimistic versions and root row locks.

The trusted application `pin` interface verifies provider, active lifecycle, successful
verification, caller access, and registered handler compatibility without resolving a credential.
ConnectionPin is internal metadata, not an HTTP execution request; future workflow publication
stores it after its own workflow access checks. Runtime `execute` rechecks access, revocation,
and provider/configuration identity before invoking the adapter with the pinned secret version.
It must never accept an untrusted caller-constructed pin.

The installed `https_status` SERVICE provider supports the registered service_task handler. It
performs a TLS-verified HEAD request to an operator-configured endpoint with a Bearer credential,
10-second timeout, no redirects, and no environment proxy inheritance. It returns only the HTTP
status code and discards response bodies/headers. Verification accepts 2xx; exceptions produce
FAILED verification or public service-unavailable code 1098 at execution. Notifications and AI
require future trusted adapters; arbitrary provider keys cannot be published.

Migration `41b114f1c753`, after `be9a70072a3d`, adds connection, grant, and connection-history
tables, constraints, and indexes. No credential material is seeded or migrated. BPMS-007/BPMS-012
will connect the publication/runtime interfaces to durable workflows; no background dispatch is
introduced here.
