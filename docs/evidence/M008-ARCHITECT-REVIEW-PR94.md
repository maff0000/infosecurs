# M008 — Architect Review: PR #94

**Architect:** Central Architecture / Project Architect
**Date:** 2026-10-04
**PR:** #94
**Reviewed head:** `73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40`
**Frozen product SHA:** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`

## Decision

**RETURNED — NOT YET ACCEPTED FOR MERGE.**

## What the Architect accepts, on the evidence reviewed

- PR #94 is documentation/evidence-only — no product path is touched.
- All seven PR checks are GREEN.
- The fresh Auditor (`docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md`) returned a GREEN verdict.
- The frozen product remains **provisionally technically GREEN**.
- The disclosed selector collision, the orphaned unreachable template (`policy/templates/policy/edit.html`), and the documentation-count discrepancy (`docs/design/M008D-POLICY-TRUTH-MATRIX.md`'s "seven simple controls" count) are **non-blocking on current evidence**.

**No product defect is currently declared.**

## Acceptance gaps — exactly three

### A1 — Real-browser E2E incomplete

`WO-M008-GOV-RECOVERY-001` requires a real-browser Customer Zero cycle: reset → login → Stages 1–4 → Risks & Actions → policy review/approval → policy PDF → reset again.

The audit report itself states that Stage 2–3 customer state was populated through direct service/model paths, and Stage 4 answers through direct HTTP POSTs. Those are useful lower-layer proofs, but they do not satisfy the Work Order's real-browser end-to-end requirement.

### A2 — Destructive cross-tenant reset not proven with the feature enabled

The Auditor's foreign-tenant reset request was exercised while `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=false`. The feature was later enabled for Customer Zero's own positive reset, but the Auditor did not directly exercise the foreign-tenant destructive attempt with the feature enabled.

For a destructive test utility, the Architect requires this proof directly — not inferred from code reading, not inferred from the feature-disabled case.

### A3 — Keyboard proof scope drift

The Architect's recovery directive required a keyboard-only Stage 4 proof. The Git-tracked Work Order was recorded instead as "keyboard-only real-browser walkthrough of at least one full guided-journey stage," and the Auditor exercised Stage 1. That alteration was not Architect-authorised and may not be silently accepted after the fact.

## Authorisation

**No product repair is authorised by this review.** These three gaps are evidence gaps in the recovery's own audit record, not findings against the product. See `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md` and `docs/work-orders/WO-M008-GOV-RECOVERY-002.md` for the bounded supplementary work this review authorises to close them.
