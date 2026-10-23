# IRENE-001 — Increment 1: Generic Question Engine, Contract, Registry

**Status: IMPLEMENTED, PL-REVIEWED, INDEPENDENTLY AUDITED GREEN.** Built
entirely in a disposable environment (`/srv/openclaw/worktrees/wo/IRENE-001-increment1-engine`
on dell-debian); never touched the persistent Beta stack (`/srv/infosecurs`)
or the shared canonical dev clone (`/srv/openclaw/gunnar-dev/infosecurs`).

## 1. Scope delivered

Per `docs/work-orders/WO-IRENE-001-STAGE3-QUESTION-ENGINE-PILOT.md` §2:

- `irene/question_engine/contract.py` — typed, frozen dataclasses for the
  four Architecture-approved capability types (`single_choice`,
  `grouped_independent_answer`, `linked_repeatable_record`,
  `delegated_workflow`), a `QuestionDefinitionProtocol`, and
  `SectionDefinition`, with Amendment D2's two independently-versioned
  axes kept genuinely distinct: each section's own `catalogue_version`,
  and the module-level `INTERACTION_CONTRACT_VERSION` shared by the
  generic engine shape itself.
- `irene/question_engine/registry.py` — an in-code, Python-reviewed
  allowlist (`SECTION_REGISTRY`, no backing table, **zero migrations**),
  mirroring `security_tasks/source_registry.py`'s plain-dict-plus-resolver
  shape and `irene/skill_loader.py`'s manifest-validation rigor. Rejects
  unregistered section codes outright (`UnregisteredSectionError`) and
  malformed/forged definitions outright (`InvalidSectionDefinitionError`,
  collecting every problem found, never partial registration).
- `irene/question_engine/presenter.py` — a section-agnostic renderer
  dispatching purely on `capability_type`, never on section identity.
- `irene/question_engine/explain.py` — an on-demand explanation entry
  point reusing the existing `irene.skill_router.select_skill()` /
  `IntentCode.EXPLAIN_CONTROL` path exactly as it already exists; no new
  dispatch mechanism, no new `IntentCode` member.
- `irene/checks.py` — additive `check_question_engine_registry`
  (`irene.E003`), mirroring the existing `E001`/`E002` boot-time-check
  convention.
- Built and proven exclusively against a synthetic, throwaway "Acme Test
  Section" fixture (`irene/tests/conftest.py`) — never Stage 3 or the
  `organisations` app.
- `irene/tests/test_question_engine_registry.py` (15 tests) and
  `irene/tests/test_question_engine_presenter.py` (11 tests) — 26 new
  tests total, since wired into `.github/workflows/ci.yml`'s `ci/unit`
  job (see §4 below — an audit finding, now corrected).

Commits: `f6e1d9a` (implementation, on `wo/IRENE-001-increment1-engine`),
merged via regular merge `8c498ec` into the pilot integration branch
`wo/IRENE-001-pilot`, plus follow-up `20568c3` (CI wiring fix). Base:
`main`@`638eff4b66c12919212dad666031e43be4a6e2a2` (the PR #128 merge
commit).

## 2. Test results

- New tests: 26/26 passed (`test_question_engine_registry.py` 15,
  `test_question_engine_presenter.py` 11).
- Pre-existing `irene/tests/` suite: 148 tests at the pre-diff baseline
  (`638eff4`), 148/148 still passing at HEAD (`8c498ec`) — the
  independent audit established this baseline itself rather than trusting
  the implementing agent's own count, which had misstated it as "172" in
  commit prose (a self-report inaccuracy, not a gate failure — corrected
  here).
- One failure present identically at both the baseline and HEAD commits:
  `irene/tests/test_browser_acceptance.py::test_irene_modal_tabs_focus_trap_escape_and_manual_fallback`,
  caused by the Playwright Chromium binary not being installed in a
  one-shot disposable Docker build (CI installs it via its own separate
  runner-only step) — a pre-existing environment gap, unrelated to this
  diff, confirmed present before this diff too.
