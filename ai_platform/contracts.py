"""
Structured contracts for the AI risk-generation adapter (M002 PID §9.3, §10).

Plain stdlib `dataclasses` - no pydantic or any other schema library is
introduced here (PID §25 reproducibility doctrine: a new dependency is not
justified for this narrow validation need; Django's own conventions plus
plain dataclasses are enough).

Every dataclass here validates itself in `__post_init__`, so an instance can
never exist half-valid. `GenerationResult.from_response_dict` is the single
choke point that turns an untrusted raw gateway payload into validated
objects - or raises `ContractValidationError`. This is "invalid/unparseable
output is a failed generation, not partially trusted data" (PID §9.3) made
concrete.

This module is generic transport/validation only. It does not decide which
M001/Baseline/Assets facts belong in a `GroundingPayload` - that is for the
Risk-domain module (a later, separate Engineer dispatch) to decide.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional


class ContractValidationError(ValueError):
    """A structured AI contract (request or response) failed strict,
    server-side validation. Always raised instead of returning a
    partially-populated object (PID §9.3)."""


MIN_RATING = 1
MAX_RATING = 5

# Execution-safety cap (PID §14). Enforced by `ai_platform.orchestration.
# generate_risks`, not here - see that module's docstring for why the cap
# is a bounded-execution concern, not a data-shape validity concern.
MAX_CANDIDATES = 8


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"'{field}' must be a non-empty string, got {value!r}")
    return value


def _require_int_range(value: Any, field: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractValidationError(f"'{field}' must be an int, got {value!r}")
    if not (lo <= value <= hi):
        raise ContractValidationError(f"'{field}' must be between {lo} and {hi}, got {value!r}")
    return value


def _require_str_list(value: Any, field: str, *, allow_empty: bool) -> list:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ContractValidationError(f"'{field}' must be a list of strings, got {value!r}")
    if not allow_empty and not value:
        raise ContractValidationError(f"'{field}' must be a non-empty list of strings")
    return list(value)


def _require_dict(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise ContractValidationError(f"'{field}' must be an object, got {value!r}")
    return value


def _require_dict_list(value: Any, field: str) -> list:
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise ContractValidationError(f"'{field}' must be a list of objects, got {value!r}")
    return list(value)


@dataclasses.dataclass(frozen=True)
class GroundingPayload:
    """What goes INTO a generation call (PID §9.3, §10).

    Deliberately generic (plain dicts for the fact groups): the Risk-domain
    module decides exactly which M001 profile / baseline / asset fields to
    pass in. This layer only guarantees the transport shape and that every
    organisation-supplied free-text value travels as inert data (PID §12) -
    it is serialised into the AI user message as JSON, never concatenated
    into the system prompt (see `ai_platform.prompts.risk_generation_v1`).
    """

    organisation_id: str
    profile_facts: dict
    baseline_facts: dict
    asset_facts: list  # list[dict]

    def __post_init__(self):
        _require_str(self.organisation_id, "organisation_id")
        _require_dict(self.profile_facts, "profile_facts")
        _require_dict(self.baseline_facts, "baseline_facts")
        _require_dict_list(self.asset_facts, "asset_facts")


@dataclasses.dataclass(frozen=True)
class RiskCandidate:
    """One proposed risk (PID §9.3, §10). Always AI-suggested, never
    confirmed truth - confirmation is a Risk-domain concern, not this
    layer's."""

    title: str
    asset_reference: str
    threat: str
    vulnerability: str
    suggested_impact: int
    suggested_likelihood: int
    rationale: str
    proposed_treatment: str
    grounding_refs: list  # list[str], e.g. "profile.endpoint_management", "asset:<uuid>"
    assumptions: list = dataclasses.field(default_factory=list)  # list[str], may be empty

    def __post_init__(self):
        _require_str(self.title, "title")
        _require_str(self.asset_reference, "asset_reference")
        _require_str(self.threat, "threat")
        _require_str(self.vulnerability, "vulnerability")
        _require_int_range(self.suggested_impact, "suggested_impact", MIN_RATING, MAX_RATING)
        _require_int_range(self.suggested_likelihood, "suggested_likelihood", MIN_RATING, MAX_RATING)
        _require_str(self.rationale, "rationale")
        _require_str(self.proposed_treatment, "proposed_treatment")
        _require_str_list(self.grounding_refs, "grounding_refs", allow_empty=False)
        _require_str_list(self.assumptions, "assumptions", allow_empty=True)

    @classmethod
    def from_dict(cls, data: Any) -> "RiskCandidate":
        if not isinstance(data, dict):
            raise ContractValidationError(f"risk candidate must be an object, got {data!r}")
        try:
            return cls(
                title=data["title"],
                asset_reference=data["asset_reference"],
                threat=data["threat"],
                vulnerability=data["vulnerability"],
                suggested_impact=data["suggested_impact"],
                suggested_likelihood=data["suggested_likelihood"],
                rationale=data["rationale"],
                proposed_treatment=data["proposed_treatment"],
                grounding_refs=data["grounding_refs"],
                assumptions=data.get("assumptions", []),
            )
        except KeyError as exc:
            raise ContractValidationError(f"risk candidate missing required field: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class ClarificationQuestion:
    """PID §11: what fact is missing, why it matters, which decision it
    affects."""

    missing_fact: str
    why_it_matters: str
    affects: str

    def __post_init__(self):
        _require_str(self.missing_fact, "missing_fact")
        _require_str(self.why_it_matters, "why_it_matters")
        _require_str(self.affects, "affects")

    @classmethod
    def from_dict(cls, data: Any) -> "ClarificationQuestion":
        if not isinstance(data, dict):
            raise ContractValidationError(f"clarification question must be an object, got {data!r}")
        try:
            return cls(
                missing_fact=data["missing_fact"],
                why_it_matters=data["why_it_matters"],
                affects=data["affects"],
            )
        except KeyError as exc:
            raise ContractValidationError(f"clarification question missing required field: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class GenerationResult:
    """What comes OUT of a generation call (PID §9.3, §11)."""

    candidates: list  # list[RiskCandidate]
    clarification_questions: list = dataclasses.field(default_factory=list)  # list[ClarificationQuestion]
    resolved_model: Optional[str] = None
    prompt_version: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def __post_init__(self):
        if not isinstance(self.candidates, list) or not all(
            isinstance(c, RiskCandidate) for c in self.candidates
        ):
            raise ContractValidationError("'candidates' must be a list of RiskCandidate")
        if not isinstance(self.clarification_questions, list) or not all(
            isinstance(q, ClarificationQuestion) for q in self.clarification_questions
        ):
            raise ContractValidationError(
                "'clarification_questions' must be a list of ClarificationQuestion"
            )

    @classmethod
    def from_response_dict(
        cls,
        data: Any,
        *,
        resolved_model: Optional[str],
        prompt_version: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> "GenerationResult":
        """Parse+validate a raw gateway JSON payload (already `json.loads`'d
        into Python objects) into a `GenerationResult`.

        Raises `ContractValidationError` on any structural/type problem.
        This is the single choke point: nothing downstream ever sees a
        partially-validated candidate (PID §9.3).
        """
        payload = _require_dict(data, "generation response")

        raw_candidates = payload.get("risks")
        if raw_candidates is None:
            raise ContractValidationError("generation response missing 'risks' array")
        raw_candidates = _require_dict_list(raw_candidates, "risks")
        candidates = [RiskCandidate.from_dict(c) for c in raw_candidates]

        raw_questions = payload.get("clarification_questions", [])
        raw_questions = _require_dict_list(raw_questions, "clarification_questions")
        questions = [ClarificationQuestion.from_dict(q) for q in raw_questions]

        return cls(
            candidates=candidates,
            clarification_questions=questions,
            resolved_model=resolved_model,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
