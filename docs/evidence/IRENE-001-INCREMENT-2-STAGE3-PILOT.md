# IRENE-001 — Increment 2: Stage 3 Adapter, Guarded Save Path, Explain-This (core)

**Status: CORE IMPLEMENTED, PL-REVIEWED, INDEPENDENTLY AUDITED GREEN.**
This document covers everything in WO-IRENE-001 §3 **except** the
real-model test (§3.7's real-model sub-item) and the end-to-end browser
demonstration (§3.11) — both remain gated on the real-model test's
separate operational approval, not yet obtained, and are tracked
separately. All work built entirely in disposable environments on
dell-debian; the persistent Beta stack (`/srv/infosecurs`) and the shared
canonical dev clone (`/srv/openclaw/gunnar-dev/infosecurs`) were never
touched.

## 1. Scope delivered

Three FORGE dispatches, each reviewed and committed by the PL, merged in
sequence onto the pilot integration branch `wo/IRENE-001-pilot`:

1. **Second-section Integration Guide proof** (commit `c10c3a3`, merged
   `04f6878`) — a genuinely different synthetic section (fictional
   "Starlight Bakery" kitchen-safety snapshot), registered purely through
   Increment 1's existing contract, exercising `single_choice`,
   `grouped_independent_answer`, and `delegated_workflow`. Plus
   `docs/guides/IRENE-SECTION-INTEGRATION-GUIDE.md`.
2. **Stage 3 adapter, guarded save path, Explain-this** (commit `454ccc6`,
   merged `effd8fd`) — the real `SectionDefinition` for Stage 3
   (`irene/question_engine/adapters/stage3_technology_data.py`), the new
   guarded save path (`organisations/services.py`), and the typed
   Explain-this context (R1), for questions 3.1–3.6.
3. **Concurrent-first-submission fix** (commit `dfd74fb`, merged
   `774503b`) — closes a narrow race the independent audit found in the
   guarded save path's first-ever-submission branch.

Base: `main`@`638eff4b66c12919212dad666031e43be4a6e2a2` (PR #128's merge),
via Increment 1's closed state at `d9ea2d4253d24fbc8d8fb43e538b49e415be92cb`.
Current pilot tip: `774503b`.

### Stage 3 adapter (Amendment D1/D3)

A real `SectionDefinition` over all 10 `STAGE3_TECHNOLOGY_DATA_FIELDS`:
four `single_choice` questions (3.1–3.4), two `grouped_independent_answer`
questions (3.5 data-handled, 3.6 assurance-status, four and two sibling
fields respectively), and question 3.7 (Key Assets) declared as the
`delegated_workflow` capability approved under D3 — no duplicate inline
editor. Registered at `irene.apps.IreneConfig.ready()` time, mirroring
the existing `irene.checks` import precedent.

Authorisation (`check_stage3_access`) composes existing primitives only —
`organisations.views.get_member_organisation_or_404` for tenant
membership (ordinary 404, never distinguishable from "doesn't exist") and
`entitlements.capabilities.has_capability` for `irene`+`foundations`
(always) plus, independently, `security` for the delegated Key Assets
path only (D1's "third, independently-checked gate"). No new
capability/entitlement code introduced. One new `irene.product_knowledge`
concept (`key_assets_manage`) was added to the existing, generic concept
map for the delegated route — matched directly against the real
`key_assets:list` URL name and the real `security` capability code the
`key_assets` app already requires.

### Guarded canonical save path (`organisations/services.py`, R2/C2)

A new, additive write path onto `OrganisationProfile`, entirely separate
from the existing manual `organisation_stage3_technology_data` view's own
full-instance save. Provides:

- Exact canonical validation, reusing `OrganisationProfileStage3Form`'s
  own field-level validation.
- Field-scoped updates (`update_fields=[...]`), never a full-instance
  save.
- Atomic grouped submissions (`transaction.atomic`).
- Safe first-ever-submission handling (no migration — see below — and,
  after the follow-up fix, safe under genuine concurrency too).
- A **distinct canonical-state stale-write check**, mechanically separate
  from Increment 1's catalogue/interaction-contract version checks (per
  C2): a SHA-256 hash of the current values of exactly the fields being
  submitted, computed at read time (or from model defaults if no row
  exists yet), round-tripped by the caller, and re-compared
  transaction-safely (via `select_for_update()`) at write time. **Zero
  new migrations** — the token is never persisted server-side.
- Idempotent receipts: a deterministic `receipt_id` and an
  already-applied check that lets a genuine retry succeed as a no-op
  while a genuine conflicting writer is still rejected.
- Preserved `AuditEvent` behaviour (the manual path's only recorded side
  effect), on a genuine write only, never on an idempotent no-op.

All three WO-mandated concurrency proofs — same-field conflict,
unrelated-field non-overwrite, idempotent retry — implemented as executed
tests, plus a dedicated test proving the stale-write check is mechanically
independent of the version checks.

**Explicitly documented, in both code and tests**: this module's
concurrency guarantee is scoped to itself. The existing manual Stage 3
view's full-instance save is not made concurrency-safe by this path's
existence, and no claim to the contrary is made.

### Explain-this typed context (R1)

`Stage3QuestionExplanationContext`/`build_explanation_context`/
`resolve_stage3_explanation` for questions 3.1–3.6: approved question
wording, permitted answer labels, stable identifiers, catalogue version,
and a minimised `current_answer_label` only — never the raw
`OrganisationProfile` row. Dispatches via Increment 1's existing,
unmodified `resolve_explanation_skill()`/`EXPLAIN_CONTROL` path. **Zero
real `ask_adviser()` calls anywhere in this scope** — every occurrence of
that name in the diff is a comment, docstring, or a test's own local
stub. `IRENE_ADVISER_MODE_ENABLED` untouched.

### Concurrent-first-submission fix

The independent audit, using its own genuinely multi-threaded test (two
real OS threads + a `threading.Barrier`, separate DB connections), proved
that two concurrent first-ever Stage 3 submissions for the same
organisation produced an unhandled `django.db.utils.IntegrityError`
(colliding on `OrganisationProfile.organisation`'s `OneToOneField` unique
constraint) rather than a graceful rejection — not one of the three
WO-mandated scenarios, and not data corruption, but a real gap in the
module's own "safe first-submission handling" claim under genuine
concurrency. Fixed by catching `IntegrityError` on that specific INSERT
and translating it to the module's own existing `StaleCanonicalStateError`
— the semantically correct outcome ("the state this submission was built
against, no row yet, is no longer true"). A new test
(`TestFirstEverSubmissionConcurrency`, following this codebase's existing
`security_tasks/tests/test_concurrency.py` precedent) reproduces the race
with two real threads, confirmed to fail against the pre-fix code and
pass against the fix, with zero regression to the three already-audited
scenarios. The existing manual Stage 3 view has the identical, separate
exposure today — confirmed by the audit, explicitly left unfixed as
out of scope for this guarded-path-only change.

## 2. Independent audit — GREEN

A fresh agent, independent of both implementing engineers, cloned the
repository separately and re-derived every WO §3.8 gate from its own
evidence (excluding the real-model test and end-to-end demonstration,
correctly out of scope):

1. **Manual-page vs. IRENE-data parity** — confirmed via direct raw-SQL
   row inspection after saving through both paths for different fields
   on the same organisation: byte-identical except the touched fields,
   correct `AuditEvent` sequence, exactly one profile row.
2. **Tenant isolation** — confirmed `check_stage3_access` genuinely calls
   the existing `get_member_organisation_or_404` (not a bypass); a
   non-member gets an ordinary 404, a member with insufficient tier gets
   a distinct `Stage3AccessDenied` — correctly distinguishable only at
   the capability layer, never at the existence layer.
3. **Failure behaviour** — zero real AI-gateway calls found anywhere;
   `IRENE_ADVISER_MODE_ENABLED` untouched.
4. **Guarded-save guarantees** — all three scenarios re-verified by
   execution; the audit additionally wrote its own genuinely
   multi-threaded variant (not just the sequential-token-capture style
   already in the suite) and confirmed the existing tests are not
   tautological. Confirmed `save_stage3_fields` never consults
   `catalogue_version`/`interaction_contract_version` when deciding
   staleness.
5. **Progress integrity** — `answered_values_for_profile` confirmed a
   pure read-through; no shadow re-derivation of
   `current_guided_stage()` found anywhere in the diff.
6. **Second-section/core-untouched scope check** — re-run across the
   *combined* diff of both increments (restricted to Increment 2's own
   additions on top of Increment 1's already-closed state, per the
   audit's own correction of an imprecise base-SHA instruction): zero
   lines changed in `irene/question_engine/{contract,registry,presenter,explain}.py`.
7. **Untouched existing code** — `organisations/views.py`,
   `organisations/forms.py`, and
   `organisations/templates/organisations/stage3_technology_data.html`
   confirmed at zero diff.
8. **Zero new migrations** — confirmed via diffstat and an empirical
   `migrate --noinput` comparison between baseline and HEAD (identical
   migration sets).
9. **Full regression** — 466 passed, 2 failed (both the same, pre-existing,
   previously-documented Playwright-binary-missing environment gap,
   confirmed identical at the pre-diff baseline) in the audit's own
   disposable run. CI wiring for all three new test files confirmed
   present and un-regressed across the manual merge-conflict resolution.

The first-submission-race finding (see above) was the audit's one
substantive finding, explicitly ruled "not blocking this disposable
pilot's GREEN closure" but worth a follow-up fix before any live/Beta
use — applied immediately (commit `dfd74fb`) rather than carried forward
as an open item, since it was narrow, well-specified, and cheap.

## 3. PL verification

Beyond reviewing every diff directly before committing (not relying on
either engineer's self-report), the PL additionally ran the full combined
`irene/tests/` + `organisations/tests/test_services_stage3_guarded_save.py`
+ `organisations/tests/test_models.py` + `test_persistence.py` suites
against the merged state (`effd8fd`, before the fix) in a disposable
container: 234 passed, 1 pre-existing failure, 1 expected skip — zero
conflict between the two concurrently-developed increments' work.

## 4. What remains before Increment 2 fully closes

- **Real-model test** (§3.7): requires its own separate model/vendor
  security and numerical cost/latency approval, not yet obtained. Not
  attempted.
- **End-to-end browser demonstration** (§3.11): requires the real-model
  test's approval first (the on-demand AI explanation step must come
  after that approval, per R4), plus a disposable deployed instance with
  synthetic organisation data. Not attempted.
- **Second mandatory acceptance condition** (an engineer adding a second
  compatible section without touching IRENE core): the second-section
  proof itself satisfies this in substance, independently audited; formal
  closure still awaits the PID Amendment's own closure-condition
  sign-off alongside the full increment.

Everything else named in WO §3 is complete and independently audited
GREEN.
