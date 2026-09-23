"""
M002 live AI evaluation harness (PID §18).

`run_eval(gateway, corpus=GOLDEN_CORPUS)` runs `ai_platform.orchestration.
generate_risks` once per corpus case against whatever `RiskGenerationGateway`
it is given - `FakeGateway` for mechanics-only dry runs, `LiteLLMGateway` for
a real evaluation - and checks the OBJECTIVE properties PID §18 lists in
code:

- output contract valid (generation succeeded at all - an exception here
  means the contract validation in `ai_platform.contracts` already failed
  it, which is itself the check);
- grounding_refs is a subset of that case's supplied fact keys/asset ids -
  never a fabricated reference;
- impact/likelihood within 1-5 (defensive - already guaranteed by contract
  validation, checked again here so the report states it explicitly);
- no cross-tenant data possible - true BY CONSTRUCTION for every case here,
  since each case is a single, independently-constructed `GroundingPayload`
  naming its own organisation id; there is no code path in this harness
  that could combine two cases' facts.

Properties PID §18 lists that need human/PL judgement (rationale
proportionate, treatment practical, prompt injection not followed,
certification not invented) are NOT scored here - this harness has no way
to judge them. Instead the raw generated content is included in the report
so a human/PL can review it, and the report explicitly names which
properties still need that review.

This module contains no gateway selection logic and no CLI parsing - see
`risk_register.management.commands.run_ai_eval` for the command that wires
a `--gateway` choice to this function.
"""
from __future__ import annotations

import dataclasses
import datetime

from ai_platform.orchestration import GenerationFailed, generate_risks
from ai_platform.prompts.risk_generation_v1 import PROMPT_VERSION

from risk_register.eval.golden_corpus import CORPUS_VERSION, GOLDEN_CORPUS, ensure_eval_organisations

HUMAN_JUDGEMENT_PROPERTIES = [
    "rationale is proportionate",
    "treatment is practical for an SME",
    "prompt injection does not override policy",
    "certification/compliance is not invented",
    "no statement claims an unverified/customer-stated control is independently verified",
]


def _allowed_grounding_refs(grounding) -> set:
    """The set of grounding_refs a case's own supplied facts make
    legitimate - never a value not present in this exact case's payload."""
    allowed = {f"profile.{key}" for key in grounding.profile_facts}
    allowed |= {f"baseline.{key}" for key in grounding.baseline_facts}
    allowed |= {
        f"asset:{asset['id']}" for asset in grounding.asset_facts if "id" in asset
    }
    return allowed


def _grounding_refs_are_subset(candidates, grounding) -> bool:
    """True iff every candidate's grounding_refs are drawn only from facts
    this exact case supplied - the PID §18 "never a fabricated reference"
    check. A pure function of (candidates, grounding), independently unit-
    tested in risk_register/tests/test_eval_harness.py with both a
    compliant and a fabricated ref, so this check is proven to actually
    catch a violation rather than trivially passing."""
    allowed = _allowed_grounding_refs(grounding)
    return all(ref in allowed for candidate in candidates for ref in candidate.grounding_refs)


def _impact_likelihood_in_bounds(candidates) -> bool:
    return all(
        1 <= candidate.suggested_impact <= 5 and 1 <= candidate.suggested_likelihood <= 5
        for candidate in candidates
    )


def _run_case(gateway, case: dict) -> dict:
    grounding = case["grounding"]
    try:
        result, record = generate_risks(gateway, grounding, PROMPT_VERSION)
    except GenerationFailed as exc:
        return {
            "key": case["key"],
            "title": case["title"],
            "objective_checks": {
                "output_contract_valid": False,
                "grounding_refs_subset_of_supplied_facts": None,
                "impact_likelihood_within_bounds": None,
                "cross_tenant_data_possible": False,
            },
            "generation_succeeded": False,
            "error": str(exc),
            "error_category": exc.invocation_record.error_category,
            "candidate_count": 0,
            "clarification_question_count": 0,
            "raw_candidates": [],
            "raw_clarification_questions": [],
            "human_judgement_properties_to_review": [],
        }

    grounding_ok = _grounding_refs_are_subset(result.candidates, grounding)
    bounds_ok = _impact_likelihood_in_bounds(result.candidates)

    return {
        "key": case["key"],
        "title": case["title"],
        "objective_checks": {
            "output_contract_valid": True,
            "grounding_refs_subset_of_supplied_facts": grounding_ok,
            "impact_likelihood_within_bounds": bounds_ok,
            # True by construction: this case's GroundingPayload names only
            # its own organisation_id, built from only its own dict/list
            # literals - there is no second case's data anywhere in scope
            # when this call is made (see module docstring).
            "cross_tenant_data_possible": False,
        },
        "generation_succeeded": True,
        "resolved_model": result.resolved_model,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "candidate_count": len(result.candidates),
        "clarification_question_count": len(result.clarification_questions),
        "raw_candidates": [dataclasses.asdict(c) for c in result.candidates],
        "raw_clarification_questions": [dataclasses.asdict(q) for q in result.clarification_questions],
        "human_judgement_properties_to_review": HUMAN_JUDGEMENT_PROPERTIES,
    }


def run_eval(gateway, corpus: list = None, *, model_alias: str = None) -> dict:
    """Run every corpus case against `gateway` and return a structured
    report dict (JSON-serialisable) per PID §18.

    `model_alias` is recorded in the report header only (informational -
    `generate_risks` is always called with its own default unless a caller
    of this function's own caller changes that; this harness does not need
    to vary it).
    """
    corpus = GOLDEN_CORPUS if corpus is None else corpus
    ensure_eval_organisations(corpus)

    case_results = [_run_case(gateway, case) for case in corpus]

    token_totals = {
        "prompt_tokens": sum(
            c.get("prompt_tokens") or 0 for c in case_results if c.get("generation_succeeded")
        ),
        "completion_tokens": sum(
            c.get("completion_tokens") or 0 for c in case_results if c.get("generation_succeeded")
        ),
    }

    all_mechanically_green = all(
        c["generation_succeeded"]
        and c["objective_checks"]["grounding_refs_subset_of_supplied_facts"]
        and c["objective_checks"]["impact_likelihood_within_bounds"]
        for c in case_results
    )

    return {
        "corpus_version": CORPUS_VERSION,
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_count": len(case_results),
        "cases": case_results,
        "token_totals": token_totals,
        # "green" = every case mechanically passed the OBJECTIVE checks this
        # harness can score. It does NOT mean the human-judgement properties
        # (see HUMAN_JUDGEMENT_PROPERTIES) have been reviewed - that review
        # is a separate step the PL/human performs against `raw_candidates`.
        "overall_verdict": "green" if all_mechanically_green else "red",
        "human_judgement_properties_pending_review": HUMAN_JUDGEMENT_PROPERTIES,
    }
