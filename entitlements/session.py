"""
Infosecurs dashboard session contract (PID §6).

The browser holds only the ordinary opaque Django session identifier;
business/session meaning (package tier, active organisation, entitlement
version) lives exclusively server-side, under one structured, versioned key
- `request.session[SESSION_KEY]` (§6.2). Every read of that stored value
goes through `validate_context` below - the ONE centralised place fail-
closed validation happens (§6.4). Nothing else in this codebase should
parse `request.session[SESSION_KEY]` directly.

`issue_context` is the `SessionContextIssuer` (§6.6): the one function that
turns "an authenticated Django user, optionally with an active organisation
and a resolved package tier" into a freshly-issued, rotated-key session
context. Both the current Django/allauth Beta login and any future external
account system are meant to call this same function - see `signals.py` for
how the current Beta login is wired to it.
"""
from __future__ import annotations

import dataclasses
import enum
from typing import Optional, Union

from django.utils import timezone as django_timezone

from entitlements.tiers import code_matches_tier, is_valid_tier

SESSION_KEY = "infosecurs_context"

# Bump only with a genuine, deliberate schema change - see
# `validate_context`'s "unknown schema version" fail-closed check below.
SCHEMA_VERSION = 1

# A separate, independent version number from SCHEMA_VERSION (PID §6.2/
# §10.3): SCHEMA_VERSION describes the *shape* of this dict,
# ENTITLEMENT_VERSION would describe a future change to *how* entitlement
# itself is decided (e.g. a new capability-decision algorithm) - kept
# distinct so either can change without forcing the other to.
ENTITLEMENT_VERSION = 1

REQUIRED_FIELDS = (
    "schema_version",
    "subject_id",
    "organisation_id",
    "package_tier",
    "package_code",
    "entitlement_version",
    "issued_at",
    "auth_source",
)


class InvalidReason(enum.Enum):
    """Every distinct fail-closed reason `validate_context` can return.
    Deliberately enumerated (not a bare string) so a test can assert
    exactly which check fired (PID §25.2's tampering matrix)."""

    MISSING = "missing"
    NOT_A_MAPPING = "not_a_mapping"
    MISSING_FIELD = "missing_field"
    UNKNOWN_SCHEMA_VERSION = "unknown_schema_version"
    UNAUTHENTICATED = "unauthenticated"
    SUBJECT_MISMATCH = "subject_mismatch"
    TIER_OUT_OF_RANGE = "tier_out_of_range"
    CODE_TIER_MISMATCH = "code_tier_mismatch"
    ORGANISATION_ID_MALFORMED = "organisation_id_malformed"


@dataclasses.dataclass(frozen=True)
class InfosecursContext:
    """A validated, typed session context. Only ever constructed by
    `validate_context` below on a fully-passed check - never partially, and
    never with a placeholder/default tier."""

    schema_version: int
    subject_id: str
    organisation_id: Optional[str]
    package_tier: int
    package_code: str
    entitlement_version: int
    issued_at: str
    auth_source: str


@dataclasses.dataclass(frozen=True)
class Invalid:
    """The explicit "deny" signal (PID §6.4) - never a silently permissive
    default. Callers (the entitlement service, any future view guard) must
    check `isinstance(result, Invalid)` and deny/redirect; this module
    itself never decides what a caller does with a deny."""

    reason: InvalidReason


ContextResult = Union[InfosecursContext, Invalid]


