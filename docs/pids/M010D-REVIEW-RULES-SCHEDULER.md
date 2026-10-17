# M010D PID — Deterministic Security Review Scheduler and Proactive Tasking

**Priority:** After M010A task service exists; may be built in parallel with M010C without schema conflicts. **Objective:** Provide upcoming/overdue work from genuine source dates and policies, not invented AI reminders.

## 1. Source catalogue and grounding

Inventory live domain fields and services before code: policy versions/next review, `risk_register.Risk` next review fields if real, remediation deadlines, evidence expiry/attestation dates where stored, supplier review dates **only if supplier module exists and offers a canonical date**, and any relevant Foundation re-confirmation rules. For each source define `rule_id`, version, live source field/service, eligibility predicate, due-date timezone, warning windows, default task kind/group, owner policy, source link, completion condition and dedupe occurrence-key definition. Do not invent a review date when none exists. If some source models lack a suitable review date, disable that rule and evidence the gap rather than guessing.

## 2. Deterministic calculation

Implement `security_tasks.review_rules` (or agreed equivalent) as registered Python rule functions returning typed due-candidates. Run at explicit scheduler cadence (e.g., daily via existing approved job runner; confirm actual host/runtime and define launch/deployment spec), tenant-by-tenant. Use UTC timestamps and configured business timezone; DST logic tested. Candidate sorts by due date/severity; missing dates skipped. Example review warnings: 30 days before due, 7 days before due, overdue; these are provisional settings, not universal mandated regulation. Avoid treating overdue as proof of security failure; explain actual task source.

## 3. Task emission and closure

For each rule candidate, derive stable `(organisation, rule_id, source_object, due_occurrence)` key. Task service upserts single occurrence atomically, persists rule/version/source due data and audit reason, does not duplicate on each run. Transition to done/cancelled does not result in daily resurrection; later due occurrence is a new task. Source review date changed: reconcile source link and due date via explicit policy (update still-open task with audit event, suppress stale candidate, or close superseded task); do not silently overwrite finished evidence. Rule double-run under concurrent schedulers must still emit one task due to database unique index. No LLM involvement in calculation or correctness.

## 4. Briefings and presentation

Home/IRENE Continue and Tasks views show upcoming tasks, due soon, overdue, blocked, recently completed—derived from authoritative task DB. Optional natural-language briefing may summarize only selected authorised task metadata after task engine computes order; no independent LLM scheduler judgement. In-app digest/review summary only in first version. Email, calendar events, webhooks and push delivery require separate consent, suppression, provider, unsubscribe and anti-spam design; not authorised by this PID.

## 5. Permissions and operational service identity

Scheduler runs with least-privilege service role, iterates organisations in isolated transactions, uses application-level tenant-scoped task services, no cross-tenant aggregation into a prompt or message. Prevent leakage in metrics, logs, errors and lock identifiers; log only IDs/counters as appropriate and bounded error metadata. One tenant failure must not prevent processing subsequent tenants; individual failures are retried idempotently.

## 6. Evaluation and acceptance

Run rule fixtures with due yesterday/today/7d/30d/beyond, no date, future/past policy version, completed review, reassigned owner, removed tenant member, manual closure, changed date, recurrence, DST start/end, UTC midnight, overlapping service workers, scheduler crash after DB write and after task creation. Assert exact one task+event per occurrence, no fabricated date, no model calls, correct organisation link, correct human task group, and no security-control auto-upgrade. Execute repeat runs and compare stable DB snapshots. Document which registered domains truly support review dates and which remain disabled.

## 7. Evidence and STOP

`docs/evidence/M010D-REVIEW-SCHEDULER.md` with inventory/rule registry, job command/deployment semantics, exact scheduler run records, duplicate race tests, timezone/clock tests, provider-free execution and recovery. STOP on duplicates, cross-tenant tasks, fabricated source dates, accidental auto-approval or deleting historical task trace.
