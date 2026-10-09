# Timing, capacity and dependency plan

Prepared 2026-10-08. These are analyst planning ranges for future implementation, not measured delivery speed, commitments, model runtimes or dates when work will be done. No task is running asynchronously. Staffing, budget, availability and start date are unknown.

## Estimation model

One person-day is eight hours of task effort including implementation, focused review, tests and documentation. The calendar illustrations assume **four task-days per person per week**; the fifth day covers general coordination/unplanned interruptions outside task estimates. Design/QA/product review capacity must be available, but people are not assigned here. Parallel agents do not automatically equal independent staffed engineers: review and shared-file ownership remain constraints.

Low/high values are optimistic-to-cautious planning estimates, not statistical P50/P90. The ranges have low-to-medium confidence until APP-BE-001 / APP-FE-001 and the first three implementation tasks provide measured throughput. Do not multiply by an invented Sol/model speed factor.

| Workstream | Tasks | Base effort (person-days) | Base hours |
|---|---:|---:|---:|
| Backend | 32 | 85.5–157 | 684–1256 |
| Frontend | 38 | 123.5–213 | 988–1704 |
| Combined | 70 | 209–370 | 1672–2960 |

For planning, hold an additional **25% explicit integration/rework reserve**: combined **261.25–462.5 person-days**. This is a separately visible assumption, not effort already included in each task or a calibrated probability. Do not add a second unnamed buffer. External access/approval delays are additional elapsed time and are not estimated as engineer work.

## Work by milestone

| Milestone | Backend person-days | Frontend person-days | Combined |
|---|---:|---:|---:|
| M0 — Baseline and trustworthy checks | 4.5–9 | 4–7 | 8.5–16 |
| M1 — Usable application foundation | 23–42 | 26.5–48 | 49.5–90 |
| M2 — Visual authoring and safe defaults | 12–22 | 38–64 | 50–86 |
| M3 — Connected case and actual system outcome | 27–50 | 32–55 | 59–105 |
| M4 — Calendar, reminders and business insights | 9–16 | 7–12 | 16–28 |
| M5 — Full coverage, repeatable demo and acceptance | 10–18 | 16–27 | 26–45 |

Milestone grouping is not a strict waterfall: a calendar/API contract can advance while an unrelated visual inspector is being built. Dependencies in the task index decide ordering. The complete demo requires every mandatory task, not only early milestones.

## Illustrative elapsed-time scenarios

The model schedules the listed dependency graph onto backend/frontend work slots (one non-preempted task per slot), choosing earliest available work and then milestone/ID. Week zero begins only after kickoff/access. It excludes decision/provider waiting and does not explicitly model every shared-file collision; the 25% reserve addresses some, not all, integration uncertainty. These are planning illustrations, not guaranteed deadlines.

| Hypothetical available delivery capacity | Base modeled weeks | With 25% reserve | Interpretation |
|---|---:|---:|---|
| 1 backend + 1 frontend | 32–55 | 40–69 | Design/QA/product support available; frontend scope is substantial. |
| 1 backend + 2 frontend | 23–42 | 29–52 | Backend and shared contract decisions increasingly constrain parallel UI work. |
| 2 backend + 2 frontend | 18–31 | 23–39 | Requires real review capacity and serialized migration/lockfile ownership. |

One person performing both workstreams serially has a base workload floor of **53–93 weeks** at the assumed four task-days/week, before reserve and waiting. This is not a recommendation to staff that way; it prevents treating total effort as instant parallel agent throughput.

## Detailed relative windows — illustrative 1 backend + 2 frontend slots

Rows show separate low/high schedules, rounded to one decimal week. “Start L/H” and “Finish L/H” are each scenario’s modeled positions, not a promise that a task may start anywhere in that interval. No calendar start date is assumed.

