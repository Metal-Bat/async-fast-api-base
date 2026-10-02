---
tags: [api]
---

# Dynamic fields and option sources

BPMS-024 adds backend metadata, preview and submission checks to `bpms.render/1`.
Angular rendering remains BPMS-017. The executable shared fixture is
[`field-sources-v1.json`](../../tests/fixtures/forms/field-sources-v1.json).
Read this with [localization](form-localization.md), [client designs](client-designs.md)
and [form architecture](../architecture/forms.md).

## Discovery and HTTP boundaries

All paths below start with `/api/v1`. Authentication uses the existing bearer/session and
registered client context. Reported device headers never select an authorized client.
JSON fields are snake_case; common headers include `Accept-Language` and `X-Request-ID`.

| Method/path | Permission and behavior | Success payload |
| --- | --- | --- |
| POST `/forms/field-catalog` | `forms.manage`; code-owned primitive contracts, no body | `data`: 20 field contracts |
| POST `/forms/render-schema` | `forms.manage`; full RenderDocument schema, including discriminated sources | Existing schema payload |
| POST `/forms/options` | `forms.manage`; `{documents, query}`; validates draft configuration and selects authenticated client variant | `result`: OptionResult |
| POST `/business-requests/{ref_id}/options` | `requests.start` plus current request visibility; body OptionQuery | `result`: OptionResult from exact pinned form/interaction |
| POST `/work-items/{ref_id}/options` | `requests.start` plus current work-item visibility; body OptionQuery | `result`: OptionResult from exact pinned form/interaction |
| POST `/forms/navigation-preview` | `forms.manage`; `{documents, query}`; validates configuration; no persistence or route execution | `data`: `{plan, data}` |

Options/navigation responses have `Cache-Control: private, no-store`. Reads do not change
workflow state; runtime option discovery is available wherever the existing resource visibility
allows reading (including historical states). It does not authorize a later write. `ref_id` is
the existing opaque revision-bearing reference; missing/invisible resources return 404 and
stale guarded revisions use the existing 409 contract. Missing authentication is 401,
missing permission 403, malformed DTOs or invalid configuration/membership 422.
Failures retain the public error envelope and `VALIDATION_FAILED` code 1002; issue pointers/codes
are under `data.issues` (for example `source.membership`, `/data/city`). A displayed option
can become invalid before submission; clients must handle that 422 and load current options.

Metadata derives from one trusted `FIELD_DEFINITIONS` registry: stable key/version 1,
layout/display/control/action classification, data types, allowed options, defaults, localized
English/Persian descriptions, child support and server-submit validation. `default` and `compact`
are renderer contracts for WEB/DESKTOP/ANDROID/IOS/B2B/SDK, not installed frontend implementations.
New trusted primitives require code and tests; authoring cannot load Python modules or SQL.

## Canonical values and sources

Sources use `bpms.options/1`. A node can declare `source` or legacy `selector`, never both.
Sources on the same canonical scope must agree across variants, including implied selectors.
Presentation, layout, picker and page settings may vary without weakening canonical constraints.

| Source kind | Membership at submit | Behavior |
| --- | --- | --- |
| `schema` | Snapshot | Values come from the pinned JSON Schema enum/const, including trusted Pydantic Enum/Literal schemas |
| `custom` | Snapshot | Bounded authored `{key,value,message?,matches?}` list, up to 256 unique typed keys; optional localized message and dependency filters |
| `domain` | Current | Registered `users` / `work_groups` selectors; live visibility, deletion/activity and reference revision checks |
| `remote` | Snapshot | Client GET metadata from an exact approved HTTPS URL; returned keys must still be in the pinned schema enum |

Domain `work_groups` exposes active groups of the actor; `users` defaults to the actor.
A `users` dependency named `group_ref` exposes active members of an active, current-revision
group that the actor belongs to. `admin.users.manage` / `admin.work_groups.manage` and superuser
permissions grant their corresponding managed visibility. Filtering and selected-reference
revision checks happen before count/pagination. Revoked membership or stale references fail
request submission and human completion even if a previous query returned the choice.

