# M009B Increment 1 — Foundations Assurance Readiness Gate + Secure CSV Ingestion

**Milestone:** M009B — Foundations Assurance Readiness + CSV + Bulk Orchestration (Increment 1 of 4)
**Parent PID:** `docs/pids/M009-AMENDMENT-2026-10-13-CSV-ASSURANCE-READINESS.md`
**Work Order:** `docs/work-orders/WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md` §2
**Implementation branch:** `wo/M009B-increment1-readiness-csv`
**Head SHA (post-repair, independently re-verified):** `0a261d07109248f595a6c51111491015f829646c`
**Base:** `3ba07998b3cc2d99bd712f9eca61c36e190de0ed` (canonical main, WO-M009B merge)
**Status:** Delivery Controller independent review **COMPLETE**, including a full repair cycle after a fresh Independent Audit returned RED. A **second** fresh Independent Audit against this head SHA is now required before Architect Acceptance — this document will be updated once that lands.

## Scope delivered

Per WO §2.1–§2.6: the Security Foundations Assurance Readiness gate (`security_baseline/readiness.py`, `questionnaire/decorators.py`, a `process_view` hook added to the existing `QuestionnaireUploadSizeGuardMiddleware`), and secure CSV V1 ingestion (`questionnaire/csv_import.py`, `declared_format` dispatch in `questionnaire/import_services.py`, the `customer_provided_answer_text` provenance field). No bulk-orchestration code (Increments 3–4) and no Increment 2 scope were touched.

## Delivery Controller independent review — initial pass

Every file in the Implementer's original diff (head `ef01db5`) was read in full and independently assessed against the Work Order's exact text, not taken on the Implementer's own report. All CSV ingestion, extraction, structural-gate, scanner-reuse, and membership-ordering logic was confirmed correct. Every constant/attribute/URL name referenced was independently grepped against the real source. Full findings in the superseded first version of this document (preserved in git history at commit `94e3e50`); summary carried forward below.

## Independent test verification — initial pass

