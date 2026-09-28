# M007-WI6 — Methodology/Metrics (Part B) and Home/Foundations (Part C) Regression Re-Proof

**Authorising commit (final merged M007 source, WI1-WI5 landed):** `d09a954cc5e1e3223a3a8b0137adc284984af343` (`main`)
**Worktree:** `/srv/infosecurs-worktrees/wi6-session-metrics-regression`, branch `wi6-session-metrics-regression`

Companion to `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Parts A/D/E).
This document covers Parts B and C: a fresh regression re-proof of the
Foundational Security Posture / Security Foundations Completion
methodology (`entitlements/metrics.py`) and the Home/Foundations pages
built on it (`organisations/views.py::organisation_detail`/
`organisation_foundations`).

## Method

`entitlements/tests/test_metrics.py` (697 lines) and `organisations/tests/
test_home_view.py` (362 lines) / `test_foundations_view.py` (207 lines)
were read in full before writing anything. All three already exhaustively
cover PID §26/§27's own required-test list — see the per-property table
below, which cites the exact existing test for every PID §26/§27 bullet.
New file `organisations/tests/test_wi6_metrics_home_foundations_reproof.py`
(18 tests) adds only what that reading identified as genuinely missing or
worth a second, independent proof route (hand-calculated expected values
checked against real rendered HTTP output, rather than against a second
call into the same service function under test).

## Part B.1 — Posture (PID §26.1)

| PID §26.1 requirement | Existing coverage | This WI's addition |
|---|---|---|
| all YES → 100% | `test_metrics.py::TestPosture::test_all_yes_is_100_percent` | `test_wi6_...::test_all_twelve_controls_yes_renders_100_percent` — re-proven through real rendered Home HTML |
| all NO → 0% | `test_metrics.py::TestPosture::test_all_no_is_0_percent` | (covered by existing + Scenario A below) |
| all UNKNOWN/missing → 0% | `test_metrics.py::TestPosture::test_all_unknown_is_0_percent_and_stays_lexically_unknown`, `test_all_missing_answers_treated_identically_to_unknown` | — |
| PARTIAL earns exactly half weight | `test_metrics.py::test_partial_earns_exactly_half_its_weight` | Exercised again as part of the hand-calculated mixed-weight test below |
| N/A excluded from denominator | `test_metrics.py::test_not_applicable_excluded_from_denominator` | Exercised again as part of the hand-calculated mixed-weight test below |
| mixed weights calculate correctly | `test_metrics.py::test_mixed_weights_hand_calculated`, `test_deterministic_round_half_up_not_bankers_rounding` | `test_wi6_...::test_hand_calculated_mixed_weight_percentage_matches_rendered_home` — an INDEPENDENTLY hand-calculated 3-control scenario (YES/PARTIAL/N-A, weight-5 controls) → 23% (round-half-up of 22.727...%), checked against the real rendered Home page, not a second call into `get_foundational_security_posture` |
| missing `BaselineAnswer` = UNKNOWN, not NO | `test_metrics.py::test_all_missing_answers_treated_identically_to_unknown` | — |
| evidence/policy/remediation/AI never move posture | `test_metrics.py::TestPostureNonInflation::test_surrounding_domain_records_do_not_change_posture` | — |
| deterministic `methodology_version` | `test_metrics.py::test_methodology_version_present_and_correct` | — |
| foreign-methodology-version isolation | `test_metrics.py::TestMethodologyVersionIsolation::test_foreign_version_active_row_never_affects_any_of_the_four_functions` (the "just-merged pre-WI6 correction" the dispatch names) | Re-ran as part of this WI's full-suite pass — still green, unmodified |

**Result: every PID §26.1 bullet is proven, either by existing coverage
(re-run and confirmed green) or by this WI's own fresh, independently
hand-calculated, HTTP-level addition. PASS.**

## Part B.2 — Completion (PID §26.2)

| PID §26.2 requirement | Existing coverage |
|---|---|
| initial untouched organisation → correct incomplete total (18) | `test_metrics.py::TestCompletion::test_fresh_organisation_is_fully_incomplete` |
| every answered baseline question increments completion exactly once | `test_each_answered_baseline_control_increments_completion_by_one` |
| UNKNOWN does not count complete | `test_unknown_and_missing_do_not_count_complete` |
| NO/PARTIAL/N-A all count complete | `test_yes_partial_no_not_applicable_all_count_complete` (parametrized) |
| profile/governance/workplace/assets/risks/policy resolvers | one positive + one negative case each: `test_organisation_profile_resolver`, `test_governance_resolver` (+ `_false_when_assignee_inactive`), `test_workplace_resolver`, `test_assets_review_resolver` (+ `_incomplete_while_suggestion_pending`), `test_risks_review_resolver_*` (3 tests), `test_policy_approved_resolver` (+ `_stays_complete_even_when_overdue`) |
| no duplicate counting; total = current v1 definition (18) | `test_full_eighteen_item_total_no_double_counting` |
| no customer-editable completion flag | `test_requirement_state_is_immutable_no_editable_completion_flag` (frozen dataclass proof + `hasattr` checks on the model) |

**Result: every PID §26.2 bullet already fully proven; re-run and
confirmed green as part of this WI's full-suite pass. No gap identified —
no new test needed for this sub-section.**

## Part B.3 — Separation between metrics (PID §26.3 / Appendix C)

`entitlements/tests/test_metrics.py::TestSeparationBetweenMetrics::
test_scenario_a_high_completion_low_posture` and
`test_scenario_b_high_posture_lower_completion` already construct and
prove both PID Appendix C scenarios exactly (Scenario A: all-NO baseline +
every milestone complete → completion 100% / posture 0%; Scenario B:
all-YES baseline + zero milestones → posture 100% / completion 12/18).
Cited, not duplicated.

**This WI's addition:** `TestMetricDivergenceVisibleOnRenderedHome` proves
the SAME two scenarios are visibly distinct on the real rendered Home page
(not merely in the service's return value) — Scenario A renders `0%`
(posture) and `100%` (completion) in the same response; Scenario B renders
`100%` (posture) and the literal completion copy `12 of 18 Foundations
items completed.` (strictly lower than 100%) in the same response.

**Result: PASS.**

## Part C — Home/Foundations regression re-proof

| Requirement | Existing coverage | This WI's addition |
|---|---|---|
| Home shows exactly the two named metric cards, no third headline score | `test_home_view.py::TestNonPausedHomeMetricCards::test_both_cards_show_the_exact_live_service_percentages` (names present) + `test_posture_disclaimer_text_is_present` (forbidden certification-adjacent wording absent) — neither one MECHANICALLY COUNTS the metric-card elements | **Gap closed:** `test_wi6_...::TestHomeShowsExactlyTwoMetricCardsNoThirdScore` — `content.count('class="metric-card"') == 2` (never 3+), `metric-card-row` appears exactly once, and a Paused session renders zero `metric-card` elements at all |
| Posture disclaimer text present; completion `X of Y` count present | `test_home_view.py::test_posture_disclaimer_text_is_present`, `test_both_cards_show_the_exact_live_service_percentages` | — |
| Needs Attention: zero-count lines omitted, correct counts/destinations, row never itself a link | `test_home_view.py::TestNeedsAttention` (9 tests) — including the mechanical real-HTML-parse (`_NeedsAttentionParser`, stdlib `html.parser`) proof in `test_every_rendered_line_is_not_itself_a_link_only_click_here_is` | Cited, not duplicated — re-ran, still green |
| Foundations: 18 v1 rows, baseline real-answer-state preserved, milestone Complete/Needs-completion wording, action destinations, no form/editable-completion-control, distinct route, `foundations` area's `destination_view_name` | `test_foundations_view.py` — all 3 classes (`TestFoundationsIsAGenuinelyDistinctRoute`, `TestFoundationsTierMatrix`, `TestFoundationsWorkspaceContent`, 12 tests total) | Cited, not duplicated — re-ran, still green |
| Metric divergence (Scenario A/B) visible in the UI, not just the service return value | (not previously tested at the HTTP layer) | **Gap closed:** `TestMetricDivergenceVisibleOnRenderedHome` (see Part B.3 above) |

**Result: PASS, all bullets. Two genuine gaps identified and closed (exact
metric-card count; UI-visible metric divergence) — everything else was
already fully proven and is cited, not duplicated.**

## Test counts

| Stage | Result |
|---|---|
| Baseline (clean checkout, before this WI's changes) | **1806 passed, 14 skipped** — `docker compose -p infosecurs-wi6 run --rm web python -m pytest -q`, `d09a954cc5e1e3223a3a8b0137adc284984af343` |
| `manage.py makemigrations --check --dry-run` (baseline and after) | "No changes detected" both times |
| `gitleaks detect --no-git` (whole worktree) and `gitleaks protect` (uncommitted diff) | both: **no leaks found** |
| New file `organisations/tests/test_wi6_metrics_home_foundations_reproof.py` (Parts B/C) | 18 passed |
| New file `entitlements/tests/test_wi6_session_entitlement_reproof.py` (Part A, see `M007-SESSION-ENTITLEMENTS.md`) | 28 passed |
| `organisations/tests/test_navigation.py` after its docstring-only edit | 12 passed — unchanged from baseline |
| **Full suite after this WI's changes** | **1852 passed, 14 skipped** (1806 baseline + 28 + 18 new tests; `organisations/tests/test_navigation.py`'s 12 were already counted in the 1806 baseline and are unchanged) |

No test was deleted, skipped, or weakened. No product source file was
modified. Two evidence files added (this one and
`M007-SESSION-ENTITLEMENTS.md`), two new test files added, one existing
test file's docstring corrected (zero assertion changes — see
`M007-SESSION-ENTITLEMENTS.md` Part D finding 6).

## Files read in full before writing any code

`docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md` §10-14,
§21-24, §26-27; `entitlements/metrics.py`; `entitlements/tests/
test_metrics.py`; `organisations/views.py` (`organisation_detail`,
`organisation_foundations` and their shared helpers);
`organisations/tests/test_home_view.py`; `organisations/tests/
test_foundations_view.py`; `organisations/templates/organisations/
detail.html`; `organisations/templates/organisations/foundations.html`.
