# C01 system catalog ownership

[seed-manifest.json](seed-manifest.json) inventories the current code-owned permission definitions, optional role templates, handler keys/versions, transforms and notification templates. Permission descriptions and optional role payloads have content hashes. Handler schemas remain owned by the immutable registry and `StepTypeService`; published versions are never rewritten by this reconciler.

Run `mise run catalog-check` for a read-only permission report. Run `mise run catalog-reconcile` to create missing permission definitions and reconcile registered step drafts in one transaction. These commands use the configured database; the acceptance runner uses its own disposable database. Installation roles require an explicit option:

```sh
PYTHONPATH=src uv run --env-file .envs/.backend python scripts/reconcile_system_catalog.py --role requester --role reviewer
```

No role is automatically assigned. Existing descriptions, permission revocations, memberships, passwords and operator-managed roles remain unchanged. Deleted definitions are reported and never restored implicitly. Role creation is blocked when its required capability is missing/deleted. Existing deleted roles also remain operator-managed. PostgreSQL transaction advisory locks serialize absent-row creation; existing database uniqueness constraints provide final identity enforcement. Each concurrent invocation uses its own session.

Requester/reviewer templates grant `requests.start`; resource eligibility and current assignment still decide individual access. Designer grants form/workflow authoring. Administrator grants the enumerated management capabilities but never superuser. Operator grants request access and task operations; recovery currently also requires superuser at the service boundary, and this template does not grant recovery. Auditor grants administrative history access. Installation owners must review these enumerated grants before assigning roles.

Dynamic business permissions, forms, workflows, integrations, users, paid-provider configurations and connection grants are operator-owned. Transforms are declared in registered handler schemas rather than seeded as universal business definitions. Templates are code-owned, with `workflow.notice/1` currently executable; MAP templates are design-only until APP-BE-014. Demo fixtures and any new bootstrap flow belong to APP-BE-005. This task introduces no new tables, default passwords, user assignments or production credentials.

Check summaries report permission gaps without credentials. The permission check does not claim full installation readiness; APP-BE-011 owns readiness across providers, catalogs and operational services. The write command calls the existing step reconciler, which rejects unavailable roots and validates existing snapshots instead of rewriting published data.
