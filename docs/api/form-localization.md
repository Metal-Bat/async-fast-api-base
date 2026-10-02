---
tags: [api]
---

# Versioned form localization

Implemented by BPMS-027. This is an additive contract on `FormDocuments` / `bpms.render/1`.
It does not activate the remaining `bpms.form/2` package proposal. Angular and Flutter renderers
are not implemented; clients must run the shared conformance vectors before claiming support.

## Authoring and publication

| Operation | Authorization and lifecycle | Localization behavior |
| --- | --- | --- |
| `POST /api/v1/form-versions` | `forms.manage`; current form ref, active form | Saves a draft with typed catalogs; gaps may remain. |
| `PUT /api/v1/form-versions/{ref_id}` | `forms.manage`; current draft ref | Replaces documents atomically and records catalog history. |
| `POST /api/v1/forms/validate` | `forms.manage`; no persistence | Returns draft issues, warnings and source revisions; optional `data` is canonical. |
| `POST /api/v1/forms/preview` | `forms.manage`; authenticated client context | Validates, selects a client variant, resolves text and converts formatting samples. |
| `POST /api/v1/form-versions/{ref_id}/publish` | `forms.manage`; current draft ref, active root | Rejects required missing/stale translations or incompatible parameters before publication. |
| `GET /api/v1/form-versions/{ref_id}` | `forms.manage` | Returns authored catalogs from that exact version, without localization or mutation. |
| `POST /api/v1/form-versions/{ref_id}/history` | `forms.manage` | Existing paginated history exposes catalog changes in `from_values` / `to_values` maps. |
| `POST /api/v1/forms/render-schema` | `forms.manage` | Complete render JSON Schema, including message references and field formatting. |

All JSON keys are snake_case. Creation returns 201; reads, validation, preview, update and publish
return 200 in the existing success envelope. Search/history use the existing `result` page envelope.
Revision-bearing ref IDs retain stale-write protection. No new permission or service credential is needed.

### Catalog profile: `bpms.messages/1`

`localization` is nullable. Null preserves existing literal labels and legacy checksums.
A catalog declares `default_locale`, `supported_locales`, `required_locales` and `catalogs`.
The profile supports **en/fa**; lists are unique, the default must be required, and required locales
must be supported. Regional preferences (`fa-IR`, `en-US`) resolve to the base language.
Runtime uses the existing request-local Accept-Language negotiation (application default en).
Preview's optional `locale` overrides the header for form text, not envelope language.
Unsupported preview locales use the package default. Missing/stale messages fall back from the
selected language to package default, then English. Required completeness prevents missing default
messages at publication. Optional-language gaps remain observable warnings.

Each catalog has at most 256 messages, each text/branch at most 2048 characters, each message at most
16 parameters; the serialized catalog is limited to 64 KiB. Render documents retain their existing
size/depth limits. Validation returns at most 32 issues and 32 warnings, but publication checks **all**
gaps before truncating diagnostics.

A message contains:

```json
{"text": {"one": "One item", "other": "{count} items"}, "parameters": {"count": "integer"}}
```

`text` is a string or exactly `one`/`other`. Plurals require integer `count`. English uses `one` for
absolute 1; Persian uses `one` for absolute 0 and 1 (Babel/CLDR integer rules). Other counts select
`other`. Named `{parameter}` interpolation and escaped `{{`/`}}` are supported. Attribute/index
access, conversions, format specifications, nested ICU/select/plural expressions and scripts are not.
Message content is plain text: clients must use text nodes, escape output and never interpret HTML.

Parameter types: `string`, `integer`, `decimal`, `date`, `datetime`. Names are bounded ASCII
identifiers. Arguments must match exactly. Integers must be JSON integers in the interoperable safe
range ±9007199254740991; booleans/floats are rejected. Other types use strings; decimals and dates
must already be canonical. Numeric/date substitutions use the resolved message language's digits.
Plural count may be implicit in a branch such as “One item”; all other declared names must appear
in every branch. Translations must retain the source parameter types and string/plural shape.

### Source revisions and draft workflow