| Task | Base days | Start L/H (week) | Finish L/H (week) |
|---|---:|---:|---:|
| APP-BE-001 | 1.5–3 | 0.0 / 0.0 | 0.4 / 0.8 |
| APP-BE-002 | 2–4 | 0.4 / 0.8 | 0.9 / 1.8 |
| APP-BE-003 | 1–2 | 0.9 / 1.8 | 1.1 / 2.2 |
| APP-BE-004 | 2–4 | 1.1 / 2.2 | 1.6 / 3.2 |
| APP-BE-005 | 3–5 | 1.6 / 3.2 | 2.4 / 4.5 |
| APP-BE-006 | 3–6 | 2.4 / 4.5 | 3.1 / 6.0 |
| APP-BE-007 | 2–4 | 3.1 / 6.0 | 3.6 / 7.0 |
| APP-BE-008 | 3–5 | 3.6 / 7.0 | 4.4 / 8.2 |
| APP-BE-009 | 3–5 | 4.4 / 8.2 | 5.1 / 9.5 |
| APP-BE-010 | 1–2 | 5.1 / 9.5 | 5.4 / 10.0 |
| APP-BE-011 | 2–4 | 5.4 / 10.0 | 5.9 / 11.0 |
| APP-BE-012 | 2–4 | 7.6 / 14.2 | 8.1 / 15.2 |
| APP-BE-013 | 1–2 | 5.9 / 11.0 | 6.1 / 11.5 |
| APP-BE-014 | 4–7 | 9.9 / 18.2 | 10.9 / 20.0 |
| APP-BE-015 | 3–5 | 6.1 / 11.5 | 6.9 / 12.8 |
| APP-BE-016 | 4–7 | 16.6 / 30.8 | 17.6 / 32.5 |
| APP-BE-017 | 2–4 | 17.6 / 32.5 | 18.1 / 33.5 |
| APP-BE-018 | 3–5 | 18.1 / 33.5 | 18.9 / 34.8 |
| APP-BE-019 | 3–6 | 6.9 / 12.8 | 7.6 / 14.2 |
| APP-BE-020 | 3–5 | 8.1 / 15.2 | 8.9 / 16.5 |
| APP-BE-021 | 4–7 | 10.9 / 20.0 | 11.9 / 21.8 |
| APP-BE-022 | 3–6 | 11.9 / 21.8 | 12.6 / 23.2 |
| APP-BE-023 | 4–7 | 12.6 / 23.2 | 13.6 / 25.0 |
| APP-BE-024 | 3–6 | 13.6 / 25.0 | 14.4 / 26.5 |
| APP-BE-025 | 3–6 | 14.4 / 26.5 | 15.1 / 28.0 |
| APP-BE-026 | 4–7 | 8.9 / 16.5 | 9.9 / 18.2 |
| APP-BE-027 | 2–4 | 15.1 / 28.0 | 15.6 / 29.0 |
| APP-BE-028 | 4–7 | 15.6 / 29.0 | 16.6 / 30.8 |
| APP-BE-029 | 3–5 | 18.9 / 34.8 | 19.6 / 36.0 |
| APP-BE-030 | 2–4 | 19.6 / 36.0 | 20.1 / 37.0 |
| APP-BE-031 | 2–4 | 20.1 / 37.0 | 20.6 / 38.0 |
| APP-BE-032 | 3–5 | 20.6 / 38.0 | 21.4 / 39.2 |
| APP-FE-001 | 2–3 | 0.0 / 0.0 | 0.5 / 0.8 |
| APP-FE-002 | 2–4 | 0.5 / 0.8 | 1.0 / 1.8 |
| APP-FE-003 | 3–5 | 1.0 / 1.8 | 1.8 / 3.0 |
| APP-FE-004 | 3–5 | 1.0 / 1.8 | 1.8 / 3.0 |
| APP-FE-005 | 3–5 | 1.8 / 3.0 | 2.5 / 4.2 |
| APP-FE-006 | 3–5 | 4.4 / 8.2 | 5.1 / 9.5 |
| APP-FE-007 | 4–7 | 5.1 / 9.5 | 6.1 / 11.2 |
| APP-FE-008 | 2–4 | 3.6 / 7.0 | 4.1 / 8.0 |
| APP-FE-009 | 2–4 | 5.1 / 9.5 | 5.6 / 10.5 |
| APP-FE-010 | 1.5–3 | 5.6 / 10.5 | 6.0 / 11.2 |
| APP-FE-011 | 2–4 | 8.6 / 15.8 | 9.1 / 16.8 |
| APP-FE-012 | 3–5 | 11.9 / 21.0 | 12.6 / 22.2 |
| APP-FE-013 | 2–4 | 6.9 / 12.8 | 7.4 / 13.8 |
| APP-FE-014 | 4–7 | 18.1 / 33.5 | 19.1 / 35.2 |
| APP-FE-015 | 3–5 | 18.9 / 34.8 | 19.6 / 36.0 |
| APP-FE-016 | 5–8 | 7.6 / 14.2 | 8.9 / 16.2 |
| APP-FE-017 | 4–7 | 8.9 / 16.8 | 9.9 / 18.5 |
| APP-FE-018 | 5–8 | 9.9 / 18.5 | 11.1 / 20.5 |
| APP-FE-019 | 3–5 | 11.1 / 20.5 | 11.9 / 21.8 |
| APP-FE-020 | 4–7 | 6.0 / 11.2 | 7.0 / 13.0 |
| APP-FE-021 | 4–6 | 7.6 / 14.2 | 8.6 / 15.8 |
| APP-FE-022 | 4–7 | 11.9 / 21.8 | 12.9 / 23.5 |
| APP-FE-023 | 4–7 | 9.1 / 16.2 | 10.1 / 18.0 |
| APP-FE-024 | 4–7 | 10.1 / 18.0 | 11.1 / 19.8 |
| APP-FE-025 | 4–7 | 15.1 / 28.0 | 16.1 / 29.8 |
| APP-FE-026 | 4–7 | 17.1 / 31.5 | 18.1 / 33.2 |
| APP-FE-027 | 3–5 | 11.1 / 19.8 | 11.9 / 21.0 |
| APP-FE-028 | 3–5 | 15.6 / 29.0 | 16.4 / 30.2 |
| APP-FE-029 | 4–6 | 12.9 / 23.5 | 13.9 / 25.0 |
| APP-FE-030 | 4–7 | 16.1 / 29.8 | 17.1 / 31.5 |
| APP-FE-031 | 3–6 | 6.1 / 11.2 | 6.9 / 12.8 |
| APP-FE-032 | 3–6 | 18.1 / 33.2 | 18.9 / 34.8 |
| APP-FE-033 | 4–7 | 19.6 / 36.0 | 20.6 / 37.8 |
| APP-FE-034 | 3–5 | 20.6 / 37.8 | 21.4 / 39.0 |
| APP-FE-035 | 3–5 | 20.6 / 37.8 | 21.4 / 39.0 |
| APP-FE-036 | 3–5 | 16.4 / 30.2 | 17.1 / 31.5 |
| APP-FE-037 | 4–6 | 21.4 / 39.0 | 22.4 / 40.5 |
| APP-FE-038 | 2–4 | 22.4 / 40.5 | 22.9 / 41.5 |

