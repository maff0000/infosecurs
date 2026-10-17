# M010A PID — Shared Security Task Spine

**Priority:** First work package. **Purpose:** Durable, tenant-isolated task administration, independent of AI availability. **Code ownership proposal:** New `security_tasks` Django app, plus only necessary existing shell/nav/capability wiring. Reconcile app naming before writing.

## 1. Product flows

Customer sees a **Tasks** sidebar item. Shared page lists tasks grouped Foundations; Risks & Actions; Policy; Evidence & Assurance; Other, with status, due/overdue, assignment, source link, dependency and history. Customer may create a simple follow-up, update assignment, mark administrative work done, open source record or return to a relevant Foundations question. No task closes an underlying risk/control/policy through implication. An authorised org colleague sees same shared task state; their private conversation remains inaccessible.

## 2. Engineering scope

- Implement `SecurityTask`, `SecurityTaskDependency`, `SecurityTaskEvent`, partial unique occurrence key and indexes per data contract. Use existing `Organisation` and membership/user relations, deliberate delete policies, stable enum constants, DB constraints. Foreign source links through allowlisted registry; verify ownership/tenant before linking; no arbitrary model references from untrusted input.
- Implement service layer `get/list/create/transition/assign/link` with fresh current permission checks, `select_for_update` or compare-and-swap, idempotency-key proof, append-only events, stable sorting/pagination, authorised deep links. Cross-org FK relationship and assignee validation mandatory.
- Implement deterministic group/priority display; do not create tasks just by visiting page. Default no automatic task generation until M010D; no needless scheduler/messaging stack. Support explicit blocked-by graph and reject cycles.
- Add ProductArea capability for Tasks / IRENE using existing seed/migration and route enforcement doctrine. Establish tier access matrix based on existing `has_capability`, not marketing tier comparisons in templates. Existing 16 ProductArea rows must not be silently changed or repurposed.
- Accessible Django templates following existing M007 shell; filters with server-side query enforcement and pagination. Add task-detail, permitted transitions and source route via registry, permission denial consistent with existing 404/403 convention.

## 3. Interfaces / transactions

Use `SecurityTaskService` callable from both future IRENE and deterministic scheduler; keep view thin. Task create carries `(organisation, kind, origin, source, occurrence_key, assignee, due, idempotency_key)` derived server-side; a repeated POST with same token returns original row, no second event. Transition requires expected version and reason; every mutation within atomic transaction and emitted activity. Bounded, escaped task text. No `TaskList` duplicate in a chat app.

## 4. Tests and fixtures

- Seed two orgs A/B with overlapping task titles and task IDs probed through cross-org routes; ensure B always non-disclosing.
- Tier restrictions, role restrictions, revoked user, anonymous redirects, forged task ID, foreign owner, other-org dependency, cycle/self-edge.
- Two simultaneous creators of same rule occurrence: one DB row; two concurrent writers with stale version: conflict not overwrite; one event per transition; repeated idempotency request no duplicate.
- Task done doesn't change `BaselineAnswer`, PolicyVersion approval, Risk status or `get_security_foundations_completion`.
- Browser Tasks page, sidebar/hamburger and keyboard/zoom. Fresh migrations and SQL constraints proven on PostgreSQL, not SQLite.

## 5. Exit and STOP

Evidence `docs/evidence/M010A-TASK-SPINE.md`: schema/migration references, API and route list, concurrency test output, two-tenant matrix, screenshots or browser logs. STOP on any cross-tenant link/assignment, duplicate occurrence under concurrency, task completion affecting canonical security fact, unsafe HTML, unreviewed core entitlement bypass. No merge required before M010B internal work proceeds if tests GREEN.
