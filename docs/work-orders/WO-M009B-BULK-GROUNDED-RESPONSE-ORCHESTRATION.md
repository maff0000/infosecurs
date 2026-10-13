# Work Order: M009B — Bulk Grounded-Answer Orchestration

**Status:** DRAFT — awaiting Architect review.
**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Predecessor:** M009A (`docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md`, CLOSED GREEN, `docs/evidence/M009A-CLOSURE.md`), merged at `ad996bfa4527623d095862199b46db6e0ea94fd0`.
**Baseline this Work Order is written against:** `23fcd6ea21173bb50b4185611c509bad4aacdcfa`.

## 0. Purpose

M009A ingests an XLSX questionnaire, runs it through a security gate and malware scan, and extracts each real question into a genuine, persisted `QuestionnaireQuestion` row (via `QuestionnaireImportQuestion.question`), with full source provenance. It never generates an answer.

M009B's job is narrow: **for the questions M009A has already linked, run them through the existing, completely unmodified M005 truth engine, in bulk, and persist the resulting `QuestionnaireResponse` rows** — with per-question progress, failure isolation, idempotent retry, tenant scoping, and bounded AI-cost/time, entirely synchronously (no background worker, no task queue — this repository has none today and M009A's own Work Order established "stop rather than reach for async infrastructure" as binding precedent, which this Work Order inherits unchanged).

## 1. A premise correction, established by direct code inspection before drafting

The parent authorisation asked this Work Order to specify "deterministic linkage between `QuestionnaireImportQuestion` and the existing M005 question/response lifecycle." **That linkage already exists and is already built, by M009A, today.**

Reading `questionnaire/import_services.py`'s extraction path directly: every `QuestionnaireImportQuestion` with `disposition="question"` already gets a real, persisted `QuestionnaireQuestion` row created synchronously at extraction time (`organisation=organisation, question_text=candidate.raw_extracted_text, source_label=f"{original_filename} - {sheet_name} {question_cell}"[:255], created_by=actor`), and `QuestionnaireImportQuestion.question` is set to it in the same atomic block. Only non-question dispositions (`heading`/`instructional_text`/`excluded_duplicate`/`excluded_ambiguous`/`excluded_other`) are left with `question=NULL`.

**Consequence for this Work Order's scope:** M009B adds no new linkage field, no new FK, no new migration touching `QuestionnaireImportQuestion` or `QuestionnaireQuestion`. Its job is to orchestrate `questionnaire.services.generate_questionnaire_response`-equivalent processing against the `QuestionnaireQuestion` rows M009A already created, at bulk scale, with the tracking M005 itself does not provide (see §3).

## 2. Scope

**In scope:**
- A bounded, synchronous, per-request batch orchestration service that, for one `QuestionnaireImport`, finds its still-unanswered linked questions and runs each through the unmodified M005 pipeline, one at a time, each in its own transaction.
- A new, minimal tracking model recording the outcome of every bulk-processing *attempt* (success or failure) — see §3 for why this is the one genuinely new piece of state.
- Tenant-scoped, entitlement-gated trigger surface: extending the existing M009A import-detail page (`questionnaire/templates/questionnaire/import_detail.html`) with a "Process next batch" action and a live progress summary — not a new page, not a new product area.
- A per-batch size cap and a per-organisation AI-invocation ceiling check, both reusing existing data (`AIInvocationRecord`), as the AI-cost/time boundary.
- A dedicated M009B evaluation corpus and test suite, wired into CI the same way M009A's was.