- `python manage.py check` — zero issues. The new `irene.E003` check was
  proven genuinely live (not decorative): the independent audit forcibly
  inserted a deliberately-invalid `SectionDefinition` directly into
  `SECTION_REGISTRY` and confirmed `manage.py check` raised
  `SystemCheckError` citing `irene.E003` with the exact validation
  problems.

## 3. Independent audit — GREEN

A fresh agent, with no memory of the implementing agent's reasoning,
cloned the repository independently and re-derived every gate from its
own evidence:

1. **Zero Stage-3/`organisations`/`key_assets` references** — confirmed:
   the diff itself introduces none; the one pre-existing `organisations.models`
   import in `irene/tests/conftest.py` predates this diff and is unrelated
   to the new fixture block.
2. **Registry genuinely rejects an unregistered section code, as an
   executed test** — confirmed by running the specific tests directly.
3. **Zero new database migrations** — confirmed via diff stat.
4. **Pre-existing `irene/tests/` suite passes unmodified, zero
   regression** — confirmed via the independently-established 148 vs. 148
   baseline comparison in §2.
5. **New test files run and genuinely prove forged-input rejection** —
   confirmed; cited `test_rejects_question_with_forged_capability_type`
   (uses `object.__setattr__` to forge an invalid capability type onto a
   frozen dataclass built outside its own constructor) as proof this is
   real rejection, not merely valid-input acceptance.

Also independently confirmed: Amendment D2's two version axes are
genuinely separate and both enforced (not merely declared); no real
AI-gateway call (`ask_adviser`) is wired anywhere in this increment;
`IRENE_ADVISER_MODE_ENABLED` is untouched; explanation dispatch adds no
new `IntentCode` member and no second dispatch mechanism.

**Scope-interpretation ruling (audit's own independent judgement):** WO
§2.2 describes the presenter as reusing the existing modal shell
(`irene/orchestration.py`, `irene/views.py`) "extended, not duplicated."
This increment's diff does not modify either file — `presenter.py` is
freestanding and URL-unwired. The audit read both existing files directly
and ruled this is **not a scope gap**: Increment 1 registers zero real
sections by design (WO §2.1), so there is no concrete call site to extend
yet; `orchestration.py`'s only candidate path (`ask_irene`) is a
different, AI-gateway-routed mechanism, and touching it to fabricate a
premature wiring point would risk exactly what WO §2.9's STOP condition
forbids (changing Stage 1/2/4+'s live Foundations-guide behaviour). The
audit noted, as a non-blocking wording suggestion for future Work Orders,
that §2.2 could say explicitly that this extension point is deferred to
the real adapter increment, to pre-empt this exact question next time.

## 4. Findings arising from the audit, corrected before Increment 2

- **CI-wiring gap (corrected):** the two new test files were not in
  `.github/workflows/ci.yml`'s explicit per-file `ci/unit` list, so they
  would have silently never run in real CI going forward despite passing
  locally. Fixed in commit `20568c3` — both files added alongside the
  existing `irene/tests/` entries.
- **Self-report test-count inaccuracy (noted, not corrected in history):**
  the implementation commit's own prose cited "172" pre-existing tests;
  the audit's independently-measured true baseline is 148. The underlying
  substance (26 new tests, zero regression) is correct; only the stated
  figure was wrong. Not corrected via history rewrite — recorded
  accurately here instead.

## 5. Closure of Increment 1

Per WO-IRENE-001's Delivery Sequence step 2: FORGE dispatch (isolated
worktree) → independent audit → PL-reviewed commit — all three complete,
verdict GREEN. Increment 2 (Stage 3 adapter, guarded save path,
Explain-this, disposable real-model test, end-to-end demonstration,
Integration Guide, second-section proof) may now proceed per WO §3,
subject to its own independent audit gates before any PR is opened.
