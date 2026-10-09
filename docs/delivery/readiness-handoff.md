# C06 / APP-BE-011 and APP-BE-012 readiness

`GET /api/v1/setup/readiness` is superuser-only. Authentication uses the current
user owner; ordinary administrators/requesters receive 403. It returns the existing
success envelope and private, no-store headers. Refresh no more often than 30 seconds
and show checked_at UTC. Scope is development_demo, never a production commitment.

Checks cover the exact Alembic head, code-owned permission definitions, four installed
role/capability mappings, published handler fingerprints, a live client release,
enabled request types, configured connections and read-only internal cache/broker/
private-bucket connectivity. Each database catalog is bounded to 4,097 rows; overflow
adds a required unknown catalog_bounds check. Database facts have a five-second bound,
and independent internal probes have three-second bounds. Exceptions become stable
safe reason keys, never host/DSN/provider/credential text. No provider verification,
paid call, provisioning, grant, publish, task enqueue or read-time seed occurs.

Required blocked checks produce blocked overall; otherwise any required unknown
produces unknown. Optional unconfigured features are not_applicable. Broker acceptance
does not establish execution: worker_execution and scheduler_execution remain unknown
because there is no trustworthy current heartbeat/probe receipt owner in this baseline.
They require explicit operator verification; this GET does not issue active commands.

Repair keys are operations (operator), permissions, clients, request_types, step_types
and connections. Reason keys: setup.fact_verified, setup.dependency_missing,
setup.optional_not_configured, setup.database_unavailable, setup.connectivity_verified,
setup.probe_unavailable, setup.operator_probe_required and setup.catalog_limit. A missing
capability uses its owning screen or operator command; no resource or user list is exposed.

`POST /api/v1/designer/dependency-readiness` requires workflows.manage and ownership
of the named workflow, or a superuser. Body:

```json
{"workflow_version_ref_id":"current-exact-ref","client_release_ref_id":null}
```

The optional exact client release checks pinned human-form renderer compatibility via
the existing form resolver; omission/null is not_checked. A disabled/inaccessible
release blocks this requested check; stale workflow or client pins return 409.
The existing publication dependency/graph/subprocess validator and workspace promotion
policy remain authoritative. The projection does not validate or execute a second graph.

The result includes exact requested refs, authorized current resource links, available
form/workflow checksums, at most 256 safe code/pointer diagnostics, selected step keys
and allowlisted repair destinations. Examples: human.form.not_published → form_versions;
connection.unavailable → connections; client.renderer.incompatible → clients;
human.candidates.empty → work_groups; binding incompatibility → workflow_versions.
Missing/inaccessible dependencies return no name/content/reference through pins. Retired
pins remain explicit; no latest-version substitution occurs. Empty candidate groups
are a separate availability fact, not another graph engine. Runtime requester/service
eligibility remains not_checked and must use existing request/use authorization.

Repair the indicated current record explicitly, return to the same node and re-read
with fresh refs. Published graphs and active execution pins remain unchanged. No schema
is added by 011/012. Generated en/fa OpenAPI and readiness-contracts.json are in wave-four;
these snapshots attest backend contracts, not frontend integration or deployed probes.
