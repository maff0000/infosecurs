"""
Deterministic scenario-instantiation engine (PID §0.2-§0.7, M002-3b
dispatch).

Turns (organisation's CONFIRMED `KeyAsset`s) x (organisation's canonical
`BaselineAnswer`s) x (`risk_register.methodology.CATALOGUE`) into
persisted, tenant-owned `Risk` rows - entirely deterministically.

NO AI CALL happens anywhere in this module. `ai_platform` is never
imported here, on purpose - this module is the deterministic replacement
for the retired `profile + baseline + assets -> LLM -> risks` path
(PID §0.1/§0.6). A later, separate Phase 3c dispatch adds AI
*interpretation* on top of the rows this engine creates (refined
impact/likelihood, rationale, prioritisation, clarification questions);
this module only produces the deterministic starting point those rows
begin life as.

Tenant-safety discipline (mirrors `risk_register.grounding`'s proven
approach - PID §16, "the last item is critical"; still the right standard
to hold this module to even though there is no outbound AI payload here -
a cross-tenant READ silently feeding a persisted `Risk` row would be just
as much a defect as a cross-tenant AI payload):

  - `instantiate_risks_for_organisation` takes a single `organisation`
    object - never an id plus a separate lookup - so there is no code path
    where a caller-supplied id could diverge from the organisation whose
    facts are actually read.
  - Every DB read below is EITHER a reverse one-to-one traversal FROM that
    exact `organisation` object (`organisation.baseline_assessment`,
    resolved by Django as a lookup keyed on that organisation's own
    primary key), or an explicit `.filter(organisation=organisation, ...)`
    at the ORM call site (`KeyAsset`, the `Risk` dedup read) - every query
    is organisation-scoped at the call site, never fetched unscoped and
    filtered afterwards.
  - The methodology catalogue itself (`risk_register.methodology.
    CATALOGUE`) is inert, versioned Python data - it carries no tenant
    identifier and makes no database query, so it cannot itself be a
    cross-tenant leak vector.

Multi-control-key applicability rule (this dispatch's explicit
requirement to "decide and document a clear, defensible rule" for a
scenario such as `cloud_service_admin_mfa_account_takeover`, whose
`control_keys` names more than one canonical baseline question):

    A scenario with more than one `control_keys` entry applies if ANY of
    its relevant controls' canonical answer is a trigger state for that
    scenario. When more than one relevant control triggers, the WORST
    applicable wording variant wins - 'no' beats 'unknown' - because an
    already-established gap on any one of the relevant controls is a real
    gap regardless of what the other relevant controls say; the other
    relevant control(s) that remain genuinely unconfirmed are still
    recorded in `assumptions`, so that uncertainty is never silently
    dropped just because a different control already settled
    applicability. See `_resolve_trigger` / `_unconfirmed_control_keys`.

`wording_for()` is always called with the ACTUAL resolved `BaselineAnswer`
state that produced the winning variant for that specific control key -
never a hand-picked/synthetic state, and never bypassed by hand-
constructing wording (PID §0.4a's non-negotiable invariant). See
`_resolve_trigger`.

Missing baseline answer (PID's explicit instruction): a control with NO
`BaselineAnswer` row at all - no assessment ever started for this
organisation, or this specific question was never answered - is treated
as `unknown` for applicability purposes, exactly like an explicit
`unknown` answer. It is never treated as `yes`/`not_applicable`, and a
scenario is never silently skipped merely because the organisation has
not yet answered the relevant question(s) (`_canonical_control_answers`).

Deterministic impact/likelihood starting point: every instantiated risk is
seeded at `impact=3` (moderate) / `likelihood=3` (possible) - the exact
midpoint of PID §8.2's 1-5 qualitative scales, for every catalogue-
originated candidate without exception. This dispatch deliberately does
not invent a scoring methodology (explicit instruction): a flat, constant,
consistent starting point is the simplest defensible choice, and the
existing "AI suggested - not yet confirmed" UI wording (PID §19) already
tells the customer these ratings are a starting point to review, not an
established fact - Phase 3c's AI interpretation and/or the customer are
expected to refine them before confirmation.

Dedup / regeneration safety (PID §15; this dispatch's §1: "this is your
regeneration/dedup mechanism, and it must be exact"): the tuple
`(organisation, scenario_id, key_asset)` is the unique identity of a
candidate risk. Re-running instantiation only ever INSERTs a new `Risk`
row for a tuple that does not already exist anywhere in this
organisation's risk register - by construction, an existing row for the
same tuple (draft, confirmed OR dismissed - status is never consulted for
this check) is looked up and skipped, never updated, overwritten or
re-created. Combined with the fact that this module never issues an
`UPDATE`/`DELETE` against `Risk` at all, "never mutate an existing Risk"
holds both by convention (only ever `.objects.create(...)`) and
structurally (the dedup lookup runs before every create).
"""
from __future__ import annotations

