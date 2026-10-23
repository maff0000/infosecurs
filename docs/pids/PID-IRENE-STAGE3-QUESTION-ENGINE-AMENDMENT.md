# PID Amendment — IRENE Reusable Question Engine, Stage 3 Pilot

**Parent authority:** `docs/pids/M010-IRENE-MASTER-PID.md` (IRENE already exists
as a delivered app — `irene/`, `foundations_journey/`, `security_tasks/` —
merged to `main`, **not deployed to the persistent Beta**; confirmed
directly: `/srv/infosecurs/.env` on the live host contains zero `IRENE_*`
keys of any kind).

**Base SHA for this Amendment:** `4b241fd2357a628d6b84699c66071c2d79a46a33`
(current exact `main`).

**Amendment status:** Central Architecture reviewed this Amendment and its
companion Work Order at reviewed head
`8a5b5ecdb7a337d5c4a2fa0c94cddcd3c0db42fe` and returned a verdict of
**architecture direction accepted in principle, targeted document
corrections required**. The two-increment delivery strategy was not
redesigned. The three items previously recorded below as "open decision
points" have been resolved as binding architectural decisions (D1–D3);
see the new section of that name, replacing the earlier defaults. The
companion Work Order carries the corresponding refinements (R1–R4).

**Governance chain for this pilot:** Architecture → this PID
Amendment/Work Order → GUNNAR → FORGE → Independent Audit → PR → Architect
Acceptance → Merge → Closure. No implementation begins until this
Amendment and its companion Work Order
(`docs/work-orders/WO-IRENE-001-STAGE3-QUESTION-ENGINE-PILOT.md`) receive
Architect Acceptance.

## What this Amendment records

Central Architecture has approved a **bounded design and disposable
pilot**: IRENE is to become the primary conversational/guided interface
to INFOSECURS, with the underlying application retaining sole ownership
of canonical security data, validation, entitlements, and consequences.
The first implementation target is **Stage 3 — "Your Technology & Data,"
questions 3.1–3.7** — chosen as the reference section because it already
exercises two of the three interaction shapes this pilot must prove
(single-choice and grouped-independent-answer) plus a link-out to a
linked/repeatable-record flow (Key Assets), without requiring any new
canonical data model.

This Amendment is scoped to **design + a disposable pilot only**. It does
not authorise deployment of M010, IRENE, or this pilot to the persistent
Beta stack.

## Current status of the product (as independently verified against `main`@`4b241fd`)

- **IRENE already exists**, delivered under M010A–F (`docs/pids/M010-IRENE-MASTER-PID.md`,
  `docs/work-orders/WO-M010-GUNNAR-ONE-PUSH.md`): the modal/conversation
  shell (`irene/` — `IntentCode`, `skill_loader.py`/`skill_router.py`,
  `tools.py` `TOOL_REGISTRY`, `orchestration.py`), the Foundations-journey
  adapter (`foundations_journey/` — `JourneyCheckpoint`, resumable,
  optimistic-concurrency `version` field), and the shared Task List
  (`security_tasks/`). This is on `main`, **undeployed**.
- **Stage 3 today is a conventional, hand-written Django page**, not a
  generic/data-driven question engine: `STAGE3_TECHNOLOGY_DATA_FIELDS`
  (`organisations/views.py:729-740`) is a plain Python list of 10
  `OrganisationProfile` fields; `organisation_stage3_technology_data`
  (`organisations/views.py:743-811`) is a single view bound to
  `OrganisationProfileStage3Form` (`organisations/forms.py:322+`), one
  `ModelForm`, one template (`organisations/templates/organisations/stage3_technology_data.html`).
  Question **3.7 "Key assets" is not a form field at all** — it links out
  to the separate `key_assets` app (list/create), confirmed via both the
  view's own docstring and the form's docstring.
- `organisations/guided_journey.py::current_guided_stage()` is the
  **single existing source of truth** for "which stage is next" / "is
  Stage 3 complete" — any IRENE adapter over Stage 3 must consume this,
  never re-derive a second definition.
