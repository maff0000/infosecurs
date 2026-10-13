# Work Order: M009B — Foundations Readiness, Secure CSV Ingestion and Bulk Grounded-Response Orchestration

**Status:** DRAFT — submitted for Central Architecture review. Documentation and implementation-planning only. No FORGE dispatch authorised by this document.
**Baseline:** `83d14c6886c453c8a942213f3639f2a9837c65ea` (canonical main, post-amendment-merge).
**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`, as amended by `docs/pids/M009-AMENDMENT-2026-10-13-CSV-ASSURANCE-READINESS.md` (ARCHITECT ACCEPTED, merged PR #105).
**Truth-engine PID:** `docs/pids/M005-QUESTIONNAIRE-ASSURANCE.md`.
**Predecessor:** M009A (`docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md`), CLOSED GREEN, `docs/evidence/M009A-CLOSURE.md`.
**Superseded reference, historical only:** PR #104 (closed, not merged, branch `docs/wo-m009b-draft` preserved). Its assumptions are **not** authority — this Work Order is written fresh against the accepted amendment, not as a revision of that draft.

## 0. What this Work Order implements

The accepted amendment (hereafter "the amendment") established: a deterministic, 100%-threshold Foundations Assurance Readiness gate enforced at the correct point in the request pipeline; a separate question-level answerability signal; a hardened CSV V1 contract; a genuinely atomic bulk-processing claim-and-persist mechanism requiring one narrowly scoped M005 extract-method refactor; and a machine-composition answer-quality contract with explicit, non-human-attributed audit provenance. This Work Order turns that architecture into four bounded, independently testable, sequentially-dispatched implementation increments.

**M005 remains the sole questionnaire truth engine throughout.** No increment in this Work Order alters `questionnaire.grounding`, `questionnaire.outcome`, the AI orchestration modules, or the `QuestionnaireQuestion`/`QuestionnaireResponse` schema, except the one named, bounded, behaviour-preserving refactor in Increment 2.

## 1. Shared conventions, binding across all four increments

- **Tenant scoping:** every new query is scoped by an explicit `organisation=` filter or a traversal through an already-validated `organisation`/`import_record` — the `get_member_organisation_or_404` idiom, reused verbatim, never re-derived.
- **Engineering notes:** per the amendment's §11 standing requirement, every increment's Implementer dispatch and Independent Audit produces a durable GitHub engineering-note PR comment (architecture/baseline SHA; scope/exclusions/ownership; exact modules/interfaces; decisions/trade-offs; acceptance tests/evidence; independent audit findings; STOP conditions and resolutions; CI/security conclusions; Architect Acceptance/closure evidence), in addition to the durable evidence document named per increment below.
- **STOP/escalation convention:** every increment's Implementer stops and returns to the Delivery Controller — never improvises past — any condition listed in that increment's own STOP section, or any of the global STOP conditions in §10.
- **No increment is dispatched until the prior increment has an accepted, fresh Independent Audit.** This is a hard sequencing rule, not a suggestion — Increment 2 does not start until Increment 1 is audited GREEN; Increment 3 does not start until Increment 2 is audited GREEN; Increment 4 does not start until Increment 3 is audited GREEN.
- **Customer Zero only, never a reset.** Every increment's live/browser verification uses the existing synthetic Customer Zero organisation (`customerzero`/"Infosecurs Limited"), real authenticated login, never a hostile/malware fixture against a persistent deployment, and never triggers a Customer Zero reset.

## 2. Increment 1 — Foundations readiness and CSV ingestion

### 2.1 Scope

Implement the Assurance Readiness Gate (amendment §3) and the CSV V1 import contract (amendment §4.1) only. **No answer generation, no export, no bulk orchestration in this increment** — a CSV import that passes the security gate reaches the identical extraction-only end-state M009A's XLSX path already reaches (real `QuestionnaireQuestion` rows created for `disposition="question"` candidates, nothing answered).

### 2.2 Exact modules/files and interfaces

| File | Nature | Content |
|---|---|---|
| `security_baseline/readiness.py` | New | `evaluate_assurance_readiness(organisation) -> AssuranceReadinessResult` (amendment §3.1), built on the unmodified `entitlements.metrics.get_security_foundations_completion`, threshold fixed at 100% (amendment §3.2). |
| `questionnaire/upload_handler.py` | Modified (extend, not duplicate) | `QuestionnaireUploadSizeGuardMiddleware` gains a `process_view` hook (amendment §3.3) checking readiness for views explicitly marked via a new small decorator, e.g. `@requires_assurance_readiness`, before `CsrfViewMiddleware.process_view` ever runs. |
| `questionnaire/decorators.py` | New, small | `requires_assurance_readiness` — marks a view function with an attribute the middleware hook checks; mirrors `entitlements.decorators.require_capability`'s own "only acts on marked, organisation-scoped routes" discipline. |
| `questionnaire/csv_import.py` | New, mirrors `xlsx_extraction.py`'s shape | CSV parsing (stdlib `csv` module only, frozen comma/RFC4180 quoting), header validation (`question` required; `reference`/`answer` optional), blank-row/duplicate-identifier rejection, bounded limits (amendment §4.1). |
| `questionnaire/import_services.py` | Modified, additive | `ingest_questionnaire_import` gains CSV as a second accepted `file_format` alongside XLSX — dispatches to `csv_import` vs `xlsx_extraction` by detected/declared format, otherwise unchanged. |
| `questionnaire/models.py` | Modified, additive | `QuestionnaireImport.file_format` choices gain `"csv"` alongside the existing `"xlsx"` — one new migration, no field/schema redesign. |
| `questionnaire/views.py` | Modified | `questionnaire_import_upload` gains the `@requires_assurance_readiness` marker; its GET branch renders blockers (amendment §3.3) instead of the upload form when not ready. |

### 2.3 Existing services reused, unmodified

`entitlements.metrics.get_security_foundations_completion`, `entitlements.models.FoundationRequirement`/`ProductArea`, `questionnaire.security_gate.run_container_gate` (CSV still passes through the same bounded structural/scanning gate — "plain text" is not an exemption, amendment §4.1), `questionnaire.scanner`, `questionnaire.import_storage`, the Customer Zero reset manifest (`QuestionnaireImport` is already a direct-FK row there from M009A; CSV imports need no new manifest entry).

### 2.4 New schema/migrations

One migration: `QuestionnaireImport.file_format` choices extended to include `"csv"`. No new model in this increment.

### 2.5 Preconditions and dependency order

None beyond canonical main at this Work Order's baseline. This increment has no dependency on Increments 2-4 and could, in principle, be developed in parallel with them — but per §1's sequencing rule, its Independent Audit must still complete before Increment 2 is *dispatched*, to keep the audit trail linear and reviewable.

### 2.6 FORGE implementation instructions

Build the `process_view` hook first, with a unit test proving it short-circuits *before* `request.POST` is ever touched (assert via a hostile large-body POST to an unready org's upload URL that the server never buffers the full body — this is the amendment §3.3 guarantee, and it is testable). Build CSV parsing second, reusing every bounded-limit numeral M009A's XLSX path already established (10 MiB upload ceiling, etc.) unless this increment's own measurement shows a CSV-specific number is required. Do not touch `questionnaire.catalogue`/`grounding`/`outcome` at all in this increment.

### 2.7 Tests and evaluation fixtures

New `questionnaire/eval/m009b_csv_ingestion_corpus.py` (mirroring `m009a_ingestion_corpus.py`'s shape): valid CSV, missing/duplicate/case-ambiguous `question` header, blank question rows, oversized file, oversized row count, invalid encoding, BOM-prefixed UTF-8, embedded comma/newline/quote in a field, a CSV renamed with a `.csv` extension but containing hostile ZIP bytes (confirm the security gate's real content-sniffing, not filename trust, still applies). New `questionnaire/tests/test_m009b_readiness_gate.py`: zero/partial/100% Foundations completion; a `DERIVED_MILESTONE` resolver returning `False`; the specific pipeline-level test named above; direct-POST-bypass attempt against an unready org (assert rejection before any multipart parsing); tenant isolation (an unready org's blockers never leak another org's Foundations state).

### 2.8 Independent audit acceptance gates

A fresh Independent Auditor confirms, against the real running code: the `process_view` hook genuinely fires before CSRF's own hook (verified by request-level instrumentation, not only unit-test mocking); a 100%-complete Customer Zero can upload a real CSV through the real UI and reach `extraction_failed`/`extracted` correctly; an incomplete Customer Zero cannot reach the upload view by any route tried (GET, direct POST, a manipulated `organisation_id`); the CSV security gate rejects every corpus fixture with a specific, accurate reason; the existing M009A XLSX path is unchanged (zero regression, confirmed by rerunning M009A's own test suite unmodified).

### 2.9 STOP conditions specific to this increment

Any readiness computation not built directly on `get_security_foundations_completion`. Any readiness check implemented only at view level without the pipeline-level hook. Any CSV limit weaker than M009A's own XLSX precedent without a named, evidenced reason. Any change to `questionnaire.catalogue`/`grounding`/`outcome`.

### 2.10 Durable evidence

`docs/evidence/M009B-INCREMENT-1-READINESS-CSV-INGESTION.md`.

### 2.11 Customer Zero / browser verification

Real authenticated login as `customerzero`; one real CSV upload reaching `extracted`; a real-browser check that an org deliberately regressed to `unknown` on one `FoundationRequirement` row (via the existing `security_baseline` test fixtures, not a destructive reset) sees the blocker UI, not the upload form — this regression must itself be reversed (restoring Customer Zero's prior completion state) before the increment's verification session ends, since no Customer Zero reset is authorised to "fix" it afterward.

### 2.12 CI/security/regression requirements

New test files hand-added to `.github/workflows/ci.yml`'s curated lists (this repository's own known, already-disclosed "CI does not auto-discover tests" characteristic). `gitleaks`/`pip-audit` clean. The existing M009A XLSX test suite reruns unmodified and green. All seven standard CI/security checks green before this increment's own PR is eligible for audit.

## 3. Increment 2 — M005 preparation/persistence extraction

### 3.1 Scope

**Exactly** the extract-method refactor specified in the amendment §6.1b, nothing more. `generate_questionnaire_response`'s public signature, docstring-described behaviour, and every observable side effect remain byte-identical.

### 3.2 Exact modules/files and interfaces

`questionnaire/services.py` only. New: `PreparedQuestionnaireResponse` (frozen dataclass, exact field list per amendment §6.1b — `organisation`, `question`, `interpretation`, `interpretation_record`, `outcome`, `outcome_warnings`, `grounding_snapshot`, `draft`, `drafting_record`, `actor`); `prepare_questionnaire_response(organisation, question, *, actor, interpretation_gateway=None, drafting_gateway=None) -> PreparedQuestionnaireResponse`; `persist_prepared_response(prepared: PreparedQuestionnaireResponse) -> QuestionnaireResponse` (renamed from `_persist_response`, identical body, identical `@transaction.atomic` decorator). `generate_questionnaire_response` becomes the two-line composition named in the amendment.

### 3.3 Existing services reused, unmodified

Everything `_persist_response`/`generate_questionnaire_response` already call: `interpret_questionnaire_question`, `build_questionnaire_grounding_snapshot`, `derive_outcome`, `draft_questionnaire_answer`, `record_event`. None of these are touched.

### 3.4 New schema/migrations

None. This is a pure code-structure change.

### 3.5 Preconditions and dependency order

Increment 1's Independent Audit must be GREEN first (§1's sequencing rule). This increment has no functional dependency on Increment 1's own content, but the sequencing rule still applies.

### 3.6 FORGE implementation instructions

Perform the extraction by literal substitution against the real, current `questionnaire/services.py` — re-read the file directly before writing a single line (do not trust this Work Order's own quoted excerpts as a substitute for reading the real, current file, which may have moved on since this Work Order was drafted). Do not rename, reorder, or alter any existing parameter, default, or docstring sentence beyond what the extraction itself mechanically requires. `generate_questionnaire_response`'s docstring is copied verbatim onto itself (unchanged) and a short new docstring is added to each of the two new functions describing only what each one now does.

### 3.7 Tests and evaluation fixtures

No new fixtures. **The acceptance gate is entirely regression-based**: the unchanged M005 14-case golden corpus (`questionnaire/eval/golden_corpus.py`/`harness.py`) passes byte-identically; every existing test file touching `generate_questionnaire_response`, `accept_questionnaire_response`, `edit_questionnaire_response_text`, or `_initial_current_answer_text` passes unmodified. One new, narrow unit test is added confirming `prepare_questionnaire_response` + `persist_prepared_response` called separately produce the exact same `QuestionnaireResponse` fields as `generate_questionnaire_response` called directly, for the same inputs (a differential equivalence test, not a new behaviour test).

### 3.8 Independent audit acceptance gates

A fresh Auditor independently reruns the full M005 golden corpus and every existing M005-adjacent test file against the refactored code and confirms byte-identical results — this audit's entire substance is "prove nothing changed," and it must say so explicitly, not merely report a passing test run.

### 3.9 STOP conditions specific to this increment

Any change to `_persist_response`'s/`generate_questionnaire_response`'s existing logic, field set, ordering, or event behaviour. Any golden-corpus or existing-test diff of any kind, including a seemingly-cosmetic one. Any temptation to "improve" the extracted functions' naming/structure beyond the minimum the extraction requires — this increment is deliberately boring by design.

### 3.10 Durable evidence

`docs/evidence/M009B-INCREMENT-2-M005-PREPARE-PERSIST-EXTRACTION.md`.

### 3.11 Customer Zero / browser verification

One real, authenticated single-question generation through the existing M005 UI flow (`questionnaire_analyse`), confirming the refactored code path produces an identical, correctly-rendered response — this is the simplest possible real-browser proof that the public behaviour is genuinely unchanged.

### 3.12 CI/security/regression requirements

All seven standard checks green. This increment's own CI run is, by design, expected to show zero new test files and zero changed assertions anywhere outside `questionnaire/services.py` and the one new differential-equivalence test.

## 4. Increment 3 — Atomic single-question orchestration

### 4.1 Scope

Implement the claim-and-persist mechanism (amendment §6.1a-c) for exactly one question at a time — the vertical slice. **No batching, no answer-text enrichment in this increment.**

### 4.2 Exact modules/files and interfaces

New `questionnaire/bulk_orchestration.py`: `QuestionnaireBulkResponseAttempt` model (new — `organisation` FK CASCADE, `import_question` FK CASCADE, `attempted_by` FK SET_NULL, `attempted_at`, `outcome` choices `claimed`/`succeeded`/`failed`, `claimed_at`, `claim_expires_at`, `resulting_response` FK SET_NULL, `failure_category`, `failure_detail`; two `UniqueConstraint`s per amendment §6.1c — one partial on `outcome="claimed"`, one partial on `outcome="succeeded"`, both scoped to `import_question`); `claim_next_eligible_question(import_record, *, actor)` (amendment §6.1, corrected per round 4's nested-savepoint fix); `claim_and_process_one_question(import_record, *, actor)` (amendment §6.1c, the full atomic claim-check-and-persist sequence, calling `prepare_questionnaire_response`/`persist_prepared_response` from Increment 2); the eligibility query (amendment §5/§4.1, extended for the CSV `answer`-column read-only-provenance rule from Increment 1).

### 4.3 Existing services reused, unmodified

`prepare_questionnaire_response`/`persist_prepared_response` (Increment 2), `evaluate_assurance_readiness` (Increment 1, rechecked per-question per amendment §3.3/§6.3), `get_member_organisation_or_404`.

### 4.4 New schema/migrations

One new model, two new constraints, one migration. No change to any existing model.

### 4.5 Preconditions and dependency order

Increment 2's Independent Audit GREEN. This increment has a genuine functional dependency on Increment 2 (it calls `prepare_questionnaire_response`/`persist_prepared_response` directly) and a genuine functional dependency on Increment 1 (readiness recheck, and CSV-imported questions as the real input).

### 4.6 FORGE implementation instructions

Build the two `UniqueConstraint`s and prove them with a real concurrent-execution test *before* writing any other logic in this increment — this is the one piece of this entire Work Order where a mistake is a genuine correctness defect, not a style issue, and it should be proven first, in isolation, against a trivial two-row fixture, before the full claim-and-process flow is built around it.

### 4.7 Tests and evaluation fixtures

Per amendment §6.2 point 7 and §6.2a: (a) two genuinely concurrent callers racing for the same question (real threads/processes, or Postgres-level `SELECT FOR UPDATE` contention realistically simulated — not merely sequential calls dressed up as concurrent) — assert exactly one `QuestionnaireResponse` exists afterward, queried at the database level; (b) a claim artificially expired mid-AI-call via test instrumentation (monkeypatch `claim_expires_at` backward, or inject a delay), followed by a reclaim and a second concurrent finaliser — same assertion; (c) a simulated crash between claiming and the AI calls completing (raise inside the test harness before `claim_and_process_one_question` reaches its atomic block) — assert the claim expires and is cleanly reclaimed with zero `QuestionnaireResponse` created in the interim; (d) tenant isolation specifically against this new code path; (e) accepted-response immutability — a question already manually answered and accepted is never selected, and its response is byte-identical before/after a bulk run touches its import.

### 4.8 Independent audit acceptance gates

A fresh Auditor reproduces the concurrency race itself, independently (not merely re-running the Implementer's own test file) — at minimum reproducing scenario (a) and (b) above against the real running code, and confirming via direct SQL that the two `UniqueConstraint`s exist exactly as specified and are the actual mechanism preventing the duplicate, not an application-level check that happens to not be exercised by the test.

### 4.9 STOP conditions specific to this increment

Any version of the claim/fencing design that creates and commits a `QuestionnaireResponse` before the ownership check (amendment §9's standing STOP condition). Any `IntegrityError` handling inside the same `atomic()` block that raised it. Any concurrency "proof" that is only a sequential test dressed up as concurrent — if the Implementer cannot construct a genuinely concurrent reproduction, that is itself a STOP, not a reason to accept a weaker test.

### 4.10 Durable evidence

`docs/evidence/M009B-INCREMENT-3-ATOMIC-CLAIM-ORCHESTRATION.md`, including the measured-latency task below.

### 4.10a Required measurement task — do not guess, per the Architect's explicit instruction

**The only genuinely measured runtime constant available at this Work Order's drafting time is `ai_platform.gateway.DEFAULT_TIMEOUT_SECONDS = 30.0`** (confirmed by direct reading). **No empirical latency distribution for the real, currently-configured AI gateway has been measured in this architecture pass**, and this Work Order does not invent one. Separately, both `docker-compose.yml` and `docker-compose.release.yml` run `python manage.py runserver` as the application server in every topology this project has today — **there is no gunicorn/uwsgi worker timeout or reverse-proxy timeout configured anywhere in this codebase**, confirmed by reading the `Dockerfile` and both Compose files directly. This is this project's own already-documented Beta-stage characteristic (`docs/delivery/BUILD-REPRODUCIBILITY.md`'s own M006 PID §12 finding about `runserver` in this deployment), not a new discovery this Work Order treats as a defect to fix.

**Consequence:** there is no hard, server-enforced request-timeout number to derive a batch size from. The real governing constraint is **human UX tolerance for a synchronous, explicit "process" action with a visible result**, not a server cutoff. This Work Order therefore requires, as a named FORGE task **before** Increment 3's own numbers are finalised for anything beyond the conservative defaults below:

1. Measure real interpret+draft latency (p50/p95/p99) against the actual configured AI gateway, inside a disposable stack, for a representative sample of real or realistic questions — recorded with real numbers, in the durable evidence document, not estimated.
2. Using that measurement plus the known `DEFAULT_TIMEOUT_SECONDS=30.0` worst-case bound (up to 2 calls × up to 2 attempts each = 4 × 30s = 120s absolute worst case per question), propose `CLAIM_TTL` as the worst-case bound plus a margin (conservative starting default: **180 seconds**, pending the measurement confirming or revising this) and a UX-driven `DEFAULT_BULK_BATCH_SIZE` for Increment 4 based on the *measured typical* latency, not the worst case (conservative starting default for Increment 3 itself, which only ever processes one question per call: **batch size is not applicable — Increment 3 is inherently single-question**).
3. Submit this measurement and the resulting proposed numbers for Architect acceptance **before** Increment 4 is dispatched — Increment 4's own batch size is explicitly not decided by this Work Order, only bounded by the method above.

### 4.11 Customer Zero / browser verification

One real, authenticated, single-question bulk-claim-and-process action through a minimal new UI control on the import-detail page (a "Process next question" button, reusing M009A's own page, not a new one), confirmed end-to-end: claim created, AI calls genuinely made, response persisted, claim finalised, page reflects the new state on reload.

### 4.12 CI/security/regression requirements

All seven standard checks green. The concurrency tests must run in CI, not only locally — if CI's own database configuration cannot genuinely exercise `SELECT FOR UPDATE` contention (e.g. a test-runner that serialises all tests against one connection), this is itself a STOP condition requiring the Delivery Controller's attention before the increment can be called audited, not a reason to accept a weaker in-process test as sufficient.

## 5. Increment 4 — Bounded bulk processing and answer composition

### 5.1 Scope

Extend Increment 3's proven single-question lifecycle to a bounded batch (`claim_and_process_one_question` called up to `DEFAULT_BULK_BATCH_SIZE` times per request, per amendment §6), add the question-level answerability signal (amendment §3.5), and add the machine-composed answer-quality enrichment for `SUPPORTED`/`CONFIRM` (amendment §5, corrected for audit provenance).

### 5.2 Exact modules/files and interfaces

`questionnaire/bulk_orchestration.py`, extended: `process_next_bulk_batch(import_record, *, actor, batch_size=DEFAULT_BULK_BATCH_SIZE)`; `assess_answerability(interpretation, grounding_snapshot) -> Answerability` (amendment §3.5); `compose_detailed_safe_answer_text(response) -> Optional[str]` (amendment §5); `_apply_machine_composed_answer_text(response, composed_text, *, attempt)` — M009B's own direct write path, never via `edit_questionnaire_response_text`. `QuestionnaireBulkResponseAttempt` gains `answer_composition_method` (choices `ai_draft_passthrough`/`application_fixed_text`/`application_composed_from_grounding`) — one additive migration. A new `ActivityEvent.event_type` choice (e.g. `questionnaire_response_machine_composed`) — one additive migration, following the repository's own precedented pattern (migrations `0002`-`0006` each added a choice the same way). `questionnaire/templates/questionnaire/import_detail.html` gains a progress summary and a "Process next batch" button (extends the existing M009A page, no new page). `questionnaire/csv_export.py` is **not** built in this increment (that is M009D) — Increment 4 produces reviewable draft responses only, per the amendment's own explicit exclusion.

### 5.3 Existing services reused, unmodified

Everything from Increments 1-3, plus `questionnaire.grounding`'s actual returned fact fields (`assurance_label`, `answer_updated_at`, evidence counts, `relevant_remediation`, policy `section_content`) read directly from the already-persisted `grounding_snapshot` — zero new grounding resolver.

### 5.4 New schema/migrations

Two additive migrations: `answer_composition_method` on `QuestionnaireBulkResponseAttempt`; the new `ActivityEvent.event_type` choice.

### 5.5 Preconditions and dependency order

Increment 3's Independent Audit GREEN, and the measurement task (§4.10a) delivered with real numbers, Architect-accepted, before `DEFAULT_BULK_BATCH_SIZE` is finalised for this increment's own implementation.

### 5.6 FORGE implementation instructions

Build `assess_answerability` and the batch loop first (pure extensions of already-proven Increment 3 code), prove them, **then** build the answer-composition enrichment as a separate, later sub-step — the amendment's own STOP condition (any version reading `draft.answer_text` for SUPPORTED/CONFIRM) applies with full force here, and keeping these two pieces of work temporally separate makes that easier to verify independently rather than reviewing one large diff.

### 5.7 Tests and evaluation fixtures

New `questionnaire/eval/m009b_answer_composition_corpus.py` per amendment §5's adversarial requirements: differential fact-containment test (every composed fact token traces to the real `grounding_snapshot`), non-omission-of-adverse-facts test (`stale_evidence_count > 0`/`active_contradicting_evidence_count > 0` must be disclosed, not quietly dropped), maximal `relevant_remediation` length, every optional field absent, a mixed-key question, and a mechanical proof the composed text never contains any substring of `draft.answer_text`. This corpus is additive to, and never merges with, the unchanged M005 14-case golden corpus. Plus: batch-size/progress tests (a batch stopping cleanly when nothing remains eligible; a batch correctly reporting per-question outcomes including `NOT_ANSWERABLE_FROM_AVAILABLE_FACTS` as its own category, never collapsed into `CONFIRM`); the `answer_composition_method` field correctly reflects which path each response actually took; the new activity event fires with the correct, non-human actor and never via `edit_questionnaire_response_text`.

### 5.8 Independent audit acceptance gates

A fresh Auditor independently verifies: the batch loop genuinely re-derives eligibility and readiness on every single question, not once per batch; the answerability signal is reported accurately against a representative set of real catalogue-coverage gaps; the composed answer text for a real `SUPPORTED` and a real `CONFIRM` fixture is independently traced, fact-by-fact, against the real `grounding_snapshot`, with zero AI-token leakage; the new activity event is genuinely distinct from, and never routed through, the human-edit event path.

### 5.9 STOP conditions specific to this increment

Any composed answer applied via `edit_questionnaire_response_text`. Any composition that omits a disclosed adverse fact. Any batch size chosen without §4.10a's measurement having been delivered and accepted. Any export capability or `send_ready` claim introduced in this increment (both are M009D's, not this Work Order's).

### 5.10 Durable evidence

`docs/evidence/M009B-INCREMENT-4-BULK-ORCHESTRATION-ANSWER-COMPOSITION.md`.

### 5.11 Customer Zero / browser verification

A real, authenticated batch run against synthetic Customer Zero's own CSV-imported questions (from Increment 1's real import), at 1280/768/375px, confirming the progress summary, the "Process next batch" button, and at least one genuinely enriched `SUPPORTED`/`CONFIRM` answer render correctly and legibly, with no horizontal overflow at 375px.

### 5.12 CI/security/regression requirements

All seven standard checks green. The unchanged M005 14-case golden corpus reconfirmed green one final time at this Work Order's close, alongside the new, independent M009B answer-composition corpus — explicitly never merged into the golden corpus.

## 6. Outstanding Product Authority / Architect decisions

Carried forward from the amendment §8, not resolved by this Work Order:
1. Whether the amendment §5 grounding-fact-based composition design (now Increment 4) is finally approved as implemented, pending the Independent Audit's fact-by-fact trace.
2. `CLAIM_TTL`/`DEFAULT_BULK_BATCH_SIZE`/daily AI-invocation ceiling — explicitly not set by this Work Order; §4.10a's measurement task produces the evidence this decision will be made from, submitted for Architect acceptance before Increment 4 is dispatched.

## 7. Delivery sequence

1. Architect reviews and corrects this Work Order (mirrors the amendment's own review cycle — expect correction rounds).
2. Architect Acceptance recorded durably in this document.
3. Delivery Controller dispatches an Implementer for Increment 1 only.
4. Fresh Independent Audit of Increment 1.
5. Implementer for Increment 2, building only on an audited Increment 1.
6. Fresh Independent Audit of Increment 2 (regression-only in substance).
7. Implementer for Increment 3, building on audited Increments 1-2.
8. Fresh Independent Audit of Increment 3, including independent reproduction of the concurrency race.
9. §4.10a's measurement task delivered and submitted for Architect acceptance.
10. Implementer for Increment 4, building on audited Increments 1-3 and the accepted measurement/numbers.
11. Fresh Independent Audit of Increment 4.
12. Consolidated PR, Architect Acceptance, merge, closure — following the exact M009A/amendment governance pattern throughout, including durable engineering notes at every step.

**No Implementer dispatch of any kind, for any increment, until this Work Order itself receives Architect Acceptance.**

## 8. Global STOP conditions

- Any need to modify `questionnaire.grounding`, `questionnaire.outcome`, the AI orchestration modules, their prompt templates, or the `QuestionnaireQuestion`/`QuestionnaireResponse` schema, beyond Increment 2's one named, bounded exception.
- Any background worker, task queue, or process outside the normal HTTP request/response cycle.
- Any readiness computation not built on `get_security_foundations_completion`.
- Any concurrency design committing a response before the ownership check, or any `IntegrityError` caught inside the block that raised it.
- Any composed answer text applied via the human-edit API, or any version reading `draft.answer_text` for SUPPORTED/CONFIRM.
- Any export, send-ready claim, or M009C/D scope migrating into this Work Order.
- Any batch-size/TTL/ceiling number adopted without §4.10a's measurement.
- Any production deployment, DARWIN change, or Customer Zero reset.
