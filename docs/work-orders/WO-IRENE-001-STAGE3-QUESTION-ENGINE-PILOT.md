# Work Order: IRENE-001 — Reusable Question Engine, Stage 3 Pilot

**Parent authority:** `docs/pids/PID-IRENE-STAGE3-QUESTION-ENGINE-AMENDMENT.md`,
itself amending `docs/pids/M010-IRENE-MASTER-PID.md`.

**Base SHA:** `4b241fd2357a628d6b84699c66071c2d79a46a33` (current exact `main`).

**Status:** Central Architecture reviewed this Work Order and its
companion PID Amendment at reviewed head
`8a5b5ecdb7a337d5c4a2fa0c94cddcd3c0db42fe` — architecture direction
accepted in principle, document corrections required before Architect
Acceptance. D1–D3 (PID Amendment) are now resolved, binding decisions,
not open defaults — see §1a below and the targeted edits throughout this
document. R1–R4 are the corresponding Work Order refinements, specified
in §1a and woven into the relevant increment sections.

**Environment:** disposable only, throughout every increment below. No
part of this Work Order touches the persistent Beta stack
(`/srv/infosecurs` / `infosecurs-relocation`). M010 itself (and therefore
IRENE) is confirmed undeployed there — this Work Order does not change
that.

## 0. What this Work Order implements

A bounded pilot proving a reusable formula: IRENE presents, guides,
explains, and progresses the user; the underlying application (existing
`OrganisationProfile`/`KeyAsset` data, existing
`organisations/guided_journey.py` stage logic, existing entitlements)
remains sole owner of canonical data, validation, entitlements, and
consequences. Reference section: Stage 3 "Your Technology & Data,"
questions 3.1–3.7 (10 `OrganisationProfile` fields + a Key Assets
link-out).

## 1a. Binding refinements from Central Architecture's PR #128 review (R1–R4)

These supersede this Work Order's earlier "default position" wording
wherever referenced below, and apply across both increments.

**R1 — Generic AI explanation.** The typed question context passed into
the existing AI gateway must contain: the approved question wording, the
permitted answer labels, stable section/question identifiers, the
catalogue version, and a minimised, authorised business context — never
the raw `OrganisationProfile` row or any field beyond what the question
being explained needs. Any AI request/prompt change this requires is
itself versioned, without altering `ai_platform.gateway.LiteLLMGateway`'s
generic architecture. The model is never given write authority over
canonical state and never invents an answer — it explains only from the
server-supplied context, consistent with Architecture invariant 5.

**R2 — Guarded canonical saves.** The new save path (§3.2) must provide,
and Increment 2's tests must prove: exact canonical validation (the same
field-level validation the existing `OrganisationProfileStage3Form`
already enforces, not a looser IRENE-specific copy); field-scoped
updates (`update_fields=[...]`, never a full-instance save); atomic
grouped submissions (`transaction.atomic`, all-or-nothing for a
multi-field submit); safe handling of an organisation's first-ever Stage
3 submission (no profile row yet); stale-write detection (reject a
submission made against an out-of-date version, per D2); idempotent
receipts (a retried identical submission must not double-apply or error);
and preservation of whatever audit/history behaviour the existing manual
save path already produces. Both a same-field concurrent-edit scenario
(two writers racing on the same Stage 3 field — the loser must be
rejected via stale-write detection, not silently overwritten) and a
different-field concurrent-edit scenario (one writer on a Stage 3 field,
one on an unrelated field/stage on the same row — both must succeed,
neither clobbers the other) must be proven as tests, not asserted.

**R3 — Progress integrity.** `organisations.guided_journey.current_guided_stage()`
remains the one and only stage-completion resolver — the IRENE adapter
calls it, never re-derives or shadows it. Question-level state shown
inside IRENE is read from the existing authoritative `OrganisationProfile`
field data only. A field's default/unset value (e.g. a "Not confirmed"
default) must never be presented or recorded as an explicitly-reviewed
answer without positive evidence that the customer actually reviewed and
submitted it through either save path — no inferring confirmation from
the mere presence of a default.

**R4 — Product experience.** The customer must be able to answer and save
the actual Stage 3 questions from inside the real IRENE interface, not a
read-only preview that hands off elsewhere to save. Increment 2's
end-to-end demonstration (§3.11) must prove, in a real browser: genuine
in-IRENE answer/save; on-demand AI explanation — genuine, not
mocked/stubbed — but only once the separate operating approval for the
disposable real-model test (§3.7) has been obtained, never before; a
page refresh that preserves authenticated state and saved answers; a
pause-then-resume of the journey (leave mid-section, return later, resume
at the correct question/state); parity with the existing manual Stage 3
page per §3.8's parity gate; and the second-section integration proof
touching zero lines of Increment 1's core.

