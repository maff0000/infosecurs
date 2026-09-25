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
FROM the exact `organisation` object passed in, or an explicit
`.filter(organisation=organisation, ...)` at the ORM call site (`Risk`) -
never fetched unscoped and filtered afterwards.

== M006-AUDIT-0001 finding F3: no organisation-authored free text on the
wire, at all ==
A fresh, independent, real-browser PID §18 acceptance audit reproduced
the fabricated-fact-adoption failure `risk_interpretation_v2` (M006 Round
7's own correction) was built to close: the model repeated a hostile
`KeyAsset.description`/`BaselineAnswer.note`'s planted "already ISO 27001
certified / MFA fully implemented" claim as established fact, despite
`v2`'s explicit instruction not to. Central Architecture's ruling:
prompt-only controls have failed twice against this class - the fix is
data minimisation at the source, not more prompt wording. As a result,
`_build_candidate` below (the sole production caller of
`InterpretationCandidate`) no longer reads or sends ANY of the three raw
organisation-authored free-text surfaces the audit named:

- `KeyAsset.description` - previously read here and appended to
  `notes`; no longer read at all;
- `BaselineAnswer.note` - previously read here (via
  `_canonical_baseline_notes`, now deleted) and appended to `notes`; no
  longer read at all;
- `KeyAsset.name` - previously reached the model indirectly via
  `risk.title` (`risk_register.scenario_engine._build_title` embeds it);
  `_candidate_title` below builds a model-only title from
  methodology-owned data instead (the scenario's own `threat_event` plus
  the asset's canonical `category` enum value), never from `risk.title`.

`notes` is therefore always `[]` on this module's outbound
`InterpretationCandidate`s. The persisted/displayed `Risk.title` - what a
human sees on the risk-register page - is completely unchanged: it is
still `risk.title`, still built by `_build_title`, still embeds
`key_asset.name`. Only what is sent to the AI wire payload changed. See
`risk_interpretation_v3`'s own module docstring for the corresponding
prompt-side correction.
"""
from __future__ import annotations

from ai_platform.gateway import LiteLLMGateway, RiskInterpretationGateway
from ai_platform.interpretation_contracts import (
    MAX_INTERPRETATION_CANDIDATES,
    InterpretationCandidate,
)
from ai_platform.interpretation_orchestration import interpret_candidates
from ai_platform.prompts.risk_interpretation_v3 import PROMPT_VERSION
from key_assets.models import CATEGORY_CHOICES
from risk_register.methodology import CATALOGUE_BY_ID
from risk_register.models import Risk


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


_CATEGORY_LABELS_BY_VALUE = dict(CATEGORY_CHOICES)


def _candidate_title(scenario, key_asset) -> str:
    """Model-facing candidate title, built ENTIRELY from methodology/
    application-owned data - the scenario's own `threat_event` plus the
    asset's canonical `category` enum value (a controlled vocabulary,
    `key_assets.models.CATEGORY_CHOICES` - the same choices set
    `KeyAsset.category`'s field definition uses - not organisation-authored
    free text) - never `key_asset.name` (M006-AUDIT-0001 F3).

    Deliberately NOT `risk.title` / `risk_register.scenario_engine.
    _build_title`'s output, which correctly, and unchangedly, embeds
    `key_asset.name` for the PERSISTED/DISPLAYED `Risk.title` a human sees
    on the risk-register page (a UI/business-domain concern this
    correction does not touch - `_build_title` itself is untouched). This
    is a separate, model-only construction used only for the outbound AI
    wire payload, mirroring `_build_title`'s "<threat_event> - <asset
    descriptor>" shape with a non-identifying descriptor in place of the
    customer's own asset name.
    """
    threat_event = scenario.threat_event.rstrip(".")
    category_label = _CATEGORY_LABELS_BY_VALUE.get(key_asset.category, key_asset.category)
    return f"{threat_event} - {category_label}"


def _build_candidate(index: int, risk: Risk) -> InterpretationCandidate:
    """One `InterpretationCandidate` for `risk`, assigned `index` for this
    one call only.

    `notes` is always `[]` and `title` is always `_candidate_title`'s
    model-only construction - M006-AUDIT-0001 F3: the live production path
    must never send `KeyAsset.description`, `BaselineAnswer.note`, or
    `KeyAsset.name` (the three raw organisation-authored free-text
    surfaces the audit named) to the model, in any form. See this module's
    own docstring for the full history and reasoning.
    """
    scenario = CATALOGUE_BY_ID[risk.scenario_id]

    return InterpretationCandidate(
        index=index,
        title=_candidate_title(scenario, risk.key_asset),
        exposure=risk.exposure,
        threat_event=risk.threat_event or risk.threat,
        vulnerability=risk.vulnerability,
        consequence=risk.consequence,
        current_impact=risk.impact,
        current_likelihood=risk.likelihood,
        asset_category=risk.key_asset.category,
        notes=[],
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

    candidates = [
        _build_candidate(index, risk)
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
