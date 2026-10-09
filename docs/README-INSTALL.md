# BACKEND delivery pack — installation and first task

This pack contains planning/rule files only. It does not change application behavior, install a dependency, create a DB migration or prove a test passed.

## Add without overwriting existing work

Copy `docs/delivery/` into the matching repository as new files. If any path already exists, compare/merge it rather than overwriting. Keep `BACKLOG.md` and its current task IDs/history intact; add a link to `docs/delivery/BACKEND-BACKLOG.md`. APP tasks are additional verified deltas, not replacements for already completed tasks.

Merge the section in `AGENTS.addendum.md` into existing AGENTS.md. Add `.agents/skills/product-delivery/SKILL.md` only if that skill path does not already exist; otherwise merge deliberately. Keep all existing skills and instructions. No global plugin installation is required.

The main backlog is self-contained. Common companion files give agents smaller sections to read: EXECUTION-RULES.md, CONTRACTS-AND-ACCEPTANCE.md, DECISIONS.md, TIMING-AND-DEPENDENCIES.md and RECORD-TEMPLATES.md. Their initial content matches the embedded plan. Shared contract changes need a versioned peer handoff and synchronized appendices; never silently edit only one side.

## Initial instruction to the agent

> Read AGENTS.md, `BACKLOG.md`, `docs/delivery/BACKEND-BACKLOG.md` and applicable skills. Start APP-BE-001. Record existing functionality and exact uncovered gaps; preserve current architecture and IDs. Then select a dependency-ready task. Do not call implementation complete without a final warning-free `mise run check` and the task's real acceptance evidence. Do not perform destructive or paid actions without their explicit authorization and environment guards.

D01 is an unresolved migration-policy conflict. It blocks new persistent schema, not independent code review, contract design or read-only inventory. No repository check or deployment was executed when this pack was authored.