**Explicitly out of scope (per the Architect's authorisation, restated so no Implementer re-derives a looser boundary):**
- No redesign of `questionnaire.grounding`, `questionnaire.outcome`, the interpretation/drafting AI orchestration modules, or the `QuestionnaireQuestion`/`QuestionnaireResponse` schema. M009B calls these exactly as `questionnaire.services.generate_questionnaire_response` already does today for a single manually-entered question — it must not special-case "imported" questions in the AI-facing contract at all.
- No M009C (exception review/UX for GAP/CONFIRM outcomes).
- No M009D (export/write-back).
- No DOCX/PDF/OCR.
- No production deployment of this Work Order's own work (standard WO-to-merge flow only).
- No DARWIN changes.
- No background worker, task queue, or cron-driven processing of any kind.
- No re-upload/supersession UI (unrelated to this Work Order, restated only to confirm it is not being smuggled back in).

## 3. The one new model: `QuestionnaireBulkResponseAttempt`

**Why a new model is necessary, not merely convenient:** `questionnaire.services.generate_questionnaire_response` already documents its own deliberate behaviour — if interpretation or drafting fails, **no `QuestionnaireResponse` row is created at all**. That is correct for M005's existing single-question UX (the Account Holder sees an inline error and can just click again), but it means a failed AI attempt leaves **zero persisted trace**. For bulk orchestration, requirement 9 ("explicit treatment of unsupported, ambiguous and failed questions without silently dropping any") cannot be satisfied by anything derived from `QuestionnaireResponse` alone — there is nothing there to derive from on failure. A minimal, explicit attempt-ledger is the smallest addition that satisfies this without touching M005's own models or behaviour.

```python
class QuestionnaireBulkResponseAttempt(models.Model):
    OUTCOME_SUCCEEDED = "succeeded"
    OUTCOME_FAILED = "failed"
    OUTCOME_CHOICES = [(OUTCOME_SUCCEEDED, "Succeeded"), (OUTCOME_FAILED, "Failed")]

    FAILURE_INTERPRETATION = "interpretation_failed"
    FAILURE_DRAFTING = "drafting_failed"
    FAILURE_CATEGORY_CHOICES = [
        (FAILURE_INTERPRETATION, "Interpretation failed"),
        (FAILURE_DRAFTING, "Drafting failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Explicit, not only traversed through import_question, so every
    # tenant-scoped query on this model can filter directly - the same
    # idiom every other bulk-row-touching service in this codebase
    # already uses (organisations/reset_service.py, questionnaire/grounding.py).
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="+")
    import_question = models.ForeignKey(
        QuestionnaireImportQuestion, on_delete=models.CASCADE, related_name="bulk_attempts"
    )
    attempted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    attempted_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES)
    # Set only when outcome == succeeded. SET_NULL (never CASCADE) so a
    # later, unrelated deletion of the response (there is no such path
    # today, but SET_NULL is the frozen WO-M009A/M005 convention for
    # every "points at a result that might independently disappear"
    # FK in this codebase) cannot take this historical attempt record
    # down with it.
    resulting_response = models.ForeignKey(
        QuestionnaireResponse, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    failure_category = models.CharField(max_length=32, choices=FAILURE_CATEGORY_CHOICES, blank=True)
    failure_detail = models.TextField(max_length=2000, blank=True)  # bounded - never an unbounded traceback dump
```

**Frozen invariants** (enforced in `save()`, mirroring `QuestionnaireImport`'s own `IMPORT_ALLOWED_STATE_COMBINATIONS` pattern):
- `outcome == succeeded` ⟺ `resulting_response is not None` and `failure_category == "" and failure_detail == ""`.
- `outcome == failed` ⟺ `resulting_response is None` and `failure_category != ""`.
- Rows are **never updated after creation** — a retry creates a **new** attempt row, never mutates an old one. This row is a ledger entry, not a status field; `QuestionnaireImportQuestion`'s own current eligibility (§5) is always derived by querying this ledger's *latest* row per question, never by denormalising a "current state" onto the question itself. (Precedent: this mirrors `QuestionnaireResponse`'s own accepted/superseded history — the old row is never deleted or silently overwritten, a new row records the new state.)

No migration touches `QuestionnaireImportQuestion`, `QuestionnaireQuestion`, or `QuestionnaireResponse`.

## 4. Orchestration service — vertical slice first, per the Architect's required delivery strategy

### Increment 1 — exactly one question, end to end (the actual proof of the architecture)

```python
def process_next_bulk_question(import_record, *, actor) -> QuestionnaireBulkResponseAttempt | None:
    """
    Finds exactly ONE eligible QuestionnaireImportQuestion for
    import_record (see §5 for "eligible"), runs it through the
    unmodified M005 pipeline, and records exactly one new
    QuestionnaireBulkResponseAttempt. Returns None if nothing is
    eligible (the caller's signal that this import is fully processed).

    Tenant scope is the caller's responsibility, exactly like every
    other M009A service function - this function trusts import_record
    and organisation have already been resolved via
    get_member_organisation_or_404, it does not re-derive them.

    Deliberately ONE question per call, not a loop - this is the
    bounded vertical slice the Architect's delivery strategy requires
    before Increment 2 adds real batching. Every later increment's
    batch loop is this same function called N times, never a new
    code path.
    """
```

Internally: select the next eligible `QuestionnaireImportQuestion` (deterministic ordering — `extraction_order`, so repeated calls are a predictable, reviewable sweep, not an arbitrary one); call `questionnaire.services.generate_questionnaire_response(organisation, import_question.question, actor=actor)` **completely unchanged** — no new parameter, no new code path inside M005 at all; on success, create a `QuestionnaireBulkResponseAttempt(outcome=succeeded, resulting_response=<the new response>)`; on `QuestionnaireInterpretationFailed`/the drafting equivalent, create a `QuestionnaireBulkResponseAttempt(outcome=failed, failure_category=..., failure_detail=str(exc)[:2000])` — never let the exception propagate past this function (failure isolation starts here, at the single-question level, before any batch loop exists at all).

**Increment 1's acceptance criterion is literally the PID's own vertical slice**: imported question → existing M005 engine → grounded draft response → durable linkage, proven by one real end-to-end test and one real-browser click of a single "Process next question" button on the import-detail page.

### Increment 2 — bounded batch, progress, restart-safety

```python
def process_next_bulk_batch(import_record, *, actor, batch_size=DEFAULT_BULK_BATCH_SIZE) -> BulkBatchResult:
    """
    Calls process_next_bulk_question up to batch_size times, stopping
    early the moment it returns None. Each call is independently
    atomic (inherited from generate_questionnaire_response's own
    @transaction.atomic persist step plus this WO's own attempt-record
    write, itself atomic) - there is no batch-spanning transaction, so
    one question's failure can never roll back a sibling's success.
    This is restart-safety's entire mechanism: a crash between calls
    N and N+1 loses nothing already committed, and the next invocation
    (another HTTP request, another button click, another management-
    command run) simply resumes at whatever is still eligible.
    """
```

`DEFAULT_BULK_BATCH_SIZE` is a frozen constant, justified by the AI-cost/time arithmetic in §6 — never left to request input unbounded.

The import-detail page gains: a progress line (`X answered, Y pending, Z failed — see below` derived live from `QuestionnaireBulkResponseAttempt` + `QuestionnaireQuestion.responses.exists()`, never a denormalised counter column that could drift), a "Process next batch" button (POST, synchronous, returns once the batch completes — same request/response shape as M009A's own upload flow, no polling, no async job id), and a list of the current latest-attempt-failed questions with their `failure_category`/truncated `failure_detail`, so a failure is visibly reported, never silently dropped (requirement 9).

## 5. Eligibility, idempotency, no-duplicate-responses

A `QuestionnaireImportQuestion` is **eligible** for `process_next_bulk_question` iff, in this exact order:

1. `disposition == "question"` and `question is not None` (M009A's own extraction already guarantees this pairing, but the orchestration layer re-checks it defensively rather than trusting it blindly).
2. `question.responses.exclude(status="superseded").exists()` is **False** — i.e. the linked `QuestionnaireQuestion` has no current (draft or accepted) response from *any* source, bulk or manual. This is the direct enforcement of "no duplicate accepted responses or duplicate historical records": M009B never processes a question a human has already answered by hand, and never re-answers one it already bulk-answered successfully. A manually-regenerated response (the existing, unchanged M005 regenerate flow) simply removes this question from M009B's eligible set going forward — no special-case code needed, the same query already handles it.
3. The latest `QuestionnaireBulkResponseAttempt` for this `import_question` (if any) has `outcome == "failed"`, or no attempt exists yet. A `succeeded` latest attempt makes the question permanently ineligible to the bulk orchestrator (it is answered; §5.2 would already exclude it independently, this is belt-and-suspenders against ever reprocessing a sibling-question's edge case).

This gives exactly-once-success semantics without a separate lock/flag column: eligibility is always computed fresh, from current state, at the moment of selection — the same "state-machine precondition enforced at the point of mutation" idiom `retry_security_gate` already established, applied here at the point of *selection* rather than *mutation* (selection is itself the gate, since the actual mutation is M005's own already-atomic persist step).

## 6. AI-cost / resource / concurrency / timeout boundaries

No per-organisation AI budget or concurrency limiter exists anywhere in this codebase today (`ai_platform/` confirmed, by direct inspection, to have only a single-call timeout, `DEFAULT_TIMEOUT_SECONDS`, plus the existing bounded one-retry policy per call). This Work Order adds the minimum necessary, reusing existing data, inventing no new infrastructure:

- **Per-batch wall-clock bound, by construction, not by a new timeout mechanism:** worst case per question is 2 AI calls (interpretation, drafting) × up to 2 attempts each (1 initial + 1 bounded retry) × `DEFAULT_TIMEOUT_SECONDS` = 4 × `DEFAULT_TIMEOUT_SECONDS` per question. `DEFAULT_BULK_BATCH_SIZE` must be chosen so `DEFAULT_BULK_BATCH_SIZE × 4 × DEFAULT_TIMEOUT_SECONDS` stays comfortably under the web server's own request timeout (to be confirmed exactly from `config/settings.py`/the dev-server's effective timeout during implementation; the Work Order fixes the *method*, the Implementer must confirm the *number* against the real configured timeout before choosing `DEFAULT_BULK_BATCH_SIZE` and record that arithmetic in the evidence document — this is a STOP condition, not a judgement call, if the real timeout value cannot be established).
- **Per-organisation daily AI-invocation ceiling, reusing `AIInvocationRecord`:** before starting a batch, count `AIInvocationRecord.objects.filter(organisation=organisation, created_at__gte=<start of UTC day>).count()`; if at or over a frozen ceiling (proposed default: 500/day/organisation, an Implementer-proposed, Architect-confirmable number — chosen only as a placeholder here, not a final decision), refuse to start the batch with a clear, visible message, never a silent partial batch. This is a read-only check against data that already exists — no new counter table, no new write path.
- **Concurrency:** no new locking is introduced. Two simultaneous "Process next batch" requests for the same import are handled by §5's eligibility query alone — each request independently selects "the next eligible question," and because each question's processing is wrapped in its own atomic block ending in a state change that removes it from eligibility, a benign race (two requests picking the same question) is resolved by whichever commits first; the second's `generate_questionnaire_response` call would still succeed but on re-check would find the question already answered and must therefore **check eligibility again, inside the same transaction that creates the `QuestionnaireBulkResponseAttempt`, immediately before persisting it** — this exact race (and its resolution) must be a named test, not an assumption.

## 7. Prompt-injection protection

**No new code is required or proposed.** Reading `ai_platform/prompts/questionnaire_interpretation_v1.py` and `questionnaire_drafting_v2.py` directly: untrusted `question_text`/`source_label` are already serialised as inert JSON data inside the user message only (never string-concatenated into the system prompt), the system prompt already contains a verbatim worked adversarial example with a required "flag as ambiguous, do not comply" response, output is already constrained to a fixed enum/catalogue-key allowlist enforced downstream, and the drafting step already cannot influence `outcome` (fixed by pure-Python `derive_outcome` beforehand). Because M009B calls `generate_questionnaire_response` with the *same* `QuestionnaireQuestion.question_text` field M005 already treats as untrusted free text today, this entire defense already applies, unchanged, to every M009A-imported question the instant it is processed. §9's testing section requires one integration test proving this is genuinely true for imported text specifically (not just re-asserting the existing M005 unit tests), because that is the one thing this Work Order changes: *who* can get text into this pipeline, not *how* the pipeline defends itself.

## 8. Tenant scoping and authorisation

Every new entry point (`process_next_bulk_question`, `process_next_bulk_batch`, and the new view) requires the caller to have already resolved `organisation` via the existing `get_member_organisation_or_404(request.user, organisation_id)` — exactly the WO-M009A/M005 convention, reused verbatim, never re-derived. The new view decorator stack mirrors `questionnaire_import_upload`'s own (`@login_required`, `@require_capability()`, reusing the `customer_assurance` ProductArea M009A already entitlement-gates on — no new `ProductArea`, no new minimum tier). Every query the orchestration service issues against `QuestionnaireImportQuestion`/`QuestionnaireBulkResponseAttempt` is scoped by an explicit `organisation=` filter or a traversal through an already-validated `import_record`/`organisation`, never a bare `.get(pk=...)` on a caller-supplied id.

## 9. Testing — new corpus, CI wiring, and the specific proofs this Work Order requires

New files, following the exact M009A precedent (`questionnaire/eval/m009a_ingestion_corpus.py` → `questionnaire/tests/test_m009a_*.py` → hand-added to `.github/workflows/ci.yml`'s curated lists):

- `questionnaire/eval/m009b_bulk_orchestration_corpus.py` — fixture builders for: a clean answerable question; a question whose text is itself a prompt-injection attempt (reusing the same adversarial pattern M005's own prompt docstring already documents); a question that will be forced to fail interpretation (fake gateway raising a non-retryable error); a question that will be forced to fail drafting only (interpretation succeeds, drafting fails); an already-manually-answered question (must be skipped, never reprocessed); an already-bulk-answered question (must be skipped on a second batch run).
- `questionnaire/tests/test_m009b_bulk_orchestration.py` covering, at minimum:
  1. Increment 1's vertical slice: one eligible question → one `generate_questionnaire_response` call → one `QuestionnaireResponse(status=draft)` → one `QuestionnaireBulkResponseAttempt(outcome=succeeded)`, with `import_question.question` the SAME row the response is attached to (durable linkage proof).
  2. Failure isolation: a batch of 3 questions where the middle one is forced to fail — the first and third both succeed and persist; the second produces exactly one `failed` attempt row and zero `QuestionnaireResponse` rows; no exception propagates out of `process_next_bulk_batch`.
  3. No-duplicate-response: a question already answered (manually or by a prior bulk run) is never selected by `process_next_bulk_question`, proven by asserting `QuestionnaireResponse.objects.count()` is unchanged after a call that had nothing eligible to find.
  4. Idempotent retry: a `failed` question is re-eligible on the next call and, once it succeeds, is never re-selected again.
  5. The race named in §6: two concurrent calls (simulated via two threads or two sequential calls with a monkeypatched mid-transaction hook) resolve to exactly one `QuestionnaireResponse` for the contested question, never two.
  6. Prompt-injection-adjacent integration proof: an M009A-imported question whose `raw_extracted_text` is itself an injection attempt, run through the REAL (fake-gateway-backed, deterministic) interpretation prompt, produces `ambiguous: true` with a note, exactly as M005's own existing unit tests already prove for manually-entered text — proving the inheritance, not re-testing the mechanism.
  7. Tenant isolation: a bulk-trigger request for another organisation's import returns 404, never leaks progress/attempt data.
  8. AI-cost ceiling: a batch request refuses to start once the organisation's daily `AIInvocationRecord` count is at the configured ceiling, with a visible message, and creates zero new attempts.
  9. Batch-size/timeout arithmetic: a test asserting `DEFAULT_BULK_BATCH_SIZE * 4 * DEFAULT_TIMEOUT_SECONDS` is below whatever the real configured request-timeout ceiling is determined to be (see §6) — a frozen regression pin, not just a comment.
- The existing M005 14-case golden corpus (`questionnaire/eval/golden_corpus.py`) is asserted unchanged (zero diff) and still green — it remains the sole truth-engine regression oracle; M009B's corpus is additive, never merged into it.
- New test files hand-added to `.github/workflows/ci.yml`'s `ci/unit`/`ci/integration` curated lists, per the repository's own known, already-disclosed "CI does not auto-discover tests" quirk.
- A real-browser (Playwright) acceptance test for Increment 1's single-click "Process next question" button and Increment 2's progress display, at the same viewport widths M009A's own acceptance tests already cover.

## 10. STOP conditions

- Any need to modify `questionnaire.grounding`, `questionnaire.outcome`, the interpretation/drafting orchestration modules, their prompt templates, or the `QuestionnaireQuestion`/`QuestionnaireResponse` schema.
- Any need for a background worker, task queue, or any process outside the normal HTTP request/response cycle.
- The real configured request-timeout value cannot be established with confidence, making §6's batch-size arithmetic a guess rather than a verified bound.
- Any scenario in which the eligibility/no-duplicate-response guarantee in §5 cannot be proven to hold under the concurrent-request race named in §6 without weakening it.
- Any indication that a real import's question count makes even Increment 2's bounded-batch-per-click UX genuinely unusable (e.g. hundreds of questions needing dozens of manual clicks) — this is a product-UX escalation back to the Architect, not a licence to unilaterally reach for async infrastructure to "fix" it.

## 11. Required durable evidence

`docs/evidence/M009B-BULK-GROUNDED-RESPONSE-ORCHESTRATION.md` — implementation rationale, the full §9 test proof (including the concurrency race and the prompt-injection-inheritance proof), the real batch-size/timeout arithmetic from §6 with the actual configured timeout value cited, real-browser acceptance evidence for both increments, and confirmation the M005 14-case golden corpus is byte-identical/unchanged.

## 12. Delivery sequence

1. Architect reviews and corrects this Work Order.
2. Architect Acceptance recorded in this document.
3. Delivery Controller dispatches an Implementer for Increment 1 only (the vertical slice) first — not both increments at once.
4. Independent Audit of Increment 1 before Increment 2 is dispatched.
5. Implementer for Increment 2, building only on an already-audited Increment 1.
6. Fresh Independent Audit of the complete M009B candidate.
7. PR, Architect Acceptance, merge, closure — following the exact M009A governance pattern throughout.

**No Implementer dispatch of any kind until this Work Order itself receives Architect Acceptance.**