## 1. Shared conventions, binding across both increments below

- **No second questionnaire database.** Every question/section
  registration entry describes and reads/writes through the *existing*
  `OrganisationProfile`/`KeyAsset` models — it never creates a parallel
  answer store.
- **No second "is this stage complete" definition.** Every completion
  check calls `organisations.guided_journey.current_guided_stage()` (or
  the specific helper it already exposes for Stage 3), never
  re-implements the logic.
- **Registry pattern:** combine the two existing idioms already proven in
  this codebase — the plain-dict allowlist + tenant-verified resolver
  style of `security_tasks/source_registry.py` and `irene/tools.py`'s
  `TOOL_REGISTRY`, and the strict-manifest-validation style of
  `irene/skill_loader.py` (required keys, no dynamic import/exec,
  path-traversal-rejected references). The new section/question registry
  must be a Python-reviewed allowlist, never database-configurable or
  model-name-driven at runtime.
- **Versioning:** per Amendment D2, two independently-versioned axes —
  stable section/question identifiers plus a versioned question
  catalogue (following the `CATALOGUE_VERSION`-constant convention
  already used by `security_baseline/catalogue.py`, `questionnaire/catalogue.py`,
  and `risk_register/methodology.py`), and a *separately* versioned
  generic interaction contract. Not a single shared version string.
  Server-issued versions are checked on every answer submission; stale/
  incompatible submissions fail safe (rejected, never silently merged).
  No registry-metadata table in Increment 1; see R2 for the Increment 2
  provenance-mechanism constraint.
- **Explain-this dispatch:** intent-code based only, via the existing
  `IntentCode` enum and `skill_router.select_skill()` — never free-text
  matching. Reuse or extend `EXPLAIN_CONTROL`, do not invent a parallel
  dispatch mechanism.
- **AI gateway discipline:** every real-model call goes through
  `ai_platform.gateway.LiteLLMGateway.ask_adviser()` exactly as it exists
  today — generic model-alias resolution via `optional_env`, server-generated
  `model_trace_id`, no model-asserted trace ID, no AI write path to
  canonical state without an explicit human confirm step. No new AI
  integration code outside this existing gateway class.
- **`IRENE_ADVISER_MODE_ENABLED` stays `false`** in every environment this
  Work Order's own CI/disposable setup creates by default. It is turned
  on only inside the one disposable, numerically-approved real-model test
  environment described in Increment 2, and only for the duration of that
  test.
- **Save-path discipline:** any new write path onto `OrganisationProfile`
  must use field-scoped persistence (e.g. `update_fields=[...]`), never a
  full-instance `save()`, given the model has no optimistic-concurrency
  version field. One saved field must never overwrite another stage's
  already-loaded data on the same row — this must be demonstrated, not
  assumed, in Increment 2's tests (two concurrent writers, one to a Stage
  3 field, one to a different stage's field on the same `OrganisationProfile`
  row).

## 2. Increment 1 — Generic question engine, contract, and registry

### 2.1 Scope
The reusable core: a typed, versioned, allowlisted section/question
contract and registration mechanism, a generic IRENE question presenter,
and the on-demand explanation interface — built with **zero knowledge of
Stage 3 specifically**. Nothing in this increment may import or reference
`organisations.views.STAGE3_TECHNOLOGY_DATA_FIELDS` or any Stage-3-specific
name.

### 2.2 Exact modules/files and interfaces
- New module, e.g. `irene/question_engine/contract.py`: typed dataclasses/
  Protocols for a `SectionDefinition`, `QuestionDefinition`, and the four
  declared adapter capability types named in the Architecture decision
  (single-choice, grouped-independent-answer, linked-repeatable-record,
  and the `delegated_workflow` shape approved for Key Assets under
  Amendment D3).
- New module, e.g. `irene/question_engine/registry.py`: the
  allowlist-registration mechanism (mirroring `source_registry.py`'s
  plain-dict-plus-resolver shape and `skill_loader.py`'s manifest-validation
  rigor). Must reject unregistered/unknown section codes outright, never
  silently.
- New generic presenter/view code reusing the existing `irene/` modal
  shell (`irene/orchestration.py`, `irene/views.py`) — extended, not
  duplicated, to render whatever a registered `SectionDefinition` declares,
  with no section-specific branching in the presenter itself.