1. Author default-language messages and call validate/preview.
2. Read `source_revisions[key]`.
3. Add translations with that hash in `source_revision`.
4. Validate again, then publish when required languages are complete.

The hash is SHA-256 of the UTF-8 encoding of compact, sorted-key, ASCII-escaped JSON containing
`text` and `parameters` (including an empty parameters object), excluding `source_revision`.
Use returned hashes; clients do not need to implement hashing. Changing source text or parameter
shape changes the hash. Old/missing translation acknowledgements produce `localization.stale`,
are not selected at runtime and block publication when that locale is required. An administrator
acknowledges review explicitly; the server never rewrites translations or published catalogs.

`localization.missing` identifies a missing catalog entry; `localization.parameters` rejects an
incompatible translation even in a draft; `localization.arguments` rejects incompatible bindings.
Missing catalog for new message references is `localization.required`. Legacy `localization_key`
continues to be ignored without a catalog and becomes a label reference when a catalog is present.

### Text bindings

Each render node may have `messages`, a typed map from role to `{key, arguments}`. Roles:
`label`, `placeholder`, `help`, `description`, `action`, `confirmation`, `loading`, `error`, `empty`,
`accessibility_label`, `accessibility_description`, `validation`.

`option_messages` is a list of `{value, message}`. Values must be distinct canonical enum values
of that choice field, including their JSON type. Labels never replace submitted values.
Selector-backed dynamic options remain BPMS-024's responsibility.

Resolved nodes expose `localized_text` and `localized_options`; compatibility fields `label`,
`options.placeholder` and `accessibility` are populated where applicable. Root localization metadata
reports `resolved_locale`, inherited direction, `catalog_revision`, and each selected message's actual
locale and source revision. A mixed fallback can therefore report fa for the view and en for a message.
These derived render documents are response views, not authoring documents to PUT back verbatim.
Outcome keys, field paths, schema enums, error codes and submitted values are never translated.
Localized forms reserve the variant key `shared` for the fallback design; targeted variants cannot
reuse it (`localization.reserved_variant`). Legacy forms without catalogs retain their prior behavior.

## Field formatting: `bpms.format/1`

A node's optional `formatting` declares `kind` (`text`, `date`, `datetime`, `decimal`), `direction`
(`auto`, `ltr`, `rtl`), `calendar`, `timezone`, `numbering`, optional `decimal_places` and `currency`.
Defaults: text, auto, gregory, UTC, latn, no fixed scale/currency. In localized views, auto inherits the
resolved language direction; explicit ltr is suitable for an email embedded in a Persian form.

| Kind | Localized input and canonical output | Display |
| --- | --- | --- |
| text | Unchanged bounded string | Unchanged; direction is separate metadata. |
| date | Gregorian `YYYY-MM-DD`; canonical ASCII ISO date | Same order, configured digits. |
| datetime | Explicit-offset ISO datetime, seconds required, ≤6 fractional digits; canonical UTC with `Z` | Converted to declared IANA timezone, configured digits. |
| decimal | Ungrouped signed decimal string; canonical ASCII decimal string | Exact value, optional fixed scale and ISO currency suffix. |

Only **Gregorian** calendar is implemented. `calendar: persian` is rejected; Persian digits do not
imply Jalali conversion. `arabext` recognizes Persian digits and decimal separator `٫`; ASCII digits
remain accepted. Grouping separators, currency input, exponents, nonfinite numbers, ambiguous local
datetimes, unknown UTC offset `-00:00`, invalid dates and rounding are rejected. No floating-point
conversion occurs. Currency is a validated ISO code displayed as a suffix; it never triggers exchange
rates or currency rounding. Fixed scales are 0–18 places and must preserve numeric value exactly.

Date/datetime formatting must bind a string field with matching JSON Schema date/date-time format.
Exact decimal formatting binds a **string field**, not JSON number. Runtime submissions are canonical;
localized values are rejected with `data.canonical_format`, including repeated items and all variants.
Localized input conversion is exposed through authorized preview samples and shared client vectors;
submission never silently guesses locale or rewrites data. Draft data may remain incomplete until
existing submit validation, as before.

