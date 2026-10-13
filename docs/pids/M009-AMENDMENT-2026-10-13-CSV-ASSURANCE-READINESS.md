# M009 — Amendment 2026-10-13: CSV-First Delivery + Assurance Readiness Gate

**Document status:** DRAFT — Central Architecture reconciliation, for Product Authority and Architect review. Not an implementation authorisation.
**Baseline:** `23fcd6ea21173bb50b4185611c509bad4aacdcfa`
**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Truth-engine PID:** `docs/pids/M005-QUESTIONNAIRE-ASSURANCE.md`
**Disposition of M009A:** CLOSED GREEN, unaffected. Nothing in this amendment reopens, deletes, or reduces the M009A ingestion implementation or `docs/evidence/M009A-CLOSURE.md`.
**Disposition of the draft M009B Work Order (PR #104):** superseded by this amendment once accepted; PR #104 itself is untouched by this document and must be reconciled or replaced under normal governance only after this amendment merges.
**Written by:** Gunnar (Delivery Controller), per Central Architecture's architecture-reconciliation assignment of 2026-10-13. No application code, model, migration, runtime configuration, or dependency was touched to produce this document.
**Revision note (2026-10-13, correction round 1):** Central Architecture reviewed the first draft (head `1d86df95f8075be4413d0efa6df402a7638e0862`) and required five corrections (C1–C5) plus several additional decisions, all incorporated below: C1 separates organisation-level readiness from question-level answerability (§3.5, new); C2 replaces an insufficient transactional-recheck argument with a genuine database-enforced claim mechanism (§6, rewritten); C3 analyses the real Django upload-middleware pipeline and moves readiness enforcement to a `process_view` hook ahead of CSRF's own body-parsing trigger (§3.3, rewritten); C4 hardens the CSV export contract (default columns reduced to `reference,question,answer`, provenance/export-encoding separated, formula-injection defense required to be proven against a real spreadsheet, no draft-export exception) (§4.2, rewritten); C5 replaces a single-control-sentence answer-composition proposal with one that uses the real, already-rich grounding-fact data `questionnaire.grounding` already returns, requiring zero M005 change (§5, rewritten).

**Revision note (2026-10-13, correction round 2):** Central Architecture reviewed the round-1 correction (head `f31e5c55edbbbeb573d6ed7081b2adb9e15cfd74`) and found two further genuine design gaps, both corrected below, not merely re-documented: **(A)** round 1's claim-expiry mechanism (§6) only governed who could currently *attempt* work — it did not prevent two genuinely concurrent `generate_questionnaire_response` calls (one from a reclaim after expiry, while the original caller's AI call was still actually running) from each independently persisting a real `QuestionnaireResponse`, since M005's own persist step has no awareness of M009B's claim ledger at all. §6 now adds a second, permanent (never-expiring) database constraint — "commit-time fencing" — checked immediately after each caller's AI call returns, which deletes the losing caller's own orphaned response rather than leaving two standing (§6.1a, §6.1b, new). **(B)** round 1's proposal to apply composed answer text via the existing `edit_questionnaire_response_text` human-edit API was withdrawn as a genuine audit-provenance mismatch, not merely a labelling nitpick — M009B now owns its own write path, its own permanent `answer_composition_method` provenance field, and its own distinctly-named, non-human-attributed activity event, plus a new, independent adversarial evaluation corpus for the composition function itself (§5, corrected). §11 (new) commits this delivery to a durable, structured GitHub engineering note per Central Architecture's standing governance requirement.

**Revision note (2026-10-13, correction round 3 — C6):** Central Architecture accepted B but found round 2's fencing design (§6.1b, as it then was) still insufficient: it detected a losing claim only *after* `generate_questionnaire_response` had already durably committed a real `QuestionnaireResponse`, relying on deleting that commit afterwards — detection-with-cleanup, not an atomic guarantee, and a crash in that exact window left an untracked orphan. Corrected (§6.1a–§6.1c, rewritten) by investigating, as the Architect's own instruction explicitly authorised, a narrowly scoped M005 extract-method refactor: reading `questionnaire/services.py` directly confirms `_persist_response` is *already* M005's own sole atomic unit, taking a fully-prepared bundle as plain arguments — exposing it (renamed, identical body) as `persist_prepared_response`, alongside a new `prepare_questionnaire_response` wrapping the pre-existing AI-call sequence, lets M009B's own transaction perform the claim-ownership check and the response INSERT as one indivisible unit. A losing claim's response is now never committed at all, so there is nothing to delete and no orphan-sweep logic is needed — that logic is removed by this correction, not merely retained as a backstop. `generate_questionnaire_response`'s external behaviour is unchanged (a two-line composition of the two extracted functions), proof required via the unchanged M005 golden corpus and its own existing test suite passing byte-identically.

**Revision note (2026-10-13, correction round 4 — bounded documentation correction, architecture not reopened):** Central Architecture accepted C6 in principle and required one final, bounded correction before merge: (1) §6.1's own claim-acquisition pseudocode caught `IntegrityError` inside the same `atomic()` block that raised it — the exact bug pattern this document elsewhere names as a STOP condition, present in the one place it had not yet been fixed; corrected via a nested `atomic()` savepoint around only the risky `create()` call, consistent with §6.1c. (2) `PreparedQuestionnaireResponse`'s exact field-by-field contract, and `prepare_questionnaire_response`/`persist_prepared_response`'s exact signatures, added to §6.1b so an Implementer can perform the extraction mechanically rather than re-deriving intent from prose. (3) §6.2a (new) consolidates the full regression-gate list — golden corpus, existing M005 tests, claim expiry/concurrency, tenant isolation, and accepted-response immutability — as explicit, named, required tests in one place. (4) This revision note and the accompanying PR comment record the correction and the SHA at which it was made.

## 0. Decision sought

Ratify a change to the previously accepted M009 delivery sequence: the first *complete end-to-end* Customer Assurance workflow becomes **CSV in, CSV out**, gated by a new deterministic **Security Foundations Assurance Readiness** predicate, before any bulk-answer export capability exists. M009A's XLSX secure-ingestion capability is preserved exactly as closed — not replaced, not silently exposed as a finished answer/export path, not deleted.