- Explanation interface: extend `irene/skill_router.py`'s existing
  `_SKILL_BY_INTENT` wiring generically (keyed by intent code, not by
  section), reusing `EXPLAIN_CONTROL` or a declared sibling intent.

### 2.3 Existing services reused, unmodified
`irene/tools.py` (`TOOL_REGISTRY`), `irene/skill_loader.py`,
`irene/skill_router.py`, `irene/models.py` (`IntentCode`),
`irene/orchestration.py`, `ai_platform/gateway.py`
(`LiteLLMGateway.ask_adviser`), `entitlements/capabilities.py` (`irene`
capability code), `config/settings.py` `IRENE_*` flags — all consumed as
they exist today, none modified in ways that change Stage 1/2/4+ behaviour.

### 2.4 New schema/migrations
None required for this increment if version-stamping is deferred to
Increment 2's adapter-specific write path. If Increment 1's contract
needs its own lightweight registry-metadata table (e.g. to record which
section/question versions exist), it must live in the `irene` app, not a
new app, and must not touch `OrganisationProfile`/`KeyAsset` schema at
all.

### 2.5 Preconditions and dependency order
None — this increment has no dependency on Stage 3 specifics and should
be implemented and tested first, exactly to prove it is genuinely generic
before Increment 2 exercises it.

### 2.6 FORGE implementation instructions
Dispatch as an isolated worktree per this PID/WO's standing FORGE
discipline. The Engineer must not reference Stage 3 field names, the
`organisations` app's models, or `key_assets` anywhere in this increment's
diff — a presence of any such reference is itself a scope violation to
report, not quietly fix.

### 2.7 Tests and evaluation fixtures
Unit tests using a **synthetic, throwaway** section/question definition
(not Stage 3) to prove: registration rejects malformed/unknown entries;
the generic presenter renders each of the four declared capability types
correctly from the fixture alone; the explanation interface dispatches by
intent code only.

### 2.8 Independent audit acceptance gates
Confirm, by direct inspection, zero Stage-3-specific or
`organisations`-app-specific references anywhere in this increment's
files. Confirm the registry genuinely rejects an unregistered section
code (not just that a registered one works).

### 2.9 STOP conditions specific to this increment
STOP and return to Architect if proving genericity requires touching
`irene/orchestration.py`'s existing Foundations-guide behaviour in a way
that could change Stage 1/2/4+'s current conversation flow.

### 2.10 Durable evidence
A new evidence doc (`docs/evidence/IRENE-001-INCREMENT-1-GENERIC-ENGINE.md`)
recording the fixture-based test results and the independent audit's
genericity-check findings.

### 2.11 Customer Zero / browser verification
Not required for this increment in isolation (no real section exists
yet) — deferred to Increment 2's end-to-end demonstration.

### 2.12 CI/security/regression requirements
Full existing `ci/unit` + `ci/integration` suite green, no regression to
any existing IRENE/Foundations-journey test.

## 3. Increment 2 — Stage 3 adapter, guarded save path, Explain-this, disposable real-model test, end-to-end demonstration, Integration Guide, second-section proof

### 3.1 Scope
Everything Stage-3-specific, plus the two mandatory proofs: a real
end-to-end browser journey through actual IRENE, and a second small
section/fixture registered without touching Increment 1's core.

### 3.2 Exact modules/files and interfaces
- New Stage 3 adapter module (e.g. `irene/question_engine/adapters/stage3_technology_data.py`)
  implementing Increment 1's contract against the existing 10
  `STAGE3_TECHNOLOGY_DATA_FIELDS` and declaring Key Assets (3.7) as the
  `delegated_workflow` capability approved under Amendment D3, not a
  duplicated inline Key Assets UI. The adapter's authorisation check for
  this delegated path must additionally enforce the existing `security`
  entitlement, on top of the `irene`+`foundations` pair already required
  to reach IRENE/Stage 3 at all (D1).
- New guarded save path (e.g. `organisations/services.py`, net new file —
  none exists today) mirroring `governance.services`'s pattern
  (tenant-membership-checked, `transaction.atomic`, domain error on
  violation), but writing with `update_fields` scoping per §1's save-path
  discipline, and meeting R2 in full: exact canonical validation,
  field-scoped updates, atomic grouped submissions, safe first-submission
  handling, stale-write detection against D2's server-issued versions,
  idempotent receipts, and preserved audit behaviour. The existing
  `organisation_stage3_technology_data` view's own direct-save path is
  left untouched/unmodified — this new path is additive, used only by the
  IRENE adapter.
