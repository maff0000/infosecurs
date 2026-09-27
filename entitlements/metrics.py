"""
M007-WI4: Foundational Security Posture / Security Foundations Completion
methodology, requirement resolvers, and Needs Attention derivation (PID
§10-14, §23-24, §26-27).

This is the ONE canonical calculation path for both metrics (PID §23): a
template, a view, or any other module must call the four functions below
rather than recomputing a percentage independently anywhere else. Nothing
here writes anything, ever, and nothing here stores a computed score - both
metrics and every per-requirement state are derived fresh from canonical
domain rows on every call, exactly like `organisations.overview.
build_overview` already does for the areas it covers (PID §10.4/§12.5:
"Do not create a customer-editable completed=True... Resolvers derive
completion from existing canonical domain records").

Resolver registry (PID §10.2, §22): `entitlements.migrations.
0003_seed_foundation_requirements` seeds exactly 18 active
`FoundationRequirement` rows, each carrying an inert `source_key` string
the database itself never interprets. `BASELINE_RESOLVERS`/
`MILESTONE_RESOLVERS` below are the ONLY place those 18 strings are given
meaning - a plain Python dict, never a stored callable/import path in the
database. Any active row whose `source_key` has no registered resolver
raises `UnresolvableFoundationRequirementError` rather than being silently
skipped (PID §10.2's own "avoid a situation where a DB row exists but no
resolver means it is quietly ignored") - deliberately fail-loud.

Core truth doctrine this module must never violate (PID §21, repeated in
the M007-WI4 dispatch): UNKNOWN != NO, evidence/policy/remediation/AI
presence never changes posture, `not_applicable` is excluded from the
posture denominator but still counts as a *completed* assessment answer.
See `RequirementState.answer_state`/`is_posture_applicable`/
`is_completion_complete` below for exactly where each of those distinctions
lives.
"""
from __future__ import annotations

import dataclasses
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

from entitlements.models import FOUNDATION_METRIC_VERSION, FoundationRequirement, RequirementKind
from organisations.overview import (
    has_approved_policy,
    is_approved_policy_review_overdue,
    is_assets_review_complete,
    is_governance_complete,
    is_organisation_profile_complete,
    is_risks_review_complete,
    is_workplace_complete,
)
from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
    BaselineAssessment,
)

# ---------------------------------------------------------------------------
# Completion states for DERIVED_MILESTONE rows. BASELINE_CONTROL rows use
# the raw ANSWER_* strings (imported above) as their `answer_state` instead
# - deliberately never rewritten to these two strings, so a baseline
# UNKNOWN stays lexically distinct from a milestone's own INCOMPLETE
# everywhere in this module's output (PID §21 "never rewrite UNKNOWN to NO
# for scoring convenience" - the same discipline extended to milestones).
# ---------------------------------------------------------------------------
STATE_COMPLETE = "complete"
STATE_INCOMPLETE = "incomplete"

# PID §11.3's state-factor table. ANSWER_NOT_APPLICABLE is deliberately
# absent - it is never assigned a posture factor at all (excluded from both
# numerator and denominator, handled as its own branch below), not merely
# "worth zero" like ANSWER_NO/ANSWER_UNKNOWN.
POSTURE_FACTOR_BY_ANSWER: dict[str, Decimal] = {
    ANSWER_YES: Decimal("1.0"),
    ANSWER_PARTIAL: Decimal("0.5"),
    ANSWER_NO: Decimal("0"),
    ANSWER_UNKNOWN: Decimal("0"),
}

# PID §14.2 - "important" for the Needs Attention important-controls signal.
IMPORTANT_CONTROL_MIN_WEIGHT = 3

# PID §14.1's destination examples, expressed as the stable `ProductArea.code`
# values the seeded WI1 data already uses (entitlements/migrations/
# 0002_seed_product_areas.py) - WI5's template builds the actual link from
# this code; nothing here renders HTML or wording (PID §14.1: "WI5 renders
# the customer-facing text... that is WI5's template concern, not yours").
DESTINATION_IMPORTANT_CONTROLS = "security_state"
DESTINATION_NOT_SURE_CONTROLS = "baseline"
DESTINATION_FOUNDATIONS_INCOMPLETE = "foundations"
DESTINATION_POLICY_REVIEW_OVERDUE = "policies"


class UnresolvableFoundationRequirementError(Exception):
    """
    Raised when an active `FoundationRequirement` row's `(requirement_kind,
    source_key)` has no registered resolver, or has a `requirement_kind`
    this module does not recognise at all. Deliberate fail-loud design
    (PID §10.2) - never silently skipped/ignored.
    """


