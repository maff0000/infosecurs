# M007-WI6 — Session / Entitlement / Tenant Adversarial Re-Proof (Part A), Stale-Assumption Sweep (Part D), AI Regression Confirmation (Part E)

**Authorising commit (final merged M007 source, WI1-WI5 landed):** `d09a954cc5e1e3223a3a8b0137adc284984af343` (`main`)
**Worktree:** `/srv/infosecurs-worktrees/wi6-session-metrics-regression`, branch `wi6-session-metrics-regression`
**Scope:** M007-WI6 — full regression / release / fresh independent audit (PROOF work item, not a feature work item)

This is a fresh, independent adversarial re-proof of the session contract,
entitlement guard, and tenant-isolation boundary against the FINAL merged
M007 source — not a rewrite of the existing WI1/WI3 coverage. `entitlements/
decorators.py`, `entitlements/session.py`, `entitlements/capabilities.py`,
`entitlements/tiers.py`, `organisations/views.py` and every relevant
pre-existing test file were read in full before any new test was written
(see "Files read" at the end of this document). No product source was
modified. One test file (`organisations/tests/test_navigation.py`) had its
own docstring corrected — see Part D.

## Method

Real Django `django.test.Client` requests against real resolved URLs, real
seeded `ProductArea`/`FoundationRequirement` rows, and this app's own
established `org_a`/`org_b`/`user_a`/`user_b`/`client_a`/`client_b`/
`user_ab`/`client_ab`/`set_session_tier` fixtures/helpers
(`entitlements/tests/conftest.py`) — reused throughout, never duplicated.
Disposable Docker stack `infosecurs-wi6` (own project name, host ports
`15632`/`18600`, distinct from every other stack on `dell-debian` and from
the parallel `wi6-browser-acceptance` Engineer's own work).

New test file: `entitlements/tests/test_wi6_session_entitlement_reproof.py`
(28 tests). Every test in it exists because it closes a specific, named gap
in the extensive pre-existing coverage — each test class docstring cites
exactly which existing file/test already covers the adjacent property, and
why this test is not a duplicate.

## Part A.1 — Full tier matrix, direct URL probes

`entitlements/tests/test_decorators.py::TestTierMatrixAtRouteLevel` already
proves PID §25.1's tier matrix (PAUSED/FOUNDATION/MONTHLY/PRO) against 12
representative Tier-1 routes plus the one seeded Tier-2 route
(`questionnaire:list`), including the Pro-inherits-Monthly PROPERTY proof
(not a duplicated fixed list). Its own `TIER1_ROUTES` list, however,
pre-dates WI5 and does not include `organisations:foundations` — the one
Tier-1 route the whole matrix was missing.

**Result:** `TestFoundationsRouteTierMatrix` (this WI's new file) proves,
freshly: Paused → 403 on Foundations (including the exact, copied-URL
case); Foundation/Monthly/Pro → 200. `organisations/tests/
test_foundations_view.py::TestFoundationsTierMatrix` already proves the
same property at the view-CONTENT layer — this is an independent
confirmation at the session/entitlement layer, not a duplicate.

`TestPostOnlyNestedObjectRouteTierMatrix` covers the dispatch's explicit
"POST-only routes, nested object routes" bullet using `remediation:start`
(POST-only, carries a nested `action_id`): Paused → 403 (denied before the
view's own method/object logic ever runs, per WI3's tenant-gate-before-
method-check ordering — confirmed by reading `remediation/views.py`);
Foundation → reaches the view body (404 on the fabricated `action_id`,
proving the request cleared the entitlement gate).

**Result: PASS, both classes.**

## Part A.2 — Client-side spoofing has zero effect

`entitlements/tests/test_decorators.py::TestClientSuppliedValuesHaveNoAuthority`
already proves forged header/query/cookie/POST-body tier signals are inert
against `key_assets:list` and `risk_register:generate` — pre-dating WI5.
The dispatch explicitly asks this be re-proven **through the new Home/
Foundations routes specifically**.

**Result:** `TestClientSideSpoofingThroughHomeAndFoundations` proves a
forged `?tier=3&package_tier=3&package=PRO` query string, `X-Package-Tier`/
`X-Package`/`X-Infosecurs-Tier` headers, and an unrelated `package=PRO`
cookie have zero effect on a genuinely Paused session, on both Home (still
renders the *Paused* content, not the metric cards) and Foundations (still
403) — and that a forged POST body with the same fields against
Foundations' GET-only route has no effect either.

**Structural proof (code-level, not just "tried representative
variants"):** `TestClientSuppliedValuesAreStructurallyNeverRead` inspects
the literal source of `entitlements.capabilities.has_capability` and
`entitlements.session.get_validated_context` (`inspect.getsource`) and
proves neither one contains the token `request.GET`, `request.POST`,
`request.headers`, `request.META`, or `request.COOKIES` anywhere — i.e. the
absence of the whole bug class, not merely its current non-occurrence. A
third test confirms `validate_context` itself (the fail-closed core) takes
only `(raw, user)` — no `request` parameter at all, so it is categorically
incapable of consulting anything client-supplied beyond what
`get_validated_context` chose to extract from `request.session`.

**`localStorage`/`sessionStorage`/JS-global/DOM-mutation reasoning
(PID's own ask, Django's test Client cannot execute JS so this is a code-
reading proof, not a runtime one):** every entitlement decision in this
codebase flows through `has_capability(request, code)` →
`get_validated_context(request)` → `request.session.get(SESSION_KEY)`. The
structural proof above establishes those two functions never read anything
from the request except `request.session`/`request.user`. `request.session`
is a `django.contrib.sessions.backends.db.SessionStore` — server-side state
keyed by an opaque cookie value the browser holds (PID §6.1's own "the
browser must hold only the ordinary opaque session identifier"); nothing in
the browser (a JS variable, `localStorage`, `sessionStorage`, a DOM
mutation) is ever transmitted to, or read by, the server as part of this
decision. There is therefore no code path by which any of those four
client-side mechanisms could matter, independent of whatever any individual
test tries — this is why the PID frames them as "structurally impossible"
rather than merely "untested".

**Result: PASS, all classes; structural absence confirmed by source
inspection.**

## Part A.3 — Tenant/object isolation, broadly

Every organisation-scoped app already has its own deep
`test_tenant_isolation.py` (1,856 lines combined across 12 apps, read in
full) proving `client_b` (a genuine member of `org_b` ONLY) cannot reach
`org_a`'s real objects (key assets, evidence, risks, policy versions,
questionnaire responses, workplaces, governance rows, remediation actions,
security-baseline rows) — always a clean 404, never a 403, never varying by
tier. `core/tests/test_route_matrix.py`'s mechanical, tree-walked sweep
additionally proves this property structurally for all 40+ organisation-
scoped routes using fabricated placeholder ids, confirming no route is
missing the membership gate. `entitlements/tests/test_decorators.py::
TestTenantMembershipDominatesOverTier` already proves a cross-org member's
own tier (up to artificially-forced PRO) never substitutes for membership
of the TARGET org.

None of that existing coverage tests the stronger case PID §25.4 also asks
for: a client who is a member of **neither** organisation under test, at
PRO tier, against real (not fabricated-id) objects.

**Result:** `TestTrulyNonMemberProTierNeverReachesForeignObjects` (a fresh
`org_c`/`user_c`/`client_c_pro` — member of `org_c` only, so login can issue
a real context at all, then forced to PRO and probed exclusively against
`org_b`) proves 404 against real `org_b` objects: a confirmed key asset (list
+ detail), an evidence item, a confirmed risk, a draft policy version, a
draft questionnaire response, an active workplace, and `organisations:
detail` (Home) itself. **PASS, 7/7.**

## Part A.4 — Active organisation alignment

`entitlements/tests/test_decorators.py::
TestStaleCrossOrganisationSessionRealignment` already proves, using
`client_ab`/`user_ab` (a genuine member of both seed organisations):
`organisation_id` realigns, the session key rotates on realignment,
`package_tier` is preserved, and a return to the first organisation
realigns cleanly again with no stale hybrid state observed (`key_assets:
list` on org_b then org_a both succeed, each reading the just-realigned
context).

**Result:** `TestActiveOrganisationAlignmentPreservesPackageCodeToo` adds
the one field the existing test does not itself check —
`package_code` — proving it is preserved unchanged through org_a→org_b→
org_a, alongside `package_tier`. **PASS.**

## Part A.5 — Logout/replay

`entitlements/tests/test_decorators.py::
TestLogoutDestroysAccessAcrossRouteFamilies` already proves cookie replay
in a fresh `Client()` fails (redirects to login) across 5 route families
(`key_assets`, `evidence`, `policy`, `workplace`, `questionnaire`), and
`core/tests/test_application_shell.py::
test_logout_still_actually_destroys_the_session` proves the same for Home
using the *same* client's own jar. Neither covers Foundations, a
representative real object URL, or PID §8.1's own final numbered steps
(9-11: a **subsequent fresh login** issues a genuinely different session
identifier than the one that was captured and replayed, and the newly
issued context reflects only the newly issued tier).

**Result:** `TestFullLogoutReplayFlow::
test_pro_session_full_logout_replay_and_fresh_relogin` runs the complete
PID §8.1 sequence end-to-end: real `client.login()` → `set_session_tier`
to PRO → confirms a Foundation capability (Foundations) AND a Monthly-only
capability (Customer Assurance) both genuinely reachable → captures the
session key and cookie value → real POST logout → confirms the OLD session
row is gone from the `django_session` table entirely (not merely
unauthenticated) → replays the OLD cookie in a genuinely fresh `Client()`
against 9 routes (Home, Foundations, key-asset list, a real key-asset
detail URL, Security, Evidence, Policy, Company, Customer Assurance) — all
9 redirect to login, never served → a genuinely fresh `client.post(login,
...)` (not `force_login`) issues a session key that differs from the
original pre-logout key, and the freshly issued context carries only the
default MONTHLY tier, never the PRO tier this test had artificially forced
onto the old session. **PASS.**

## Part A.6 — Invalid session matrix

`entitlements/tests/test_session_contract.py::
TestEachFailClosedCheckIsIndependent` already proves every
`InvalidReason` at the unit level, including the bool-tier type-confusion
angle explicitly (`@pytest.mark.parametrize("bad_tier", [..., True, False,
...])`), and `entitlements/tests/test_decorators.py::
TestFailClosedInvalidSessionContextRedirectsToLogin` already proves 5 of
the 8 required-field-missing/tampered variants at the route level (schema
version, subject mismatch, tier out of range, code/tier mismatch,
malformed org id) plus one explicit missing-field case
(`package_code`) plus the fully-missing-context case.

**Result:**
`TestEveryRequiredFieldMissingIndividuallyAtRouteLevel` parametrizes over
all 8 of `entitlements.session.REQUIRED_FIELDS` (`schema_version`,
`subject_id`, `organisation_id`, `package_tier`, `package_code`,
`entitlement_version`, `issued_at`, `auth_source`), deleting each one
individually and confirming a route-level redirect-to-login for every
single one — not just the one field the existing route-level test
happened to cover.
`TestBoolTierTypeConfusionAtRouteLevel` re-proves the bool angle
end-to-end through a real request: a session carrying `package_tier: True`
(`== 1`, i.e. would silently mean FOUNDATION under a naive `in {0,1,2,3}`
check) is denied on Foundations; `package_tier: False` (`== 0`, i.e. would
silently mean PAUSED) is denied even on Home, which a *genuine* Paused
session is allowed to reach — proving the point is "never a valid value at
all", not "fails to reach some higher bar". Confirmed against
`entitlements.tiers.is_valid_tier`'s own docstring, which already documents
`isinstance(value, bool)` is deliberately excluded from tier validity.
**PASS, 8/8 fields + both bool directions.**

## Part D — Stale route/destination assumption search

Full-repository search (`grep` for "Overview"/"detail"/"flat card
list"/"temporarily"/"app-header__nav-primary"/"active_nav" across every
`.py`/`.html` file, plus targeted reads of every hit) for stale references
to the old M006 destination/navigation semantics M007 (WI1-WI5) superseded.

| # | Location | Finding | Classification | Action taken |
|---|----------|---------|-----------------|---------------|
| 1 | `entitlements/migrations/0002_seed_product_areas.py` (comment) | Describes the WI1-flagged temporary `foundations → organisations:detail` placeholder, explicitly says "flagged... WI5 MUST land a follow-on migration" | **B — historical documentation, correctly framed as history** | None. Migration 0004 (below) is the resolution; the comment correctly describes a past state and explicitly forecasts its own resolution. |
| 2 | `entitlements/migrations/0004_foundations_real_destination.py` | The actual resolving migration — updates `foundations`'s `destination_view_name` to `organisations:foundations` | **C — still-valid current source, this IS the fix** | None. |
| 3 | `entitlements/tests/test_migration_0004_foundations_destination.py`, `organisations/tests/test_foundations_view.py::test_seeded_foundations_product_area_now_points_at_the_real_workspace` | Proves migration 0004 actually landed and the row now points at the real route | **C — checked, not stale** | None. Re-ran; still green (part of the 1,806/14 baseline). |
| 4 | `entitlements/navigation.py::_pick_current_area` (docstring, product source) | States "the seeded data has exactly two such collisions **today**" — `home`/`foundations` both pointing at `organisations:detail` — as a CURRENT fact. This became false the moment migration 0004 landed: `foundations` now points at `organisations:foundations`, a different destination from `home`'s `organisations:detail`, so this pair no longer collides in `areas_by_view` (confirmed by reading `build_navigation_tree`'s own grouping-by-`destination_view_name` logic). No behavioural impact — `_pick_current_area`'s tie-break rule for this pair is simply unexercised now; the ONE real remaining collision (`security`/`security_state`) is unaffected and still correctly resolved. | **A — genuinely stale, but touches product source** | **Not self-fixed** (per this dispatch's own instruction to STOP rather than modify product source outside the explicitly-authorised bug-fix path). Flagged here for PL/Engineer routing: a one-line docstring correction, cosmetic only, zero behavioural risk. `entitlements/tests/test_navigation.py`'s own `TestActiveItemHighlighting` class docstring (lines ~164-179, read in full) had **already independently identified this exact same stale docstring** in its own comments ("The OTHER collision `_pick_current_area`'s own docstring still describes... was WI1's own flagged temporary placeholder state... M007-WI5's migration 0004 resolved it... so that collision no longer exists") when WI5 replaced the old `test_home_foundations_collision_prefers_home` test — so this finding independently corroborates, rather than newly discovers, a gap WI5's own Engineer already flagged in a test comment but did not go back and fix at the source. |
| 5 | `templates/base.html` lines 33-64 (`<nav class="app-header__nav-primary">`), `core/context_processors.py` (`active_nav`, `_NAV_SECTION_BY_NAMESPACE`, `_ORGANISATIONS_URL_NAME_TO_SECTION`) | The entire OLD M006 flat 7-item primary-nav rendering path is now **structurally unreachable dead code**: confirmed by reading every template in the repo — every organisation-scoped template now `{% extends "application_shell.html" %}` (a standalone template, WI2/WI5), and `application_shell.html` does not itself extend `base.html`; only the 4 pre-organisation-selection pages (`login`, `organisations:list`/`:create`, `identity/unsafe_link_rejected.html`) still extend `base.html`, and none of them ever has `organisation` in its own context (confirmed by reading `organisations/views.py::organisation_list`/`organisation_create`), so `base.html`'s `{% if organisation %}`-gated nav-primary block can never render for any currently-registered request. `active_nav()`'s own mapping FUNCTION is unchanged and still computed correctly (`core/tests/test_active_nav.py` still green) - only its practical rendering destination is now dead. | **A — genuinely stale/dead code, touches product source** | **Not self-fixed** (product source: a template and a context processor, not a test/doc file). Flagged for PL/Engineer routing: candidate for deletion of `templates/base.html`'s nav-primary block once `organisations/tests/test_navigation.py` (item 6) is retired/superseded — non-blocking, no behavioural risk (the code is unreachable, not incorrectly reachable), no security implication. |
| 6 | `organisations/tests/test_navigation.py` (module/class docstrings — **test file**) | Its own module docstring claimed to test "the primary organisation-scoped navigation added to `templates/base.html`" — stale premise per finding 5: every assertion in this file (seven destinations linked, exactly one `aria-current="page"`, nav absent pre-organisation-selection) still PASSES, but now incidentally exercises the WI2/WI5 shell sidebar (`application_shell.html`/`entitlements.navigation`), not `base.html`, because `base.html`'s own nav-primary never renders for `organisations:detail` any more. | **A — genuinely stale assumption, test-file-only, self-fixed** | **Fixed in this dispatch.** Corrected the module docstring only (see diff) to state plainly what template/mechanism the tests now actually exercise, and why the file is kept rather than deleted (PID's "never weaken/delete existing coverage" — this file still independently proves the same seven-destination-reachable property its own PID §5/§22 authority names, just via a different, WI2/WI5-native rendering path). **Zero assertions changed** — re-ran after the edit: all 12 tests in this file still pass (see "Test counts" below). This is a proven supersession in the sense Part D's own discipline requires: I can point to the exact template `{% extends %}` line (`organisations/templates/organisations/detail.html:1`) proving `base.html` is not the template in play, and the new docstring is strictly MORE accurate than the old one, never weaker. |
| 7 | `entitlements/capabilities.py` line 42 comment ("`detail` (Overview/Home)") | Calls the `detail` route "Overview/Home" — both names, correctly acknowledging the M006→M007 rename without asserting either is now wrong | **C — checked, not stale** | None. |
| 8 | `organisations/views.py` (docstrings on `organisation_detail`/`organisation_hub`) | Both explicitly describe the OLD M006 "flat Overview card list" in the past tense ("used to render", "supersedes") while correctly stating current WI5 behaviour | **B — historical documentation, correctly framed as history** | None. |
| 9 | `core/tests/test_badge_narrow_viewport_regression.py` (Playwright real-browser test, module docstring) | Already explicitly documents the WI5 rewrite and retargets its own "Overview" badge coverage to `organisations:foundations` (the real successor page) | **B — historical documentation, correctly framed as history; already resolved by WI5's own Engineer** | None. **Not touched** — this is a real-browser Playwright test file, out of scope for this dispatch (parallel Engineer's territory) regardless of its classification. |
| 10 | `organisations/overview.py` (the whole M006 module) and its tests (`organisations/tests/test_overview.py`) | Still fully live, unchanged, independently used by `entitlements/metrics.py`'s milestone resolvers (`is_organisation_profile_complete` etc.) — `organisations/views.py`'s own docstring confirms this module "remains fully intact and independently tested" | **C — still-valid, actively reused** | None. |

