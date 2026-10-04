# WO-M008-GOV-RECOVERY-002 — M008 Audit Supplement: Close Three Evidence Gaps

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Parent amendments:** `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md`, `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md`
**Exact frozen product SHA:** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`
**Exact recovery branch base:** `73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40`
**Status:** APPROVED FOR DELIVERY CONTROLLER DISPATCH

## Purpose

Close only the three evidence gaps identified by Architect review (`docs/evidence/M008-ARCHITECT-REVIEW-PR94.md`: A1, A2, A3). This Work Order is documentation/evidence/re-verification work only. It does **NOT** authorise product repair.

## Implementer

Dispatch one bounded Implementer. It may create **only**:

```
docs/evidence/M008-AUDIT-SUPPLEMENT-PREFLIGHT.md
```

It must verify:

- `origin/main` remains the frozen SHA `6393912bc4f7a98e5d167a465369bf2a8ef26c57`;
- this supplement starts from the reviewed PR #94 head `73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40`;
- every product path remains byte-identical to the frozen SHA (confirmed directly, not assumed);
- the disposable audit environment/identities the next phase will use;
- the exact S1/S2/S3 scenarios below, summarised in its own words as the plan the next, separately-dispatched Auditor will execute.

After committing the preflight document, the Implementer **STOPS**. No product changes of any kind.

## Fresh independent Auditor

Dispatch a new Auditor who has **not performed any prior M008 audit** and inherits **no previous conclusion** — from either the two prior full audits or this Work Order's own Architect review.

### S1 — True browser-only Customer Zero E2E

With real Chromium/Playwright, entirely through the rendered UI:

```
reset Customer Zero
  → login
  → complete Stage 1 through the rendered UI
  → complete Stage 2 through the rendered UI
  → complete Stage 3 through the rendered UI
  → complete all 12 Stage 4 questions through the rendered UI
  → Risks & Actions through the UI
  → deterministic policy generation/review through the UI
  → policy approval through the UI
  → real policy PDF download through the UI
  → final reset through the UI
  → prove forced fresh login
```

During this customer journey:
- **no** ORM/model writes to populate customer state;
- **no** direct service calls to populate customer state;
- **no** direct HTTP form POSTs outside browser automation;
- read-only DB inspection *after* actions is allowed, to confirm what the UI-driven actions actually persisted.

**Explicitly prove the Stage 1 save/redirect path** so the previous unexplained automation anomaly (noted in `docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md`) is genuinely **closed**, not merely worked around or routed past.

### S2 — Keyboard-only Stage 4

Using real Chromium and **no mouse/pointer clicks at all**:

- enter Stage 4 by normal UI navigation;
- traverse controls by keyboard;
- select answers by keyboard;
- save/advance by keyboard;
- complete all 12 questions;
- include at least one "Not sure";
- exercise at least one conditionally-gated option set (a control whose NOT_APPLICABLE option is only offered given a specific prior fact);
- mechanically prove visible focus at every interactive stop;
- prove no keyboard trap;
- prove the final reviewed/still-needs-confirming progress state.

### S3 — Foreign-tenant reset with the reset feature enabled

Run with `DJANGO_ENV=development` and `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true`.

Create Customer Zero and a second, unrelated, synthetic tenant/user. Authenticate as the second tenant and, while the reset feature remains enabled:

- attempt GET/POST against Customer Zero's reset URL;
- attempt identifier/URL forgery where applicable;
- attempt a reset against the second tenant itself, even though it is not the trusted fixture.

Prove mechanically:
- every destructive attempt fails closed;
- Customer Zero's DB state and evidence bytes are unchanged by any of these attempts;
- the second tenant's own DB state and evidence bytes are unchanged;
- only the trusted Customer Zero fixture can then perform a positive reset.

### Audit output

Create a durable report, committed to branch `arch/m008-governance-recovery` (continuing PR #94), at:

```
docs/evidence/M008-FINAL-REVERIFICATION-AUDIT-SUPPLEMENT.md
```

Containing, at minimum: exact SHAs; an explicit independence statement; the exact commands/scripts run; S1/S2/S3 results in full; evidence locations; any anomalies and their root causes; and an unequivocal verdict.

**Any product defect: NOT GREEN / STOP.** No repair is authorised under this Work Order; it returns to the Architect for a new Amendment and Work Order.

## PR #94 — continued

This supplement continues PR #94. It is additionally authorised to add **only**:

```
docs/evidence/M008-ARCHITECT-REVIEW-PR94.md
docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md
docs/work-orders/WO-M008-GOV-RECOVERY-002.md
docs/evidence/M008-AUDIT-SUPPLEMENT-PREFLIGHT.md
docs/evidence/M008-FINAL-REVERIFICATION-AUDIT-SUPPLEMENT.md
```

No product paths. All required CI/security checks must be GREEN on PR #94's new head before the stop gate below is reached.

## Mandatory Architect stop gate

After the supplemental audit is GREEN and PR #94's **new** head has all required CI/security checks GREEN:

**STOP. DO NOT MERGE.**

Return to the Project Architect with:

1. new PR #94 head SHA;
2. frozen product SHA;
3. supplement preflight path;
4. supplement audit path and verdict;
5. S1 browser-only journey result;
6. S2 keyboard-only Stage 4 result;
7. S3 enabled-reset foreign-tenant result;
8. complete PR changed-path list;
9. all CI/check conclusions;
10. residuals.

**Only explicit Project Architect acceptance after that return authorises merge.**