def _baseline_resolver(question_key: str) -> Callable[[dict], str]:
    """
    One resolver shape, reused for all 12 `BASELINE_CONTROL` source_keys
    (they are identical logic parameterised only by which catalogue
    question they read) - `baseline_answers` is the pre-fetched
    {question_key: answer} map for one organisation (see
    `_fetch_baseline_answers` below), so resolving all 12 controls costs
    one shared query pass, never one query per requirement (PID's own "no
    N+1 query explosion across the 18 requirement rows"). A missing key in
    that map means no `BaselineAnswer` row exists for this question at all
    - this codebase's own existing convention for "unanswered" (confirmed
    in `organisations.overview._security_baseline_area`'s identical
    `answers.get(item["key"], ANSWER_UNKNOWN)` pattern) - never conflated
    with a deliberate `no`.
    """

    def resolver(baseline_answers: dict) -> str:
        return baseline_answers.get(question_key, ANSWER_UNKNOWN)

    return resolver


# The 12 BASELINE_CONTROL source_keys are exactly
# `security_baseline.catalogue.CATALOGUE_KEYS` (entitlements/migrations/
# 0003_seed_foundation_requirements.py's own `BASELINE_ROWS` sets
# `source_key` to this exact catalogue key per row) - built programmatically
# rather than 12 hand-written near-duplicate entries.
BASELINE_RESOLVERS: dict[str, Callable[[dict], str]] = {
    key: _baseline_resolver(key) for key in CATALOGUE_KEYS
}

# The 6 DERIVED_MILESTONE source_keys, exactly as
# entitlements/migrations/0003_seed_foundation_requirements.py's
# `MILESTONE_ROWS` defines them. Each resolver takes `organisation` and
# returns a plain bool - the predicates themselves are extracted/reused
# from `organisations.overview` (PID §24), never re-derived here.
MILESTONE_RESOLVERS: dict[str, Callable[..., bool]] = {
    "organisation_profile": is_organisation_profile_complete,
    "governance_roles": is_governance_complete,
    "workplace": is_workplace_complete,
    "assets_review": is_assets_review_complete,
    "risks_review": is_risks_review_complete,
    "policy_approved": has_approved_policy,
}


def _fetch_baseline_answers(organisation) -> dict[str, str]:
    """
    One bounded query pass (assessment lookup + its answers) shared by all
    12 baseline resolvers for one organisation - never one query per
    requirement row. A missing `BaselineAssessment` altogether (never
    started) returns an empty map, which every baseline resolver above
    already treats identically to "assessment exists but this particular
    question has no answer row" via its own `.get(..., ANSWER_UNKNOWN)` -
    both are UNKNOWN, per PID §11.5 ("Missing rows are treated exactly as
    the existing product treats an unanswered baseline control: UNKNOWN").
    """
    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    if assessment is None:
        return {}
    return {answer.question_key: answer.answer for answer in assessment.answers.all()}


@dataclasses.dataclass(frozen=True)
class RequirementState:
    """
    One resolved `FoundationRequirement` row - the shared per-requirement
    detail both metrics below are built from (PID §23), and exactly what
    `get_foundations_requirement_states` exposes on its own for a future
    WI5 Foundations workspace to render directly (PID §15).

    `answer_state` is either one of the raw `security_baseline.models`
    `ANSWER_*` strings (for a `BASELINE_CONTROL` row) or one of this
    module's `STATE_COMPLETE`/`STATE_INCOMPLETE` (for a
    `DERIVED_MILESTONE` row) - deliberately never normalised into one
    shared vocabulary, so a baseline UNKNOWN is never even superficially
    interchangeable with a milestone's INCOMPLETE.

    `is_posture_applicable` is only meaningful when `counts_toward_posture`
    is True (today: only `BASELINE_CONTROL` rows) - False exactly when the
    answer is `not_applicable` (PID §11.3: excluded from posture's
    denominator entirely, not merely worth zero).

    `is_completion_complete` is only meaningful when
    `counts_toward_completion` is True - for a `BASELINE_CONTROL` row this
    is True for `yes`/`partial`/`no`/`not_applicable` and False only for
    `unknown` (PID §12.3: "A deliberate no is a completed assessment answer
    even though it earns no posture points" - and, symmetrically, so is
    `not_applicable`); for a `DERIVED_MILESTONE` row it is simply that
    milestone's own resolved boolean.
    """

    code: str
    title: str
    requirement_kind: str
    source_key: str
    product_area_code: str
    min_package_tier: int
    security_weight: int
    display_order: int
    counts_toward_posture: bool
    counts_toward_completion: bool
    answer_state: str
    is_posture_applicable: bool
    posture_factor: Decimal | None
    is_completion_complete: bool