from key_assets.models import KeyAsset
from risk_register.methodology import CATALOGUE, VARIANT_NO
from risk_register.models import Risk
from security_baseline.models import ANSWER_UNKNOWN, BaselineAssessment

# PID §8.2 midpoint - see module docstring "Deterministic impact/likelihood
# starting point" for why this is a flat constant rather than a derived
# value.
DEFAULT_IMPACT = 3
DEFAULT_LIKELIHOOD = 3

# M006-AUDIT-0003 H1: appended to a derived `Risk.title` ONLY when
# `key_asset.name` actually had to be cut short to fit the field - never
# for a title that already fits in full. Plain ASCII on purpose (not a
# Unicode ellipsis character) so it can never itself introduce a
# multibyte-boundary concern into the truncation math below.
TITLE_TRUNCATION_MARKER = "..."


def _canonical_control_answers(organisation) -> dict:
    """This organisation's canonical `BaselineAnswer` states, keyed by
    `question_key`, or `{}` if no assessment has been started yet.

    `organisation.baseline_assessment` is a reverse OneToOneField accessor
    - Django resolves it as a lookup scoped to `organisation`'s own primary
    key, exactly as `risk_register.grounding._baseline_facts` already
    relies on; there is no separate id parameter here that could be
    widened or mismatched. `{}` here is what makes every subsequent
    `control_answers.get(key, ANSWER_UNKNOWN)` below correctly default a
    never-asked question to `unknown` rather than raising or silently
    treating it as answered.
    """
    try:
        assessment = organisation.baseline_assessment
    except BaselineAssessment.DoesNotExist:
        return {}
    return {answer.question_key: answer.answer for answer in assessment.answers.all()}


def _resolve_trigger(scenario, control_answers: dict):
    """The multi-control-key applicability rule (see module docstring).

    Returns `(control_key, resolved_state)` for whichever of the
    scenario's `control_keys` produced the WORST applicable wording
    variant ('no' beats 'unknown'), or `None` if none of the scenario's
    relevant controls are in a trigger state at all - i.e. the scenario
    does not apply for this asset/organisation combination.

    `resolved_state` is always one of the organisation's own actual
    (possibly defaulted-to-unknown) answer values - never synthesised -
    so a caller can safely pass it straight to
    `scenario.wording_for(resolved_state)`.
    """
    winning = None  # (control_key, state)
    for control_key in scenario.control_keys:
        state = control_answers.get(control_key, ANSWER_UNKNOWN)
        if not scenario.applies_to(state):
            continue
        variant = scenario.trigger_states[state]
        if variant == VARIANT_NO:
            return (control_key, state)  # worst possible - short-circuit
        if winning is None:
            winning = (control_key, state)
    return winning


def _unconfirmed_control_keys(scenario, control_answers: dict) -> list:
    """Every one of this scenario's relevant `control_keys` whose
    canonical answer is `unknown` (explicitly answered `unknown`, or never
    answered at all) - recorded as `assumptions` regardless of which
    specific control key ended up driving applicability in
    `_resolve_trigger`. This keeps a genuinely-unconfirmed relevant control
    visible even when a *different* relevant control already established a
    confirmed 'no' gap (PID §0.4a: uncertainty must never be silently
    dropped)."""
    return [
        control_key
        for control_key in scenario.control_keys
        if control_answers.get(control_key, ANSWER_UNKNOWN) == ANSWER_UNKNOWN
    ]