Every claim below about what already exists in this codebase was independently verified by direct reading of the real code at this baseline (see §2's citations) — not assumed from the earlier M009B draft.

## 1. Old-versus-new reconciliation

| M009 master PID commitment | Status under this amendment |
|---|---|
| XLSX is the first-class, first-delivered end-to-end format | **Superseded.** CSV becomes the first end-to-end format. XLSX (M009A) remains delivered and closed, but its answer-generation/export path is now scheduled *after* CSV's, not before it. |
| M009B = bulk answer generation, no gating beyond the existing `customer_assurance` tier | **Superseded.** A new Assurance Readiness predicate is now a hard precondition, additional to and independent of package-tier entitlement. The M009B draft in PR #104 did not include this gate and must be revised. |
| Questionnaire interpretation selects from the existing `questionnaire.catalogue` (unchanged) | **Confirmed, not superseded.** Verified: the catalogue is a small (29-entry), deliberately curated, versioned allowlist — not a database-reflection mechanism. This amendment reuses it exactly as-is (§4). |
| M005 truth engine, outcome vocabulary, immutability (`questionnaire.services`/`grounding`/`outcome`) | **Confirmed, not superseded, with one narrowly scoped, Architect-authorised exception.** `questionnaire.grounding`/`outcome` and the model schema remain fully untouched. `questionnaire.services` gains a pure extract-method refactor (§6.1b) — `generate_questionnaire_response` is decomposed into `prepare_questionnaire_response` + `persist_prepared_response`, with byte-identical external behaviour, proven by the unchanged golden corpus — required to make the concurrency fix (C6) genuinely atomic rather than detect-and-delete. No semantic change to any M005 behaviour. |
| M009C (review), M009D (export) scope boundaries | **Narrowed, not superseded.** M009D now additionally owns CSV export/formula-injection hardening as its first deliverable, with XLSX write-back deferred inside M009D as a separately-scoped increment (§8). |
| M009B/C/D as three independent Work Orders | **Confirmed.** This amendment explicitly forbids collapsing them into one implementation Work Order (§8). |

## 2. What already exists — verified, not assumed

Every item below was confirmed by direct reading of the real code at `23fcd6ea21173bb50b4185611c509bad4aacdcfa`, specifically to avoid proposing something that already exists under a different name, or weakening something already load-bearing.

### 2.1 `entitlements/metrics.py` already computes the exact knowledge-completeness signal this amendment needs

This repository already has **two distinct, deliberately separate** aggregate metrics, built on `entitlements.models.FoundationRequirement` (18 active rows: 12 `BASELINE_CONTROL` rows mirroring `security_baseline.catalogue`'s 12 controls one-to-one, plus 6 `DERIVED_MILESTONE` rows — `organisation_profile`, `governance_roles`, `workplace`, `assets_review`, `risks_review`, `policy_approved` — each resolved by an existing `organisations.overview` predicate):

- **`get_foundational_security_posture(organisation)`** — a *weighted security-quality* score (`Σ(security_weight × state_factor) / Σ(security_weight) × 100`, YES=1.0/PARTIAL=0.5/NO or UNKNOWN=0, NOT_APPLICABLE excluded from both sums). This is the dashboard's existing score. **Confirmed by reading the function body: it measures how secure the organisation looks, not whether the customer has finished answering.** The Architect's explicit instruction not to derive a readiness threshold from "the dashboard weighted score" refers to exactly this function, and this amendment does not use it for the gate.
- **`get_security_foundations_completion(organisation)`** — an *unweighted completion* percentage over the same 18 active rows: `completed_count / total_count × 100`. A `BASELINE_CONTROL` row counts as complete for **any** of `yes`/`partial`/`no`/`not_applicable` — **only `unknown` counts as incomplete.** A `DERIVED_MILESTONE` row is complete iff its existing resolver returns `True`. **This is already, precisely, a knowledge-completeness predicate, not a compliance-quality one** — a documented `no` counts the same as a documented `yes` for this metric, exactly matching this amendment's own binding outcome 3 ("a ready customer may still have genuine security GAPs... the gate is not a compliance certification"). Both functions are read-only, derive-fresh on every call (nothing stored/cached), and fail loudly (`UnresolvableFoundationRequirementError`) rather than silently skipping an unresolvable row.

**Design decision:** the Assurance Readiness Gate (§3) is defined as a threshold on `get_security_foundations_completion`, reusing it directly, unmodified. No new scoring logic, no new weighting scheme, and no new model is proposed for the *computation* itself. This is the single largest scope reduction this research produced relative to the M009B draft's original §3.2, which spoke of "proposed invariant categories" as if they needed to be built — they are already built, under `entitlements.models.FoundationRequirement`, and already versioned (`FOUNDATION_METRIC_VERSION = "2026-09-v1"`).

**What genuinely is new** (§3): the *threshold* (what completion percentage, or whether it must be exactly 100%, constitutes "ready"), the *gate enforcement* at every Customer Assurance entry point, the *blocker-explanation contract* (which specific incomplete items to show the customer and which Foundations action each links to), and the *pause-not-erase* behaviour when readiness is lost mid-processing. None of that exists today.

### 2.2 `questionnaire.catalogue` is already the exact "flexible, safe, governed fact access" surface requested — not something to build

Confirmed exhaustively: exactly **29 entries** — `control:<key>` ×12 (sourced 1:1 from `security_baseline.catalogue`, description text = that control's own real question text), `policy_section:<key>` ×8 (sourced from `ai_platform.policy_contracts.ALLOWED_SECTION_KEYS`), `org:<fact>` ×9 (certifications, working model, four data-handling flags, "receives security questionnaires," "develops/hosts own software" — all backed by real, typed `OrganisationProfile` fields, never free text). This is small enough to send to the interpretation AI call **in full, every time** — no retrieval, ranking, or pagination step is needed or proposed. New keys require a reviewed, versioned Python-module edit (`CATALOGUE_VERSION` bump) — never a runtime database write, never a column the model itself can introduce. `questionnaire.grounding` already has the exact 1:1 resolver for every prefix.

**Design decision:** M009B reuses this catalogue and `build_questionnaire_grounding_snapshot` completely unchanged. This amendment does not propose extending the catalogue's coverage — if a future increment genuinely needs a new fact family, that is its own separately-adjudicated M005 behavioural change (per the original M009B draft's own instruction, restated here because it remains correct), not something this amendment pre-authorises.

### 2.3 `questionnaire.services._initial_current_answer_text` — read verbatim, design constraint confirmed exactly

```python
def _initial_current_answer_text(outcome, draft):
    if outcome == OUTCOME_CONFIRM:
        return CONFIRM_APPLICATION_SAFE_ANSWER_TEXT
    if outcome == OUTCOME_SUPPORTED:
        return SUPPORTED_APPLICATION_SAFE_ANSWER_TEXT
    return draft.answer_text  # GAP and NOT_APPLICABLE only
```

For `SUPPORTED`/`CONFIRM`, the AI's raw draft text (`draft.answer_text`) is **never read at all** for the customer-facing starting value — two fixed, non-interpolated application strings are used instead, verbatim:

> **CONFIRM:** "Not yet confirmed. The current security record does not contain enough confirmed information to answer this requirement definitively. Please review the underlying security state before sending a final response."
>
> **SUPPORTED:** "Supported by the current security record. This reflects the organisation's recorded security state for this requirement and does not by itself mean the control has been independently verified or that supporting evidence is attached. Please review before sending."

`GAP`/`NOT_APPLICABLE` are explicitly untouched by this safeguard — the raw draft is used as-is for those two outcomes today. The raw AI draft is preserved unmodified in `ai_draft_text` for every outcome regardless (for provenance/eval), only the customer-facing `current_answer_text` *starting value* is substituted for the two outcomes where fabrication risk is highest. §5 proposes a bounded evolution; §5 does not touch this function.

### 2.4 No existing precedent for CSV, formula-injection defense, or AI-call concurrency/leasing

Confirmed by repository-wide search: **zero** existing CSV import/export code anywhere in this codebase, **zero** existing spreadsheet-formula-injection defense anywhere, and **zero** existing lease/claim/lock mechanism for preventing duplicate concurrent AI processing (the only superficial grep hits for "claim" are anti-fabrication prose — e.g. `outcome.py`'s "nothing here actually SUPPORTS the claim" — not a concurrency primitive). §4 and §7 therefore propose genuinely new, from-first-principles designs for these two areas specifically, not a reuse of something that already exists. Everywhere else in this amendment, reuse was possible and is proposed instead of a new mechanism.

## 3. Assurance Readiness Gate

### 3.1 Contract

A single, read-only service function, `security_baseline.readiness.evaluate_assurance_readiness(organisation) -> AssuranceReadinessResult`:

```python
@dataclass(frozen=True)
class AssuranceReadinessResult:
    ready: bool
    completion_percentage: float          # from get_security_foundations_completion, unmodified
    threshold_percentage: float           # frozen constant, see §3.2
    policy_version: str                   # mirrors FOUNDATION_METRIC_VERSION
    blockers: tuple[ReadinessBlocker, ...] # empty iff ready
    evaluated_at: datetime
    source_revision: str                  # FOUNDATION_METRIC_VERSION, for drift detection
```

`ReadinessBlocker` names the specific incomplete `FoundationRequirement` row(s) (`code`, `title`, and — critically — the real Foundations UI route to resolve it, taken from that requirement's own `product_area.destination_view_name`, never a hand-maintained second copy of the URL). No AI call. No new database write. No caching — evaluated fresh on every call, exactly like the two functions it's built on.

### 3.2 Threshold — fixed at 100%, per Central Architecture's incorporated decision

`get_security_foundations_completion` returns a percentage over 18 active rows. **This amendment fixes the V1 threshold at 100% completion** (every row engaged — zero `unknown`s, every `DERIVED_MILESTONE` resolver satisfied) — per Central Architecture's explicit instruction to incorporate this as the decision, not merely a recommendation. A documented `no`/`partial`/`not_applicable` answer counts exactly the same as a `yes` for this threshold — `get_security_foundations_completion`'s own existing "only `unknown` is incomplete" logic already guarantees this; no change to that function is proposed or needed to honour it. There is no lower/softer threshold variant in this revision — the blocker-while-ready complexity a sub-100% threshold would have required (§3.1's `ReadinessBlocker` contract needing to describe "ready, but 2 items still unknown") is avoided entirely.

### 3.3 Enforcement surface — including the exact point in the request pipeline, per C3

**View-level enforcement alone is too late, and this amendment does not assume otherwise (C3).** M009A's own `QuestionnaireUploadSizeGuardMiddleware` already had to solve exactly this class of problem for upload size, and the reasoning it documents is directly re-applicable here, verified by re-reading the actual Django middleware pipeline, not assumed: Django's `MIDDLEWARE` list order governs both `process_request` and `process_view` hooks, in the same top-to-bottom order, for the "incoming" direction. `CsrfViewMiddleware.process_view` runs *before* the target view function is ever called, and it reads `request.POST` to validate the CSRF token — which triggers Django's lazy multipart-parsing machinery (consuming `request.upload_handlers`) *before* the view function's first line of code ever executes. A readiness check placed only inside the view function therefore runs **after** the server has already received and parsed the entire request body — too late to prevent the server from doing that work for an unready organisation, even though (verified separately) Django's default upload handlers write multipart data to a process-local temp file or memory buffer, not into `questionnaire.import_storage`'s actual per-tenant persistent directory — so no *permanent* artifact is created by parsing alone, but real bandwidth, memory/disk, and CPU are already spent.

**Enforcement point, concretely:** a `process_view` hook — not `process_request` — because `organisation_id` is a URL keyword argument, and `process_view` is the first middleware hook Django calls *after* URL resolution has already bound `view_kwargs`, but *before* the view function (or any later middleware's `process_view`, including `CsrfViewMiddleware`'s) runs. Placed on the *same* existing `QuestionnaireUploadSizeGuardMiddleware` (extended, not duplicated — it already sits before `CsrfViewMiddleware` in `MIDDLEWARE` for exactly this class of reason) or a new sibling middleware positioned identically. The hook activates only for view functions explicitly marked as readiness-gated (a plain attribute set by a small decorator on the view, mirroring `require_capability`'s own "only acts on marked, organisation-scoped routes" discipline — never a blanket check applied to every request) — resolves `organisation_id` from `view_kwargs`, calls `evaluate_assurance_readiness`, and if `ready` is `False`, returns a response **immediately**, short-circuiting the view and every later middleware's `process_view` (including CSRF's) — so `request.POST` is never read, the multipart parser never runs, and zero bytes of the unready organisation's upload are ever received into memory or a temp file beyond whatever the WSGI server itself buffers before Django's middleware chain even starts (a pre-existing, unrelated boundary this amendment does not change).

This same hook protects every Customer Assurance entry point:

- GET renders blockers + links, no file-input control rendered at all — not merely disabled, since a disabled control can still be POSTed to directly (the `process_view` hook catches that POST regardless of what the rendered HTML looked like).
- POST is rejected by the hook before CSRF's own `process_view`, as above — not as a second, redundant check inside the view (the view-level check from the original draft is removed as the *primary* mechanism and demoted to a defensive, cheap, redundant re-check only, since defence-in-depth costs nothing here but must never be mistaken for the actual enforcement point).
- Before `process_next_bulk_question`/`process_next_bulk_batch` (§6) starts *and before each individual question's processing*, not just once at batch start — this path has no multipart body to worry about, so the check is a plain, synchronous function call at the top of each unit of work, not a middleware concern.

If readiness is lost mid-batch, the batch stops cleanly after whatever is already committed, with a clear "paused — Foundations readiness no longer met" status, never a partial-batch error treated as a crash. Existing historical imports/responses remain fully viewable under existing authorisation rules regardless of current readiness — the gate blocks *new* work, never access to *already-produced* work.

### 3.4 What this is explicitly not

Not a second entitlement tier (the existing `customer_assurance` Monthly+ `ProductArea` gate is unchanged and is checked independently, in addition to readiness — both must pass). Not a compliance score. Not a guarantee any individual question is answerable (a ready organisation can still produce a correct `GAP` for a specific question — the gate is about having *engaged* with the baseline, not about every answer being `SUPPORTED`).

### 3.5 Answerability — a separate, question-level signal, per C1

**Readiness is an organisation-level precondition to start processing at all. It is not a prediction that any specific imported question can be answered.** A customer's CSV can legitimately ask something no catalogue key maps to at all (e.g. a sub-processor-specific question with no corresponding `control:`/`policy_section:`/`org:` entry) — that has nothing to do with whether the organisation has finished its Foundations baseline, and conflating the two would misreport genuinely unrelated failures as "not ready," which is both inaccurate and actively unhelpful (it would send the customer to fix Foundations items that have nothing to do with the actual problem).

**Contract:** after Call A (interpretation) returns and `questionnaire.catalogue`/`QuestionnaireInterpretation.from_response_dict` have already validated `selected_keys` as a genuine subset of the catalogue, but *before* drafting runs, the bulk orchestration layer (never M005 itself — this is purely a classification over data M005 already produces, with zero new data source and zero change to `derive_outcome`'s own authority over the persisted outcome) computes:

```python
def assess_answerability(interpretation, grounding_snapshot) -> Answerability:
    """
    ANSWERABLE: selected_keys is non-empty AND at least one selected
    key's grounding fact has a non-"unknown"/non-absent answer (a
    control fact's "answer" != "unknown", a policy_section fact's
    "section_present" is True, or an org fact resolves to a real
    typed value - never a blank/None).
    NOT_ANSWERABLE_FROM_AVAILABLE_FACTS: selected_keys is empty
    (nothing in the 29-entry catalogue matches this question at all),
    or every selected key resolved to an unknown/absent fact.
    """
```

This is reported explicitly, never silently folded into `CONFIRM` (even though `derive_outcome` will, independently and correctly, also often reach `CONFIRM` in the `NOT_ANSWERABLE_FROM_AVAILABLE_FACTS` case) — the two signals answer different questions for different audiences: `derive_outcome`'s result is the customer-facing truth value; `Answerability` is an operator-facing diagnostic recorded on `QuestionnaireBulkResponseAttempt` (a new, additional field — not a new model) explaining *why* a question landed where it did, so a batch's progress report can distinguish "12 answered, 2 not currently answerable from recorded facts (no matching catalogue coverage), 1 failed" rather than collapsing the middle category into an undifferentiated "answered CONFIRM," which would hide a genuinely different, non-readiness-related gap (the catalogue itself not covering that topic) from whoever is triaging a batch's results.

**This requires no new data source, no M005 change, and no new readiness computation** — it is a pure function over `interpretation.selected_keys` and the already-built `grounding_snapshot`, both of which `generate_questionnaire_response` already produces internally on every call; the orchestration layer only needs to read them, which requires `generate_questionnaire_response` to return (or the orchestration layer to independently re-derive, more likely the cleaner boundary) the intermediate `grounding_snapshot` it already built, not only the final `QuestionnaireResponse` — a small, additive, backward-compatible return-value note for Work Order stage, not a behavioural change to any existing caller.

## 4. CSV V1 contract

### 4.1 Import

- UTF-8 only, optional UTF-8 BOM stripped before parsing; any other encoding is a deterministic rejection (not a best-effort re-decode attempt — silent mojibake is worse than a clear error). Standard library `csv` module only, comma delimiter, standard RFC 4180 quoting — frozen, not configurable.
- Required header: `question`. Optional headers: `reference` (a customer-supplied stable identifier for export round-tripping) and `answer`. **Decided (per Central Architecture's incorporated instruction): a non-blank imported `answer` is read-only provenance and is never overwritten, regenerated, or treated as eligible for bulk processing by M009B** — a row with a non-blank `answer` is excluded from §6's eligibility query exactly like an already-accepted response (§5 of the superseded WO's own eligibility rule, extended here to cover this new entry path), and its original value is preserved byte-for-byte in any later export's `answer` column for that row unless a human reviewer (M009C, out of this amendment's scope) explicitly changes it. Duplicate or case-ambiguous headers, an empty required header, or zero data rows are all deterministic rejections, each with its own named, test-pinned error — mirroring M009A's own named-rejection-reason discipline (`security_gate.py`'s per-fixture specific reasons), never one generic "invalid file" message.
- Blank `question` cells are recorded (never silently dropped — the row count must reconcile) but excluded from processing, same disposition shape M009A already uses (`excluded_other`-equivalent) — reusing the `disposition` enum's existing values rather than inventing CSV-specific ones.
- Row order is the durable provenance locator (`extraction_order`, reusing the exact field M009A's `QuestionnaireImportQuestion` already has) — no fuzzy question-text matching for export reconciliation, ever.
- Resource limits, frozen (exact numbers an Implementer must confirm are achievable within the same request-timeout arithmetic M009B's own draft already established in §6 of the superseded WO, not re-derived from scratch): bounded upload bytes (propose reusing M009A's existing 10 MiB ceiling — a CSV this large would already be an unusual customer file), bounded row count, bounded per-field length, bounded total text length. No silent truncation — exceeding any limit is a named rejection, not a quiet cut-off.
- Storage: reuses M009A's `import_storage` module, security gate shape, and ClamAV CLEAN-only requirement unchanged — a CSV is not exempted from malware scanning merely because it is "plain text" (a CSV can still carry a payload if some downstream tool ever opens it as something else, and the scanning cost is negligible). SHA-256 computed and immutably recorded exactly as M009A already does. Filename/MIME are untrusted exactly as M009A already treats them.

### 4.2 Export — hardened, per C4

- A new, separate, immutable, versioned artifact per export action — never an in-place rewrite of the original upload (mirrors M009A's own "original always immutable" principle, now applied to the export side).
- **Default customer-facing columns, decided: `reference,question,answer` only.** `outcome`/`review_status`/any other internal M005 vocabulary are **never** written to the customer-facing export file — they remain in INFOSECURS's own database only, visible to the organisation's users through the product UI (M009C's review surface), never shipped inside the ordinary response file a customer hands to a third party. This directly resolves the Product Authority question the original draft left open — there is no external-facing label mapping to design, because the internal vocabulary is simply not exported by default at all. `reference` = the customer's own imported `reference` value when supplied, else the stable `QuestionnaireImportQuestion.id` — never a newly-generated value that discards a customer-supplied identifier. `question` = the original `raw_extracted_text`, byte-identical, in original import row order (§4.1's `extraction_order`) — never re-ordered, never re-derived by matching text.
- **Provenance and export encoding are two separate representations, never conflated.** The durable, persisted `raw_extracted_text`/`current_answer_text` values are never mutated for export purposes — they remain exactly as extracted/composed, forever, as M009A's own immutability principle already requires. A dedicated, pure `encode_for_csv_export(value: str) -> str` function is applied *only* at serialisation time, on an in-memory copy, producing the one-off defused string written into that specific export file — the database never stores a defused value, and a human reading the same text inside the product UI always sees the real, unmodified original.
- **Formula-injection defense, concretely, and proven against real spreadsheet software, not only the raw string:** `encode_for_csv_export` prefixes any field beginning with `=`, `+`, `-`, `@`, tab, or carriage return with a single leading `'` (apostrophe) — the standard, documented defusal technique, inert to every spreadsheet formula engine. Applied to `question` and `answer` only — never to `reference` (a customer-supplied identifier, still passed through the same function defensively, since nothing prevents a customer from putting a hostile string in their own reference column either). **Acceptance requires an executable test that actually opens the produced CSV file in a real, scriptable spreadsheet application (LibreOffice Calc, already available for CI/local use, headless-invokable) and asserts the defused cell's evaluated/displayed value is the literal defused string, not a formula result** — a string-level unit test alone does not satisfy this Work Order's acceptance criterion.
- **No draft export, ever — decided.** The strict `send_ready` predicate is now the *only* path to any export, with no watermarked-draft exception: every row with a non-blank `question` has exactly one current `accepted` response; every `CONFIRM` outcome has been reviewed and resolved (M009C's job; this amendment only states the export-time check); every `GAP` has been individually reviewed, not silently present; every `NOT_APPLICABLE` has been individually reviewed, not bulk-accepted; no row present in the import is missing from the export. An export attempted before `send_ready` is `True` is refused outright, unconditionally — the original draft's "Product-Authority-authorised watermarked draft" branch is removed by this correction, not merely deprioritised.

## 5. Answer-quality contract for SUPPORTED/CONFIRM — revised, per C5

The original proposal (one fixed-shape sentence naming a single control) was correctly judged insufficient — it did not use the real richness of data M005 already produces. Re-reading `questionnaire/grounding.py` directly (not assumed) shows the grounding snapshot for a `control:<key>` fact already carries, for every selected key, far more than a single state value: `answer` (yes/no/partial/unknown/not_applicable), `answer_updated_at` (a real date — staleness is already knowable), `assurance_label` (an existing human-readable label), `active_supporting_evidence_count`/`active_contradicting_evidence_count`/`stale_evidence_count`, `open_remediation_count`, and `relevant_remediation` (a list of `{status, owner, target_date, treatment_summary}` — each already `None`/absent rather than invented when genuinely unknown, per M005's own existing "never invent owner/date" discipline). A `policy_section:<key>` fact similarly already carries `policy_exists`, `approved_version_number`, `section_present`, and the real `section_content` text. **None of this requires any new field, resolver, or M005 change — it is all already returned by the existing, unmodified `build_questionnaire_grounding_snapshot` and already persisted on every `QuestionnaireResponse.grounding_snapshot`.**

**Revised design:** a new, M009B-owned composition function, `questionnaire.bulk_orchestration.compose_detailed_safe_answer_text(response) -> Optional[str]`, reads `response.grounding_snapshot` (already persisted, read-only, the exact data `derive_outcome` itself used to reach the current outcome — not a new or different source) and, for `SUPPORTED`/`CONFIRM` outcomes only, deterministically composes a short, question-specific sentence enumerating **every** selected key's resolved fact (not just one, correcting the original proposal's narrower shape), e.g.:

> "Supported by recorded answers: 'Do you encrypt data at rest?' — Yes (recorded 2026-09-02, 2 supporting evidence item(s) on file). Policy section 'encryption' is present in the approved policy. Please review before sending."

> "Not yet confirmed: 'Do you have an incident response plan?' — Partial (recorded 2026-08-15). Open remediation: owner Jane Smith, target 2026-11-01, 'Finalise IR runbook.' Please review the underlying security state before sending a final response."

Every interpolated value is read directly from the already-resolved fact dict — the control's own fixed catalogue question text, the literal `answer`/`assurance_label`, the literal `answer_updated_at` date, the literal evidence counts, the literal `relevant_remediation` entries (omitted entirely, not replaced with an invented placeholder, when the list is empty) — **zero characters of `draft.answer_text` are read, exactly as the existing safeguard already guarantees.** A fixed, shorter fallback sentence (closer to the original generic text) is used whenever a selected key's fact is sparse enough that the richer composition would read as empty or redundant (e.g. an `org:*` fact, which is a bare typed flag with no date/evidence/remediation structure to enumerate) — this is a presentation decision, not a safety one, and is left to Work Order-stage UX review.

**Boundary with M005, resolved cleanly:** this function does **not** modify `questionnaire.services._initial_current_answer_text` or any other M005 file — `_initial_current_answer_text`'s existing fixed-text behaviour remains the untouched default for every caller that does not opt in. M009B's orchestration layer calls this new function *after* `generate_questionnaire_response` returns its (generic-text) `QuestionnaireResponse`.

**Audit provenance — withdrawn and corrected.** The previous draft proposed applying the composed text via `questionnaire.services.edit_questionnaire_response_text`, reasoning that reuse of an existing public API was itself sufficient. **That reasoning is wrong and is withdrawn**, per the Architect's own correct objection: `edit_questionnaire_response_text` exists specifically to represent *a human Account Holder's own wording edit* (its own docstring, read directly, frames it exactly this way), and its audit event, `EVENT_QUESTIONNAIRE_RESPONSE_EDITED`, carries no structural marker distinguishing "a person typed this" from "the system deterministically assembled this from recorded facts" — passing a bulk-run's technical actor identity into `actor=` does not fix this, because the event *type* itself, not just its actor field, is what a reader of the activity log relies on to understand what happened.

**Corrected design — M009B owns its own write path and its own, explicitly-labelled event, never routed through the human-edit API:**

- M009B sets `response.current_answer_text` directly, via its own short atomic update (`response.current_answer_text = composed_text; response.save(update_fields=["current_answer_text", "updated_at"])`) — this is not a safety regression: `QuestionnaireResponse`'s own model-level protection (`PROTECTED_WHILE_DRAFT_FIELDS`, enforced in `.save()` itself, not inside any particular calling function) already governs every write to this field regardless of caller, and only takes effect once `status` is `accepted`/`superseded` — a still-`draft` response is mutable by design, which is exactly how `edit_questionnaire_response_text` itself already works today, as a thin wrapper, not a safety boundary of its own.
- M009B records the composition method **permanently and explicitly on its own ledger row**, never only in a generic activity event: `QuestionnaireBulkResponseAttempt` gains an `answer_composition_method` field (choices: `ai_draft_passthrough` — GAP/NOT_APPLICABLE, unchanged from today; `application_fixed_text` — SUPPORTED/CONFIRM using M005's existing, untouched default, if this enrichment is not applied/not yet approved; `application_composed_from_grounding` — this proposal's enrichment, when applied). This is queryable, permanent, and independent of any activity-log naming convention — any future audit of "how was this answer actually produced" has a direct, structured answer without relying on event-type archaeology.
- M009B additionally emits its own, distinctly-named activity event — proposed as a new `ActivityEvent.event_type` choice, e.g. `questionnaire_response_machine_composed` — fired directly by M009B's own module, **never** via `edit_questionnaire_response_text`, with `actor` set to a dedicated, clearly-non-human system identity (never attributed to whichever human happened to trigger the batch) and structured metadata referencing the `QuestionnaireBulkResponseAttempt` id and the selected grounding keys used. `ActivityEvent.event_type`'s choices have already been extended additively multiple times in this repository's own history (migrations `0002` through `0006` each added a new choice) — this is a precedented, low-risk, additive pattern, not a redesign of the `activity` app, and remains a Work Order/implementation-stage migration, not something this architecture document itself performs.

**Bounded, question-specific, anti-fabrication:** unchanged from the prior draft — every interpolated value is read from the already-persisted `grounding_snapshot`, zero characters of `draft.answer_text` are read, nothing is invented. This remains true regardless of which write path applies the text; the correction above is about *how the action is recorded*, not about what text is produced or where its data comes from.

**Independent answer-quality/adversarial evaluation corpus — new, required, per B.** A dedicated corpus (`questionnaire/eval/m009b_answer_composition_corpus.py`), separate from both the existing M005 14-case golden corpus and M009B's own orchestration test suite, specifically targeting the composition function's own correctness and safety, at minimum:
1. **Differential fact-containment test:** every fact token that appears in a composed answer must trace back to a literal value present in that response's own `grounding_snapshot` — mechanically checked (e.g. by parsing the composed sentence's interpolated values back against the snapshot dict), not merely eyeballed, for a representative set of fixture snapshots.
2. **Non-omission of adverse facts:** a fixture where `stale_evidence_count > 0` or `active_contradicting_evidence_count > 0` is present must result in a composed answer that discloses it — a composer that quietly drops an unfavourable fact while keeping favourable ones would itself be a fabrication-adjacent failure mode, distinct from inventing a fact outright, and this is the specific adversarial case that catches it.
3. Maximal `relevant_remediation` list length (bounded truncation behaviour, never an unbounded sentence).
4. Every optional field absent (sparse-fact fallback sentence, §5's existing fallback rule).
5. A mixed question selecting several keys of different richness (control + policy_section + org in one question).
6. The composed text is re-verified never to contain any substring of the corresponding `draft.answer_text` for that response (a mechanical, not just logical, proof that the AI draft contributed zero characters).

This corpus is additive to, and does not alter, the existing M005 14-case golden corpus, which remains byte-identical and unchanged.

## 6. M009B orchestration — revised, with a genuine race-safe claim mechanism per C2

**The superseded draft's concurrency argument was insufficient and is withdrawn.** It relied on "eligibility is re-checked inside the same transaction that persists the attempt record" — but that check happens *after* the (slow, externally-latent) AI calls, which is exactly the window a real race lives in: two concurrent requests can both pass the eligibility check, both then spend 10-40 real seconds calling the AI gateway, and only discover the conflict afterwards — by which point one of the two AI calls, and its cost, was always wasted, and (worse) the "first to commit wins" framing described but did not actually specify a mechanism that prevents the *second* caller from having already created its own competing response before the check runs. This correction replaces that argument with an explicit, database-enforced work-claim, established **before** any AI call, using Postgres itself as the mutual-exclusion primitive — no new queue, worker, or lock service, per the Architect's explicit restriction.

### 6.1 Claim mechanism

`QuestionnaireBulkResponseAttempt` (unchanged shape from the superseded WO's §3) gains two additional fields and one additional state, used only for this purpose:

```python
STATE_CLAIMED = "claimed"      # new: in addition to "succeeded"/"failed"
outcome = models.CharField(max_length=16, choices=[..., (STATE_CLAIMED, "Claimed")])
claimed_at = models.DateTimeField()
claim_expires_at = models.DateTimeField()
```

```python
class Meta:
    constraints = [
        # Postgres partial unique index - at most one "claimed" row per
        # import_question at any time, enforced by the database itself,
        # not by an application-level check-then-act sequence. This is
        # the actual race-safety mechanism; everything else in this
        # section exists to use it correctly.
        models.UniqueConstraint(
            fields=["import_question"],
            condition=models.Q(outcome="claimed"),
            name="one_active_claim_per_import_question",
        ),
    ]
```

**Claim step** (one short, fast, AI-free transaction — the only transaction that matters for race-safety):

```python
def claim_next_eligible_question(import_record, *, actor) -> Optional[QuestionnaireBulkResponseAttempt]:
    with transaction.atomic():
        # Opportunistic expiry sweep: any claim past its own expiry is
        # relabelled "failed" (failure_category="claim_expired") before
        # this same transaction looks for something to claim - a crashed
        # worker's abandoned claim becomes reclaimable on the very next
        # call, with no separate recovery step or operator action.
        QuestionnaireBulkResponseAttempt.objects.filter(
            outcome="claimed", claim_expires_at__lt=timezone.now()
        ).update(outcome="failed", failure_category="claim_expired")

        candidate = _next_eligible_import_question(import_record)  # §5's eligibility query, unchanged
        if candidate is None:
            return None

        # The create is isolated in its own NESTED atomic() block - a
        # genuine Postgres SAVEPOINT, since we are already inside the
        # outer atomic() above. This is the correction this round
        # requires, consistent with §6.1c: catching IntegrityError
        # directly inside the SAME atomic() block that raised it (the
        # outer block above, in the previous revision of this
        # pseudocode) leaves that transaction in Postgres's "aborted"
        # state for any later statement - exactly the bug named as a
        # STOP condition elsewhere in this document, which this
        # correction now also fixes here, in the block where it first
        # appeared. Isolating the risky create() in its own nested
        # atomic() means ONLY this savepoint rolls back on conflict;
        # the sweep's UPDATE above, already applied earlier in this
        # same outer transaction, is unaffected and commits normally
        # when the outer block exits - Django's own documented pattern
        # for handling an expected IntegrityError without corrupting
        # the surrounding transaction.
        try:
            with transaction.atomic():
                return QuestionnaireBulkResponseAttempt.objects.create(
                    organisation=import_record.organisation,
                    import_question=candidate,
                    attempted_by=actor,
                    outcome="claimed",
                    claimed_at=timezone.now(),
                    claim_expires_at=timezone.now() + CLAIM_TTL,
                )
        except IntegrityError:
            # Another request's transaction won the unique-constraint
            # race for this exact question between our SELECT and our
            # INSERT - the database caught it, not application logic.
            # Caught here, inside the nested savepoint, so the outer
            # transaction (and the sweep's own work above) remains
            # healthy. Return None for this candidate; the caller tries
            # the next eligible question or ends the batch early. Never
            # retried against the same candidate within this call.
            return None
```

### 6.1a Why detect-and-delete is not atomicity, and what C6 requires instead

**Round 2's "finalisation" step is withdrawn as insufficient, per the Architect's own correct finding.** It called the unmodified `generate_questionnaire_response` — which internally performs its own, already-complete, already-committed `@transaction.atomic` insert of a real `QuestionnaireResponse` — and only afterwards checked whether this attempt's claim was still valid, deleting the response if not. **Between those two steps, a losing caller's `QuestionnaireResponse` is genuinely, durably committed to the database** — visible to any other concurrent reader, however briefly — before being deleted. That is detection with manual cleanup, not an atomic persistence guarantee, and a crash in that exact window leaves a real orphan with no attempt record. This is the precise defect named: "the current approach detects competing attempts after M005 has already persisted the responses."

**The real fix requires the claim-ownership check and the response-creating `INSERT` to be the *same* database transaction** — so that a losing claim's response is never committed at all, because the whole transaction containing it rolls back as one atomic unit. That is only possible if the code that creates a `QuestionnaireResponse` can be invoked *from inside* M009B's own transaction, rather than only via `generate_questionnaire_response`'s own self-contained call (which opens and closes its own transaction internally, with no hook for an external ownership check in between).

### 6.1b A narrowly scoped M005 extract-method refactor — investigated directly, confirmed low-risk, authorised by the Architect's own instruction

Reading `questionnaire/services.py` directly (not assumed) confirms this separation already exists, structurally, inside M005's own code — it only needs to be exposed, not invented:

```python
@transaction.atomic
def _persist_response(organisation, question, *, interpretation, interpretation_record,
                       outcome, outcome_warnings, grounding_snapshot, draft, drafting_record, actor) -> QuestionnaireResponse:
    ...  # creates exactly one QuestionnaireResponse + fires EVENT_QUESTIONNAIRE_RESPONSE_GENERATED, nothing else

def generate_questionnaire_response(organisation, question, *, actor, interpretation_gateway=None, drafting_gateway=None) -> QuestionnaireResponse:
    ...  # interpret (AI call 1) -> record EVENT_QUESTION_INTERPRETED (plain create, unconditional, pre-existing, unrelated to this race) -> grounding -> derive_outcome -> build drafting_request -> draft (AI call 2)
    return _persist_response(organisation, question, interpretation=interpretation, ..., actor=actor)
```

`_persist_response` is *already* the sole atomic unit, already receiving a fully-prepared, ready-to-persist bundle as plain keyword arguments, with zero dependency on anything that happens after it. **The proposed refactor is a pure extract-method — rename `_persist_response` to a public `persist_prepared_response` (identical body, identical `@transaction.atomic` decorator, identical behaviour), and wrap the existing "interpret → record event → ground → derive outcome → build drafting request → draft" sequence — already one contiguous, side-effect-bounded block inside `generate_questionnaire_response` today — into its own `prepare_questionnaire_response` function returning the same bundle of values `_persist_response` already takes as arguments.** `generate_questionnaire_response` itself becomes a two-line composition of the two, **with byte-identical external behaviour for every existing caller** — the single-question UI flow, `questionnaire_response_regenerate`, and the M005 golden corpus all call `generate_questionnaire_response` exactly as today and observe no difference whatsoever. This is the "narrowly scoped M005 preparation/persistence separation" the Architect's own instruction authorised investigating — confirmed here, directly, to be a rename-and-extraction of code that is already structured this way, not a new design imposed on M005. **Acceptance requires the unchanged M005 14-case golden corpus and `generate_questionnaire_response`'s own existing test suite to pass byte-identically against the refactored code** — this is the proof the Architect's instruction requires, and this document treats it as a hard gate, not a formality.

**Exact contract, specified field-by-field so FORGE does not have to guess positional arguments or infer behaviour from the diagram alone:**

```python
@dataclass(frozen=True)
class PreparedQuestionnaireResponse:
    """The exact, complete set of values `_persist_response` already
    takes as parameters today, carried as one bundle instead of nine
    separate arguments - field names are identical to `_persist_
    response`'s own existing parameter names (verified by direct
    reading, not renamed for this proposal), so the mapping from this
    dataclass onto `persist_prepared_response`'s body is 1:1 and
    mechanical, not an interpretation."""
    organisation: Organisation
    question: QuestionnaireQuestion
    interpretation: QuestionnaireInterpretation   # ai_platform.questionnaire_interpretation_contracts
    interpretation_record: AIInvocationRecord
    outcome: str                                  # OUTCOME_SUPPORTED/CONFIRM/GAP/NOT_APPLICABLE - unchanged vocabulary
    outcome_warnings: list[str]
    grounding_snapshot: dict
    draft: QuestionnaireDraft                      # ai_platform.questionnaire_drafting_contracts
    drafting_record: AIInvocationRecord
    actor: object                                  # the exact `actor` generate_questionnaire_response's own caller already passes through unchanged


def prepare_questionnaire_response(
    organisation, question: QuestionnaireQuestion, *, actor,
    interpretation_gateway: QuestionnaireInterpretationGateway = None,
    drafting_gateway: QuestionnaireDraftingGateway = None,
) -> PreparedQuestionnaireResponse:
    """Performs exactly the module docstring's existing steps 1-4
    (interpret, record EVENT_QUESTION_INTERPRETED, ground, derive
    outcome) plus building the drafting request and calling step 4's
    draft - i.e. everything generate_questionnaire_response's body
    already does TODAY, up to but not including the final call to
    _persist_response, extracted verbatim, not rewritten. Raises the
    same QuestionnaireInterpretationFailed/QuestionnaireDraftingFailed
    exceptions generate_questionnaire_response already raises, in the
    same circumstances, with the same "nothing QuestionnaireResponse-
    shaped persisted" guarantee - this function creates no
    QuestionnaireResponse under any circumstance, only the pre-existing
    EVENT_QUESTION_INTERPRETED side effect, exactly as today."""


def persist_prepared_response(prepared: PreparedQuestionnaireResponse) -> QuestionnaireResponse:
    """Renamed from `_persist_response`. Its single `prepared` argument
    unpacks, field-by-name, onto exactly the parameter list
    `_persist_response` already has - `persist_prepared_response(p)`
    must behave identically to calling the original
    `_persist_response(p.organisation, p.question, interpretation=
    p.interpretation, interpretation_record=p.interpretation_record,
    outcome=p.outcome, outcome_warnings=p.outcome_warnings,
    grounding_snapshot=p.grounding_snapshot, draft=p.draft,
    drafting_record=p.drafting_record, actor=p.actor)` - same
    `@transaction.atomic` decorator, same body, same
    EVENT_QUESTIONNAIRE_RESPONSE_GENERATED emission, same return
    value. This explicit unpacking mapping is what makes the
    extraction mechanical rather than a reinterpretation - an
    Implementer should be able to generate this function's body by
    literal substitution, not by re-deriving intent from this
    document's prose."""


def generate_questionnaire_response(
    organisation, question, *, actor,
    interpretation_gateway=None, drafting_gateway=None,
) -> QuestionnaireResponse:
    """UNCHANGED public signature, UNCHANGED docstring, UNCHANGED
    external behaviour for every existing caller. New body only:"""
    prepared = prepare_questionnaire_response(
        organisation, question, actor=actor,
        interpretation_gateway=interpretation_gateway,
        drafting_gateway=drafting_gateway,
    )
    return persist_prepared_response(prepared)
```

**Honest note on one pre-existing side effect, unrelated to the race:** `EVENT_QUESTION_INTERPRETED` fires unconditionally inside `prepare_questionnaire_response`, exactly as it already does today, independent of what happens later — so under a genuine double-claim race (§6.1a's scenario), *both* callers' interpretation steps still each fire their own `EVENT_QUESTION_INTERPRETED` event, even though only one ever goes on to have a `QuestionnaireResponse` actually committed. This is pre-existing, unchanged M005 behaviour (its own docstring already states interpretation-succeeding is recorded independent of later failure) and has no bearing on the duplicate-*response* problem this section fixes — stated here for transparency, not left for a reviewer to discover unmentioned.

### 6.1c Atomic claim-check-and-persist — the actual fix

```python
class Meta:
    constraints = [
        models.UniqueConstraint(fields=["import_question"], condition=models.Q(outcome="claimed"), name="one_active_claim_per_import_question"),
        # Permanent, never-expiring - defence in depth alongside the
        # explicit, locked ownership check below, not a substitute for it.
        models.UniqueConstraint(fields=["import_question"], condition=models.Q(outcome="succeeded"), name="one_successful_response_per_import_question"),
    ]
```

```python
def claim_and_process_one_question(import_record, *, actor):
    attempt = claim_next_eligible_question(import_record, actor=actor)  # §6.1's short claim transaction, unchanged
    if attempt is None:
        return None

    # AI work - entirely OUTSIDE any transaction, exactly as
    # generate_questionnaire_response already does internally today.
    prepared = prepare_questionnaire_response(
        attempt.import_question.question.organisation,
        attempt.import_question.question,
        actor=actor,
    )

    try:
        with transaction.atomic():
            # Re-verify OUR claim is still the live, non-expired owner,
            # with a row lock - immediately before persistence, inside
            # the SAME transaction the persist itself runs in. This is
            # requirement 2 (verify ownership immediately before
            # persistence) and requirement 1's complement: the AI calls
            # already happened above, outside this block entirely.
            current = QuestionnaireBulkResponseAttempt.objects.select_for_update().get(pk=attempt.pk)
            if current.outcome != "claimed" or current.claim_expires_at < timezone.now():
                raise ClaimNoLongerValid()

            # The exact, unmodified M005 persist step, now called FROM
            # INSIDE this transaction - Django nests this as a SAVEPOINT
            # automatically; it is not a second, independent commit.
            response = persist_prepared_response(prepared)

            current.outcome = "succeeded"
            current.resulting_response = response
            current.save(update_fields=["outcome", "resulting_response"])
            # If THIS raises IntegrityError (the permanent constraint),
            # the entire "with" block - including persist_prepared_
            # response's own INSERT above - rolls back as one unit.
            # The losing caller's QuestionnaireResponse is NEVER
            # committed to the database at all. Nothing to delete,
            # because nothing was ever durably written.
    except (ClaimNoLongerValid, IntegrityError):
        # Django's atomic() context manager guarantees the connection is
        # left in a clean, usable state after this exception propagates
        # out of the "with" block (a savepoint rollback when nested, or
        # the whole transaction when top-level) - this is documented
        # Django behaviour, not something this design hand-rolls. A
        # FRESH statement, outside the rolled-back block, now records
        # the failure honestly.
        QuestionnaireBulkResponseAttempt.objects.filter(pk=attempt.pk, outcome="claimed").update(
            outcome="failed", failure_category="lost_claim_race_or_expired"
        )
        return None
    return attempt
```

### 6.2 Why this satisfies each requirement of C6

1. **Interpretation and drafting outside any transaction:** unchanged — `prepare_questionnaire_response` performs both AI calls exactly as `generate_questionnaire_response` already does, entirely before the `with transaction.atomic()` block above ever opens.
2. **Claim ownership verified immediately before persistence:** the `select_for_update()` + outcome/expiry check is the literal first thing inside the transaction, before `persist_prepared_response` is ever called.
3. **Atomic persist of the response + claim finalisation together:** both writes are inside one `with transaction.atomic()` block — Django/Postgres guarantee they commit together or not at all.
4. **Stale claim holders prevented from persisting:** a stale/expired/already-reclaimed holder's `select_for_update()` check raises `ClaimNoLongerValid` *before* `persist_prepared_response` is ever invoked — no response is even attempted, let alone created, for a claim already known to be dead.
5. **Never deletes unrelated or human-created drafts:** there is no delete-on-recovery code path left in this design *at all* — a losing attempt's response was never committed in the first place, so there is nothing to clean up, manually or otherwise, and therefore nothing that could ever be mistargeted at an unrelated row. Round 2's orphan-draft-sweep logic is removed entirely by this correction, not merely left in place as a backstop — it existed to solve exactly the detect-and-delete problem this redesign eliminates structurally, and retaining it would be both dead complexity and a residual risk of the exact kind requirement 5 warns against.
6. **PostgreSQL uniqueness errors handled via correct transaction/savepoint behaviour:** the `IntegrityError` from the permanent constraint is caught *outside* the `with transaction.atomic()` block, exactly as Django's own documentation requires for continued use of the connection afterwards — the failure-recording `.update()` call that follows is a genuinely fresh statement against a clean transaction state, not a write attempted against an already-aborted one.
7. **Correctness under claim expiry, concurrent execution, crashes and retry:** the only failure window remaining is a crash *before* `claim_and_process_one_question` ever reaches its `with transaction.atomic()` block (i.e., during the AI calls themselves) — in that case nothing is persisted at all, the claim row remains `claimed` until it expires, and the next call reclaims and retries cleanly; this is the ordinary, already-covered expiry/reclaim path, not a new case. §9's test matrix is revised accordingly: (a) two genuinely concurrent callers racing for the same question — assert exactly one `QuestionnaireResponse` ever exists afterward, at the database level, not merely at the end of one test's own view of it; (b) a claim artificially expired mid-AI-call via test instrumentation, followed by a reclaim and a second concurrent finaliser — same assertion; (c) a simulated crash between the claim and the AI calls completing — assert the claim expires and is cleanly reclaimed with zero `QuestionnaireResponse` created in the interim.

### 6.2a Consolidated regression gates — all required, none optional

This correction touches M005's own file for the first time in this amendment (§6.1b's extract-method refactor), so the full acceptance bar for the eventual Work Order/implementation PR is stated here explicitly, in one place, rather than left scattered across prior sections for a reviewer to assemble themselves:

1. **The unchanged M005 14-case golden corpus** (`questionnaire/eval/golden_corpus.py`/`harness.py`) passes byte-identically against the refactored `questionnaire/services.py` — zero diff to the corpus itself, zero behavioural difference in its results.
2. **Every existing M005 test** that exercises `generate_questionnaire_response`, `accept_questionnaire_response`, `edit_questionnaire_response_text`, or `_initial_current_answer_text`'s own existing test file(s) passes unmodified — proving the extract-method refactor changed nothing these tests can observe.
3. **Claim expiry and concurrency** — §6.2 point 7's three named scenarios (genuine two-caller race, expiry-during-active-call followed by reclaim, crash before the atomic block is ever reached), each asserting at the database level that exactly one `QuestionnaireResponse` exists for the contested question afterward, never a transient second one visible to any reader at any point.
4. **Tenant isolation** — a bulk-trigger request for one organisation's import can never claim, process, or read any `QuestionnaireImportQuestion`/`QuestionnaireQuestion`/`QuestionnaireResponse`/`QuestionnaireBulkResponseAttempt` row belonging to a different organisation; every query in `claim_next_eligible_question`/`claim_and_process_one_question` is scoped by an explicit `organisation=` filter or a traversal through an already-validated `import_record`, per §8's existing tenant-scoping requirement, now also asserted specifically against the new claim/fencing code path, not only the ingestion path M009A already proved this for.
5. **Accepted-response immutability** — a `QuestionnaireResponse` already `accepted` (by a human, via the existing, unmodified `accept_questionnaire_response`) is never selected as eligible for a new claim (§5's eligibility query already excludes it structurally), and no code path introduced by this correction ever calls `persist_prepared_response` or any write against an `accepted`/`superseded` response — the model's own `PROTECTED_WHILE_DRAFT_FIELDS` guard remains the enforcement backstop, unchanged, but this must also be asserted as an explicit, named test (claim a question whose linked `QuestionnaireQuestion` already has an `accepted` response from a human; assert it is never selected, and that the accepted response's every field is byte-identical before and after the bulk run completes).

### 6.3 Readiness recheck, unchanged in placement

Readiness (§3.3) is still rechecked inside the claim step, before the claim is created — if readiness has been lost, `claim_next_eligible_question` returns `None` immediately, exactly as if nothing were eligible, and the batch ends cleanly rather than claiming work it should not start.

Call A (interpret) continues to receive the full 29-key catalogue (§2.2) — no new fact-access design is needed beyond what M005 already has; this amendment's "narrow, typed, bounded" requirement is satisfied by the catalogue's existing size and the existing schema-constrained response contract, not by inventing a new retrieval layer.

## 7. Modular responsibility map

| Concern | Owning module | Status |
|---|---|---|
| Readiness computation | `entitlements/metrics.py` (`get_security_foundations_completion`) | Existing, reused unmodified |
| Readiness gate/threshold/blocker contract | `security_baseline/readiness.py` (new, thin) | New — §3.1–3.2 |
| Readiness pipeline-level enforcement | extends `questionnaire.upload_handler.QuestionnaireUploadSizeGuardMiddleware`'s `process_view` hook | New — §3.3, per C3 |
| Question-level answerability | `questionnaire/bulk_orchestration.py` (new) | New — §3.5, per C1 |
| CSV secure ingestion | `questionnaire/csv_import.py` (new, mirrors `xlsx_extraction.py`'s shape) | New — §4.1 |
| CSV export + formula-injection defense | `questionnaire/csv_export.py` (new) | New — §4.2, M009D, per C4 |
| Security gate / scanning / storage | `questionnaire/security_gate.py`, `scanner.py`, `import_storage.py` | Existing, reused unmodified |
| Fact catalogue / grounding | `questionnaire/catalogue.py`, `grounding.py` | Existing, reused unmodified |
| Deterministic outcome | `questionnaire/outcome.py` | Existing, unmodified, untouchable without separate M005 review |
| AI interpretation/drafting | `ai_platform.questionnaire_interpretation_orchestration`, `.questionnaire_drafting_orchestration` | Existing, reused unmodified |
| Prepare/persist decomposition | `questionnaire/services.py` (`prepare_questionnaire_response`/`persist_prepared_response`, extracted from the existing `generate_questionnaire_response`/`_persist_response`) | Modified — §6.1b, per C6, pure extract-method, zero behaviour change, golden-corpus-proven |
| Default answer-text composition | `questionnaire/services.py::_initial_current_answer_text` | Existing, unmodified — this amendment's §5 does not touch it |
| Enriched answer-text composition (SUPPORTED/CONFIRM) | `questionnaire/bulk_orchestration.py::compose_detailed_safe_answer_text`, its own direct write path, its own `answer_composition_method` provenance field, and a new, distinctly-named `ActivityEvent` type (additive migration) | New — §5, per C5 and B, requires zero M005 change |
| Bulk orchestration/attempt ledger/claim mechanism | `questionnaire/bulk_orchestration.py` (new) | New — §6, per C2 |
| Review (exception handling) | out of this amendment's scope | M009C |
| Export send-ready predicate | `questionnaire/csv_export.py` | New — §4.2, M009D |

No concern appears in two places on this list. No existing module's responsibility is widened beyond what it already does, with one named, Architect-authorised exception: `questionnaire/services.py` gains the extract-method decomposition in the row above — a structural rename/extraction, not a widening of what the module is responsible for (it still owns exactly the same pipeline, now exposed in two callable pieces instead of one). `questionnaire/bulk_orchestration.py` is deliberately one module owning three related-but-distinct concerns (answerability, answer-text enrichment, the claim ledger) rather than three separate files, because all three operate on the same `QuestionnaireBulkResponseAttempt` row's lifecycle and splitting them would scatter one object's state machine across files for no benefit — this is a Work Order-stage file-layout detail, not an architectural claim.

## 8. Milestone decomposition and Product Authority decision points

- **M009A** — CLOSED GREEN. Unaffected.
- **This amendment** — architecture only. No code.
- **M009B (revised)** — readiness gate enforcement; CSV secure ingestion (reusing M009A's gate/scanner/storage); bulk orchestration against the existing, unmodified M005 engine; one-question-then-bounded-batch delivery (unchanged from the superseded draft's own vertical-slice strategy); durable per-attempt status. **Explicitly excludes** any export capability and any send-ready claim — M009B produces reviewable draft responses only.
- **M009C** — per-question exception review UX, approved/edited history, staleness checks.
- **M009D** — CSV export, formula-injection hardening, send-ready predicate, deterministic ordering. XLSX write-back is a separately-scoped increment *within* M009D, gated on its own re-confirmation, not assumed to ride along automatically.
- **M009E** — full product acceptance: real customer-style flow, regression, independent audit, Customer Zero walk-through, recovery/backup, security/performance.

**Decisions resolved by this correction round** (incorporated directly into the sections cited, no longer open):

- Readiness threshold: **fixed at 100%** (§3.2).
- Export draft path: **removed — no export before `send_ready`, no exception** (§4.2).
- Imported `answer` column semantics: **read-only provenance, never overwritten or reprocessed** (§4.1).
- Export outcome/review_status mapping: **moot — these fields are not exported by default at all** (§4.2).

**Product Authority decisions still requiring adjudication before a Work Order can be written** (everything else in this amendment is Gunnar's to resolve at Work Order stage):

1. Whether §5's revised, grounding-fact-based SUPPORTED/CONFIRM answer-composition proposal is approved, deferred, or needs further revision — distinct from the original (now-superseded) single-control-sentence version this corrects.
2. The daily per-organisation AI-invocation ceiling, `DEFAULT_BULK_BATCH_SIZE`, and `CLAIM_TTL` numeric values (§6) — explicitly NOT set by this document; must be derived from a real, measured request-timeout and AI-latency figure at Work Order/implementation stage, never guessed (restated as a standing instruction, not only a one-time decision).

## 9. Security controls and STOP conditions carried forward unchanged

Every security control already specified in the superseded M009B draft Work Order (tenant scoping via `get_member_organisation_or_404`, prompt-injection inheritance from M005's existing, verified defenses, per-question failure isolation, no batch-spanning transactions, immutability of accepted/superseded responses) applies identically here and is not restated in full — this amendment changes *what gates entry* and *what format flows through*, not the underlying M005/M009A safety mechanisms, which remain exactly as already verified.

**New STOP conditions this amendment adds:**
- Any need to compute readiness from anything other than `get_security_foundations_completion`'s existing, unmodified logic, or any new completion/scoring metric of any kind.
- Any readiness enforcement that relies solely on a view-level check without the pipeline-level `process_view` hook described in §3.3.
- Any concurrency design for the claim mechanism (§6) that is not a database-enforced constraint — an application-level "check then act" sequence, however it is worded, does not satisfy C2.
- Any CSV formula-injection defense that has not been verified by actually opening the exported file in a real spreadsheet application (LibreOffice Calc or equivalent), not only asserted against the raw string.
- Any export reachable before `send_ready` is `True` — there is no authorised exception, decided (§8).
- Any attempt to implement §5's revised answer-text composition before it receives its own separate, explicit acceptance, or any version of it that reads `draft.answer_text` for `SUPPORTED`/`CONFIRM`.
- Any attempt to overwrite, regenerate, or reprocess a CSV row's customer-supplied `answer` value (§4.1), decided.
- Any `DEFAULT_BULK_BATCH_SIZE`/daily-ceiling/`CLAIM_TTL` value chosen without a real, measured runtime figure to ground it (§8, decision 2).
- Any concurrency design in which a `QuestionnaireResponse` is created and durably committed *before* the claim-ownership check that determines whether it should exist — detect-and-delete after a real commit does not satisfy C6, regardless of how quickly the deletion follows.
- Any M005 change beyond the exact extract-method decomposition named in §6.1b — any version that alters `_persist_response`'s/`generate_questionnaire_response`'s existing logic, field set, or event behaviour, or that does not pass the unchanged golden corpus byte-identically, is out of scope and must return to the Architect.
- Any `IntegrityError` handling for the permanent fencing constraint that is caught *inside* the same `transaction.atomic()` block it was raised in, rather than outside it — this leaves the connection in Postgres's "aborted transaction" state for any subsequent statement, which is itself a correctness bug, not a style preference.
- Any composed answer text applied via `questionnaire.services.edit_questionnaire_response_text`, or via any write path that does not also record `answer_composition_method` and fire the dedicated, non-human-attributed activity event (§5).
- Any claim to have tested the composition function's safety without the specific differential fact-containment and non-omission-of-adverse-facts tests named in §5's adversarial corpus.

## 10. Return gate

This document is submitted in DRAFT for Central Architecture and Product Authority review. Pending acceptance:
- PR #104 remains frozen, untouched.
- No M009B/C/D Work Order will be drafted.
- No FORGE dispatch of any kind.
- No DARWIN, production, or Customer Zero changes.

Once accepted and merged, the next action is a revised M009B Work Order (superseding PR #104's draft) incorporating the readiness gate, CSV ingestion, and whichever of §8's decisions the Product Authority has by then resolved — itself requiring its own separate Architect Acceptance before any implementation dispatch.

## 11. Durable engineering-note governance — adopted as standing practice

Per Central Architecture's standing requirement, every PID amendment, Work Order, and implementation PR from this point forward carries a durable GitHub engineering note (a structured PR comment, in addition to this committed document) covering: architecture/PID and baseline SHA; scope, exclusions, and ownership; exact implementation modules and interfaces; engineering decisions and trade-offs; acceptance tests and evidence; independent audit findings; STOP conditions and their resolutions; CI/security conclusions; Architect Acceptance and closure evidence.

For this PR (#105), that note is posted as a PR comment on `https://github.com/maff0000/infosecurs/pull/105`, cross-referencing this document's section numbers for each item, with "acceptance tests and evidence," "independent audit findings," and "CI/security conclusions" explicitly marked not-yet-applicable (this PR is architecture only — no implementation exists to test or audit yet) rather than omitted, so the template's shape is established now and filled in as this milestone actually proceeds through a Work Order and implementation.
