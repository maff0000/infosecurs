# M008 — Governance Recovery Amendment

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Recovery date:** 2026-10-04
**Frozen product SHA:** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`
**Status:** AUTHORISED GOVERNANCE RECOVERY; **PRODUCT_GREEN WITHHELD**

## What this Amendment records

`docs/architecture/DELIVERY-GOVERNANCE.md` establishes the mandatory delivery chain — PID/Amendment → Git-tracked Work Order → Delivery Controller → Implementer → Independent Audit → PR → Architect Acceptance → Merge → Closure — and its four hard invariants, effective 2026-10-04.

PRs #88–#93 against this epic were merged after this new mandatory governance doctrine became effective, but **without** durable, Git-tracked implementation Work Orders and **without** a recorded Project Architect acceptance step prior to merge. This is a **governance defect** — a gap in the recorded chain of authority — and is recorded here as exactly that. It is **not**, by itself, evidence of a product defect.

## What this Amendment does NOT do

- It does **not** retroactively classify PR #86 (WI-ERRATA, merge `aa1048486f86f386333ea1ce2f1cbe1cc2b17cfd`) or PR #87 (M008B-WI1, merge `ba571aaa087970f70e4580c1ae47bf41cb172d14`) as governance violations. Those merges pre-date the point at which the new doctrine became mandatory, and are not judged against a standard that did not yet exist at the time they were made.
- It does **not** falsely claim that historical Work Orders existed for PRs #88–#93. None did. This Amendment does not manufacture a historical record that is not true.
- It does **not** authorise reverting or reimplementing any technically-accepted code merely to manufacture a historical sequence that did not actually occur. The product's technical content stands as delivered; what is being recovered here is the governance record around it, not the product itself.
- It does **not** authorise any M008 product change. See the accompanying Work Order (`docs/work-orders/WO-M008-GOV-RECOVERY-001.md`) for the exact, narrow, documentation-only scope this recovery permits.

## Current status of the product

The product at the frozen SHA above is **PROVISIONAL TECHNICAL GREEN / GOVERNANCE UNACCEPTED**:

- Technically, the delivered work has been independently tested and independently audited twice, with the second, fresh audit returning a clean verdict on the frozen SHA.
- Governably, it has not yet passed through the recorded chain this Amendment and its Work Order now require: a durable, Git-tracked Work Order; a bounded, Git-tracked Implementer preflight record; a genuinely independent re-verification audit conducted *under* that Work Order (not inheriting either prior audit's own conclusion); and explicit, durable Project Architect acceptance — before any merge, and before M008 may be declared PRODUCT_GREEN.

## What this Amendment authorises

One fresh, independent re-verification pass, conducted under the accompanying Work Order, against the frozen product SHA. Nothing else. See that Work Order for the complete, bounded scope.

## What happens if a defect is found during recovery

Any defect discovered during this recovery's re-verification audit returns to the Architect for a new Amendment and a new Work Order. No repair is authorised under this Amendment or its accompanying recovery Work Order.

## Closure condition

M008 remains **open** — not PRODUCT_GREEN, not closed — until all of the following have happened, in order, and are each durably recorded in Git:

1. this recovery Amendment and its Work Order are committed (this document and its sibling);
2. the bounded Implementer's preflight record is committed;
3. the fresh, independent re-verification audit is committed, with an unequivocal GREEN verdict;
4. a recovery PR, restricted to the documentation paths this Work Order names, is opened and all required CI checks are green;
5. the Project Architect reviews the actual Git evidence and issues a durable Architect Acceptance record;
6. the Project Architect — and no other actor — explicitly declares M008 PRODUCT_GREEN;
7. the recovery PR is merged.

No other actor may declare M008 PRODUCT_GREEN.
