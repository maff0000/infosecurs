# M009 — Amendment 2026-10-13: CSV-First Delivery + Assurance Readiness Gate

**Document status:** DRAFT — Central Architecture reconciliation, for Product Authority and Architect review. Not an implementation authorisation.
**Baseline:** `23fcd6ea21173bb50b4185611c509bad4aacdcfa`
**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Truth-engine PID:** `docs/pids/M005-QUESTIONNAIRE-ASSURANCE.md`
**Disposition of M009A:** CLOSED GREEN, unaffected. Nothing in this amendment reopens, deletes, or reduces the M009A ingestion implementation or `docs/evidence/M009A-CLOSURE.md`.
**Disposition of the draft M009B Work Order (PR #104):** superseded by this amendment once accepted; PR #104 itself is untouched by this document and must be reconciled or replaced under normal governance only after this amendment merges.
**Written by:** Gunnar (Delivery Controller), per Central Architecture's architecture-reconciliation assignment of 2026-10-13. No application code, model, migration, runtime configuration, or dependency was touched to produce this document.

## 0. Decision sought

Ratify a change to the previously accepted M009 delivery sequence: the first *complete end-to-end* Customer Assurance workflow becomes **CSV in, CSV out**, gated by a new deterministic **Security Foundations Assurance Readiness** predicate, before any bulk-answer export capability exists. M009A's XLSX secure-ingestion capability is preserved exactly as closed — not replaced, not silently exposed as a finished answer/export path, not deleted.

Every claim below about what already exists in this codebase was independently verified by direct reading of the real code at this baseline (see §2's citations) — not assumed from the earlier M009B draft.

## 1. Old-versus-new reconciliation

| M009 master PID commitment | Status under this amendment |
|---|---|
| XLSX is the first-class, first-delivered end-to-end format | **Superseded.** CSV becomes the first end-to-end format. XLSX (M009A) remains delivered and closed, but its answer-generation/export path is now scheduled *after* CSV's, not before it. |
| M009B = bulk answer generation, no gating beyond the existing `customer_assurance` tier | **Superseded.** A new Assurance Readiness predicate is now a hard precondition, additional to and independent of package-tier entitlement. The M009B draft in PR #104 did not include this gate and must be revised. |
| Questionnaire interpretation selects from the existing `questionnaire.catalogue` (unchanged) | **Confirmed, not superseded.** Verified: the catalogue is a small (29-entry), deliberately curated, versioned allowlist — not a database-reflection mechanism. This amendment reuses it exactly as-is (§4). |
| M005 truth engine, outcome vocabulary, immutability (`questionnaire.services`/`grounding`/`outcome`) | **Confirmed, not superseded.** Untouched by this amendment; see §2 for the specific, previously under-scoped safeguard this amendment must design around rather than weaken. |
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

### 3.2 Threshold — a Product Authority decision point, not Gunnar's to set

`get_security_foundations_completion` returns a percentage over 18 active rows. Two candidate thresholds, both consistent with "knowledge completeness, not compliance":

- **100% completion** (every row engaged, zero `unknown`s, every `DERIVED_MILESTONE` resolver satisfied) — the cleanest, most defensible interpretation of "enough foundational coverage," and the one this amendment recommends as the default unless the Product Authority wants a softer bar.
- **A lower frozen percentage** (e.g. 80%) — would require the blocker contract (§3.1) to still name every genuinely-unknown item even when the organisation is already "ready," since "ready" would no longer mean "nothing is unknown." This adds real complexity (the gate UI would need to say "ready, but note: 2 items are still unknown" rather than a clean pass/fail) for an unclear product benefit.

**This amendment proposes 100% as the frozen threshold and flags the exact number as the single most consequential open decision in this document** (§8 restates it). Everything else in this section is designed to work identically whichever number is chosen.

### 3.3 Enforcement surface

Every Customer Assurance entry point calls `evaluate_assurance_readiness` and fails closed if `ready` is `False`:

- The upload page's GET (render blockers + links, no file-input control rendered at all — not merely disabled, since a disabled control can still be POSTed to directly).
- The upload view's POST, *before* `import_storage`/the security gate ever reads a byte — mirroring M009A's own `_validate_supersedes_target`-first-statement idiom exactly: readiness is checked before any resource is touched, every time, never trusted from a prior page load.
- Any API entry point equivalent to the above (none exists today beyond the Django views themselves; this is a forward-looking requirement should one be added).
- Before `process_next_bulk_question`/`process_next_bulk_batch` (the M009B orchestration layer, §6) starts *and before each individual question's processing*, not just once at batch start — re-checked per question specifically to satisfy the "recheck before resume/retry" requirement and the "pause safely without erasing history" requirement: if readiness is lost mid-batch, the batch stops cleanly after whatever is already committed, with a clear "paused — Foundations readiness no longer met" status, never a partial-batch error treated as a crash.

Existing historical imports/responses remain fully viewable under existing authorisation rules regardless of current readiness — the gate blocks *new* work, never access to *already-produced* work.

### 3.4 What this is explicitly not

Not a second entitlement tier (the existing `customer_assurance` Monthly+ `ProductArea` gate is unchanged and is checked independently, in addition to readiness — both must pass). Not a compliance score. Not a guarantee any individual question is answerable (a ready organisation can still produce a correct `GAP` for a specific question — the gate is about having *engaged* with the baseline, not about every answer being `SUPPORTED`).

## 4. CSV V1 contract

### 4.1 Import

- UTF-8 only, optional UTF-8 BOM stripped before parsing; any other encoding is a deterministic rejection (not a best-effort re-decode attempt — silent mojibake is worse than a clear error). Standard library `csv` module only, comma delimiter, standard RFC 4180 quoting — frozen, not configurable.
- Required header: `question`. Optional headers: `reference` (a customer-supplied stable identifier for export round-tripping) and `answer` (an existing answer the customer already has, carried as read-only provenance — M009B does not process pre-filled answers, it only generates new ones for rows without one; this is explicitly out of this amendment's own scope to design the exact semantics of — flagged in §8). Duplicate or case-ambiguous headers, an empty required header, or zero data rows are all deterministic rejections, each with its own named, test-pinned error — mirroring M009A's own named-rejection-reason discipline (`security_gate.py`'s per-fixture specific reasons), never one generic "invalid file" message.
- Blank `question` cells are recorded (never silently dropped — the row count must reconcile) but excluded from processing, same disposition shape M009A already uses (`excluded_other`-equivalent) — reusing the `disposition` enum's existing values rather than inventing CSV-specific ones.
- Row order is the durable provenance locator (`extraction_order`, reusing the exact field M009A's `QuestionnaireImportQuestion` already has) — no fuzzy question-text matching for export reconciliation, ever.
- Resource limits, frozen (exact numbers an Implementer must confirm are achievable within the same request-timeout arithmetic M009B's own draft already established in §6 of the superseded WO, not re-derived from scratch): bounded upload bytes (propose reusing M009A's existing 10 MiB ceiling — a CSV this large would already be an unusual customer file), bounded row count, bounded per-field length, bounded total text length. No silent truncation — exceeding any limit is a named rejection, not a quiet cut-off.
- Storage: reuses M009A's `import_storage` module, security gate shape, and ClamAV CLEAN-only requirement unchanged — a CSV is not exempted from malware scanning merely because it is "plain text" (a CSV can still carry a payload if some downstream tool ever opens it as something else, and the scanning cost is negligible). SHA-256 computed and immutably recorded exactly as M009A already does. Filename/MIME are untrusted exactly as M009A already treats them.

### 4.2 Export

- A new, separate, immutable, versioned artifact per export action — never an in-place rewrite of the original upload (mirrors M009A's own "original always immutable" principle, now applied to the export side).
- Deterministic columns, proposed (confirmed against the real `QuestionnaireResponse`/`QuestionnaireImportQuestion` fields, not invented): `reference,question,answer,outcome,review_status`. `reference` from the import row if supplied, else the stable `QuestionnaireImportQuestion.id`. `question` = the original `raw_extracted_text`, byte-identical, in original row order. `answer` = `QuestionnaireResponse.current_answer_text` for the response currently `accepted` for that question (never a `draft` — see "send-ready" below). `outcome`/`review_status` are the internal M005 vocabulary — whether this is appropriate to expose to the end customer verbatim, or whether it needs a separate, simpler external-facing label mapping, is a genuine Product Authority question (§8), not assumed here either way.
- **Formula-injection defense is mandatory and must be verified against a real spreadsheet application, not just unit-tested against the raw string.** Any field beginning with `=`, `+`, `-`, `@`, tab, or carriage return (the known Excel/Sheets active-content trigger set) is prefixed with a single leading `'` (apostrophe) before being written — the standard, widely-documented defusal technique, reversible by the reader if they genuinely need the literal leading character, and inert to every spreadsheet application's formula engine. This applies to every exported text field sourced from untrusted content (`question`, `answer`) — never to `outcome`/`review_status`, which are always one of a small fixed internal enum and can never carry injected content.
- **Strict `send_ready` predicate**, computed, not stored as a flag an operator could accidentally leave stale: every row with a non-blank `question` has exactly one current `accepted` response; every `CONFIRM` outcome has been reviewed and resolved (not left at the generic safe text — resolution is M009C's job, this amendment only states the export-time check); every `GAP` has been reviewed (acknowledged, not silently present); every `NOT_APPLICABLE` has been individually reviewed, not bulk-accepted; no row is missing entirely from the export that was present in the import. An export attempted before `send_ready` either refuses outright or — only if the Product Authority explicitly authorises it (§8) — produces a visibly watermarked "DRAFT — not yet reviewed" artifact, never an unmarked one indistinguishable from a true final export.

## 5. Answer-quality evolution for SUPPORTED/CONFIRM — proposed, not yet approved

The existing safeguard (§2.3) is correct and is not weakened by this proposal. The gap it leaves is real: at bulk scale, a customer receiving the same fixed sentence for every `SUPPORTED` question (regardless of which control it came from) reads as low-quality, even though it is safe.

**Proposed evolution** (explicitly gated on separate review, per the original instruction this amendment restates rather than bypasses): replace the two fixed strings with two **application-owned, parametrised templates**, filled *only* with already-validated, already-resolved, non-AI data:

```
SUPPORTED: "Supported by the organisation's recorded answer to '{control_question_text}': {resolved_state_label}. This reflects recorded security state and does not by itself mean independent verification or attached evidence. Please review before sending."
CONFIRM:   "Not yet confirmed. Recorded state for '{control_question_text}' is {resolved_state_label}, which is not sufficient to answer this requirement definitively. Please review the underlying security state before sending a final response."
```

`{control_question_text}` is the catalogue's own fixed description string for the specific key(s) `derive_outcome` actually used to reach this outcome — never AI-generated text, never a summary, the literal existing string already in `questionnaire.catalogue`/`security_baseline.catalogue`. `{resolved_state_label}` is the literal grounding-snapshot value (e.g. "Yes," "Partial," "Not applicable") — never AI-generated, never paraphrased. **Zero characters of `draft.answer_text` are read for these two outcomes under this proposal either** — the only change from today is that the *application* now composes a slightly richer, still 100%-non-AI sentence instead of one universal sentence. The anti-fabrication guarantee is structurally identical: no model-generated token ever reaches a SUPPORTED/CONFIRM customer-facing answer.

**This is a proposal for separate, explicit Architect/Product-Authority review, not an approval.** Until accepted, M009B implementation uses the existing fixed text unchanged, and the customer-facing limitation ("answers for Supported/Confirm questions use standard wording, not question-specific detail, until a reviewed enhancement ships") is stated plainly in the product UI — never silently implied to already exist.

## 6. M009B orchestration — revised

Per-question lifecycle unchanged in spirit from the superseded draft (one new ledger model, `QuestionnaireBulkResponseAttempt` — success/failure per attempt, justified because a failed `generate_questionnaire_response` call leaves zero trace today; see the superseded WO §3 for the exact shape, carried forward unchanged by this amendment since nothing in the new requirements affects it). Two things change:

- **Readiness is now rechecked at every entry point named in §3.3**, including per-question inside a batch, not only once at batch start.
- **No lease/claim precedent exists anywhere in this codebase (§2.4) — this amendment proposes the concurrency boundary fresh**, reusing the exact mechanism the superseded WO's own §6 already derived independently (eligibility is re-checked inside the same transaction that persists the attempt record, so two racing requests for the same question resolve to exactly one success, never two) — restated here because the new readiness recheck must happen inside that same boundary, not as a separate, racy pre-check.

Call A (interpret) continues to receive the full 29-key catalogue (§2.2) — no new fact-access design is needed beyond what M005 already has; this amendment's "narrow, typed, bounded" requirement is satisfied by the catalogue's existing size and the existing schema-constrained response contract, not by inventing a new retrieval layer.

## 7. Modular responsibility map

| Concern | Owning module | Status |
|---|---|---|
| Readiness computation | `entitlements/metrics.py` (`get_security_foundations_completion`) | Existing, reused unmodified |
| Readiness gate/threshold/blocker contract | `security_baseline/readiness.py` (new, thin) | New — §3 |
| CSV secure ingestion | `questionnaire/csv_import.py` (new, mirrors `xlsx_extraction.py`'s shape) | New — §4.1 |
| CSV export | `questionnaire/csv_export.py` (new) | New — §4.2, M009D |
| Security gate / scanning / storage | `questionnaire/security_gate.py`, `scanner.py`, `import_storage.py` | Existing, reused unmodified |
| Fact catalogue / grounding | `questionnaire/catalogue.py`, `grounding.py` | Existing, reused unmodified |
| Deterministic outcome | `questionnaire/outcome.py` | Existing, unmodified, untouchable without separate M005 review |
| AI interpretation/drafting | `ai_platform.questionnaire_interpretation_orchestration`, `.questionnaire_drafting_orchestration` | Existing, reused unmodified |
| Answer-text composition | `questionnaire/services.py::_initial_current_answer_text` | Existing; §5 proposes a separate evolution, not yet approved |
| Bulk orchestration/attempt ledger | `questionnaire/bulk_orchestration.py` (new) | New — §6 |
| Review (exception handling) | out of this amendment's scope | M009C |
| Export send-ready predicate | `questionnaire/csv_export.py` | New — §4.2, M009D |

No concern appears in two places on this list. No existing module's responsibility is widened beyond what it already does.

## 8. Milestone decomposition and Product Authority decision points

- **M009A** — CLOSED GREEN. Unaffected.
- **This amendment** — architecture only. No code.
- **M009B (revised)** — readiness gate enforcement; CSV secure ingestion (reusing M009A's gate/scanner/storage); bulk orchestration against the existing, unmodified M005 engine; one-question-then-bounded-batch delivery (unchanged from the superseded draft's own vertical-slice strategy); durable per-attempt status. **Explicitly excludes** any export capability and any send-ready claim — M009B produces reviewable draft responses only.
- **M009C** — per-question exception review UX, approved/edited history, staleness checks.
- **M009D** — CSV export, formula-injection hardening, send-ready predicate, deterministic ordering. XLSX write-back is a separately-scoped increment *within* M009D, gated on its own re-confirmation, not assumed to ride along automatically.
- **M009E** — full product acceptance: real customer-style flow, regression, independent audit, Customer Zero walk-through, recovery/backup, security/performance.

**Product Authority decisions requiring adjudication before a Work Order can be written** (everything else in this amendment is Gunnar's to resolve at Work Order stage):

1. The exact readiness threshold (§3.2) — 100% completion, or a lower frozen percentage with the added blocker-while-ready complexity that implies.
2. Whether §5's parametrised SUPPORTED/CONFIRM answer-text proposal is approved, deferred, or rejected outright.
3. The exact `review_status`/`outcome` export-column semantics (§4.2) — raw M005 vocabulary exposed to the customer, or a separate simpler external label mapping.
4. Whether a pre-send-ready "DRAFT — not yet reviewed" watermarked export is authorised at all, or whether export is strictly blocked until `send_ready` (§4.2).
5. The exact semantics of an optional `answer` column present in an imported CSV (§4.1) — read-only provenance only (this amendment's default assumption), or something M009B/C must actively reconcile against a freshly generated answer.
6. The daily per-organisation AI-invocation ceiling and `DEFAULT_BULK_BATCH_SIZE` numeric values (carried forward unchanged from the superseded WO's own §6, still unset pending the real request-timeout figure an Implementer must confirm).

## 9. Security controls and STOP conditions carried forward unchanged

Every security control already specified in the superseded M009B draft Work Order (tenant scoping via `get_member_organisation_or_404`, prompt-injection inheritance from M005's existing, verified defenses, per-question failure isolation, no batch-spanning transactions, immutability of accepted/superseded responses) applies identically here and is not restated in full — this amendment changes *what gates entry* and *what format flows through*, not the underlying M005/M009A safety mechanisms, which remain exactly as already verified.

**New STOP conditions this amendment adds:**
- Any need to compute readiness from anything other than `get_security_foundations_completion`'s existing, unmodified logic.
- Any CSV formula-injection defense that has not been verified by actually opening the exported file in a real spreadsheet application (Excel or Google Sheets), not only asserted against the raw string.
- Any export reachable before `send_ready` is `True`, unless Product Authority decision 4 (§8) explicitly authorises a watermarked draft path.
- Any attempt to implement §5's proposed answer-text evolution before it receives its own separate, explicit acceptance.

## 10. Return gate

This document is submitted in DRAFT for Central Architecture and Product Authority review. Pending acceptance:
- PR #104 remains frozen, untouched.
- No M009B/C/D Work Order will be drafted.
- No FORGE dispatch of any kind.
- No DARWIN, production, or Customer Zero changes.

Once accepted and merged, the next action is a revised M009B Work Order (superseding PR #104's draft) incorporating the readiness gate, CSV ingestion, and whichever of §8's decisions the Product Authority has by then resolved — itself requiring its own separate Architect Acceptance before any implementation dispatch.