def _resolve_requirement(
    requirement: FoundationRequirement, organisation, baseline_answers: dict
) -> RequirementState:
    if requirement.requirement_kind == RequirementKind.BASELINE_CONTROL:
        resolver = BASELINE_RESOLVERS.get(requirement.source_key)
        if resolver is None:
            raise UnresolvableFoundationRequirementError(
                f"FoundationRequirement {requirement.code!r} is an active BASELINE_CONTROL "
                f"row with source_key {requirement.source_key!r}, which has no registered "
                "resolver in entitlements.metrics.BASELINE_RESOLVERS."
            )
        answer = resolver(baseline_answers)
        is_posture_applicable = answer != ANSWER_NOT_APPLICABLE
        posture_factor = POSTURE_FACTOR_BY_ANSWER.get(answer) if is_posture_applicable else None
        is_completion_complete = answer != ANSWER_UNKNOWN
        return RequirementState(
            code=requirement.code,
            title=requirement.title,
            requirement_kind=requirement.requirement_kind,
            source_key=requirement.source_key,
            product_area_code=requirement.product_area.code,
            min_package_tier=requirement.min_package_tier,
            security_weight=requirement.security_weight,
            display_order=requirement.display_order,
            counts_toward_posture=requirement.counts_toward_posture,
            counts_toward_completion=requirement.counts_toward_completion,
            answer_state=answer,
            is_posture_applicable=is_posture_applicable,
            posture_factor=posture_factor,
            is_completion_complete=is_completion_complete,
        )

    if requirement.requirement_kind == RequirementKind.DERIVED_MILESTONE:
        resolver = MILESTONE_RESOLVERS.get(requirement.source_key)
        if resolver is None:
            raise UnresolvableFoundationRequirementError(
                f"FoundationRequirement {requirement.code!r} is an active DERIVED_MILESTONE "
                f"row with source_key {requirement.source_key!r}, which has no registered "
                "resolver in entitlements.metrics.MILESTONE_RESOLVERS."
            )
        complete = bool(resolver(organisation))
        return RequirementState(
            code=requirement.code,
            title=requirement.title,
            requirement_kind=requirement.requirement_kind,
            source_key=requirement.source_key,
            product_area_code=requirement.product_area.code,
            min_package_tier=requirement.min_package_tier,
            security_weight=requirement.security_weight,
            display_order=requirement.display_order,
            counts_toward_posture=requirement.counts_toward_posture,
            counts_toward_completion=requirement.counts_toward_completion,
            answer_state=STATE_COMPLETE if complete else STATE_INCOMPLETE,
            is_posture_applicable=False,
            posture_factor=None,
            is_completion_complete=complete,
        )

    # Neither controlled kind (entitlements.models.RequirementKind only
    # defines these two) - genuinely unreachable with today's model choices
    # constraint, but fail loudly rather than silently ignore a row here
    # too, matching the same discipline as the two branches above.
    raise UnresolvableFoundationRequirementError(
        f"FoundationRequirement {requirement.code!r} has unrecognised "
        f"requirement_kind {requirement.requirement_kind!r}."
    )


def get_foundations_requirement_states(organisation) -> list[RequirementState]:
    """
    PID §23's shared building block: resolves every active
    `FoundationRequirement` row to a `RequirementState`, in
    `display_order`. `get_foundational_security_posture`,
    `get_security_foundations_completion` and `get_needs_attention` all
    build their results from exactly this list - never a second,
    independently recomputed pass over the same rows.

    Bounded query cost regardless of the number of requirement rows: one
    query for the active+ordered `FoundationRequirement` rows (with
    `product_area` select_related to avoid a per-row FK query), one bounded
    pass for all `BaselineAnswer` rows shared by every `BASELINE_CONTROL`
    resolver, and one small, fixed number of milestone queries (one per
    distinct domain model the 6 `DERIVED_MILESTONE` resolvers touch) - not
    one query per requirement.
    """
    requirements = list(
        FoundationRequirement.objects.filter(is_active=True)
        .select_related("product_area")
        .order_by("display_order", "code")
    )
    baseline_answers = _fetch_baseline_answers(organisation)
    return [
        _resolve_requirement(requirement, organisation, baseline_answers)
        for requirement in requirements
    ]


