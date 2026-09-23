"""
Tests for risk_register.methodology - the versioned common-security
methodology catalogue (PID §0.4/§0.4a).

Pure Python data/logic module: no database access, so none of these tests
need `@pytest.mark.django_db`. They mirror the shape of
security_baseline/tests/test_models.py's catalogue-invariant checks
(`test_catalogue_has_the_pid_defined_twelve_areas_with_unique_keys`) and
add the methodology-specific invariants PID §0.4/§0.4a require: category/
control-key referential integrity against the real `key_assets`/
`security_baseline` catalogues, and the `unknown` != `no` wording split
being real and machine-checkable, not just present in a docstring.
"""
import pytest

from key_assets.models import CATEGORY_CHOICES
from risk_register.methodology import (
    CATALOGUE,
    CATALOGUE_BY_ID,
    CATALOGUE_IDS,
    CATALOGUE_VERSION,
    VARIANT_NO,
    VARIANT_UNKNOWN,
    ControlGapWording,
    MethodologyScenario,
)
from security_baseline.catalogue import CATALOGUE_KEYS as BASELINE_KEYS
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
)

_VALID_ASSET_CATEGORIES = {key for key, _label in CATEGORY_CHOICES}

# Phrases that assert a control is definitely absent - one appears in every
# scenario's `no`-state wording below. Used to prove the `unknown`-state
# wording never makes the same assertive absence claim.
_ASSERTIVE_ONLY = [
    "is not enabled",
    "are not applied",
    "is not backed up",
    "is not promptly removed",
    "do not receive",
    "is no known route",
    "are no protections",
    "is not kept separate",
    "is no basic control",
    "has no",
    "is not protected",
]


class TestCatalogueLoadsCleanly:
    def test_catalogue_is_non_empty_and_loaded(self):
        assert len(CATALOGUE) > 0
        assert CATALOGUE_VERSION

    def test_catalogue_by_id_matches_catalogue(self):
        assert len(CATALOGUE_BY_ID) == len(CATALOGUE)
        for scenario in CATALOGUE:
            assert CATALOGUE_BY_ID[scenario.scenario_id] is scenario

    def test_catalogue_ids_list_matches_catalogue(self):
        assert CATALOGUE_IDS == [s.scenario_id for s in CATALOGUE]


class TestScenarioIdUniqueness:
    def test_scenario_ids_are_unique(self):
        ids = [s.scenario_id for s in CATALOGUE]
        assert len(ids) == len(set(ids))

    def test_scenario_ids_are_non_empty_strings(self):
        for scenario in CATALOGUE:
            assert isinstance(scenario.scenario_id, str)
            assert scenario.scenario_id.strip() != ""


class TestCatalogueCount:
    def test_count_is_within_pid_range_of_12_to_20(self):
        # PID §0.4 (Central Architecture ruling 2026-09-23): "roughly
        # 12-20 ... is preferred ... Do not create filler scenarios merely
        # to hit a count."
        assert 12 <= len(CATALOGUE) <= 20


class TestAssetCategoryReferentialIntegrity:
    def test_every_scenario_asset_category_is_a_real_key_assets_category(self):
        for scenario in CATALOGUE:
            assert scenario.asset_category in _VALID_ASSET_CATEGORIES, (
                f"{scenario.scenario_id} uses unknown asset category "
                f"{scenario.asset_category!r}"
            )

    def test_at_least_one_scenario_per_pid_explicitly_cited_category(self):
        # PID §0.4 explicitly cites these categories as required starter
        # coverage; the dispatch's own suggested-coverage list additionally
        # requires device encryption/MFA(both)/backups/endpoint protection/
        # email-phishing to each be represented.
        categories_covered = {s.asset_category for s in CATALOGUE}
        for expected in ("endpoint", "identity_or_productivity", "people", "business_application"):
            assert expected in categories_covered