Select items keep the existing `{key: string, value: string}` contract. **Decode `json-scalar/1`
keys before writing canonical data.** `key = "json:" + compact JSON scalar`, with JSON string
escaping (ASCII escaping for non-ASCII), no whitespace and no NaN/Infinity. Examples:

| Canonical value | Wire key |
| --- | --- |
| integer `1` | `json:1` |
| boolean `true` | `json:true` |
| string `"1"` | `json:"1"` |
| string `"json:1"` | `json:"json:1"` |

Labels are never submitted as values. `selected_keys` takes encoded wire keys for lookup through
the same visibility rules. Null represents no selection when permitted by the schema and is
not a selectable option. Missing stays missing; a schema `default` is an annotation and is not
inserted by lookup, preview or validation. `required` still rejects missing values. Numeric
versus boolean versus string keys remain distinct. Existing ordinary selectors keep their wire
format; this encoding is explicit only on the new field-option contract.

### Example query and result

Use the fixture's `documents` with `/forms/options`, or send only this query to a pinned runtime
resource. `node_pointer` addresses the selected render tree, not the data object.

```json
{"node_pointer":"/root/children/1","data":{"country":"IR"},"page":1,"size":25,"generation":7,"selected_keys":[],"row_indices":[]}
```

```json
{"success":true,"request_id":"<request UUID>","error":null,"code":200,"result":{"dialect":"bpms.options/1","key_encoding":"json-scalar/1","state":"READY","generation":7,"locale":"en","source_revision":"<sha256>","dependency_fingerprint":"<sha256>","dependencies":{"country":"IR"},"items":[{"key":"json:1","value":"Tehran"}],"page":1,"size":25,"total":1,"total_pages":1,"remote":null}}
```

The response is always a page because source state/revision metadata is required. Page starts at
1; size defaults to 20 and is bounded by 100. Search matches labels/keys for static sources and
resource names for domain sources. Empty pages retain filtered total. Bounds are in generated
OpenAPI. At most 100 selected keys and eight named dependencies/row indices are accepted.
Form documents/data retain existing 64 KiB, depth and node-count limits; array length is at most
256. Dependencies must resolve typed scalar scopes and reject cyclic or cross-row references.

## Client state, dependent options and races

Dependencies map parameter names to schema scopes. Missing/null/invalid parents yield BLOCKED.
An optional BPMS expression `enabled_when` is typed boolean over `request`; missing or invalid
predicate input blocks availability. It never grants permission or writes/clears data.
`source_revision` hashes source, bound schema and catalog; `dependency_fingerprint` hashes bound
parameters, row indices, locale and predicate input data when present. Repeated `items` bind
using outer-to-inner `row_indices`; sibling collections cannot borrow another row's parents.

Clients must implement this state contract:

1. On parent, row, locale, search, page, selected lookup or predicate-input changes, increment the
   control's `generation`; invalidate options/selected-label results and cancel older requests.
   Any data change invalidates a source with `enabled_when`. Keep canonical values intact and
   mark incompatible selections invalid; automatic clearing belongs to BPMS-029.
2. While fetching, show LOADING locally and prevent selecting old choices. The backend returns
   BLOCKED, READY, EMPTY or CLIENT_FETCH, not a synthetic network-progress result.
3. Apply a response only to its original node/interaction when generation, expected source
   revision and dependency fingerprint still match the active request. Ignore stale responses
   even if cancellation failed. These hashes are correlation tokens, not authorization proofs.
4. Network errors produce local ERROR with retry; do not treat errors as empty valid choices.
   Retry uses a new generation with current inputs. EMPTY has no selectable matches; BLOCKED
   waits for valid parents. Previously selected removed keys stay invalid until corrected.
5. Snapshot choices remain valid in that published version; changed domain membership is checked
   currently. Submit never trusts client state, generation or a prior lookup result.