def _quantize_percentage(value: Decimal) -> int:
    """
    Deterministic whole-number rounding (PID §11.6/§12's shared rounding
    requirement) - round-half-up on a `Decimal`, never float division/
    rounding anywhere in this module.
    """
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclasses.dataclass(frozen=True)
class FoundationalSecurityPosture:
    """PID §11's result shape. `requirement_states` is filtered to exactly
    the rows that count toward posture (today: the 12 `BASELINE_CONTROL`
    rows) - a caller wanting the full 18-row picture uses
    `get_foundations_requirement_states` directly."""

    percentage: int
    earned_points: Decimal
    available_points: Decimal
    methodology_version: str
    requirement_states: tuple[RequirementState, ...]


def get_foundational_security_posture(organisation) -> FoundationalSecurityPosture:
    """
    PID §11.5's formula:

        earned_points = sum(weight * state_factor) over applicable controls
        available_points = sum(weight) over applicable controls
        posture_percentage = earned_points / available_points * 100

    `not_applicable` removes that control's weight from BOTH sums entirely
    (PID §11.3/§11.5) - never merely scored zero like `no`/`unknown`. Only
    `FoundationRequirement` rows with `counts_toward_posture=True` (today:
    the 12 `BASELINE_CONTROL` rows) participate at all; evidence, policy,
    remediation and AI records never enter this calculation because
    nothing in this function - or in any resolver it calls - ever reads
    those models (PID §21, §26.1).
    """
    states = get_foundations_requirement_states(organisation)
    posture_states = [state for state in states if state.counts_toward_posture]

    earned = Decimal("0")
    available = Decimal("0")
    for state in posture_states:
        if not state.is_posture_applicable:
            continue
        weight = Decimal(state.security_weight)
        available += weight
        earned += weight * state.posture_factor

    percentage = _quantize_percentage((earned / available) * 100) if available > 0 else 0

    return FoundationalSecurityPosture(
        percentage=percentage,
        earned_points=earned,
        available_points=available,
        methodology_version=FOUNDATION_METRIC_VERSION,
        requirement_states=tuple(posture_states),
    )


@dataclasses.dataclass(frozen=True)
class SecurityFoundationsCompletion:
    """PID §12's result shape. `requirement_states` is filtered to exactly
    the rows that count toward completion (today: all 18 active rows)."""

    percentage: int
    completed_count: int
    total_count: int
    methodology_version: str
    requirement_states: tuple[RequirementState, ...]


def get_security_foundations_completion(organisation) -> SecurityFoundationsCompletion:
    """
    PID §12.2's formula: `completed_applicable_items / total_applicable_items
    * 100`, unweighted (every item contributes exactly 1 or 0, never
    `security_weight` - PID §12.2 "Do not weight completion by security
    importance").

    Note on "applicable" for v1: PID §12.3 explicitly folds a `BASELINE_CONTROL`
    row's `not_applicable` answer into "Complete" ("Complete when answer is
    one of: yes, partial, no, not_applicable... A deliberate no is a
    completed assessment answer even though it earns no posture points" -
    the same treatment extends to not_applicable), and none of the 6
    `DERIVED_MILESTONE` resolvers can themselves produce a "structurally
    not applicable" result in v1 (PID's own "the 6 milestone predicates are
    never not_applicable in v1"). So `total_count` here is simply every
    `counts_toward_completion=True` active row (18 today) - §12.2's generic
    "excluded" denominator hook is not exercised by any v1 resolver; a
    genuinely inapplicable completion item is a future-methodology concept
    this module does not need to invent for v1.
    """
    states = get_foundations_requirement_states(organisation)
    completion_states = [state for state in states if state.counts_toward_completion]

    total_count = len(completion_states)
    completed_count = sum(1 for state in completion_states if state.is_completion_complete)

    if total_count > 0:
        percentage = _quantize_percentage(Decimal(completed_count) / Decimal(total_count) * 100)
    else:
        percentage = 0

    return SecurityFoundationsCompletion(
        percentage=percentage,
        completed_count=completed_count,
        total_count=total_count,
        methodology_version=FOUNDATION_METRIC_VERSION,
        requirement_states=tuple(completion_states),
    )