class TestControlKeyReferentialIntegrity:
    def test_every_scenario_control_key_is_a_real_baseline_key(self):
        for scenario in CATALOGUE:
            for control_key in scenario.control_keys:
                assert control_key in BASELINE_KEYS, (
                    f"{scenario.scenario_id} references unknown control key "
                    f"{control_key!r}"
                )

    def test_every_scenario_has_at_least_one_control_key(self):
        for scenario in CATALOGUE:
            assert len(scenario.control_keys) >= 1

    def test_a_scenario_may_carry_more_than_one_control_key(self):
        multi_key_scenarios = [s for s in CATALOGUE if len(s.control_keys) > 1]
        assert len(multi_key_scenarios) >= 1


class TestRequiredCoverage:
    """PID §0.4/dispatch: device encryption, MFA (user + admin), backups,
    endpoint protection and email/phishing protection must each be
    represented against at least one relevant asset category."""

    @pytest.mark.parametrize(
        "required_key",
        [
            "device_encryption",
            "mfa_user_accounts",
            "mfa_privileged_accounts",
            "backups",
            "endpoint_protection",
            "email_phishing_protection",
        ],
    )
    def test_required_control_key_is_covered_by_at_least_one_scenario(self, required_key):
        covering = [s for s in CATALOGUE if required_key in s.control_keys]
        assert covering, f"No scenario covers required control key {required_key!r}"


class TestAnswerStateApplicabilityRule:
    def test_every_scenario_has_at_least_one_trigger_state(self):
        for scenario in CATALOGUE:
            assert len(scenario.trigger_states) >= 1

    def test_trigger_states_are_real_baseline_answer_states(self):
        valid_states = {ANSWER_YES, ANSWER_PARTIAL, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_NOT_APPLICABLE}
        for scenario in CATALOGUE:
            for state in scenario.trigger_states:
                assert state in valid_states

    def test_yes_never_triggers_a_scenario(self):
        for scenario in CATALOGUE:
            assert ANSWER_YES not in scenario.trigger_states

    def test_not_applicable_never_triggers_a_scenario(self):
        for scenario in CATALOGUE:
            assert ANSWER_NOT_APPLICABLE not in scenario.trigger_states

    def test_no_and_unknown_are_both_used_somewhere_in_the_catalogue(self):
        all_states = {state for s in CATALOGUE for state in s.trigger_states}
        assert ANSWER_NO in all_states
        assert ANSWER_UNKNOWN in all_states

    def test_applies_to_matches_trigger_states_membership(self):
        for scenario in CATALOGUE:
            for state in (ANSWER_YES, ANSWER_PARTIAL, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_NOT_APPLICABLE):
                assert scenario.applies_to(state) == (state in scenario.trigger_states)