No other stale route-name/destination assumption was found. Grep coverage:
every hit for `Overview`, `organisations:detail`, `app-header__nav-primary`,
`active_nav`, and `temporarily` across every `.py`/`.html` file in the
repository was individually read and classified above (the three
`ai_platform`/`risk_register` "temporarily" hits are unrelated code-editing
narration in AI eval harness comments, not routing — confirmed by reading
each, excluded from the table as not a routing hit at all).

## Part E — AI regression confirmation

Three AI evaluation harnesses exist in this repository (confirmed
exhaustive by `find . -type d -name eval`, no others found):
`policy/tests/test_eval_harness.py`, `questionnaire/tests/
test_eval_harness.py`, `risk_register/tests/test_eval_harness.py`. All
three ran unmodified as part of the full 1,806-test baseline (see "Test
counts" below) — all green, no skips among them.

- **Raw hostile organisation prose cannot fabricate security claims** —
  already proven: `risk_register/tests/test_eval_harness.py::
  TestPromptInjectionInNotesCorpusCasePayloadExclusion::
  test_hostile_corpus_text_never_reaches_the_wire_payload` (hostile
  "IGNORE ALL PREVIOUS INSTRUCTIONS"/"SYSTEM OVERRIDE" corpus text
  confirmed absent from the actual wire payload sent to the model) and
  `questionnaire/eval/golden_corpus.py`'s own `adversarial_prompt_injection_
  in_question` case (key `adversarial_prompt_injection_in_question`,
  exercised via `questionnaire/tests/test_eval_harness.py::
  test_injection_case_reports_prompt_injection_resisted`) — a
  deliberately-BAD tenant state where a successful injection would produce
  a false `SUPPORTED`, and a genuinely-resisted injection produces `GAP`
  instead; the harness confirms the latter. No prompt module was touched
  in this dispatch (none was needed — no regression found).
- **Customer Assurance SUPPORTED/CONFIRM safe-wording behaviour** —
  unchanged: `questionnaire/tests/test_outcome.py`'s 20+ deterministic
  case tests (all green, unmodified) prove the outcome engine
  (`questionnaire/outcome.py`) derives `SUPPORTED`/`CONFIRM`/`GAP`/
  `NOT_APPLICABLE` purely from canonical tenant facts, never from AI
  output — `questionnaire/tests/test_eval_harness.py::TestNegativeControl`
  additionally proves the harness itself can detect a case where a real
  outcome-engine-derived `SUPPORTED` is correctly asserted (self-
  consistency check on the corpus, not a weakening).
- **AI grounding boundaries / advisory-only doctrine** — unchanged: no
  edit was made to any file under `ai_platform/prompts/`,
  `policy/grounding.py`, `questionnaire/grounding.py`, `risk_register/
  interpretation_service.py`, or any eval harness/golden-corpus file. This
  is confirmed by `git status --short` in "Files changed" below — the AI
  layer has zero diff in this dispatch.

**No AI regression found. No prompt change made or needed.**

## Test counts

| Stage | Result |
|---|---|
| Baseline (clean checkout, before this WI's changes) | **1806 passed, 14 skipped** (`docker compose -p infosecurs-wi6 run --rm web python -m pytest -q`, full suite, `d09a954cc5e1e3223a3a8b0137adc284984af343`) |
| New file `entitlements/tests/test_wi6_session_entitlement_reproof.py` (Part A) | 28 passed |
| New file `organisations/tests/test_wi6_metrics_home_foundations_reproof.py` (Parts B/C) | 18 passed |
| `organisations/tests/test_navigation.py` after its docstring-only edit | 12 passed (unchanged from baseline — confirms the edit changed no behaviour) |
| Full suite after this WI's changes | see `docs/evidence/M007-METRICS.md`'s own "Test counts" section for the final combined number (same run covers both evidence docs) |

## Files changed in this dispatch

- `organisations/tests/test_navigation.py` — docstring-only correction (Part D, finding 6). Zero assertions changed.
- `entitlements/tests/test_wi6_session_entitlement_reproof.py` — new (Part A).
- `organisations/tests/test_wi6_metrics_home_foundations_reproof.py` — new (Parts B/C, see `M007-METRICS.md`).
- `docs/evidence/M007-SESSION-ENTITLEMENTS.md` — new (this file).
- `docs/evidence/M007-METRICS.md` — new (see that file).

No product source file was modified. No AI prompt module was modified. No existing test's assertions were weakened, deleted, or reduced in scope.

## Files read in full before writing any code

`docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md` §6-9,
§19, §25-27; `entitlements/decorators.py`; `entitlements/session.py`;
`entitlements/capabilities.py`; `entitlements/tiers.py`;
`entitlements/metrics.py`; `entitlements/navigation.py`;
`entitlements/tests/conftest.py`; `entitlements/tests/test_decorators.py`;
`entitlements/tests/test_capabilities.py`;
`entitlements/tests/test_session_contract.py`;
`entitlements/tests/test_login_issues_context.py`;
`entitlements/tests/test_navigation.py`; `organisations/views.py`;
`organisations/tests/test_navigation.py`;
`organisations/tests/test_tenant_isolation.py`;
`core/tests/test_route_matrix.py`; `core/tests/test_csrf_and_methods.py`;
`core/tests/test_application_shell.py`; `core/tests/test_active_nav.py`;
`core/context_processors.py`; `templates/base.html`;
`templates/application_shell.html`; every app's own
`test_tenant_isolation.py` (12 files); `questionnaire/tests/
test_eval_harness.py`; `questionnaire/tests/test_outcome.py`;
`risk_register/tests/test_eval_harness.py`; `policy/tests/
test_eval_harness.py`.