The shared fixture covers parent change, missing parent, recovery and typed keys across every
client kind. Loading/error/cancellation are client responsibilities; no browser renderer is
claimed tested. Desktop uses grid; mobile declares a bottom-sheet capability with inline fallback;
WEB/B2B/SDK use the shared controls and identical canonical data. B2B/SDK may submit canonical data
without requesting any presentation metadata.

## Remote policy and response mapping

`FORM_CLIENT_OPTION_URLS` defaults to `[]`. Each URL must exactly match an approved HTTPS endpoint,
without embedded authentication, query or fragment. Approval is rechecked at lookup. Remote sources
require pinned enum keys and expose `method=GET`, `credentials=omit`, `redirects=error`,
`items_pointer`, `key_pointer`, `value_pointer`, and distinct search/page/size/selected parameter
names plus typed dependency bindings. Clients append parameters with URL encoding, use the same
key/value wire contract for returned items, enforce page bounds, validate mappings and keys, and
apply the generation contract to their fetch. Missing selected keys are unavailable; unknown
remote keys must never be submitted. Host applications enforce CORS/transport policy themselves.

No server HTTP fetch occurs. No credential or arbitrary integration execution is inferred from
a URL. A future server-fetch adapter must use the governed integration boundary. This release
supports remote presentation only over a bounded authoritative schema snapshot.

## Interaction, protection and navigation

`interaction` declares input mode, picker, required capability names, default/compact fallback,
validation timing and bounded min/max width. Submit validation is mandatory; change/blur are
additional client hints. Invalid input-mode/picker component combinations fail authoring validation.
Missing capabilities fail selection unless fallback is explicit; fallback uses inline picker,
removes navigation and falls back from remote choices to the same pinned schema choices.
Existing typed accessibility, grid placement, messages, format hints and rules remain supported.
Hidden or disabled fields never bypass schema requiredness or membership validation. Collections
and attachments retain their canonical JSON/ownership contracts; repeated lookup does not create
row identity or attachment authorization. New `on_change` scripts/behavior fields are rejected.

`navigation` uses `bpms.navigation/1`. `FORM_NAVIGATION_ROUTES` defaults to `[]`; exact local route
strings such as `/people/pick` are host resolved. Navigation declares object `argument_schema`,
argument-name to form-scope bindings, object `result_schema`, and writable form-scope to result-scope
`result_mappings`. Schemas use the existing bounded subset; arbitrary executable code is forbidden.
Result mappings cannot overlap, target read-only/calculated scopes (including protected descendants
and ancestors), or write repeated rows. Collection mutation/identity is owned by BPMS-029.

```json
{"route":"/people/pick","argument_schema":{"type":"object","properties":{"current":{"type":"string"}},"required":["current"]},"arguments":{"current":"/properties/person"},"result_schema":{"type":"object","properties":{"id":{"type":"string"},"name":{"type":"string"}},"required":["id","name"]},"result_mappings":{"/properties/person":"/properties/id","/properties/name":"/properties/name"},"cancel":"preserve"}
```

The preview query has `node_pointer`, canonical `data`, optional `result`, `expected_data_revision`
and `cancelled`. The plan returns route, typed arguments, result schema and data hash. On return,
the client supplies the original hash: a changed data snapshot rejects the result. All mapped
values validate before the returned proposal can replace client data; invalid results leave input
unchanged. Cancel preserves data. This is a proposal, not a saved submission; normal server schema,
write-policy and current membership checks still apply when saved/submitted. Future renderers must
implement the same atomic staging and cancellation contract.

## Compatibility and ownership

No new tables, migrations, dependency packages or checksum normalization were introduced.
Legacy raw documents/checksums stay unchanged; source/interaction/navigation are optional additive
contracts. Runtime selectors gain current membership enforcement at authoritative submission
boundaries. Existing calculations/write protections remain in force. BPMS-028 owns authored reusable
components; BPMS-029 owns initialization, conditional-required execution, data-affecting dependency
graphs, clearing and collection mutation. This contract advertises none of those as new executors.
