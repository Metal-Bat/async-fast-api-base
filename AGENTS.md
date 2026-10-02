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
