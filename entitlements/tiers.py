"""
Canonical commercial package tier hierarchy (PID §5).

This module is the SINGLE source of truth for the tier integer <-> package
code mapping and the cumulative access rule. Nothing else in this codebase
(now, or in a later WI) should re-derive or duplicate this mapping - PID §5's
own explicit invariant is "No separate 'Foundation enabled' flag should be
needed for a Monthly or Pro customer", which only holds if every consumer
goes through the same comparison (`current_tier >= required_tier`) against
the same four fixed values.
"""
from __future__ import annotations

TIER_PAUSED = 0
TIER_FOUNDATION = 1
TIER_MONTHLY = 2
TIER_PRO = 3

CODE_PAUSED = "PAUSED"
CODE_FOUNDATION = "FOUNDATION"
CODE_MONTHLY = "MONTHLY"
CODE_PRO = "PRO"

# The one canonical mapping. Every tier<->code translation anywhere in this
# codebase must go through TIER_CODE_BY_VALUE/CODE_TIER_BY_VALUE (or the
# helper functions below), never a second hand-written dict.
TIER_CODE_BY_VALUE = {
    TIER_PAUSED: CODE_PAUSED,
    TIER_FOUNDATION: CODE_FOUNDATION,
    TIER_MONTHLY: CODE_MONTHLY,
    TIER_PRO: CODE_PRO,
}
CODE_TIER_BY_VALUE = {code: value for value, code in TIER_CODE_BY_VALUE.items()}

# Frozen - this is fixed product methodology (cumulative tiers 0-3), not
# runtime-configurable data.
VALID_TIERS = frozenset(TIER_CODE_BY_VALUE)
VALID_CODES = frozenset(CODE_TIER_BY_VALUE)

MIN_TIER = min(VALID_TIERS)
MAX_TIER = max(VALID_TIERS)


def is_valid_tier(value) -> bool:
    """
    True only for exactly one of the four canonical integers - deliberately
    excludes bool (a JSON `true`/`false` deserialises to Python bool, which
    is an int subclass and would otherwise satisfy `value in VALID_TIERS`
    via `True == 1`). A tampered/malformed session must never be treated as
    a valid tier by accident of Python's numeric type coercion.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value in VALID_TIERS


def tier_code(tier: int) -> str:
    """Raises KeyError for anything not in VALID_TIERS - callers must
    validate with `is_valid_tier` first; this is not a fail-closed boundary
    itself, `entitlements.session.validate_context` is."""
    return TIER_CODE_BY_VALUE[tier]


def code_tier(code: str) -> int:
    return CODE_TIER_BY_VALUE[code]


def code_matches_tier(tier, code) -> bool:
    """True only when `code` is exactly the one canonical string for
    `tier` - the ONE place this comparison is made (PID §6.4's "package
    code matches package tier" check consumes this, never re-derives it)."""
    return is_valid_tier(tier) and TIER_CODE_BY_VALUE.get(tier) == code


def has_access(current_tier: int, required_tier: int) -> bool:
    """
    The single cumulative access rule (PID §5): `current_tier >=
    required_tier`. This is the whole rule - Pro (3) satisfies a Monthly
    (2) or Foundation (1) requirement automatically because 3 >= 2 >= 1,
    with no separate per-tier flag anywhere.
    """
    return current_tier >= required_tier