class TestUnknownIsNeverCollapsedIntoNo:
    """The load-bearing PID §0.4a invariant: `unknown` must never
    deterministically produce the same assertive-absence claim as `no`."""

    def test_no_and_unknown_wording_variants_differ_for_every_dual_trigger_scenario(self):
        checked = 0
        for scenario in CATALOGUE:
            if ANSWER_NO in scenario.trigger_states and ANSWER_UNKNOWN in scenario.trigger_states:
                no_wording = scenario.wording_for(ANSWER_NO)
                unknown_wording = scenario.wording_for(ANSWER_UNKNOWN)
                assert no_wording.vulnerability != unknown_wording.vulnerability
                assert no_wording.variant == VARIANT_NO
                assert unknown_wording.variant == VARIANT_UNKNOWN
                checked += 1
        assert checked >= 5, "Expected several dual (no + unknown) scenarios to check."

    def test_unknown_wording_never_makes_an_assertive_absence_claim(self):
        checked = 0
        for scenario in CATALOGUE:
            if ANSWER_UNKNOWN not in scenario.trigger_states:
                continue
            unknown_text = scenario.wording_for(ANSWER_UNKNOWN).vulnerability.lower()
            for phrase in _ASSERTIVE_ONLY:
                assert phrase not in unknown_text, (
                    f"{scenario.scenario_id}: unknown-state wording contains "
                    f"assertive absence phrase {phrase!r}: {unknown_text!r}"
                )
            checked += 1
        assert checked >= 5

    def test_no_wording_does_make_an_assertive_absence_claim(self):
        # The mirror-image check: the `no` variant is allowed - expected -
        # to state the gap definitively for every scenario that triggers on
        # `no`.
        checked = 0
        for scenario in CATALOGUE:
            if ANSWER_NO not in scenario.trigger_states:
                continue
            no_text = scenario.wording_for(ANSWER_NO).vulnerability.lower()
            assert any(phrase in no_text for phrase in _ASSERTIVE_ONLY), (
                f"{scenario.scenario_id}: no-state wording does not read as "
                f"an assertive absence claim: {no_text!r}"
            )
            checked += 1
        assert checked >= 5

    def test_unknown_wording_uses_a_hedging_phrase(self):
        for scenario in CATALOGUE:
            if ANSWER_UNKNOWN not in scenario.trigger_states:
                continue
            unknown_text = scenario.wording_for(ANSWER_UNKNOWN).vulnerability.lower()
            assert "not confirmed" in unknown_text or "if it is not" in unknown_text or "if they are not" in unknown_text

    def test_wording_for_raises_for_an_answer_state_the_scenario_does_not_trigger_on(self):
        scenario = CATALOGUE[0]
        non_trigger_states = {ANSWER_YES, ANSWER_PARTIAL, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_NOT_APPLICABLE} - set(
            scenario.trigger_states
        )
        assert non_trigger_states, "Fixture assumption: expected at least one non-trigger state."
        for state in non_trigger_states:
            with pytest.raises(ValueError):
                scenario.wording_for(state)

    def test_partial_where_present_always_resolves_to_the_unknown_variant(self):
        scenarios_with_partial = [s for s in CATALOGUE if ANSWER_PARTIAL in s.trigger_states]
        assert scenarios_with_partial, "Expected at least one scenario to use 'partial' as a trigger."
        for scenario in scenarios_with_partial:
            wording = scenario.wording_for(ANSWER_PARTIAL)
            assert wording.variant == VARIANT_UNKNOWN


class TestControlGapWordingHelper:
    def test_for_variant_returns_no_and_unknown_correctly(self):
        wording = ControlGapWording(no="gap is definite", unknown="gap is uncertain")
        assert wording.for_variant(VARIANT_NO) == "gap is definite"
        assert wording.for_variant(VARIANT_UNKNOWN) == "gap is uncertain"

    def test_for_variant_rejects_an_unsupported_variant(self):
        wording = ControlGapWording(no="a", unknown="b")
        with pytest.raises(ValueError):
            wording.for_variant("maybe")


class TestScenarioFieldCompleteness:
    """Every field PID §0.4's exact field list requires is present and
    non-trivially populated for every scenario."""

    @pytest.mark.parametrize(
        "field_name",
        ["scenario_id", "asset_category", "exposure", "threat_event", "suggested_treatment"],
    )
    def test_string_field_is_non_empty_for_every_scenario(self, field_name):
        for scenario in CATALOGUE:
            value = getattr(scenario, field_name)
            assert isinstance(value, str)
            assert value.strip() != ""

    def test_vulnerability_and_consequence_are_control_gap_wording_instances(self):
        for scenario in CATALOGUE:
            assert isinstance(scenario.vulnerability, ControlGapWording)
            assert isinstance(scenario.consequence, ControlGapWording)
            assert scenario.vulnerability.no.strip() != ""
            assert scenario.vulnerability.unknown.strip() != ""
            assert scenario.consequence.no.strip() != ""
            assert scenario.consequence.unknown.strip() != ""

    def test_every_scenario_is_a_methodology_scenario_instance(self):
        for scenario in CATALOGUE:
            assert isinstance(scenario, MethodologyScenario)
