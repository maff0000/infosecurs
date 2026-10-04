# M008 — Governance Recovery Amendment 002

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Parent recovery amendment:** `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md`
**Frozen product SHA:** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`
**Reviewed PR head:** `73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40`
**Status:** AUTHORISED — AUDIT SUPPLEMENT ONLY; **PRODUCT_GREEN STILL WITHHELD**

## What this Amendment records

Following Architect review of PR #94 (`docs/evidence/M008-ARCHITECT-REVIEW-PR94.md`), three acceptance gaps were identified in the recovery audit's own evidence record (A1 — real-browser E2E incomplete; A2 — destructive cross-tenant reset not proven with the feature enabled; A3 — keyboard proof scope drift). This Amendment authorises exactly the bounded supplementary verification needed to close those three gaps, and nothing else.

## What this Amendment explicitly does NOT authorise

- **No product defect has been declared.** The three gaps are evidence gaps, not product findings.
- **No application-code change is authorised.**
- **No test-code change is authorised.**
- **No migration, model, dependency, configuration, or CI change is authorised.**
- **No M009.**
- **No production use.**
- **No real customer data.** Synthetic, disposable audit state only.

If supplementary verification exposes a genuine product defect or an architecture ambiguity: **STOP**, and return to the Architect for a new Amendment and Work Order. No repair is authorised under this Amendment or its accompanying Work Order.

## Closure condition

M008 remains open, exactly as `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md` already states — this Amendment adds one further required step to that closure sequence: a GREEN supplementary audit (`docs/evidence/M008-FINAL-REVERIFICATION-AUDIT-SUPPLEMENT.md`) closing gaps A1, A2, and A3, reviewed by the Project Architect, before any merge and before any PRODUCT_GREEN declaration.

**No other actor may declare M008 PRODUCT_GREEN.**
