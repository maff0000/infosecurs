"""
PID.md M002 §0.5's "derive it from here ... don't hand-maintain a second,
potentially-drifting mapping" requirement:
relevant_control_keys_for_category() must be a pure function of
risk_register.methodology.CATALOGUE, so these tests independently
recompute the expected answer straight from that catalogue (never from the
function under test) for several categories.
"""
import pytest

from key_assets.models import (
    CATEGORY_BUSINESS_APPLICATION,
    CATEGORY_ENDPOINT,
    CATEGORY_OTHER,
    CATEGORY_PEOPLE,
)
from key_assets.protection_checks import relevant_control_keys_for_category
from risk_register.methodology import CATALOGUE as METHODOLOGY_CATALOGUE
from security_baseline.catalogue import CATALOGUE_KEYS


def _independently_computed_keys(category):
    """
    A from-scratch recomputation of "control keys for this category",
    written directly against risk_register.methodology.CATALOGUE rather
    than calling relevant_control_keys_for_category() - so a passing
    assertion actually proves agreement with the methodology catalogue,
    not just internal self-consistency.
    """
    keys = []
    for scenario in METHODOLOGY_CATALOGUE:
        if scenario.asset_category == category:
            for key in scenario.control_keys:
                if key not in keys:
                    keys.append(key)
    return keys


class TestRelevantControlKeysForCategory:
    def test_endpoint_category_matches_methodology_catalogue(self):
        expected = _independently_computed_keys(CATEGORY_ENDPOINT)
        assert expected, "test fixture assumption: endpoint must have scenarios in the catalogue"
        assert relevant_control_keys_for_category(CATEGORY_ENDPOINT) == expected
        # Spot-check the exact set a human reading PID §0.5 would expect for
        # an employee-endpoint asset: device encryption, endpoint
        # protection, patching.
        assert set(expected) == {"device_encryption", "endpoint_protection", "patching"}

    def test_people_category_matches_methodology_catalogue(self):
        expected = _independently_computed_keys(CATEGORY_PEOPLE)
        assert expected
        assert relevant_control_keys_for_category(CATEGORY_PEOPLE) == expected
        assert set(expected) == {
            "joiner_mover_leaver",
            "security_awareness_training",
            "incident_reporting_route",
        }

    def test_category_with_no_scenarios_returns_empty_list_not_an_error(self):
        # No methodology scenario currently targets "other" - this is a
        # legitimate result (PID §0.5 does not require every category to
        # have protection checks), not a bug.
        assert _independently_computed_keys(CATEGORY_OTHER) == []
        assert relevant_control_keys_for_category(CATEGORY_OTHER) == []

    def test_every_returned_key_is_a_real_security_baseline_catalogue_key(self):
        for category in {s.asset_category for s in METHODOLOGY_CATALOGUE}:
            for key in relevant_control_keys_for_category(category):
                assert key in CATALOGUE_KEYS

    def test_no_duplicate_keys_within_a_category(self):
        # cloud_service's one scenario declares two control_keys and is a
        # realistic case for this - but even a category whose scenarios
        # share a control key across multiple scenarios must de-duplicate.
        for category in {s.asset_category for s in METHODOLOGY_CATALOGUE}:
            keys = relevant_control_keys_for_category(category)
            assert len(keys) == len(set(keys))

    @pytest.mark.django_db
    def test_is_a_pure_function_with_no_database_query(self, django_assert_num_queries):
        with django_assert_num_queries(0):
            relevant_control_keys_for_category(CATEGORY_ENDPOINT)
