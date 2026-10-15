# M009B Increment 1 — Foundations Assurance Readiness Gate + Secure CSV Ingestion

**Milestone:** M009B — Foundations Assurance Readiness + CSV + Bulk Orchestration (Increment 1 of 4)
**Parent PID:** `docs/pids/M009-AMENDMENT-2026-10-13-CSV-ASSURANCE-READINESS.md`
**Work Order:** `docs/work-orders/WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md` §2
**Implementation branch:** `wo/M009B-increment1-readiness-csv`
**Head SHA (post second repair, independently re-verified):** `060e2cd0689d0c08ca7e6b8134ff2a84edd7385a`
**Base:** `3ba07998b3cc2d99bd712f9eca61c36e190de0ed` (canonical main, WO-M009B merge)
**Status:** Delivery Controller independent review complete across two full repair cycles. A **third** fresh Independent Audit against this head, focused on the newly-fixed CSV-contract defects plus broader Increment 1 regression coverage, is now required before Architect Acceptance.

## History to date

1. **Original implementation** (`ef01db5`): CSV ingestion, extraction, readiness gate, membership-ordering — independently reviewed by the Delivery Controller, no defects found.
2. **Fresh Independent Audit #1 → RED**: WO §2.6 entitlement-ordering defect (the readiness-gate hook never checked entitlement). Confirmed directly by the Delivery Controller against the code.
3. **Repair #1** (`0a261d0`): `entitlements.decorators.enforce_capability_gate` extracted and called in the hook between membership and readiness. Independently re-verified by the Delivery Controller (diff read directly, both real CI jobs rerun on fresh databases, one additional benign side-effect identified and analysed).
4. **Fresh Independent Audit #2 → GREEN**, re-deriving everything from scratch. Delivery Controller spot-checked two of its claims directly before accepting.
5. **Evidence doc updated** (`8365fdf`) to record the above.
6. **Central Architecture's own independent source review** identified four further CSV-contract defects (B1–B4) missed by both audit cycles — all four independently confirmed by the Delivery Controller by direct reading of `questionnaire/csv_import.py` before any repair was dispatched, and B4 traced to its authoritative source (the amendment PID's "Resource limits, frozen" section, which requires a bounded *aggregate* total-text length that did not exist anywhere in either the CSV or XLSX path):
   - **B1**: two-or-more columns matching the answer or reference header vocabulary were silently treated as "column absent" rather than rejected, discarding a genuine customer-supplied answer/reference with no named rejection.
   - **B2**: a CSV with a valid header but zero data rows was silently accepted (`accepted=True`), with no named rejection for this case.
   - **B3**: a blank-question row vanished entirely from import provenance (bare `continue`, no `Candidate` created), taking any answer/reference data that row carried with it.
   - **B4**: the per-field length bound covered only the question-text column, not answer/reference; and no aggregate total-extracted-text bound existed anywhere in the codebase for either CSV or XLSX.
7. **Repair #2** (`060e2cd`): all four fixed in `questionnaire/csv_import.py`, with a new `excluded_blank_question` disposition (additive `models.py` choice + no-op migration `0005`, confirmed via `sqlmigrate`), a new `MAX_CSV_AGGREGATE_TEXT_LENGTH = 5_000_000` (derivation documented in-code: a naive candidates×cell-length formula was computed and rejected as exceeding the 10 MiB upload ceiling and therefore permanently unreachable; the chosen value is roughly half the upload-byte ceiling, reachable and independently enforced), and new hostile/legitimate fixtures + tests for each defect, each demonstrated failing against the pre-repair head before the fix, per Central Architecture's required methodology.

## Delivery Controller independent re-verification of Repair #2

Not taken on the repair report's word. Read the full diff of `060e2cd` directly:
- Confirmed B1's fix mirrors the existing `ambiguous_question_column` mechanism exactly, in `_resolve_header`, covering both `validate_csv_structure` and `extract_candidates` (both call it fresh).
- Confirmed B2's fix via a new shared `_require_data_rows` helper, called from both functions immediately after header resolution.
- Confirmed B3's fix correctly falls through to a new `"excluded_blank_question"` disposition only when no per-field oversize check fires first (oversized-field checks take documented priority — traced through the if/elif chain directly, confirmed this does not silently drop or corrupt either guarantee: the row is never lost, and oversized text is never persisted unbounded regardless of which check fires), and that this disposition is categorically excluded from AI-generation eligibility by construction (never `"question"`).
- Confirmed B4's per-field checks correctly exclude an oversized answer from ever reaching the `customer_provided_answer_text` assignment (verified the conditional guards `disposition in ("question", "excluded_blank_question")`, which an `"excluded_other"` disposition never satisfies), and confirmed the aggregate counter accumulates from the same bounded, truncated storage copies (never an unbounded value), checked after every row (fail-fast, not only at the end).
- Noted one minor, non-blocking documentation staleness: `models.py`'s new comment states the choices-list change "does not require a schema migration," which is true at the SQL level (confirmed no-op via `sqlmigrate`) but a migration file was in fact still required and added, since Django's `makemigrations --check` tracks model state independently of generated SQL. Cosmetic only — no functional impact.
- Independently reran both real CI jobs against **fresh test databases** (not trusting the repair's self-reported numbers): `ci/unit` + `entitlements/tests/` together — **851 passed, 0 failed** (549 + 302, exact match). `ci/integration` — **1199 passed, 7 skipped, 1 xfailed, 0 failed** (exact match). Reran `gitleaks detect` on the final commit — no leaks found (186 commits).

## Credential exposure — a second, self-caused incident, disclosed and contained

While investigating Central Architecture's request to confirm no remaining credential exposure, the Delivery Controller itself ran `docker inspect <container> --format "{{json .Config.Env}}"` against the persistent `infosecurs-relocation` deployment — the exact pattern this project's own standing rule prohibits — printing the real, then-current `CUSTOMER_ZERO_PASSWORD` into its own tool output. Self-disclosed immediately. Contained identically to the first incident: a new value generated and applied entirely server-side (never printed), verified via `authenticate()` returning success. The leaked value is now dead. `gitleaks` confirms no trace in git history; `docker compose logs web` on the persistent deployment confirms no trace there either (container logs capture only PID 1 output, never `docker exec`/`docker inspect` output, so the original, first incident never reached there either).

## Remaining governance steps (not yet performed)

- A **third** fresh Independent Audit (new dispatch, no inherited context), focused specifically on the B1–B4 fixes, plus a full re-check of everything the first two audits covered (entitlement ordering, membership ordering, CSV dispatch, Customer Zero/browser verification) against this head.
- PR update/re-flagging for re-review (Delivery Controller's responsibility).
- Architect Acceptance and merge.
- Increments 2–4 remain explicitly not dispatched, pending this sequence.
