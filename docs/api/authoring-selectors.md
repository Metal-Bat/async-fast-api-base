---
tags: [api, designer, select]
---

# Workflow authoring selectors

All selectors return bounded `key`/`value` choices. Submit `key` unchanged; `value` is a display label. Database keys are opaque revision-bearing refs. Showing a choice does not authorize its later use: save, publish and execution resolve current access and version again.

| Resource | Endpoint | Required operation permission | Eligibility |
| --- | --- | --- | --- |
| Users, active work groups, form/workflow roots, request types, statuses and outcomes | `POST /api/v1/designer/selectors/{kind}` | `workflows.manage` | Current active/visible rows; root visibility and request-type workflow visibility apply. |
| Exact form versions | `POST /api/v1/designer/selectors/form_versions` | `workflows.manage` | Published, nondeleted version under an active visible form root. A non-superuser sees owned forms. |
| Exact workflow versions | `POST /api/v1/designer/selectors/workflow_versions` | `workflows.manage` | Published, nondeleted version under an active workflow root visible through owner/open/grant rules. |
| Published form component, data type or subprocess version | `POST /api/v1/designer/library/select` | `forms.manage` or `workflows.manage` by kind | Library visibility and authoring filters apply before pagination. |
| Published step type versions | `POST /api/v1/step-types/select` | `workflows.manage` | Enabled published registered handlers. |
| AI agents, providers, connections, connection models and agent choices | `POST /api/v1/ai-agents/.../select` | `workflows.manage` and per-resource access where relevant | Each AI selector applies its own published/installed/verified checks. |
| Service or notification connections | `POST /api/v1/integration-connections/select?kind=SERVICE` or `kind=NOTIFICATION` | `workflows.manage` and connection use grant/ownership | Active, verified, nondeleted connection of the selected kind. Credential references are never returned. |
| Registered clients and releases | `POST /api/v1/clients/select`, `POST /api/v1/client-releases/select` | `forms.manage` | Current authorized client/release context. |

For the generic designer route, allowed `kind` values are `users`, `work_groups`, `forms`, `form_versions`, `workflows`, `workflow_versions`, `request_types`, `definition_status`, `request_status`, `process_status` and `outcome`. Unknown kinds are rejected by DTO validation. Searches use case-insensitive substring matching against resource names and occur before page/size limits. Version labels include `· v<number>` to distinguish pins; the server still relies on the opaque key.

A version picker request:

```http
POST /api/v1/designer/selectors/form_versions?response_format=page
Content-Type: application/json
Authorization: Bearer <access-token>

{"search":"purchase","page":1,"size":20}
```

A response has the shared page envelope:

```json
{
  "success": true,
  "request_id": "example-request-id",
  "error": null,
  "code": 200,
  "result": {
    "items": [{"key":"<exact-form-version-ref>","value":"Purchase form · v3"}],
    "page": 1,
    "size": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

Use `response_format=items` to receive the same bounded `items` array as the top-level JSON response. Empty searches return `[]` or an empty page. The library selector requires a `kind` in the JSON body and additionally accepts `category`, `locale` and `capabilities` filters. The integration selector requires `kind` as a query parameter and uses a standard `SelectQuery` body. `Accept-Language` changes translated enum labels, never submitted keys.

Use the [full workflow roadmap](../roadmap/full-workflow.md) to see where these choices feed graph authoring. The live [Swagger UI](http://localhost:8000/api/v1/swagger-ui) gives exact request constraints and route responses.