- **No service layer currently exists for `OrganisationProfile` saves.**
  `organisations/views.py` saves the form directly inline
  (`form.save(commit=False)` → `profile.save()`). `OrganisationProfile`
  has **no optimistic-concurrency field** (contrast with
  `foundations_journey.models.JourneyCheckpoint.version` and
  `security_tasks.models.SecurityTask.version`, which both have one).
- **Entitlements already gate Stage 3**:
  `ORGANISATIONS_URL_NAME_TO_CAPABILITY["stage3_technology_data"] = "foundations"`
  (`entitlements/capabilities.py:87`, independently confirmed). IRENE's own
  shell is gated separately under the `irene` capability code
  (`entitlements/capabilities.py:48-51`). No new entitlement code is
  architecturally required by default — see the open decision point
  below.
- **`IRENE_ADVISER_MODE_ENABLED` already exists and defaults to `false`**
  (`config/settings.py:73`, independently confirmed), with its own
  settings-file comment stating it is "the ONLY flag that gates a real
  call to the AI gateway" and that no approval has yet been given to
  enable it against any live campaign. It is not merely off — the entire
  `IRENE_*` flag surface is **absent from the live Beta's `.env`**,
  independently confirmed (zero matches).
- **Versioning precedent already exists** in sibling apps (a module-level
  `CATALOGUE_VERSION` string, stamped onto the answer row at save time —
  `security_baseline/catalogue.py`, `questionnaire/catalogue.py`,
  `risk_register/methodology.py`), but **not for Stage 1–3** — Stage 3's
  fields carry no catalogue-version or row-version concept today.
- **A typed/versioned/allowlisted registry pattern already exists** for
  two adjacent concerns — `security_tasks/source_registry.py` (plain-dict
  allowlist, tenant-verified resolvers) and `irene/skill_loader.py`
  (filesystem + strict-frontmatter manifest validation) — but **no
  existing mechanism already does this for questions/sections**. This is
  the genuinely new piece this pilot must build, by combining both
  existing idioms rather than inventing a third pattern.
- **An "Explain this" precedent already exists**: `IntentCode.EXPLAIN_CONTROL`
  (`irene/models.py:74`), routed via `skill_router.py` to the
  `foundations-guide` skill, dispatched by controlled intent code only —
  "the customer's own words never choose which skill loads." This pilot's
  on-demand explanation reuses this mechanism; it does not invent a new
  dispatch path.

## What this Amendment does NOT do

- Does not deploy M010, IRENE, or this pilot to the persistent Beta stack.
- Does not create a second questionnaire/answer database, a second
  "is Stage 3 complete" definition, or a second Key Assets flow.
- Does not enable `IRENE_ADVISER_MODE_ENABLED` in any persistent
  environment — only a disposable, separately-authorised real-model test
  is in scope, per its own numerical cost/latency/vendor-security approval
  gate (see Work Order §2, Increment 2).
- Does not introduce a new entitlement/capability code. Per D1 below,
  access through IRENE is gated by composing existing codes (`irene` +
  the destination section's own code — `foundations` for Stage 3;
  `security` for the delegated Key Assets workflow), never a new code.
- Does not touch Stage 1, Stage 2, Stage 4+, or any app outside the exact
  files/modules named in the companion Work Order.
- Does not become a platform-wide rewrite. The explicit purpose is to
  invent, prove, and document the reusable formula **once**, against one
  reference section, so that future sections predominantly consist of
  registered question definitions, domain adapters, and tests — not new
  IRENE core functionality.

## What this Amendment authorises