def _build_title(scenario, key_asset) -> str:
    """The ONE authoritative builder of a `Risk.title` value (M006-AUDIT-0003
    H1 correction) - the sole call site is `instantiate_risks_for_organisation`
    below.

    Confirmed root cause (fresh independent Auditor, `docs/evidence/
    M006-AUDIT-0003.md`, confirmed by Central Architecture): `KeyAsset.name`
    and `Risk.title` are both `CharField(max_length=255)`, and this
    function's pre-correction body (`f"{threat_event} - {key_asset.name}"`)
    had no bound of its own - so a completely valid, maximum-length
    `KeyAsset.name` could deterministically produce a title longer than
    `Risk.title`'s own capacity, raising `django.db.utils.DataError` at the
    `Risk.objects.create(...)` call site and leaving the customer at a dead
    end (PID §18 item 7) despite having done nothing wrong.

    Central Architecture's ruling on the correct fix, applied here exactly:
    bound the DERIVED title to `Risk.title`'s own field capacity - derived
    via Django's own model introspection
    (`Risk._meta.get_field("title").max_length`), not a second hardcoded
    `255` - never shrink the source `key_asset.name` itself (it remains
    completely intact on its own `KeyAsset` row, still reachable through the
    unchanged `key_asset` FK - this function only ever affects the derived
    summary string, not the customer's own data), never enlarge
    `Risk.title`, never catch `DataError` and show a friendlier error, never
    silently skip the risk candidate.

    Behaviour:
      1. The methodology-owned `threat_event` portion and the literal
         `" - "` separator are ALWAYS preserved in full, never truncated -
         see the `ValueError` guard below for what happens if that portion
         alone can't fit.
      2. As much of `key_asset.name` as remains within the field's capacity
         (after the threat_event/separator/marker overhead) is kept.
      3. `TITLE_TRUNCATION_MARKER` is appended ONLY when truncation actually
         happened - a title that already fits in full is returned completely
         unmodified, exactly as this function returned it before this
         correction; nothing is needlessly marked or altered for the common
         case.

    Truncation, when it happens, slices `key_asset.name` with ordinary
    Python string indexing/slicing, which operates on Unicode codepoints,
    not raw bytes - so a Unicode asset name (accented characters, CJK,
    emoji, ...) is never cut mid-character. Proven, not merely assumed - see
    the Unicode boundary test in `risk_register/tests/test_scenario_engine.py`.

    The `ValueError` below is a catalogue/programming-time invariant guard,
    not runtime "handling" of a customer-triggered condition: if a
    scenario's own `threat_event` were ever so long that even a
    zero-length asset-name contribution, plus the separator and the
    truncation marker, could not fit in `Risk.title`'s capacity, that is a
    defect in the catalogue entry itself - the fix is to shorten that
    scenario's `threat_event`, not to further mangle the methodology-owned
    prefix at runtime to force a fit. `TestCatalogueThreatEventFitsTitleField`
    proves this condition does not occur for any scenario in the current
    `CATALOGUE`, for every current methodology scenario - this guard exists
    so that, if it ever did, the failure would be loud and immediate at
    generation time rather than a silent truncation of methodology-owned
    text.
    """
    max_length = Risk._meta.get_field("title").max_length
    threat_event = scenario.threat_event.rstrip(".")
    prefix = f"{threat_event} - "

    worst_case_overhead = len(prefix) + len(TITLE_TRUNCATION_MARKER)
    if worst_case_overhead > max_length:
        raise ValueError(
            f"Scenario {scenario.scenario_id!r}'s threat_event leaves no "
            f"room for ANY asset-name content within Risk.title's "
            f"max_length={max_length} (fixed prefix alone is "
            f"{len(prefix)} chars, plus a {len(TITLE_TRUNCATION_MARKER)}-char "
            "truncation marker in the worst case). This is a "
            "catalogue/programming-time invariant violation - shorten this "
            "scenario's threat_event; do not attempt to fix this at "
            "runtime by truncating methodology-owned text."
        )

    full_title = f"{prefix}{key_asset.name}"
    if len(full_title) <= max_length:
        return full_title

    available_for_name = max_length - len(prefix) - len(TITLE_TRUNCATION_MARKER)
    return f"{prefix}{key_asset.name[:available_for_name]}{TITLE_TRUNCATION_MARKER}"