Preview `format_values` accepts up to 32 `{node_pointer, value}` samples; each input is at most
256 characters and points to a node in the selected render document that declares formatting.
The result includes `{node_pointer, canonical, display}`. It does not replace preview `data`.
Bad samples return `valid: false` and `localization.format_value` at `/format_values`.

## Runtime reads, authorization and caching

Business-request and work-item DTOs resolve text from their exact pinned form version, including
retired versions. The recorded `variant_key`, client context, design revision and interaction revision
remain fixed. Locale switches neither reselect variants nor update persisted snapshots, request data,
submission seals, history, or replay keys. Changing form definitions later does not change old views.
Authorization remains with the existing request/work-item service checks before DTO construction.

No server-side resolved-document cache is introduced. Preview, business-request and work-item HTTP
responses use `Cache-Control: private, no-store`; existing middleware varies by Accept-Language.
No response is shared between actors or clients. `Content-Language` describes the envelope;
`localization.resolved_locale` and per-message locales describe form content (including preview override).
If clients retain in-memory views, key them by pinned form version, catalog revision, locale, actor and
pinned client interaction, and clear them on session/context changes.

## Example

The executable input example is `tests/fixtures/forms/localization-v1.json` under `form`. It includes
English/Persian labels and an explicit LTR email field. The same file carries plural and formatting
vectors for browser/native client conformance. No client-rendering test is implied.

```bash
jq '.form + {locale: "fa-IR", format_values: [{node_pointer: "/root", value: "ada@example.test"}]}' \
  tests/fixtures/forms/localization-v1.json > /tmp/form-preview.json
curl -X POST "$BASE_URL/api/v1/forms/preview" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H 'Content-Type: application/json' \
  -H 'Accept-Language: fa-IR' --data-binary @/tmp/form-preview.json
```

Success envelope (selected `data` fields shown):

```json
{
  "success": true,
  "request_id": "019a0000-0000-7000-8000-000000000001",
  "error": null,
  "code": 200,
  "data": {
    "valid": true,
    "issues": [],
    "warnings": [],
    "variant_key": "shared",
    "formatted_values": [{"node_pointer": "/root", "canonical": "ada@example.test", "display": "ada@example.test"}]
  }
}
```

In JavaScript, send the same JSON with `fetch(url, {method: "POST", headers, body: JSON.stringify(input)})`;
read `response.data.localization` and use text nodes for `localized_text`. Keep the canonical form-data
object separate from display strings. To create a draft, use the `form` fixture plus a current
`form_ref_id` and `number`; then publish its returned `ref_id` using the operation table above.

| HTTP status | Existing public error | Situation |
| --- | --- | --- |
| 401 | Existing authentication error | Missing/invalid session. |
| 403 | 2002 NOT_ALLOWED | Lacks forms.manage or existing runtime access. |
| 404 | Existing not-found error | Missing form or hidden runtime resource. |
| 409 | 1004 VERSION_CONFLICT | Stale ref, inactive root or immutable version. |
| 422 | 1002 VALIDATION_FAILED | Invalid DTO/profile or invalid publish documents; business validation includes pointer issues. |
| 200 | Successful validation envelope | Draft/preview `valid: false` reports document issues, not an HTTP failure. |

## Persistence and compatibility

Migration `49c0a2d18e76` follows `6bc31d7f2a10` and adds nullable JSONB `FORM_VERSION.LOCALIZATION`
and `FROM_LOCALIZATION`/`TO_LOCALIZATION` history columns. Existing rows remain SQL NULL and are not
rewritten. The existing whole-row published-version trigger already covers added columns.
Deploy the migration before updated application/worker code. Downgrade removes catalog/history
columns and loses new localization content; export new versions before an intentional rollback.
No package dependency, configuration, permission or worker transport change is required.

Legacy checksums omit the null catalog. Localized form checksums include the entire catalog; design
revision includes its catalog revision but is stable across locale changes. Runtime response additions
are additive; published legacy documents and checksum calculations retain their existing behavior.
