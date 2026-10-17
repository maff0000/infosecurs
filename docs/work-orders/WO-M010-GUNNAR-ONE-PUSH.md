# WO-M010 — GUNNAR / FORGE Single Coordinated IRENE Delivery Campaign

**Scope:** Build all M010A–M010F in one long push (implementation campaign), with internal test checkpoints and one final independently audited product candidate. **Owner:** GUNNAR. **Source:** `maff0000/infosecurs`. **No automatic merge, deployment, reset, real customer data or privilege expansion.** **Product Authority direction:** build comprehensively once, then review/test/fix/change.

## 1. One-time preflight before writing code

1. Read in sequence README, all five architecture docs, master M010 PID, M010A–F, this WO and acceptance plan; reconcile with `PID.md`, M008 code/current fixtures, M009/M009B Work Order and current `main` HEAD; record evidence of discrepancies. Confirm exact repo/host/worktree and running mutable environments; **do not** touch persistent `/srv/infosecurs` runtime or Customer Zero state during campaign.
2. Confirm which M009B increments merged/under review, current M008 screens, ProductArea/entitlements, actual review-date fields, scheduler provision and AI gateway. Identify code conflicts before branch creation. Identify existing security-task model if one appeared after doc authorship; reuse, do not duplicate.
3. Prepare docs-only incorporation PR or branch as required by project governance: place this pack in prescribed repo paths, update `PID.md` and `docs/ROADMAP.md` with additive references, record Product Authority's one-push authorisation and identity/name decisions. Do not silently merge main if branch protection disallows it; produce handoff evidence.
4. Establish one integration branch `wo/M010-irene-ai-first-campaign` from reverified main (or governed feature branch namespace); use disposable Docker/Postgres, synthetic Customer Zero, independent ports/volumes; pin exact base SHA and CI config. No secrets in outputs.
5. Establish baseline regression counts and a two-tenant adversarial fixture before implementation. Record baseline failures separately rather than conceal them; do not overwrite protected data.

## 2. Execute six packages sequentially as internal checkpoints

**WP-A task spine (M010A)** → models/constraints, task service, dependencies, shared page/menu, migrations, unit/integration/race tests. Commit and evidence.

**WP-B structured journey (M010B)** → existing M008 question view-model, fully validated answer adapter, versioned checkpoint/resume, UNKNOWN/N/A workflow, task link, parity tests. Commit and evidence.

**WP-C IRENE UI/tool/skills (M010C)** → modal shell, conversation privacy, product map, safe tool registry, skill manifest/loader, fake-model test harness, preferences, deterministic fallback, a11y. Commit and evidence. Live provider mode must remain off until the numeric budgets and vendor security assessment are approved; deterministic path is releasable independently.

**WP-D scheduler (M010D)** → inventory actual due-date fields, implement eligible deterministic review rules, one-shot scheduled management command/launcher, stable occurrence idempotency, in-app briefings, DST/race tests; disable unsupported rules with evidence. Commit.

**WP-E entitlements/M009 adapter (M010E)** → four-tier capability matrix, current M009 admission/read-only safe links/exception tasks where services exist, feature-disable for missing bulk functionality; no M009 pipeline rewrite. Commit.

**WP-F integration/audit prep (M010F)** → whole-user journeys, security challenge, browser/a11y/regression, migrations and rollback, performance & provider budget approval gate, docs/runbooks, final evidence. Commit and open **one integrated PR**; do not merge.

Gunnar may use multiple specialist FORGE engineers/agents and internal branches/worktrees as implementation detail, but one authoritative integration candidate is the delivery output; do not permit parallel authors to mutate the same shared code/DB instance without controlled merges.

## 3. Time-saving autonomy without unsafe shortcuts

No requirement to ask Central Architecture for sign-off between A–F when changes satisfy the written contracts, and no ritual full independent audit on each internal commit. Developer tests and quick security smokes are expected throughout. An **uninterrupted long push does not mean untested/unreviewed code**. At the end, fresh independent Auditor must challenge the integrated system, not rely on FORGE's claims. Blockers requiring immediate escalation: any tenant/access leak, M008 truth change, unsafe AI tool, uncontrolled cost/secret exposure, M009 collision, destructive migration, or inability to demonstrate core correctness. Cosmetic fixes and expected integration issues are repaired autonomously within approved scope, with evidence.

## 4. Acceptance thresholds before candidate submission

- Every M010 feature F01–F12 traced to implementation and tests; no critical missing capability represented as complete.
- Existing Foundations manual paths and 12-question versioned catalogue regression-identical where unchanged; Stage-4 parity all option variants; 18-item metric untouched.
- Two-tenant, mixed tier/role test matrix including revoked membership, objects/tasks/conversations, malicious model inputs, cross-org dependency, scheduler, links and logs.
- DB race tests for idempotency, migrations on fresh PostgreSQL, crash/retry and rollback flag.
- Normal path zero LLM calls; provider outage doesn't break tasks/manual; optional model quotas enforced with measured, approved numerical parameters before live enablement.
- UI WCAG 2.2 AA oriented real browser/keyboard/mobile; modal can close, manual app remains present.
- Post-build CI/security checks, CodeQL PR triggers, fresh independent full audit GREEN before requesting exact-head acceptance.

## 5. Exact scope protections

May add `security_tasks` and `irene` apps as warranted; may modify M007 shell/nav and M008 views/forms **only** to expose same validated backend contract with regressions. No unauthorised amendment to canonical baseline question/options, M002 risk scenarios, M003 security truth, M004 policy approvals, M005 grounded assurance or M009 bulk claim/AI budgets. Don't introduce one-off AI provider stack, free-text replacement of checkbox methodology, unsafe task-to-control completion automation, global embeddings, new external notifications, raw SQL tools or autonomous high-consequence decisions. Any business process requiring unavailable source fields remains disabled and listed as gap.

## 6. Evidence discipline and final return

Each work package writes `docs/evidence/M010[A-F]-*.md` (paths from PIDs), containing exact working commit SHA, changed files, tests, known gaps, manual browser evidence and STOP status; final `docs/evidence/M010-CAMPAIGN-FINAL-RETURN.md` includes full traceability and Product Authority candidate list. Submit one PR with complete, intelligible history; Gunnar independent review followed by fresh Auditor. Show exact main/base, PR head, all seven appropriate checks, migration dependency map, gateway budgets, browser proof, two-tenant red-team negative results and whether M009 optional adapters were disabled. No false GREEN for unavailable tool, untested source rule or missing approval.

## 7. Done versus deployed

**Implementation complete** means PR candidate satisfies tests and fresh audit. **Architect accepted** means Central Architecture approves a pinned head for merge. **Merged** means verified parent-SHA lineage and post-merge CI on main. **Released** means separate production readiness, DPIA/privacy/retention/provider review, brand clearance, user acceptance and rollout authorisation. These are distinct statuses. Gunnar must not conflate them.
