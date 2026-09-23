"""
AI practitioner-interpretation service (M002 PID §0.6/§0.7 - M002-3c
dispatch): the seam between the Risk-domain view layer and
`ai_platform`'s new interpretation contract/gateway/orchestration.

`interpret_draft_risks` is the single entrypoint the view calls. It:

1. selects this organisation's DRAFT AI-suggested `Risk` rows that trace to
   a catalogue scenario and a confirmed asset (see `_select_candidates`'
   docstring for why those two filters);
2. builds one `InterpretationCandidate` per selected `Risk` row, assigning
   each a small, per-call, sequential integer `index` (1, 2, 3, ...) that
   exists ONLY for the duration of this one call - never the `Risk`'s real
   UUID primary key (PID's explicit index-scheme requirement, see
   `ai_platform.interpretation_contracts`'s module docstring);
3. calls `ai_platform.interpretation_orchestration.interpret_candidates`
   (one call, at most one bounded retry for a retryable failure only - the
   same discipline `ai_platform.orchestration.generate_risks` already uses
   for the retired generation task);
4. on success, maps each returned `InterpretationOutcome.index` straight
   back to the actual `Risk` object this function already holds a
   reference to (never re-fetched, never re-resolved from anything the
   model returned) and UPDATES (never creates) that `Risk`'s
   `impact`/`likelihood`/`rationale`/`proposed_treatment` plus its
   `ai_invocation_record` FK - still `status=draft_ai_suggested` (PID §2:
   still requires explicit customer confirmation before it becomes
   organisational truth);
5. on failure, leaves every existing `Risk` row completely untouched - the
   same guarantee `ai_platform.orchestration.generate_risks` already gives
   the retired generation flow for gateway failures. This holds
   structurally, not just by convention: `interpret_candidates` either
   returns an `InterpretationResponse` in which
   `InterpretationResponse.from_response_dict` has already proven every
   requested index has exactly one matching outcome, or it raises
   `ai_platform.interpretation_orchestration.InterpretationFailed` before
   this function ever reaches its Risk-update loop - so there is no code
   path where some Risk rows get updated and others don't from the same
   call.

Tenant-safety discipline (mirrors `risk_register.scenario_engine` and
`risk_register.grounding`'s proven approach - PID §16, "the last item is
critical", extended here to the interpretation task's own outbound
payload): every DB read below is either a reverse one-to-one traversal
FROM the exact `organisation` object passed in
(`organisation.baseline_assessment`), or an explicit
`.filter(organisation=organisation, ...)` at the ORM call site (`Risk`) -
never fetched unscoped and filtered afterwards. `KeyAsset.description` and
`BaselineAnswer.note` values reached via `risk.key_asset` / the canonical
baseline are only ever read for a `Risk` that itself already passed the
`organisation=organisation` filter above, so there is no path by which a
different organisation's free text could end up in one of this
organisation's `InterpretationCandidate.notes`.
"""
from __future__ import annotations

from ai_platform.gateway import LiteLLMGateway, RiskInterpretationGateway
from ai_platform.interpretation_contracts import (
    MAX_INTERPRETATION_CANDIDATES,
    InterpretationCandidate,
)
from ai_platform.interpretation_orchestration import interpret_candidates
from ai_platform.prompts.risk_interpretation_v1 import PROMPT_VERSION
from risk_register.methodology import CATALOGUE_BY_ID
from risk_register.models import Risk
from security_baseline.models import BaselineAssessment


def _canonical_baseline_notes(organisation) -> dict:
    """This organisation's canonical `BaselineAnswer.note` values, keyed by
    `question_key` - `{}` if no assessment exists, and a control key with a
    blank note is simply absent from the returned dict (there is nothing
    useful to add to a candidate's `notes` for it).

    Mirrors `risk_register.scenario_engine._canonical_control_answers`'s
    exact tenant-scoping pattern (a reverse OneToOneField traversal from
    this exact `organisation` object) - reused rather than reimplemented
    differently, since that module already gets this specific read right.
    """
    try:
        assessment = organisation.baseline_assessment
    except BaselineAssessment.DoesNotExist:
        return {}
    return {answer.question_key: answer.note for answer in assessment.answers.all() if answer.note}


