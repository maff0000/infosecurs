"""
PID §5's own required proofs: the cumulative invariant and the exact
`current_tier >= required_tier` access rule - the single source of truth
every other tier check in this codebase must consume.
"""
import itertools

from entitlements import tiers


class TestCumulativeInvariant:
    def test_pro_ge_monthly_ge_foundation_ge_paused(self):
        assert tiers.TIER_PRO >= tiers.TIER_MONTHLY >= tiers.TIER_FOUNDATION >= tiers.TIER_PAUSED

    def test_exact_values(self):
        assert (tiers.TIER_PAUSED, tiers.TIER_FOUNDATION, tiers.TIER_MONTHLY, tiers.TIER_PRO) == (0, 1, 2, 3)


class TestOneCanonicalMapping:
    def test_tier_code_round_trip(self):
        for tier in (tiers.TIER_PAUSED, tiers.TIER_FOUNDATION, tiers.TIER_MONTHLY, tiers.TIER_PRO):
            assert tiers.code_tier(tiers.tier_code(tier)) == tier

    def test_every_tier_has_exactly_one_code(self):
        assert tiers.TIER_CODE_BY_VALUE == {
            0: "PAUSED",
            1: "FOUNDATION",
            2: "MONTHLY",
            3: "PRO",
        }

    def test_code_tier_is_the_exact_inverse(self):
        for tier, code in tiers.TIER_CODE_BY_VALUE.items():
            assert tiers.CODE_TIER_BY_VALUE[code] == tier


class TestCodeMatchesTier:
    def test_correct_pairs_match(self):
        for tier, code in tiers.TIER_CODE_BY_VALUE.items():
            assert tiers.code_matches_tier(tier, code) is True

    def test_mismatched_pairs_do_not_match(self):
        for tier, code in tiers.TIER_CODE_BY_VALUE.items():
            for other_code in tiers.VALID_CODES - {code}:
                assert tiers.code_matches_tier(tier, other_code) is False

    def test_invalid_tier_never_matches_any_code(self):
        for code in tiers.VALID_CODES:
            assert tiers.code_matches_tier(4, code) is False
            assert tiers.code_matches_tier(-1, code) is False
            assert tiers.code_matches_tier("2", code) is False


class TestIsValidTier:
    def test_the_four_canonical_integers_are_valid(self):
        for tier in tiers.VALID_TIERS:
            assert tiers.is_valid_tier(tier) is True

    def test_out_of_range_integers_are_invalid(self):
        for tier in (-1, 4, 100, -100):
            assert tiers.is_valid_tier(tier) is False

    def test_bool_is_never_treated_as_a_valid_tier(self):
        # True == 1 and False == 0 in Python - a tampered JSON session
        # value of `true`/`false` must never be silently accepted as
        # tier 1/0 via that numeric coincidence.
        assert tiers.is_valid_tier(True) is False
        assert tiers.is_valid_tier(False) is False

    def test_non_numeric_types_are_invalid(self):
        for value in ("1", None, 1.0, [1], {"tier": 1}):
            assert tiers.is_valid_tier(value) is False


class TestHasAccess:
    def test_access_rule_is_exactly_current_ge_required(self):
        for current, required in itertools.product(range(-1, 5), range(-1, 5)):
            assert tiers.has_access(current, required) == (current >= required)

    def test_pro_inherits_every_lower_tier_capability(self):
        for required in (tiers.TIER_PAUSED, tiers.TIER_FOUNDATION, tiers.TIER_MONTHLY, tiers.TIER_PRO):
            assert tiers.has_access(tiers.TIER_PRO, required) is True

    def test_foundation_is_denied_monthly_and_pro_capabilities(self):
        assert tiers.has_access(tiers.TIER_FOUNDATION, tiers.TIER_MONTHLY) is False
        assert tiers.has_access(tiers.TIER_FOUNDATION, tiers.TIER_PRO) is False

    def test_paused_is_denied_everything_above_paused(self):
        assert tiers.has_access(tiers.TIER_PAUSED, tiers.TIER_FOUNDATION) is False
        assert tiers.has_access(tiers.TIER_PAUSED, tiers.TIER_MONTHLY) is False
        assert tiers.has_access(tiers.TIER_PAUSED, tiers.TIER_PRO) is False