- Section/question identifiers and a versioned question catalogue, plus
  the separately-versioned generic interaction contract from Increment 1
  (per D2) — not a single shared version string — stamped onto whichever
  record the guarded save path writes.
- Explain-this wiring for questions 3.1–3.6 via the existing
  `EXPLAIN_CONTROL` intent (or a declared sibling), dispatched with the
  typed question context specified in R1 (approved wording, permitted
  answer labels, stable identifiers, catalogue version, minimised
  authorised business context) — content sourced from server-side
  canonical definitions only, no model-generated option text anywhere,
  per Architecture invariant 5.
- A second, deliberately small section/fixture (e.g. a 2-3 field synthetic
  section, or a genuinely small real section if one is identified as
  low-risk) registered purely through Increment 1's documented contract,
  written by whoever implements the Integration Guide, as the mandatory
  "second section without touching IRENE core" proof.

### 3.3 Existing services reused, unmodified
`OrganisationProfile`, `KeyAsset`, `organisations.guided_journey.current_guided_stage()`
(per R3, the sole stage-completion resolver — never re-derived),
`entitlements.capabilities`/`decorators.require_capability` (per D1,
composed as `irene`+`foundations` for the Stage 3 adapter and
additionally `security` for the delegated Key Assets path — independently
rechecked on every read/explain/save/resume, not cached),
`ai_platform.gateway.LiteLLMGateway.ask_adviser`. The existing
`organisation_stage3_technology_data` view, `OrganisationProfileStage3Form`,
and `stage3_technology_data.html` template remain in place, untouched —
this pilot adds a second, IRENE-presented path to the same data, it does
not replace the first.

