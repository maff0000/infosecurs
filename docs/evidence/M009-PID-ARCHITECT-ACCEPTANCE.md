# M009 — Master PID Architect Acceptance

**Architect:** Central Architecture / Project Architect
**Acceptance date:** 2026-10-10
**PR:** #101
**Architecture baseline:** `13d39be071651e523a1f1821082d596ac30b9bdd`
**Accepted PID candidate head before this record:** `25e74d9f86d16b1a25537242ffd6921b435646f6`
**Decision:** **ARCHITECT ACCEPTED**

## Architecture outcome

M009 is approved as a secure document-processing, orchestration, review and export layer around the existing M005 questionnaire truth engine.

M009 does not create a second questionnaire truth engine.

The existing M005 interpretation, grounding, deterministic assurance outcome, drafting, review and immutable-history architecture remains authoritative.

## Accepted product model

Security Foundations establishes and maintains the organisation's security truth.

Customer Assurance converts that truth into recurring operational value:

uploaded customer questionnaire
→ secure extraction
→ deterministic source provenance
→ existing grounded-answer engine
→ exception-first review
→ truthful accepted responses
→ completed send-ready questionnaire.

The customer reviews exceptions rather than manually re-entering the organisation's security programme into customer spreadsheets.

## Accepted format strategy

XLSX is the mandatory first-class format.

The originally uploaded workbook is immutable.

Completed XLSX output is a separately-versioned copy populated using deterministic source/answer-cell provenance.

DOCX follows only after the XLSX provenance contract is proven.

PDF is best-effort structured/text extraction with generated output where appropriate.

OCR is out of scope.

## Accepted truth and review rules

Persisted questionnaire outcomes remain:

- SUPPORTED
- CONFIRM
- GAP
- NOT_APPLICABLE

No numeric AI confidence score becomes security truth.

Initial M009 bulk acceptance is authorised only for SUPPORTED responses.

CONFIRM requires resolution.

GAP requires explicit review but may be accepted as a truthful final external answer.

NOT_APPLICABLE requires explicit individual review in initial M009.

Send-ready status is determined by a whole-questionnaire deterministic readiness predicate.

No unresolved, failed, unanswered or unreviewed answerable item may silently disappear from a send-ready export.

## Accepted security architecture

Uploaded questionnaires are untrusted artifacts.

A mandatory security gate precedes business/document semantic parsing and question extraction.

The gate may perform only bounded structural/container inspection needed for type and safety validation.

Tenant isolation, immutable originals, content-based type validation, size and expansion limits, archive/path-traversal defence, macro/external-link/formula controls, malware scanning abstraction and private opaque storage are binding requirements.

Questionnaire content is data, never AI/system authority.

## Accepted provenance and history architecture

Source provenance and grounding provenance remain separate and mandatory.

Source provenance identifies where the external question came from.

Grounding provenance identifies what Infosecurs truth produced its response.

Accepted historical responses remain immutable.

M009 may surface staleness by deterministically rebuilding the current grounding state for the historical response's validated keys and comparing it to the historical grounding state.

Regeneration creates a new response attempt.

## Accepted evaluation architecture

The existing M005 14-case golden corpus remains unchanged as the single-question truth-engine regression oracle.

M009 adds a separate evaluation layer for:

- file ingestion;
- extraction accuracy;
- source provenance;
- document order;
- bulk failure isolation;
- prompt-injection resistance;
- tenant isolation;
- write-back fidelity;
- original-artifact preservation;
- formula safety;
- export readiness;
- re-upload/version history;
- stale-response handling.

The M005 corpus proves truth-engine equivalence.

The M009 corpus proves safe scaling of that engine across real questionnaire artifacts.

## Governance decision

**M009 MASTER PID IS ARCHITECT ACCEPTED.**

This acceptance authorises M009A Work Order preparation only after PR #101 is merged.

It does not authorise implementation directly.

Implementation still requires the normal governed chain:

PID
→ Git-tracked Work Order
→ Delivery Controller
→ Implementer
→ Independent Audit
→ PR
→ Architect Acceptance
→ Merge
→ Closure.
