---
tags: [api]
---

# Workflow field inventory

`POST /api/v1/designer/field-inventory` is a read-only designer analysis. The caller must be authenticated and hold both `workflows.manage` and `forms.manage`. The workflow must also be visible to the caller. The endpoint reads exact workflow and form revisions; it does not run steps, AI, providers or submissions, and it never changes a definition. Successful responses set `Cache-Control: private, no-store`.

## Request

```json
{
  "workflow_version_ref_id": "<exact-workflow-version-ref>",
  "start_form_version_ref_id": "<exact-form-version-ref>",
  "locale": "en",
  "page": 1,
  "size": 25,
  "search": "quantity",
  "classification": null
}
```

`workflow_version_ref_id` is required. An omitted `start_form_version_ref_id` excludes the start collection point. The API does not select the latest form. Both published and draft revisions are accepted; a stale revision fails. A request type may choose a form independently, so the caller must pass the intended exact start form version. `locale` is `en` or `fa`; `page` is 1–1000, `size` is 1–100, and `search` is at most 128 characters. Search and classification filter rows after the full inventory and summary have been computed. Ordering is by collection point, schema path and field identity. The response uses the normal success envelope.

## Result

`workflow_version_ref_id`, `graph_checksum`, and `form_snapshots` identify analyzed revisions. Each form snapshot includes its exact `ref_id` and checksum; a draft checksum is null. `complete` is false and `diagnostics` names coverage gaps such as an empty graph, unknown handler, unresolved request field, inaccessible subprocess, graph cycle or traversal limit. A row without detected consumers becomes `UNKNOWN_ANALYSIS` when coverage is incomplete.

`summary` counts collection-point field definitions, unique form-version field definitions, user-entry occurrences, nested collection item definitions, automatic sources, conditional-only fields, review candidates, and possible user inputs. The counts are definition counts, not runtime array-row counts or a universal minimum form size. `total` is the filtered row count; `page` and `size` describe the returned slice. `declared_ports` lists input and bound output port declarations separately from form fields.

Each field row has `identity` (exact form ref, collection point, schema scope), `path`, `label`, `type`, `source`, `required`, `user_entry`, `classification`, `component_instance`, `collection_scope`, `actor_targets`, `component_scopes`, `occurrences`, `author_description`, `business_rationale`, `first_use`, `dependencies`, and `suggestions`. An evidence item has a stable reason code, exact definition location, target, optional condition, localized explanation and `via` chain for transitive calculations. A suggestion is a review prompt with impacted locations and a caveat, never a removal instruction. User-authored schema descriptions and any explicit `x-business-rationale` are returned separately from technical reasons. `resolved_pins` identifies accessible exact component, data-type and subprocess versions with checksums.

Reason codes currently include `SCHEMA_REQUIRED`, `VALIDATION`, `STEP_PORT`, `NOTIFICATION_BINDING`, `INTEGRATION_BINDING`, `ROUTING`, `ASSIGNMENT`, `CALCULATION`, `VISIBILITY`, `SELECTOR`, `NAVIGATION`, `REVIEW`, `ACTION_REQUIRED`, and `SUBPROCESS_MAPPING`. The classification values are `ALWAYS_REQUIRED`, `CONDITIONALLY_REQUIRED`, `OPTIONAL_USED`, `SYSTEM_SUPPLIED`, `DERIVED`, `NO_DETECTED_CONSUMER`, and `UNKNOWN_ANALYSIS`.

A small result excerpt:

```json
{
  "workflow_version_ref_id": "<exact-workflow-version-ref>",
  "graph_checksum": null,
  "form_snapshots": {
    "start": {"ref_id": "<exact-form-version-ref>", "checksum": null}
  },
  "complete": true,
  "diagnostics": [],
  "summary": {
    "field_definitions": 2,
    "unique_field_definitions": 2,
    "user_entry_occurrences": 2,
    "user_entered": 2,
    "repeated_collection": 0,
    "automatic_sources": 0,
    "conditional_only": 0,
    "review_candidates": 1,
    "possible_user_inputs": 2
  },
  "fields": [
    {
      "identity": "<exact-form-version-ref>:start:/properties/quantity",
      "form_version_ref_id": "<exact-form-version-ref>",
      "collection_point": "start",
      "component_instance": null,
      "collection_scope": null,
      "path": "/properties/quantity",
      "label": "Quantity",
      "type": "integer",
      "source": "USER_INPUT",
      "required": false,
      "user_entry": true,
      "classification": "OPTIONAL_USED",
      "component_scopes": ["/render_schema/root/children/0"],
      "occurrences": 1,
      "author_description": null,
      "business_rationale": null,
      "actor_targets": ["REQUESTER"],
      "first_use": "/bindings/0",
      "dependencies": [{
        "reason": "STEP_PORT",
        "location": "/bindings/0",
        "target": "approval.quantity",
        "condition": null,
        "explanation": "Feeds a declared step input",
        "via": []
      }],
      "suggestions": []
    }
  ],
  "declared_ports": [{
    "scope": "workflow",
    "step": "approval",
    "direction": "INPUT",
    "port": "quantity",
    "type_schema": {"type": "integer"},
    "source_kind": "REQUEST",
    "source": "USER_INPUT",
    "source_path": "/properties/quantity",
    "location": "/bindings/0/target_port",
    "required": null,
    "nullable": null,
    "cardinality": null
  }],
  "resolved_pins": [],
  "page": 1,
  "size": 25,
  "total": 2
}
```

Actual responses wrap this value in the project's standard success envelope. Stale or invisible version references return the existing not-found/error contract. Missing permissions return the standard forbidden response. Invalid pagination or enum values return FastAPI validation errors. Analysis limits and inaccessible nested definitions are reported as incomplete diagnostics where a bounded result is still possible.

The analyzer does not infer business purpose, inspect execution values, or automatically remove form fields. An opaque handler or unresolved read prevents an unused claim. Form variants are analyzed as separate render occurrences over the shared data schema.