def _build_rationale(scenario, key_asset, control_key: str, resolved_state: str) -> str:
    """`Risk.rationale` is a required, non-blank model field the PID §0
    field list does not explicitly name (only `title`/`exposure`/
    `threat_event`/`vulnerability`/`consequence`/`proposed_treatment`/
    `impact`/`likelihood`/`grounding_refs`/`assumptions`/`source`/`status`/
    `ai_invocation_record` are). A short, deterministic provenance
    sentence - naming the exact scenario, asset and driving control answer
    - is this dispatch's judgement call for what belongs there; flagged in
    the dispatch report rather than left unexplained."""
    return (
        f"Automatically derived from methodology scenario "
        f"'{scenario.scenario_id}' for confirmed asset '{key_asset.name}': "
        f"the organisation's canonical baseline answer for "
        f"'{control_key}' is '{resolved_state}'."
    )


def instantiate_risks_for_organisation(organisation) -> list:
    """Deterministically instantiate candidate `Risk` rows for
    `organisation` from its CONFIRMED `KeyAsset`s x canonical
    `BaselineAnswer`s x `risk_register.methodology.CATALOGUE`.

    Returns the list of newly-created `Risk` rows (empty if nothing new
    applies, or everything applicable already exists). Never mutates,
    overwrites or re-creates a `Risk` row for an
    `(organisation, scenario_id, key_asset)` tuple that already exists,
    regardless of that row's current status (draft/confirmed/dismissed) -
    see module docstring "Dedup / regeneration safety".
    """
    control_answers = _canonical_control_answers(organisation)

    confirmed_assets = KeyAsset.objects.filter(
        organisation=organisation, status=KeyAsset.STATUS_CONFIRMED
    )

    # (scenario_id, key_asset_id) tuples that already exist for this
    # organisation, regardless of status - the exact dedup key this
    # dispatch's §1 requires. A single upfront query, refreshed in-memory
    # as new rows are created below, rather than one query per candidate.
    existing_tuples = set(
        Risk.objects.filter(organisation=organisation).values_list(
            "scenario_id", "key_asset_id"
        )
    )

    created = []
    for asset in confirmed_assets:
        for scenario in CATALOGUE:
            if scenario.asset_category != asset.category:
                continue
            dedup_key = (scenario.scenario_id, asset.id)
            if dedup_key in existing_tuples:
                continue

            trigger = _resolve_trigger(scenario, control_answers)
            if trigger is None:
                continue
            control_key, resolved_state = trigger
            wording = scenario.wording_for(resolved_state)

            grounding_refs = [f"baseline.{key}" for key in scenario.control_keys] + [
                f"asset:{asset.id}"
            ]
            assumptions = [
                f"baseline.{key}: control state not confirmed"
                for key in _unconfirmed_control_keys(scenario, control_answers)
            ]

            risk = Risk.objects.create(
                organisation=organisation,
                key_asset=asset,
                scenario_id=scenario.scenario_id,
                title=_build_title(scenario, asset),
                exposure=scenario.exposure,
                # `threat` (pre-existing field) and `threat_event` (new
                # field) are deliberately populated with the same content
                # here - see risk_register/models.py's module docstring
                # note on this unresolved overlap, flagged rather than
                # guessed at further.
                threat=scenario.threat_event,
                threat_event=scenario.threat_event,
                vulnerability=wording.vulnerability,
                consequence=wording.consequence,
                impact=DEFAULT_IMPACT,
                likelihood=DEFAULT_LIKELIHOOD,
                rationale=_build_rationale(scenario, asset, control_key, resolved_state),
                proposed_treatment=scenario.suggested_treatment,
                grounding_refs=grounding_refs,
                assumptions=assumptions,
                # PID §0.7: every persisted M002 V1 Risk row originates
                # from the catalogue - there is no "AI novel suggestion"
                # status. `SOURCE_AI` is used here (rather than
                # `SOURCE_MANUAL`) because these rows are exactly what a
                # customer must still explicitly review/confirm before
                # they become organisational truth (PID §2) - the same
                # "requires customer confirmation" semantics `SOURCE_AI`
                # already carries - and Phase 3c's AI interpretation will
                # attach to these same rows next. `SOURCE_MANUAL` means
                # "the customer's own direct assertion" per this model's
                # own docstring, which is not what a catalogue-derived
                # candidate is.
                source=Risk.SOURCE_AI,
                status=Risk.STATUS_DRAFT_AI_SUGGESTED,
                # No AI call happened anywhere in this dispatch.
                ai_invocation_record=None,
            )
            created.append(risk)
            existing_tuples.add(dedup_key)

    return created


__all__ = ["instantiate_risks_for_organisation", "DEFAULT_IMPACT", "DEFAULT_LIKELIHOOD"]