## Key dependencies and parallel-work rules

The principal authoring chain is baseline → typed metadata/pickers → form controls and node inspectors → human/mapping/branch/service configuration → publication/defaults → real case → combined browser demo. Calendar/reminders require their own persistence and notification contracts; dashboards require authorized metric definitions. Default restore depends on exact baseline/dependency readiness, not just a reset button.

Run baseline/review/design-system work in parallel across repos. Frontend may use labeled fixtures while a producer contract is being implemented, but that task stays unintegrated. Backend migration writers serialize through one owner. Contract generation, lockfile changes, shared picker components, route registries and seed/template manifests also need a single integration owner per batch. Do not have agents edit the same generated output concurrently.

Tasks APP-BE-032 and APP-FE-038 record backend and full-product acceptance separately. Backend-only verification does not depend on frontend final signoff, preventing a circular dependency; final frontend/product acceptance consumes the backend record.

## Scope additions not hidden in the base estimate

A named vendor integration, Jalali input/conversion, service-principal redesign, multi-replica session store, calendar sync/recurrence or major newly discovered UI/API gaps need scoped estimates after their contracts/access are known. The base includes the local HTTP sandbox adapter and AI evaluation harness, not unbounded provider certification or paid evaluation campaigns. No paid vendor/security/legal approval is assumed.

## Re-estimation checkpoints

After intake, remove already-satisfied implementation work and retain the relevant verification effort. After the first three implementation tasks, measure review/rework and actual check/setup effort, then update task ranges and rerun the dependency model. Reforecast at the first visual-authoring demo, first sandbox receipt and full reset rehearsal. Every change preserves original estimate, new estimate, reason and scope impact; never quietly revise numbers to make a missed target disappear.

## Suggested first execution batch

Start APP-BE-001 and APP-FE-001 together. Follow with APP-BE-002 and APP-FE-002, resolve D01 through APP-BE-003, then seed/live-query work and the frontend Angular/PrimeNG review. Freeze C02–C05 and C11 early so profile/help/views/pickers and visual authoring can proceed independently. No production rollout, paid calls or destructive demo reset is part of this intake batch.