def _select_candidate_risks(organisation) -> list:
    """This organisation's draft AI-suggested `Risk` rows eligible for
    interpretation, oldest first, capped at
    `MAX_INTERPRETATION_CANDIDATES` (PID §14's execution-safety bound,
    applied here as "which Risk rows this call selects" rather than as a
    response-truncation the way `ai_platform.orchestration.generate_risks`
    applies it - see `ai_platform.interpretation_orchestration.
    interpret_candidates`'s own docstring for why an over-cap request is a
    caller-contract violation for this task, not a model-output quirk to
    tolerate).

    Filtered to `key_asset__isnull=False` and a `scenario_id` that actually
    resolves in the methodology catalogue: every M002 V1 catalogue-
    originated draft risk (`risk_register.scenario_engine.
    instantiate_risks_for_organisation`) always has both, so this is a
    defensive exclusion of anything else (e.g. a manually-created draft
    risk with blank `exposure`/`consequence`) that would otherwise fail
    `InterpretationCandidate`'s own non-empty-string validation - flagged
    as a documented judgement call, not silently swallowed: PID §0.7
    requires every M002 V1 persisted Risk to originate from the catalogue,
    so in practice this filter should never exclude anything a customer
    would expect to see interpreted.
    """
    queryset = (
        Risk.objects.filter(
            organisation=organisation,
            status=Risk.STATUS_DRAFT_AI_SUGGESTED,
            key_asset__isnull=False,
        )
        .exclude(scenario_id="")
        .order_by("created_at")
    )
    return [risk for risk in queryset if risk.scenario_id in CATALOGUE_BY_ID][
        :MAX_INTERPRETATION_CANDIDATES
    ]


def _build_candidate(index: int, risk: Risk, notes_by_control_key: dict) -> InterpretationCandidate:
    """One `InterpretationCandidate` for `risk`, assigned `index` for this
    one call only. `notes` collects the organisation's own free text that
    is actually relevant to this specific candidate - the asset's own
    description, plus the canonical baseline note (if any) for each of the
    catalogue scenario's `control_keys` - exactly the PID §12 examples
    ("baseline notes; asset descriptions"), never a database identifier.
    """
    scenario = CATALOGUE_BY_ID[risk.scenario_id]

    notes: list = []
    if risk.key_asset.description:
        notes.append(risk.key_asset.description)
    for control_key in scenario.control_keys:
        note = notes_by_control_key.get(control_key)
        if note:
            notes.append(note)

    return InterpretationCandidate(
        index=index,
        title=risk.title,
        exposure=risk.exposure,
        threat_event=risk.threat_event or risk.threat,
        vulnerability=risk.vulnerability,
        consequence=risk.consequence,
        current_impact=risk.impact,
        current_likelihood=risk.likelihood,
        asset_category=risk.key_asset.category,
        notes=notes,
    )


def interpret_draft_risks(organisation, gateway: RiskInterpretationGateway = None) -> list:
    """Run one bounded AI interpretation call over `organisation`'s
    eligible draft AI-suggested risks, and apply the result.

    Returns the list of updated `Risk` rows (may be empty - e.g. no
    eligible draft risks exist yet). Raises
    `ai_platform.interpretation_orchestration.InterpretationFailed` if the
    call fails - see this module's docstring point 5: no `Risk` row is
    touched in that case.

    `gateway` defaults to a real `LiteLLMGateway()` (constructed lazily
    inside this call, not at import time - PID §14: interpretation happens
    only on an explicit user action, mirroring `LiteLLMGateway`'s own lazy
    config-loading discipline). Tests pass
    `ai_platform.testing.FakeInterpretationGateway` explicitly.
    """
    candidate_risks = _select_candidate_risks(organisation)
    if not candidate_risks:
        return []

    notes_by_control_key = _canonical_baseline_notes(organisation)
    candidates = [
        _build_candidate(index, risk, notes_by_control_key)
        for index, risk in enumerate(candidate_risks, start=1)
    ]
    risk_by_index = {index: risk for index, risk in enumerate(candidate_risks, start=1)}

    gateway = gateway if gateway is not None else LiteLLMGateway()

    result, record = interpret_candidates(
        gateway, str(organisation.pk), candidates, PROMPT_VERSION
    )

    updated = []
    for outcome in result.outcomes:
        risk = risk_by_index[outcome.index]
        risk.impact = outcome.suggested_impact
        risk.likelihood = outcome.suggested_likelihood
        risk.rationale = outcome.rationale
        risk.proposed_treatment = outcome.suggested_treatment
        risk.ai_invocation_record = record
        risk.save(
            update_fields=[
                "impact",
                "likelihood",
                "rationale",
                "proposed_treatment",
                "ai_invocation_record",
                "updated_at",
            ]
        )
        updated.append(risk)

    return updated


__all__ = ["interpret_draft_risks"]