@dataclasses.dataclass(frozen=True)
class NeedsAttentionSignal:
    """
    One Needs Attention line (PID §14). `count == 0` means this signal has
    nothing to show - WI5's template is the one that omits a zero-count
    line entirely (PID §27 "zero-count line omitted"); this module always
    returns all four signals (count 0 where nothing applies) so WI5 has one
    single, always-present shape to check rather than a variable-length
    list. `destination_product_area_code` is a stable `entitlements.
    models.ProductArea.code` (never a raw URL/HTML fragment - PID §14.1
    "do not build any HTML or wording here") for WI5's template to build
    its own `click here` link from.
    """

    key: str
    count: int
    destination_product_area_code: str


@dataclasses.dataclass(frozen=True)
class NeedsAttention:
    """PID §14's four initial signals, in the order PID §14 lists them."""

    important_controls: NeedsAttentionSignal
    foundations_incomplete: NeedsAttentionSignal
    not_sure_controls: NeedsAttentionSignal
    policy_review_overdue: NeedsAttentionSignal


def get_needs_attention(organisation) -> NeedsAttention:
    """
    PID §14's deterministic, read-only aggregation of exactly four signals,
    every one derived from `get_foundations_requirement_states`'s own
    per-item states - never a second, independently recomputed pass (PID
    §23, and PID §27's "incomplete-Foundations count matches the completion
    resolver's own per-item states exactly [no independent recount]").

    - Important controls (PID §14.2): `security_weight >= 3` AND answered
      `partial` or `no`. Never `unknown` (that is the separate "Not sure"
      signal below, so it is never double-counted into this one) and
      never `not_applicable` (PID §14.2 "Do not treat not_applicable as a
      problem" - `not_applicable` answers can only ever equal
      `ANSWER_NOT_APPLICABLE`, which is neither `partial` nor `no`, so this
      is naturally excluded without a separate check).
    - Foundations incomplete: every `counts_toward_completion` row whose
      own `is_completion_complete` is False - the exact same per-item facts
      `get_security_foundations_completion` itself counts, not a second
      derivation.
    - Not sure controls: every `counts_toward_posture` row (i.e. every
      `BASELINE_CONTROL`) answered `unknown` - deliberately not restricted
      to `security_weight >= 3` (unlike the important-controls signal
      above): PID §14's own wording lists this as its own, separately
      counted line ("baseline controls marked Not sure"), with no
      importance-weight qualifier.
    - Policy review overdue: reuses `is_approved_policy_review_overdue`
      directly (the same predicate `organisations.overview._policy_area`
      and `has_approved_policy`'s own completion milestone consume) -
      never a second overdue definition.
    """
    states = get_foundations_requirement_states(organisation)

    important_controls_count = sum(
        1
        for state in states
        if state.counts_toward_posture
        and state.security_weight >= IMPORTANT_CONTROL_MIN_WEIGHT
        and state.answer_state in (ANSWER_PARTIAL, ANSWER_NO)
    )
    not_sure_count = sum(
        1
        for state in states
        if state.counts_toward_posture and state.answer_state == ANSWER_UNKNOWN
    )
    completion_states = [state for state in states if state.counts_toward_completion]
    foundations_incomplete_count = sum(
        1 for state in completion_states if not state.is_completion_complete
    )
    policy_review_overdue = is_approved_policy_review_overdue(organisation)

    return NeedsAttention(
        important_controls=NeedsAttentionSignal(
            key="important_controls_not_fully_implemented",
            count=important_controls_count,
            destination_product_area_code=DESTINATION_IMPORTANT_CONTROLS,
        ),
        foundations_incomplete=NeedsAttentionSignal(
            key="foundations_items_incomplete",
            count=foundations_incomplete_count,
            destination_product_area_code=DESTINATION_FOUNDATIONS_INCOMPLETE,
        ),
        not_sure_controls=NeedsAttentionSignal(
            key="controls_marked_not_sure",
            count=not_sure_count,
            destination_product_area_code=DESTINATION_NOT_SURE_CONTROLS,
        ),
        policy_review_overdue=NeedsAttentionSignal(
            key="policy_review_overdue",
            count=1 if policy_review_overdue else 0,
            destination_product_area_code=DESTINATION_POLICY_REVIEW_OVERDUE,
        ),
    )


__all__ = [
    "UnresolvableFoundationRequirementError",
    "STATE_COMPLETE",
    "STATE_INCOMPLETE",
    "BASELINE_RESOLVERS",
    "MILESTONE_RESOLVERS",
    "RequirementState",
    "FoundationalSecurityPosture",
    "SecurityFoundationsCompletion",
    "NeedsAttentionSignal",
    "NeedsAttention",
    "get_foundations_requirement_states",
    "get_foundational_security_posture",
    "get_security_foundations_completion",
    "get_needs_attention",
]