- `gitleaks detect` — no leaks found. `pip-audit` — no known vulnerabilities. `makemigrations --check --dry-run` — clean.
- Both real CI jobs (`ci/unit`, `ci/integration` from `.github/workflows/ci.yml`) independently replicated against **freshly created test databases** (`--create-db`), matching CI's own per-job Postgres-service isolation: 534 passed / 0 failed, and 1194 passed / 7 skipped / 1 xfailed / 0 failed respectively.
- A disclosed, non-blocking methodological finding: a bare, undifferentiated `pytest -q` across the whole repository (not how CI runs, not a WO acceptance criterion) surfaces a known, pre-existing class of order-dependent test-isolation hazard (already documented in the repo's own root `conftest.py`) that the new M009B test files' collection position newly falls within the blast radius of in that one invocation shape only. Confirmed not pre-existing-vs-introduced by rebuilding `3ba07998b` from scratch under identical conditions (clean, 2343 passed). Does not occur in either real CI job.

## Credential exposure — disclosed, contained, verified

The original Implementer self-disclosed running `docker exec infosecurs-relocation-web-1 env | grep -i customer` against the **persistent** `infosecurs-relocation` deployment, printing the real `CUSTOMER_ZERO_PASSWORD` into its own tool output. Never committed, pushed, or reused. Contained by the Delivery Controller: new value generated entirely server-side, `.env` updated in place, service recreated, real Django password hash updated by reading the credential from the container's own environment — the old or new value was never printed in any visible tool output. Verified via `authenticate()` returning the real user object.

## Fresh Independent Audit #1 — RED

A genuinely fresh Auditor (no inherited context) was dispatched against head `94e3e50`. Verdict: **RED**. One confirmed defect against WO §2.6's binding ordering requirement ("membership → entitlement → readiness, in that order"); everything else (CSV ingestion, both real CI jobs reproduced independently, `gitleaks`/`pip-audit`, the live Customer Zero/browser verification per WO §2.11 performed with real Playwright) confirmed GREEN.

**Defect:** `QuestionnaireUploadSizeGuardMiddleware.process_view` checked membership then readiness, but never entitlement — the real `@require_capability()` check only ever runs at view-invocation time, always after every middleware `process_view` hook has returned, so the actual runtime order was membership → readiness → entitlement. Concrete consequence: a member with a package tier insufficient for `customer_assurance` (`min_package_tier=2`) hitting an unready organisation's upload URL got the real readiness-blocker page (200, real Foundations completion data) instead of the generic 403 `require_capability` should produce — a genuine entitlement-tier bypass / information disclosure, untested by the shipped suite because its own autouse fixture stubs every organisation to always-ready by default.

Independently re-confirmed by the Delivery Controller directly against the code before accepting the verdict (not taken on the Auditor's word): the hook contained no call to `has_capability`/`require_capability` anywhere in its body; `customer_assurance`'s `min_package_tier=2` confirmed directly in `entitlements/migrations/0002_seed_product_areas.py`. Disclosed transparently on PR #107 (`https://github.com/maff0000/infosecurs/pull/107#issuecomment-6169351332`); PR not merged.

## Repair

A bounded repair dispatch (fresh context, full defect + required-invariant brief, no shortcut reimplementation permitted) produced commit `0a261d0` on the same branch:

- `entitlements/decorators.py`: extracted the reusable core of `require_capability`'s own decision (invalid-session-context redirect, active-organisation alignment, the capability/tier check itself — deliberately excluding membership, which both call sites already prove independently beforehand) into a new `enforce_capability_gate(request, organisation_id, capability_code=None)`, called by both `require_capability`'s `wrapped_view` and the new hook, so the decision exists in exactly one place.
- `questionnaire/upload_handler.py`: the hook now calls `enforce_capability_gate` between the existing membership check and the existing readiness check — runtime order is now genuinely membership → entitlement → readiness, matching WO §2.6.
- Four new tests in `questionnaire/tests/test_m009b_readiness_gate.py` (`TestEntitlementCheckedBetweenMembershipAndReadiness`): insufficient tier + unready org → 403 never blocker page (GET and POST, POST also proving no upload handler invoked and no row created); non-member with insufficient tier → still plain 404 (ordering regression guard); sufficiently-entitled member of an unready org → still sees the blocker page (regression protection for existing behaviour).

**Delivery Controller independent re-verification of the repair** (not taken on the repair report's word): read the full diff of commit `0a261d0` directly. Noted one subtlety the repair's own report did not mention — the refactor incidentally reorders the pre-existing `Invalid`-session-context check relative to the membership check inside `require_capability`'s own `wrapped_view` (previously: invalid-context check, then membership; now: membership, then invalid-context check inside `enforce_capability_gate`). Analysed directly: this affects only the combination of a non-member with a tampered/invalid session context, which no existing test (`entitlements/tests/test_decorators.py::TestFailClosedInvalidSessionContextRedirectsToLogin`, which only ever uses member fixtures) covers either way. The change makes the existing "every non-member gets a uniform 404" invariant *more* consistent, not less (previously such a non-member got a login redirect instead of the uniform 404 every other non-member gets) — assessed as a benign, non-blocking side effect of the extraction, not a new defect, and not worth a further repair round.

Re-ran both real CI jobs myself, independently, against fresh test databases (not trusting the repair's self-reported numbers): `ci/unit` + full `entitlements/tests/` suite together — **836 passed, 0 failed** (534 + 302, exact match). `ci/integration` — **1199 passed, 7 skipped, 1 xfailed, 0 failed** (matches the repair's own reported figures exactly). Re-ran `gitleaks detect` myself on the final commit — no leaks found.

## Remaining governance steps (not yet performed)

- A **second** fresh Independent Audit (new dispatch, no inherited context) against head `0a261d0`, specifically re-checking WO §2.6's ordering requirement against the repaired code, plus a full re-run of everything the first audit checked (nothing is assumed carried over).
- PR update/re-flagging for re-review (Delivery Controller's responsibility).
- Architect Acceptance and merge.
- Increments 2–4 remain explicitly not dispatched, pending this sequence.
