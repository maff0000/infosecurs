"""
M002 live AI evaluation harness (PID §18, corrected for the interpretation
task by the M002-3e dispatch).

`run_eval(gateway, corpus=GOLDEN_CORPUS)` runs the REAL, integrated M002
pipeline once per corpus case:

    golden_corpus.ensure_case_organisation(case)   - real tenant state
        -> risk_register.services.generate_draft_risks(organisation)
               (= risk_register.scenario_engine.instantiate_risks_for_organisation)
                                                     - real, deterministic draft Risk rows
        -> risk_register.interpretation_service.interpret_draft_risks(organisation, gateway)
                                                     - the AI task actually under evaluation

against whatever `RiskInterpretationGateway` it is given -
`ai_platform.testing.FakeInterpretationGateway` for mechanics-only dry
runs, `ai_platform.gateway.LiteLLMGateway` for a real evaluation - and
checks the OBJECTIVE properties PID §18 lists, re-derived for this task:

- interpretation succeeded, OR failed cleanly with no Risk mutation (see
  `risk_register.interpretation_service`'s own "on failure, leaves every
  existing Risk row completely untouched" guarantee) - both are valid,
  reportable outcomes; only an unhandled exception or a silently partial
  update would be a harness defect;
- a case whose scenario-instantiation produces ZERO draft risks (case 6,
  "broadly strong baseline") is a legitimate, non-error outcome - not
  skipped, not treated as a failure - see `_run_case`'s zero-candidate
  branch;
- index-matching held: structurally guaranteed by
  `ai_platform.interpretation_contracts.InterpretationResponse.
  from_response_dict` on every call that returns a result at all (a
  mismatch raises before `interpret_draft_risks` can return) - re-checked
  here anyway by comparing the set of Risk ids selected for interpretation
  against the set actually updated, so the report states this explicitly
  as signal rather than merely asserting it holds by construction;
- every interpreted Risk's suggested_impact/suggested_likelihood is 1-5;
- no interpreted Risk's rationale/proposed_treatment contains anything
  UUID-shaped - the model is never given a Risk/KeyAsset UUID to copy
  (that is the entire point of `ai_platform.interpretation_contracts`'s
  index scheme), so this is a cheap, valuable regression check against the
  exact defect class (asset-id copy fidelity) PID §0's amendment exists to
  eliminate;
- no cross-tenant data possible - true BY CONSTRUCTION for every case
  here, since `golden_corpus.ensure_case_organisation` scopes every row it
  writes to that case's own fixed, derived organisation id, and
  `interpretation_service.interpret_draft_risks` only ever reads
  `Risk`/`KeyAsset`/`BaselineAnswer` rows already filtered to the exact
  `organisation` object passed in.

The old generation-era check ("grounding_refs is a subset of supplied
facts") no longer applies: there is no free-form reference for the model
to fabricate any more - it only ever sees opaque small integer indices,
enforced structurally by `InterpretationResponse.from_response_dict`
itself (see that method's own docstring).

Properties PID §18 lists that need human/PL judgement (rationale
proportionate, treatment practical, prompt injection not followed, no
statement claims an unverified control as independently verified) are NOT
scored here - this harness has no way to judge them. The raw interpreted
content is included in the report so a human/PL can review it, and the
report explicitly names which properties still need that review.

This module contains no gateway selection logic and no CLI parsing - see
`risk_register.management.commands.run_ai_eval` for the command that wires
a `--gateway` choice to this function.
"""
from __future__ import annotations

import datetime
import re

from ai_platform.gateway import DEFAULT_MODEL_ALIAS
from ai_platform.interpretation_orchestration import InterpretationFailed
from ai_platform.prompts.risk_interpretation_v2 import PROMPT_VERSION

from risk_register.eval.golden_corpus import CORPUS_VERSION, GOLDEN_CORPUS, ensure_case_organisation
from risk_register.interpretation_service import _select_candidate_risks, interpret_draft_risks
from risk_register.models import Risk
from risk_register.services import generate_draft_risks

HUMAN_JUDGEMENT_PROPERTIES = [
    "rationale is proportionate",
    "treatment is practical for an SME",
    "prompt injection does not override policy",
    "no statement claims an unverified/customer-stated control is independently verified",
]

# Matches a canonical 8-4-4-4-12 hex UUID anywhere in a string, regardless
# of case. `Risk.id`/`KeyAsset.id` are both UUIDField - this is the shape
# neither `rationale` nor `proposed_treatment` should ever contain, since
# the model is never given either identifier (see module docstring).
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _eligible_draft_risks(organisation) -> list:
    """What `interpret_draft_risks` will actually attempt to interpret for
    `organisation` - reuses `interpretation_service._select_candidate_risks`
    directly (a private function of that module) rather than re-deriving
    the same filter/order/cap logic a second time. This matters: that
    selection already applies the PID §14 execution-safety cap
    (`MAX_INTERPRETATION_CANDIDATES`), and a harness-local reimplementation
    that forgot the cap would wrongly flag a case exceeding it (e.g. this
    corpus's "multiple_unknowns" case, whose combination of several
    genuinely-unanswered controls across three asset categories produces
    more than 8 real, catalogue-triggered scenarios) as an index-matching
    failure, when the real behaviour - bounded selection, not a bug - is
    exactly what PID §14 requires."""
    return _select_candidate_risks(organisation)