def validate_context(raw, *, user) -> ContextResult:
    """
    Fail-closed validation (PID §6.4). Every one of the required checks is
    independent - a single failed check anywhere returns `Invalid`, never a
    default/permissive tier. The organisation-membership re-verification
    that a *present* `organisation_id` would need is deliberately NOT done
    here: that is the tenant-scoping layer's job
    (`organisations.views.get_member_organisation_or_404`), a SEPARATE gate
    per PID §9.3/§6.5 - this function only proves the stored
    `organisation_id` is well-formed, never that the user is still a member
    of it.
    """
    if raw is None:
        return Invalid(InvalidReason.MISSING)
    if not isinstance(raw, dict):
        return Invalid(InvalidReason.NOT_A_MAPPING)

    for field in REQUIRED_FIELDS:
        if field not in raw:
            return Invalid(InvalidReason.MISSING_FIELD)

    if raw["schema_version"] != SCHEMA_VERSION:
        return Invalid(InvalidReason.UNKNOWN_SCHEMA_VERSION)

    if user is None or not getattr(user, "is_authenticated", False):
        return Invalid(InvalidReason.UNAUTHENTICATED)

    subject_id = raw["subject_id"]
    if not isinstance(subject_id, str) or subject_id != str(user.pk):
        return Invalid(InvalidReason.SUBJECT_MISMATCH)

    tier = raw["package_tier"]
    if not is_valid_tier(tier):
        return Invalid(InvalidReason.TIER_OUT_OF_RANGE)

    code = raw["package_code"]
    if not isinstance(code, str) or not code_matches_tier(tier, code):
        return Invalid(InvalidReason.CODE_TIER_MISMATCH)

    organisation_id = raw["organisation_id"]
    if organisation_id is not None and (not isinstance(organisation_id, str) or not organisation_id.strip()):
        return Invalid(InvalidReason.ORGANISATION_ID_MALFORMED)

    return InfosecursContext(
        schema_version=raw["schema_version"],
        subject_id=subject_id,
        organisation_id=organisation_id,
        package_tier=tier,
        package_code=code,
        entitlement_version=raw["entitlement_version"],
        issued_at=raw["issued_at"],
        auth_source=raw["auth_source"],
    )


def get_validated_context(request) -> ContextResult:
    """Convenience wrapper: read `SESSION_KEY` off `request.session` and
    validate it against `request.user`. The one place other than
    `validate_context` itself that should ever look at the raw session
    value."""
    raw = request.session.get(SESSION_KEY)
    user = getattr(request, "user", None)
    return validate_context(raw, user=user)


def issue_context(
    request,
    user,
    *,
    package_tier: int,
    organisation_id=None,
    auth_source: str,
    package_code: Optional[str] = None,
) -> dict:
    """
    The `SessionContextIssuer` (PID §6.6). Constructs a fresh, structured
    `infosecurs_context` for `user` and stores it under `SESSION_KEY`,
    rotating the session key first (`request.session.cycle_key()`) - this
    is the architectural session-fixation-prevention mechanism PID §8.2/
    §19.1 requires: whenever a new security context is issued (login, or a
    later organisation/tier switch), the underlying session identifier
    genuinely changes, in the service itself, not bolted on by a view later.

    `cycle_key()` retains the in-memory session dict and only changes the
    key used to persist it - calling it before writing the new context (as
    here) or after makes no difference to what ends up stored; this order
    is chosen so the intent reads as "rotate, then issue under the new
    identity".

    Raises `ValueError` if a caller passes a `package_code` that does not
    match `package_tier` - this function must never silently persist an
    internally-inconsistent context; it is the trusted issuer, so it holds
    itself to the exact same code/tier invariant `validate_context` checks
    on every read.
    """
    if package_code is None:
        from entitlements.tiers import tier_code

        package_code = tier_code(package_tier)
    elif not code_matches_tier(package_tier, package_code):
        raise ValueError(f"package_code {package_code!r} does not match package_tier {package_tier!r}")

    context = {
        "schema_version": SCHEMA_VERSION,
        "subject_id": str(user.pk),
        "organisation_id": str(organisation_id) if organisation_id is not None else None,
        "package_tier": package_tier,
        "package_code": package_code,
        "entitlement_version": ENTITLEMENT_VERSION,
        "issued_at": django_timezone.now().isoformat(),
        "auth_source": auth_source,
    }

    request.session.cycle_key()
    request.session[SESSION_KEY] = context
    return context
