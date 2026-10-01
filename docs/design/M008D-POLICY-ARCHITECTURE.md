# M008D — Deterministic Policy Architecture (Design Proposal)

**Status:** DESIGN ARTEFACT — not implemented. Sample artefacts produced
under this proposed architecture are in `M008D-SAMPLE-POLICY-A.md`,
`-B.md`, `-C.md` (rendered to PDF separately) and
`M008D-POLICY-TRUTH-MATRIX.md`.

## 1. What an excellent SME policy actually is

A policy an SME owner can read in one sitting, understand without a
security background, hand to a staff member or a customer without
embarrassment, and that never says something is true that isn't. It
separates three kinds of sentence, always distinguishably:

- **CURRENT_CONFIRMED_PRACTICE** — what the customer told us is actually
  happening today.
- **NORMATIVE_REQUIREMENT** — what the organisation is committing to do,
  as policy, regardless of current practice.
- **GAP_OR_FUTURE_ACTION** — what needs to happen and hasn't yet.

The existing eight section keys (`purpose_and_scope`,
`responsibilities_and_governance`, `access_and_authentication`,
`devices_protection_and_updates`, `information_handling_and_backup`,
`workplace_and_remote_working`, `security_incidents_and_reporting`,
`review_approval_and_document_control`) are preserved exactly — this
redesign changes *how each section's content is produced*, not its name
or its place in the document.

## 2. Composition pipeline (replacing the one-shot generation call)

```
confirmed baseline/profile/governance facts (read-only projection)
        │
        ▼
versioned curated clause library (Git, not a DB table — like
security_baseline/catalogue.py and risk_register/methodology.py already
are)
        │
        ▼
deterministic clause selection (facts → which clauses apply, which
variant of each clause's wording)
        │
        ▼
assembled PolicyVersion.sections (same JSON shape as today)
        │
        ▼
existing ReportLab renderer (policy/pdf.py) — UNCHANGED
```

Zero LLM calls in the default path. The existing `policy.services.
generate_policy_draft`'s one `LiteLLMGateway` call becomes a *non-default,
separately authorised exception path* (M008D §D3.4) — e.g. for a future
Monthly+ "ask AI to help phrase this clause" assist — never the routine
Foundation-tier default.

## 3. Clause library shape (proposed, illustrative — not final wording)

Each clause: `clause_id`, target `section_key`, applicability condition
(a boolean function over confirmed facts), parameterised wording template,
and a `truth_classification` per sentence/fragment it contributes.

Example (illustrative, not final copy):

```
clause_id: "access.mfa_user_all_yes"
section_key: "access_and_authentication"
applies_when: BaselineAnswer(mfa_user_accounts) == YES
truth_classification: CURRENT_CONFIRMED_PRACTICE
template: "Multi-factor authentication is enabled for all staff accounts."

clause_id: "access.mfa_user_partial"
section_key: "access_and_authentication"
applies_when: BaselineAnswer(mfa_user_accounts) == PARTIAL
truth_classification: mixed — one CURRENT_CONFIRMED_PRACTICE sentence +
  one GAP_OR_FUTURE_ACTION sentence, never merged into one ambiguous
  claim
template: "Multi-factor authentication is enabled for some staff
  accounts. Extending this to all accounts is an identified action."

clause_id: "access.mfa_user_commitment"
section_key: "access_and_authentication"
applies_when: always (every organisation gets this clause regardless of
  current state)
truth_classification: NORMATIVE_REQUIREMENT
template: "All staff accounts must use multi-factor authentication where
  the platform supports it."

clause_id: "access.mfa_user_unknown"
section_key: "access_and_authentication"
applies_when: BaselineAnswer(mfa_user_accounts) == UNKNOWN
truth_classification: GAP_OR_FUTURE_ACTION (explicit, not silent)
template: "Whether multi-factor authentication is enabled for all staff
  accounts has not yet been confirmed. This should be established and
  addressed."
```

One clause per `(control, answer-state)` combination, selected
deterministically — never an LLM deciding which clause "sounds right."
Every clause's wording is reviewed and versioned exactly like
`security_baseline.catalogue.CATALOGUE_VERSION` already is.

## 4. Provenance

Every `PolicyVersion` stores the exact clause-ID set selected and the
template/methodology version used (M008D §D3.5's additive `generation_
source` enum member — `template`/`deterministic`, alongside the existing
`ai`/`manual`). The clause-to-source matrix (below) is this provenance,
rendered human-readably for review, not a separate invented concept.

## 5. Immutability — unchanged

Existing `PolicyVersion.save()` guard, approval/review lifecycle, PDF
rendering, and tenant-scoped download/history all stay exactly as today.
A new policy after facts change is a new draft/version, never an
in-place rewrite — unchanged rule.
