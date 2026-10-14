# M009B Increment 1 — Foundations Assurance Readiness Gate + Secure CSV Ingestion

**Milestone:** M009B — Foundations Assurance Readiness + CSV + Bulk Orchestration (Increment 1 of 4)
**Parent PID:** `docs/pids/M009-AMENDMENT-2026-10-13-CSV-ASSURANCE-READINESS.md`
**Work Order:** `docs/work-orders/WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md` §2
**Implementation branch:** `wo/M009B-increment1-readiness-csv`
**Head SHA (Implementer hand-back, independently re-verified):** `ef01db59006ac2b781b80864653f94765509e758`
**Base:** `3ba07998b3cc2d99bd712f9eca61c36e190de0ed` (canonical main, WO-M009B merge)
**Status:** Delivery Controller independent review **COMPLETE**. Fresh Independent Audit and Architect Acceptance **PENDING** — this document will be updated once both land, per WO §1 ("No increment is dispatched until the prior increment has an accepted, fresh Independent Audit").

## Scope delivered

Per WO §2.1–§2.6: the Security Foundations Assurance Readiness gate (`security_baseline/readiness.py`, `questionnaire/decorators.py`, a `process_view` hook added to the existing `QuestionnaireUploadSizeGuardMiddleware`), and secure CSV V1 ingestion (`questionnaire/csv_import.py`, `declared_format` dispatch in `questionnaire/import_services.py`, the `customer_provided_answer_text` provenance field). No bulk-orchestration code (Increments 3–4) and no Increment 2 scope were touched, consistent with the explicit dispatch authorisation (Increment 1 only).

## Delivery Controller independent review

Every file in the Implementer's diff was read in full and independently assessed against the Work Order's exact text, not taken on the Implementer's own report:

- `security_baseline/readiness.py`, `questionnaire/decorators.py`, `questionnaire/upload_handler.py` (the `process_view` hook), `questionnaire/csv_import.py`, `questionnaire/import_services.py`, `questionnaire/models.py`, `questionnaire/views.py`, `questionnaire/forms.py`, the new migration (`0004_m009b_csv_import.py`), the new templates, `questionnaire/eval/m009b_csv_ingestion_corpus.py`, `questionnaire/tests/conftest.py`, `.github/workflows/ci.yml`, and both new test files (`test_m009b_csv_import.py`, `test_m009b_readiness_gate.py`) — all confirmed correct and consistent with the Work Order.
- Every constant/attribute/URL name referenced across files (`QuestionnaireImport.FILE_FORMAT_XLSX/CSV`, `RequirementState.title`, `SecurityFoundationsCompletion.completed_count/total_count`, `organisations:foundations`, `product_name`'s context-processor origin) was independently grepped against the real source, not assumed.
- The membership-before-readiness ordering (WO §2.6/§2.9 binding invariant) and the CSRF-fires-after-readiness ordering (the hook's pipeline position) are both genuinely proven by real HTTP tests exercising the un-stubbed middleware, not merely asserted — `test_membership_before_readiness_non_member_gets_404_never_readiness_response`, `test_hook_fires_before_csrf_process_view` (negative control, `Client(enforce_csrf_checks=True)`) paired with the pre-existing `test_m009a_views.py::test_requires_csrf` (positive control, now exercised under the new autouse ready-by-default fixture). One cosmetic finding: `test_hook_fires_before_csrf_process_view`'s own docstring implies the ready-org/403 comparison lives in the same test function; it actually lives in the other, pre-existing file. The underlying claim is true and proven — this is a documentation-precision note, not a defect, and does not warrant a repair dispatch.

## Credential exposure — disclosed, contained, verified

The Implementer self-disclosed running `docker exec infosecurs-relocation-web-1 env | grep -i customer` against the **persistent** `infosecurs-relocation` deployment, printing the real `CUSTOMER_ZERO_PASSWORD` into its own tool output. Never committed, pushed, or reused elsewhere. Contained by the Delivery Controller:

- New value generated entirely server-side (`secrets.token_urlsafe(24)`), `.env` updated via in-place regex substitution, `web` service recreated, and the real Django user's password hash updated by reading the credential from the container's own environment — at no point was the old or new value printed in any visible tool output.
- Verified via `authenticate()` returning the real user object (`AUTH_RESULT: SUCCESS`).
- No other secret, system, or deployment was touched by this incident or its containment.

## Independent test verification

The Implementer's claimed test counts were not taken on trust. The Delivery Controller independently:

1. Ran `gitleaks detect --source=. -v` — **no leaks found** (182 commits).
2. Ran `pip-audit -r requirements.txt` — **no known vulnerabilities found**.
3. Confirmed `makemigrations --check --dry-run` — no changes detected.
4. Replicated the **exact two real CI jobs** (`.github/workflows/ci.yml`'s `ci/unit` and `ci/integration`), each against a freshly created test database (`--create-db`), matching CI's own job-level Postgres-service isolation exactly:
   - **`ci/unit`** (the curated list including `questionnaire/tests/test_m009b_csv_import.py`): **534 passed, 0 failed.**
   - **`ci/integration`** (the curated list including `questionnaire/tests/test_m009b_readiness_gate.py` and the full, unmodified `test_m009a_browser_acceptance.py`): **1194 passed, 7 skipped, 1 xfailed, 0 failed.**

   Both fresh-DB runs are clean. This directly confirms the Work Order's binding requirement that "the existing M009A XLSX test suite reruns unmodified and green" and that CI would pass on this branch.

### Disclosed methodological finding (non-blocking, does not affect CI or this increment's acceptance)

A separate, undifferentiated `pytest -q` invocation across the **entire repository with no file arguments** — not how CI runs, not a Work Order acceptance criterion, but a natural thing a future engineer might try locally — surfaced 2 failures (`questionnaire/tests/test_services.py`) and 1 setup error (`test_m009b_csv_import.py`'s second parametrize case), all order-dependent (each passes cleanly in isolation). Root cause: this repository's root `conftest.py` already documents a known, pre-existing class of hazard (`_wi6_ensure_entitlements_seed_data`'s own docstring: data-migration-seeded rows are not reliably restored after a `transaction=True` test flushes the database in an undifferentiated single session). Independently confirmed via a from-scratch rebuild of the pre-Increment-1 main commit (`3ba07998b`) under identical conditions: that commit is clean (2343 passed, 0 failed) under the same bare `pytest -q` invocation — so this hazard is not newly *created* by this increment's code, but the new CSV test file's alphabetical collection position now happens to newly fall within its blast radius in that one, non-CI invocation shape. Recorded here for transparency; does not block this increment, since it does not occur in either real CI job or any supported verification path.

## Independently reviewed, confirmed correct — no defects found in the Implementer's application code

No logic, security, or architectural defect was found in the Increment 1 diff itself. All design decisions beyond the Work Order's literal text (the exact-blockers-tuple readiness design, the anonymous-user pass-through, the CSV-specific `source_label` fix, the autouse-fixture test-infrastructure pattern) were independently cross-checked against the real codebase and found sound.

## Remaining governance steps (not yet performed)

- Fresh Independent Audit (new `Agent` dispatch, no inherited context) against this exact head SHA, including its own real-browser Customer Zero verification per WO §2.11/§2.8.
- PR opening (Delivery Controller's responsibility, not the Implementer's).
- Architect Acceptance and merge.
- Increments 2–4 remain explicitly not dispatched, pending this sequence.
