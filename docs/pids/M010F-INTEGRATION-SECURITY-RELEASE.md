# M010F PID — Integrated Acceptance, Independent Challenge and Release Boundary

**Priority:** Final campaign package. **Objective:** Produce one independently challengeable whole-product candidate, not six self-attested pieces. **No merge or production deployment within this PID.**

## 1. Integration completion

Finish M010A–E in one integration branch with per-package commits and a durable evidence index. Reconcile current main and M009B state; rebase/merge policy per repo governance, never rewrite an accepted SHA's history. Compare actual migration state, current ProductArea seeds, M008 Stage 4 and M009 code. Test full fresh Django/PostgreSQL setup, backup/restore, reverse/roll-forward where safe, and feature flag OFF behavior. If a source domain remains unavailable, leave that optional adapter disabled, disclose it and keep base experience intact.

## 2. Acceptance matrix (minimum)

- **F01/F03/F04:** Home→IRENE auto-open, six-stage guidance, 12 approved control questions, distinct stage/12/18 progress, conditional options and immutable methodology, manual-vs-IRENE full answer parity.
- **F05/F06:** Tasks shared, assignments, source links, dependencies/graph cycles, state transitions, checkpoints, per-user privacy, manual changes reflected and multi-tab concurrency.
- **F07:** Scheduler due/overdue and recurrence correctness, no duplicates under races/DST, no fabricated source date, no model call.
- **F08/F09:** Skills versioning, tool allowlist, server authorisation, approved task proposal/confirmation, forbidden approval actions, prompt-injection and tool-call red-team.
- **F10:** AI cost/latency/timeout/quota measurement, safe provider outage, no data leakage, shutdown flag, portable artifact.
- **F11/F12:** Tier/access matrix and M009 integrations without readiness bypass, status available only when actually implemented.

## 3. Independent verification plan

Fresh independent Auditor receives only canonical repository, governing PIDs and clean environment, not Implementer summaries as evidence. Auditor re-derives key service invariants, builds adversarial fixtures independent of shipped tests, runs CI/security and browser flows, attacks two-tenant cross-object authorization, validates quotas/provider payload redaction, checks accessibility, race/idempotency and exact migrations. Gunnar independently spot checks material claims. Store machine-readable test and threat matrices; findings classed blocking/non-blocking with exact source SHA and reproducible steps. All critical/high violations are RED even if unit tests pass.

## 4. End-to-end customer scenarios

1. New small business user logs in, IRENE opens; answer 12 controls via approved options, including Not sure; complete profile stages; manual route still works.
2. Pause at question 7, create task, sign out/in, resume exact stage; another member sees shared task not private chat; role/tier/revocation changes remove access.
3. N/A conditional checks; attacker forges hidden option; no domain mutation, appropriate error.
4. Changing answer via manual page is reflected next time IRENE loads and downstream scenario/risk/policy state remains canonical.
5. Review scheduler runs twice concurrently and across DST; exactly one correct task; human task done doesn't mark control implemented.
6. User asks AI a hard question; response uses approved skill, bounded projection and authorised links, no customer A/B crossover; provider times out → structured journey continues.
7. Higher-tier member with 100% Foundations links to M009 upload; 99% or lower-tier member gets existing blocker/denial; no new upload bypass; no unsupported assurance claims.
8. Tenant export/deletion/privacy checks and backup/restore respect relevant retention and audit contract (production-only specifics subject to separate gate).

## 5. Quality tools and evidence

GitHub checks: ci/unit, ci/integration, security/dependencies, security/sast, security/secrets, security/container, CodeQL on PR; exact head and push-trigger semantics documented. Run all existing M007/M008/M009/M005 regressions (including 14-case golden corpus, if affected). Tooling: pytest with fresh Postgres, Playwright real Chromium, `makemigrations --check --dry-run`, gitleaks, pip-audit, dependency pins and container check, accessibility axe or equivalent + manual keyboard; maintain security test corpus under repo. No unsafe secret/environment dumping. Performance sample conditions, median/p95 time and API/provider use logged under non-sensitive identifiers, budgets product-approved.

## 6. Release, rollback, availability and operations

Set IRENE OFF and keep Tasks/manual answers functional in degradation or rollback. Confirm migrations do not break old code on app rollback; if they do, require a documented expand/contract rollout rather than risky downgrade. Run scheduler only once with specified deployment/leader rules and bounded worker concurrency; monitor failed rule runs and task count, no leaking titles/data in metrics. Real customer data is forbidden until separate privacy/security/readiness and hosting gate. Brand IRENE requires trademark clearance before marketing. No production deploy from merge authorisation alone.

## 7. Final handoff required from Gunnar

- One final PR URL, exact head/base, all commits and file list.
- M010A–F evidence index; requirement/negative-test traceability.
- Data model/migrations and backups; performance/cost numbers with agreed caps.
- Auditor RED/GREEN verdict and independent source-checked evidence; unresolved defects and disposition.
- Changes to root PID/roadmap, technical runbook and operator instructions.
- Confirmation that canonical M008/M009 behaviour and production instance untouched.
- Product screenshots and notes describing features unavailable due to explicit gating.

Only Central Architecture issues exact-SHA merge acceptance after this. Product Authority separately decides commercial rollout and subsequent improvements from user testing.
