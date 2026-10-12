## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

@RTK.md

## Entity field formatting

- Write every SQLModel entity `Field(...)` declaration across multiple lines, including short declarations.
- Put each `Field` argument on its own line. Expand nested `Column(...)` and `ForeignKey(...)`
  calls the same way; keep simple scalar type constructors such as `String(64)` compact.
- Use trailing commas so Ruff preserves the expanded layout. Do not use formatter suppression.
- Apply this to new or edited entity declarations, including shared entity bases. Do not mix a repository-wide reformat into feature work.
- Preserve all types, defaults, constraints, names, indexes and history behavior when formatting.

```python
name: str = Field(
    sa_column=Column(
        "NAME",
        String(255),
        nullable=False,
    ),
)
```

## Detailed Swagger contracts

- Load and follow `.agents/skills/swagger-contracts/SKILL.md` when adding or changing HTTP routes,
  public DTOs, or OpenAPI documentation. It supplements the existing API documentation skill.
- Document actual authorization, lifecycle, parameters, nested schemas, examples, errors, and
  response headers. Preserve the project's envelopes, public error codes and localized Swagger.

## DTO wire format

- Every JSON request, response, pagination, and envelope model must inherit `core.base_dto.BaseDTO`.
- JSON and OpenAPI field names must serialize as `snake_case`; do not add serialization aliases.
- Validation-only aliases may be used temporarily for backward-compatible input, but canonical examples and new clients must use `snake_case`.
- HTTP header aliases are exempt because their names follow HTTP conventions rather than the JSON DTO contract.

## Cross-layer software consistency and repair work

For cross-layer consistency and affected APP work, read `BACKLOG.md` and the current approved decisions. Follow `.agents/skills/contract-consistency/SKILL.md` in addition to existing skills.

- Reuse current implementations and preserve existing APP/assistant IDs. Completed planning history belongs in Git, not duplicate backlogs. The new CONS tasks own only cross-cutting consistency checks; concrete feature repairs remain with their actual APP owner.
- Follow the software design contract and repair register in `docs/delivery/consistency-2026-10-09/`. Private entities, public DTOs and UI models share meaning through explicit mappings; they are not required to be the same class or expose identical fields.
- Fixed public JSON, including nested models and computed fields, follows BaseDTO/snake_case with documented validation-only aliases; dynamic document keys and HTTP headers have separate existing contracts. Preserve current envelopes, operation IDs, selectors, private binary APIs and stable error values.
- Existing PATCH self-profile/preferences routes are compatibility exceptions to conventional resource PUT. Preserve their semantics; review `docs/delivery/consistency-2026-10-09/SKILL-AMENDMENTS.md` rather than breaking the API to match older prose.
- Reconcile current backend recorded DB-002/D07 decisions in `docs/delivery/approved-decisions.json` and `docs/changes/DB-002.md` before changing migrations or readiness labels. DB-002 supersedes the old migration-file policy. Never rewrite applied revisions, blindly stamp or reset shared data. Exact accepted SDK exceptions remain VERIFIED_WITH_EXCEPTION, not strict exception-free or full demo readiness. Do not expand exceptions or suppress new diagnostics.
- Keep clear application ownership, atomic invariants, authorized projections, immutable published pins, current refs, unchanged replay payloads and required human approval. No new parallel workflow engine, scheduler, generic action executor, permission system or JSON-console product UI.
- Frontend design is PrimeNG-first for standard touched business UI, with semantic tokens and explicit tested exceptions. Persisted/reset defaults and canonical values must agree with the backend; neutral actor cleanup is distinct. Reuse existing shared controls through documented public seams without domain/presentation inversion; do not duplicate Administration schema controls into Studio or replace domain-specific configuration. One frozen producer manifest governs the main transport and reviewed metadata slices. Preserve en/fa, RTL, accessibility, unsaved input and uncertain-result recovery.
- Full final `mise run check` and actual task-specific acceptance are required. Compare start/end source identity, retain failed/partial evidence and scope deadlines. Missing peer/services or required skips prevent integrated completion. No local fixture result is promoted to real-service/browser/deployed/user acceptance.

This section supplements the existing rules. If a newer repository decision conflicts, record it and preserve working contracts until resolved; do not silently choose a breaking cleanup.
