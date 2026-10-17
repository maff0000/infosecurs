# M010 MASTER PID — IRENE AI Security Adviser and Shared Security Tasks

**Programme state:** Product-authorised design / implementation campaign specification. **Product Authority:** User. **Central Architecture:** ChatGPT. **Delivery Controller:** GUNNAR. **Implementer:** FORGE. **Customer AI name:** IRENE. **Base and repository:** `maff0000/infosecurs`, current `main` reverified at implementation start. **Milestone:** M010 separate from M009B Customer Assurance delivery.

## 1. Mission and outcome

Transform current manual Foundations-first INFOSECURS into a genuinely AI-first customer experience, without changing canonical security truth. IRENE is the primary optional guided interface: she remembers the user's place, renders the approved structured question and available options, explains decisions, manages safe shared tasks, knows registered product links/relationships, and uses a deterministic engine to monitor upcoming reviews. The underlying app remains fully operational when IRENE is closed/offline. Name locked internally as IRENE, not Gunnar (already engineering delivery controller); external clearance required before public launch.

## 2. Dependency and version contract

Built on M007 shell/entitlements/18-item Foundation completion, M008 structured-first profile/baseline/12-control methodology and stage flows, M002/M003 risk/evidence, M004 policy, M005 grounded answer and M009 readiness/assurance (only once available). Existing implementation, not a stale proposal, is the concrete behaviour source. All M009B Increments 3/4 remain independently owned; do not modify their code/contracts or remove their gates. If user wants delivery in parallel, implement independent M010 layers first and integrate M009 using tested narrow adapters after M009 source stabilises. A main-base drift/conflicting PR is a reconciliation gate, never silently reset or force-push.

## 3. Frozen success capabilities

**F01** authenticated login → Home and IRENE workspace; accessible modal; manual alternative; privacy-respecting preference.
**F02** current organisation, entitlement, role and user context validated on each request/tool.
**F03** deterministic six-stage guidance across existing routes/forms, with Stage-4 exact 12 approved question keys/options, no duplicate catalogue, explicit UNKNOWN and gated N/A.
**F04** 18-item canonical completion, stage-local reviewed/confirmed and stage position all displayed correctly without conflation.
**F05** durable, shared Task List menu/page with grouping, ownership, dependencies, due dates, source links, filters and audit.
**F06** checkpoint by tenant+user+journey, resume after interruption and reconcile manual changes.
**F07** deterministic scheduled reviews create deduplicated policy/risk/evidence/remediation tasks when credible review fields exist; no LLM dependence.
**F08** approved product knowledge registry, direct authorised navigation, versioned progressive skill loading and bounded optional advice.
**F09** safe task lifecycle actions, explicitly confirmed before AI-proposed writes; canonical baseline writes only through existing protected services; no policy approval or risk acceptance by AI.
**F10** robust AI outage fallback, quotas, minimised prompts, privacy and tenant isolation.
**F11** higher-tier capability gates allow later expansion without changing foundational truth.
**F12** integration entry point for Customer Assurance state and exceptions after M009 availability without rewriting M009 response engine or 100% readiness gate.

## 4. Non-functional release bars

- No critical/high unresolved security/tenant/entitlement issue; a non-member receives same non-disclosing response as manual routes.
- WCAG 2.2 AA intended accessibility: keyboard, focus, ARIA, reduced motion, mobile viewports, zoom, contrast.
- Deterministic paths (question screens, answers, task CRUD, review rules, stage metrics) make zero model calls; measured and asserted.
- Configured AI cost/latency hard controls evidenced before enabling optional Adviser Mode. Approved values required; no invented ceiling.
- Two isolated test tenants plus role/tier/revocation scenarios; every registered read/write tool tested.
- All new migrations reversible where safe; fresh installation, backup/restore, concurrent worker/race and rollback tested.
- No production deployment, real customer data, or active Customer Zero reset under this PID.

## 5. Work-package PIDs (one campaign)