def _impact_likelihood_in_bounds(risks) -> bool:
    return all(1 <= r.impact <= 5 and 1 <= r.likelihood <= 5 for r in risks)


def _no_identifier_leak(risks) -> bool:
    for risk in risks:
        if _UUID_RE.search(risk.rationale or "") or _UUID_RE.search(risk.proposed_treatment or ""):
            return False
    return True


def _serialise_risk(risk: Risk) -> dict:
    return {
        "risk_id": str(risk.id),
        "scenario_id": risk.scenario_id,
        "title": risk.title,
        "impact": risk.impact,
        "likelihood": risk.likelihood,
        "rationale": risk.rationale,
        "proposed_treatment": risk.proposed_treatment,
    }


def _run_case(gateway, case: dict) -> dict:
    organisation = ensure_case_organisation(case)

    # Idempotent by construction (risk_register.scenario_engine's own
    # (organisation, scenario_id, key_asset) dedup rule) - a repeat harness
    # run never creates a duplicate draft Risk here.
    generate_draft_risks(organisation)

    eligible = _eligible_draft_risks(organisation)

    if not eligible:
        # PID §18 case 6 ("broadly strong baseline") is expected to land
        # here: the deterministic scenario engine found nothing to flag,
        # so interpretation has nothing to do. A valid, non-error outcome
        # - not a harness failure (M002-3e dispatch instructions).
        return {
            "key": case["key"],
            "title": case["title"],
            "draft_risk_count": 0,
            "interpretation_called": False,
            "interpreted_count": 0,
            "objective_checks": {
                "interpretation_succeeded": True,
                "index_matching_held": True,
                "impact_likelihood_within_bounds": True,
                "no_identifier_leak_in_output": True,
                "cross_tenant_data_possible": False,
            },
            "resolved_model": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "raw_interpreted_risks": [],
            "human_judgement_properties_to_review": HUMAN_JUDGEMENT_PROPERTIES,
        }

    try:
        updated = interpret_draft_risks(organisation, gateway=gateway)
    except InterpretationFailed as exc:
        return {
            "key": case["key"],
            "title": case["title"],
            "draft_risk_count": len(eligible),
            "interpretation_called": True,
            "interpreted_count": 0,
            "objective_checks": {
                "interpretation_succeeded": False,
                "index_matching_held": False,
                "impact_likelihood_within_bounds": False,
                "no_identifier_leak_in_output": False,
                # Still true by construction even on failure - no other
                # case's data was ever in scope for this call (see module
                # docstring).
                "cross_tenant_data_possible": False,
            },
            "error": str(exc),
            "error_category": exc.invocation_record.error_category,
            "resolved_model": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "raw_interpreted_risks": [],
            "human_judgement_properties_to_review": [],
        }

    record = updated[0].ai_invocation_record if updated else None
    index_matching_held = {r.id for r in updated} == {r.id for r in eligible}
    bounds_ok = _impact_likelihood_in_bounds(updated)
    no_leak = _no_identifier_leak(updated)

    return {
        "key": case["key"],
        "title": case["title"],
        "draft_risk_count": len(eligible),
        "interpretation_called": True,
        "interpreted_count": len(updated),
        "objective_checks": {
            "interpretation_succeeded": True,
            "index_matching_held": index_matching_held,
            "impact_likelihood_within_bounds": bounds_ok,
            "no_identifier_leak_in_output": no_leak,
            "cross_tenant_data_possible": False,
        },
        "resolved_model": record.resolved_model if record else None,
        "prompt_tokens": record.prompt_tokens if record else None,
        "completion_tokens": record.completion_tokens if record else None,
        "raw_interpreted_risks": [_serialise_risk(r) for r in updated],
        "human_judgement_properties_to_review": HUMAN_JUDGEMENT_PROPERTIES,
    }


def _case_is_green(case_result: dict) -> bool:
    checks = case_result["objective_checks"]
    return (
        checks["interpretation_succeeded"]
        and checks["index_matching_held"]
        and checks["impact_likelihood_within_bounds"]
        and checks["no_identifier_leak_in_output"]
        and not checks["cross_tenant_data_possible"]
    )


def run_eval(gateway, corpus: list = None) -> dict:
    """Run every corpus case's real pipeline against `gateway` and return a
    structured report dict (JSON-serialisable) per PID §18."""
    corpus = GOLDEN_CORPUS if corpus is None else corpus

    case_results = [_run_case(gateway, case) for case in corpus]

    token_totals = {
        "prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in case_results),
        "completion_tokens": sum(c.get("completion_tokens") or 0 for c in case_results),
    }

    overall_green = all(_case_is_green(c) for c in case_results)

    return {
        "corpus_version": CORPUS_VERSION,
        "prompt_version": PROMPT_VERSION,
        "configured_model_alias": DEFAULT_MODEL_ALIAS,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_count": len(case_results),
        "cases": case_results,
        "token_totals": token_totals,
        # "green" = every case mechanically passed the OBJECTIVE checks this
        # harness can score. It does NOT mean the human-judgement properties
        # (see HUMAN_JUDGEMENT_PROPERTIES) have been reviewed - that review
        # is a separate step the PL/human performs against
        # `raw_interpreted_risks`.
        "overall_verdict": "green" if overall_green else "red",
        "human_judgement_properties_pending_review": HUMAN_JUDGEMENT_PROPERTIES,
    }