### 3.4 New schema/migrations
Per D2, the canonical `OrganisationProfile` schema is not modified to
store registry version information, and no registry-metadata table was
authorised for Increment 1. If Increment 2 requires a minimal,
non-authoritative provenance mechanism (e.g. a small new model/table in
the `irene` app recording `{organisation, section_code, question_code,
catalogue_version, answered_via}`), it is permitted only if this exact
purpose, schema, and migration are what gets implemented — no broader
table, no field holding an alternative answer value, and it must never
determine security completion on its own (that remains
`current_guided_stage()`'s exclusive role per R3). Migration must not
touch any Stage 1/2/4+ table.

### 3.5 Preconditions and dependency order
Increment 1 complete and independently audited GREEN first.

### 3.6 FORGE implementation instructions
Dispatch as an isolated worktree. The Engineer must demonstrate the
concurrent-write non-overwrite proof required by §1 explicitly as a test,
not merely assert it.

### 3.7 Tests and evaluation fixtures
- Unit/integration tests for the Stage 3 adapter against all 10 fields
  plus the Key Assets delegation (including the additional `security`
  entitlement check on that delegated path, per D1).
- The concurrent-write proofs required by R2: a same-field race (second
  writer's stale version is rejected, not overwritten) and a
  different-field race (both writers succeed, neither clobbers the
  other) — both as executed tests, not assertions.
- A **disposable, explicitly-approved real-model test**: before this
  sub-item runs, obtain explicit model/vendor security and numerical
  cost/latency approval for a bounded number of real `ask_adviser()` calls
  against synthetic organisation data only (never real customer data, per
  Architecture invariant 7) — recorded as its own approval artifact before
  the test executes, not assumed. `IRENE_ADVISER_MODE_ENABLED` is set to
  `true` only inside this one disposable test environment, for the
  duration of the test, then torn down.

### 3.8 Independent audit acceptance gates
- **Manual-page vs. IRENE-data parity**: an answer saved through the
  existing manual Stage 3 page and one saved through the new IRENE adapter
  must be indistinguishable in the underlying `OrganisationProfile`
  row — confirmed by direct database inspection, not by trusting either
  code path's own claim.
- **Tenant isolation**: confirmed directly (attempt from one tenant's
  session against another tenant's organisation, expect refusal, same
  non-disclosure convention already used by `source_registry.py`'s
  resolvers — "wrong org" must not be distinguishable from "doesn't
  exist").
- **Failure behaviour**: confirmed that Stage 3 remains fully completable
  with `IRENE_ADVISER_MODE_ENABLED=false` and with the AI gateway
  deliberately made unreachable — per Architecture invariant 10, a
  customer must always be able to complete the section without AI
  availability.
- **Guarded-save guarantees (R2)**: directly re-run or re-verify the
  same-field and different-field concurrent-write proofs against the
  actual implementation, not just read the test code; confirm a retried
  identical submission is genuinely idempotent (no double-apply, no
  error) and that a stale submission is genuinely rejected rather than
  silently accepted.
- **Progress-integrity check (R3)**: confirm directly, by inspection of a
  profile with unanswered fields, that a default/unset value is never
  presented or recorded as an explicitly-reviewed answer absent a real
  submission through one of the two save paths.
- **Both mandatory acceptance conditions** (Amendment "Closure condition"
  item 3) independently re-verified: a real browser session completing
  the full Stage 3 journey through actual IRENE with genuinely useful
  on-demand explanations: and the second-section proof genuinely touching
  zero lines of Increment 1's orchestration/modal/renderer code (a `git
  diff` scope check, not a verbal claim).

### 3.9 STOP conditions specific to this increment
STOP and return to Architect if the guarded save path cannot be built
without also modifying the existing manual Stage 3 view/form/template, or
if the real-model test's approved cost/latency budget would be exceeded
by the planned test volume.

### 3.10 Durable evidence
`docs/evidence/IRENE-001-INCREMENT-2-STAGE3-PILOT.md`: adapter test
results, concurrent-write proof, real-model test approval artifact and
results (model/vendor names and non-secret config only — no prompts/
responses containing anything resembling customer data, since only
synthetic data is in scope), end-to-end browser demonstration record, and
the independent audit's parity/isolation/failure-behaviour findings.

`docs/guides/IRENE-SECTION-INTEGRATION-GUIDE.md`: the reusable formula
itself, written against the real Increment 1 contract, with the second
section's registration as its own tested, cited example.

### 3.11 Customer Zero / browser verification
Mandatory, real browser, disposable environment, proving R4 in full:
full Stage 3 journey through actual IRENE (login → dashboard →
Infosecurs Limited → Stage 3 via IRENE → genuine in-IRENE answer/save →
confirm persisted via direct DB check → refresh, confirm authenticated
state and saved answers survive → pause the journey and resume it later,
confirm it resumes at the correct question/state → at least one on-demand
AI explanation, obtained only after the separate real-model test's
operating approval in §3.7 has been granted, never before → manual-page
parity per §3.8 → the second-section integration proof touching zero
lines of Increment 1's core). This is the pilot's primary acceptance
evidence — a 200 status code alone is never sufficient, matching the
standing discipline already applied to the Customer Zero login
acceptance gate on this delivery line.

### 3.12 CI/security/regression requirements
Full existing `ci/unit` + `ci/integration` suite green. No regression to
the existing manual Stage 3 page, Stage 1/2/4+, or any other IRENE
skill/tool already delivered under M010A–F.

## Product Authority / Architect decisions — resolved

The three decision points previously named in the companion PID Amendment
(entitlement gating, versioning granularity, linked-repeatable-record
capability modelling) have been resolved by Central Architecture as D1–D3
(see Amendment and §1a above), with R1–R4 as this Work Order's
corresponding refinements. Both increments may proceed under these
resolved decisions once this corrected package itself receives Architect
Acceptance; no further decision is outstanding before Increment 2 begins.

## Delivery sequence

1. Architect Acceptance of this Amendment + Work Order (this package).
2. FORGE dispatch, Increment 1 (isolated worktree) → independent audit →
   PL-reviewed commit.
3. FORGE dispatch, Increment 2 (isolated worktree, depends on #2) →
   independent audit (parity/isolation/failure-behaviour +
   both mandatory acceptance conditions) → PL-reviewed commit.
4. Single PR for the whole pilot (or two PRs, PL's call, following this
   PID lineage's own "regular merge, preserve history" convention) →
   Architect Acceptance → Merge → Closure.
5. Deployment of any part of this pilot to the persistent Beta is a
   separate, later, explicitly-gated decision — not implied by this Work
   Order's closure.

## Global STOP conditions

- Any attempt to create a second questionnaire database, a second
  "Stage 3 complete" definition, or a second Key Assets UI.
- Any real-model call outside the one disposable, approved test
  environment, or against anything other than synthetic organisation
  data.
- Any change to the existing manual Stage 3 page's behaviour for users
  not going through IRENE.
- Any deployment action against the persistent Beta stack.
- Any expansion of scope toward a platform-wide rewrite, additional
  sections beyond the one required second-section proof, or additional
  IRENE features not named in this Work Order.