| Package | PID | Work | Internal exit evidence |
|---|---|---|---|
| A | M010A | Tenant-scoped shared task spine, dependencies, lifecycle, page/sidebar | DB/race/membership tests and task browser smoke |
| B | M010B | Existing Foundations guided adapter, answer parity and checkpoints | Manual-vs-guided parity, N/A/UNKNOWN tests |
| C | M010C | IRENE modal, conversation, product knowledge, skills, constrained tool mode | Accessibility, prompt/tool trust, model-free fallback |
| D | M010D | Scheduled security review rules and in-app briefings | Time/DST/dedup/rule correctness tests |
| E | M010E | Higher-tier and M009 Customer Assurance adapters | Entitlement/readiness/grounding non-bypass tests |
| F | M010F | Integrated system, adversarial/performance/a11y audits and release documentation | Consolidated independent auditor GREEN |

These are internal work packages for Gunnar's **one implementation push**. They do not require six architecture approval waits, six merges, or six final product releases. Maintain bounded commits, tests and safety stop conditions while implementing; return one integrated exact-SHA candidate. No implementation beyond these scoped package PIDs.

## 6. Mandatory design invariants

1. No second Foundations question database, answer ledger, completion formula or policy/risk consequence engine.
2. No customer-authored prose sent to consequential AI without individual threat-model authorisation; structured first, prose by exception.
3. No model-generated `option_code` acceptance; current server-side choices and explicit customer gesture.
4. No raw direct model database access; every tool per-call tenant and capability check.
5. Conversation memory cannot become authoritative fact; task and checkpoint state must be persisted independently.
6. Task completion cannot mark security control as implemented or approve policy/risk.
7. Scheduler emits at most one active occurrence for same tenant/source/rule/window (DB-proven).
8. No generative dependency for normal Foundations journey; user can work with AI disabled.
9. No model action on protected high-consequence domain writes.
10. No historical/hidden tenant data revealed through counts, titles, completion badges, model prompt, logs or cached context.
11. No unauthorised M009B contract or deployment changes.
12. GitHub exact SHA, migration state, CI, evidence, audit and delivery scope remain reconstructable.

## 7. Roles and one-push delivery authority

Product Authority has requested one long coordinated implementation, then review/test/fix/change. Gunnar may dispatch FORGE for **all six M010 work packages under this one campaign** after docs incorporation and dependency preflight, without asking for serial architecture approvals when the implementation stays in scope. Internally FORGE uses dependency-ordered commits, tests, security checks and recorded evidence at each waypoint. One protected integration PR / release candidate is submitted at the end for genuinely fresh independent audit and exact-head Architect Acceptance. Gunnar shall not self-approve merge, production, reset, real customer data, new privileged AI action or architectural deviation. Any critical STOP below halts affected work immediately (other independent work may proceed if safe) and is escalated.

## 8. STOP and change handling

STOP: cross-tenant information disclosure, improper capability bypass, incorrect baseline answer persistence, fabricated security assertions, unaudited approval/acceptance action, lost/duplicated task transactions, uncontrolled AI/provider processing, secret exposure, schema migration affecting current authoritative models without approval, materially incompatible main/M009 changes, unavailable security test harness, or demonstrably false product claims. Ordinary cosmetic/UI/test adjustments may be made within campaign without escalation; every change is evidenced. If dependency conflict occurs, Gunnar proposes a contract-preserving alternative to Central Architecture; do not improvise a new security model.

## 9. Acceptance and handoff

Final report must include exact integrated PR head/base, per-package commit mapping and changed files; migration/rollback plan; traceability matrix F01–F12; before/after manual answer equivalence; full two-tenant adversarial record; browser/a11y tests; concurrency/scheduler proof; measured provider budgets/fallback; existing regression suites including M007/M008/M009; secrets/SAST/dependencies/container scanning; fresh independent Auditor verdict, unresolved findings with dispositions, and evidence index. If GREEN, Central Architecture separately authorises merge. Production requires distinct release/privacy/brand gates.

## 10. Detailed supporting authority

Read the five M010 architecture documents, six package PIDs, single Gunnar campaign Work Order, traceability and template. Future skills, tests and optional operations must not contradict these documents or existing authoritative application services. If incomplete or unimplemented real domain service prevents an optional adapter, gate that adapter off rather than fake completion.