1. Design and implementation, in a **disposable environment only**
   (never the persistent Beta), of:
   - A typed, versioned, allowlisted section/question contract and
     registration mechanism (new — the genuine gap identified above).
   - A generic IRENE question presenter and on-demand explanation
     interface, built on the existing `irene/` shell, `IntentCode`
     dispatch, and `skill_loader.py`/`skill_router.py` mechanics.
   - A Stage 3 domain adapter against the existing
     `OrganisationProfile`/`KeyAsset` data and the existing
     `organisations/guided_journey.py` single-source-of-truth, with a
     new guarded save/receipt path (closing the service-layer gap
     identified above) that writes with field-level scoping, never a
     full-instance save, given `OrganisationProfile` has no
     optimistic-concurrency field of its own.
   - A disposable, explicitly-approved real-model `ask_adviser()` test
     using synthetic organisation data only.
   - An end-to-end browser demonstration of the complete Stage 3 journey
     through the real IRENE interface, and a Section Integration Guide
     proving a second, small section/fixture can be registered without
     modifying IRENE's central orchestration, modal, or answer renderer.
2. An independent audit of the above (manual-page vs. IRENE-data parity,
   tenant isolation, failure behaviour) before any PR is opened.
3. Nothing beyond design, disposable-environment implementation, and
   independent audit. Deployment of this pilot (or any part of M010) to
   the persistent Beta remains separately gated and is explicitly not
   authorised by this Amendment.

## Architectural decisions (D1–D3, resolved by Central Architecture on PR #128 review)

These were raised below as open decision points with defaults; Central
Architecture has now decided them. They are binding on the companion Work
Order, superseding the earlier "default position… confirm or override"
framing.

**D1 — Entitlements.** No new entitlement/capability code. Access through
IRENE to a destination section requires **both** the `irene` capability
code and the destination section's own existing code — `foundations` for
Stage 3. The delegated Key Assets workflow (question 3.7) must
additionally enforce its own existing `security` entitlement — a third,
independently-checked gate on top of the `irene`+`foundations` pair, not
a substitute for either. Every read, explanation, save, and resume
request must independently recheck authorisation and tenant membership —
no caching an earlier check's result within the same session.

**D2 — Versioning.** Two independently-versioned axes, not one: stable
section/question identifiers plus a versioned question catalogue, and a
*separately* versioned generic interaction contract. Server-issued
versions must be checked when an answer submission is received;
incompatible or stale submissions fail safe — rejected outright, never
silently accepted or auto-merged. The canonical Stage 3 answer schema
(`OrganisationProfile`) is **not** modified merely to store registry
version information, and **no registry-metadata table is authorised for
Increment 1**. Increment 2 *may* define one minimal, non-authoritative
provenance mechanism, but only if the companion Work Order names its
exact purpose, schema, and migration explicitly — and that mechanism must
never hold an alternative answer value or determine security completion
in its own right.

**D3 — Key Assets.** A generic `delegated_workflow` capability type is
approved for question 3.7. IRENE explains the question and directs the
customer to the existing, already-authorised Key Assets workflow, then
resumes appropriately on return. No duplicate asset editor. No claim of
implementing generic inline repeatable-record CRUD — `delegated_workflow`
is a declared delegation shape, not a stand-in for one.

## What happens if a defect is found during the pilot

Any defect found during implementation, independent audit, or the
end-to-end browser demonstration is routed back through FORGE for repair
before PR submission — the same discipline already standing for every
other delivery in this PID lineage (merged ≠ deployed; a fix must reach
the board). No defect is waived silently; none is fixed by expanding this
pilot's scope beyond the companion Work Order's named files/modules.

## Closure condition

This Amendment and its companion Work Order close when:

1. Both are Architect-Accepted.
2. The bounded pilot (generic engine + contract + registry + Stage 3
   adapter + Explain-this + guarded save path + disposable real-model
   test + end-to-end browser demonstration + Section Integration Guide
   with a second proven section + independent audit) is complete in the
   disposable environment.
3. Both of the mandatory acceptance conditions hold, independently
   verified: the Product Owner can use the real IRENE interface to
   complete the pilot section and receive genuinely useful on-demand AI
   explanations; and an engineer can add another compatible section from
   the documented contract without changing IRENE's central
   orchestration, modal, or answer renderer.
4. A PR is opened, independently audited, and Architect-Accepted.

Deployment to the persistent Beta is explicitly out of this closure's
scope and requires its own, separately-gated authorisation — the same
discipline already standing for every live-release decision in this
delivery line.
