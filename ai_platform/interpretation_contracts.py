"""
Structured contracts for the AI risk-INTERPRETATION task (M002 PID §0.6,
§0.7, §9.3, §10 - M002-3c dispatch).

This is a NEW, NARROWER contract for a NEW task - it does not reuse
`ai_platform.contracts`'s `GroundingPayload`/`RiskCandidate`/
`GenerationResult` shapes (those were built for the now-retired
"profile + baseline + assets -> LLM -> risks" open-generation task and are
kept only as historical record - see that module's own docstring). It does
reuse `ai_platform.contracts`'s generic validation helpers
(`_require_str` etc.), `ContractValidationError`, `MIN_RATING`/
`MAX_RATING`, `MAX_CANDIDATES` and `ClarificationQuestion` - those are
task-shape-independent, and duplicating them here would be exactly the
kind of needless second implementation the M002-3c dispatch instructions
warn against.

== The architectural rule this module exists to enforce ==
PID §0.6: "The LLM must not be responsible for reproducing database UUIDs
or manufacturing foreign-key references." By the time a `Risk` row reaches
this task, `risk_register.scenario_engine` (Phase 3b) has already
deterministically assigned it a real `key_asset` FK and a real
`scenario_id` - there is no reason for the model interpreting it to ever
see, let alone reproduce, either identifier. Every `Risk` this task
interprets is therefore represented to the model as an
`InterpretationCandidate` carrying only a small, per-call, sequential
integer `index` (1, 2, 3, ...) and descriptive, non-identifying fields.
`InterpretationRequest`/`InterpretationResponse` never carry a `Risk.id`,
a `KeyAsset.id`, or an `organisation_id` in their wire content (see
`InterpretationCandidate.to_wire_dict`) - the caller
(`risk_register.interpretation_service`) is the only place that ever maps
an `index` back to the real `Risk` object it already holds a reference to.

`InterpretationResponse.from_response_dict` is the single choke point that
turns an untrusted raw gateway payload into validated objects, and it is
where the index-matching rule the M002-3c dispatch requires is enforced:
every input index must have exactly one matching output index - no
missing, no extra, no duplicate - or the whole response is rejected and
`ai_platform.interpretation_orchestration.interpret_candidates` never
returns a result a caller could apply to any `Risk` row. This mirrors
`ai_platform.contracts`'s "invalid/unparseable output is a failed
generation, not partially trusted data" discipline (PID §9.3), extended to
cover an index mismatch as an equally invalid response, not merely a
missing field.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from ai_platform.contracts import (
    MAX_CANDIDATES,
    MAX_RATING,
    MIN_RATING,
    ClarificationQuestion,
    ContractValidationError,
    _require_dict,
    _require_dict_list,
    _require_int_range,
    _require_str,
    _require_str_list,
)

# Same execution-safety cap PID §14 sets for generation (max 8 proposed
# risks per generation), reused rather than re-derived: a single number,
# defined once in ai_platform.contracts, so the two tasks can never drift
# apart on what "bounded" means. Enforced by `InterpretationRequest.
# __post_init__` below (a caller-contract violation, not a model-output
# problem - unlike generation's MAX_CANDIDATES truncation, which bounds
# what the MODEL returned).
MAX_INTERPRETATION_CANDIDATES = MAX_CANDIDATES


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractValidationError(f"'{field}' must be a positive int, got {value!r}")
    return value


@dataclasses.dataclass(frozen=True)
class InterpretationCandidate:
    """One already-existing, catalogue-instantiated `Risk` row, represented
    for exactly one interpretation call (M002 PID's explicit index scheme -
    see module docstring).

    Deliberately excludes: the `Risk.id` UUID, the `key_asset` UUID, the
    `scenario_id`, the `organisation_id` - none of these are needed for the
    model to do its job (explain/refine/prioritise), and PID §0.6 requires
    the model never be asked to reproduce or invent any of them. What IS
    included is exactly what a human practitioner reviewing this candidate
    would also look at: the methodology-derived exposure/threat_event/
    vulnerability/consequence, the asset's category, the current (starting-
    point) impact/likelihood, and any genuinely relevant free text the
    organisation itself wrote (asset description / baseline answer notes) -
    untrusted data, same PID §12 injection framing as the retired
    generation prompt used.
    """

    index: int
    title: str
    exposure: str
    threat_event: str
    vulnerability: str
    consequence: str
    current_impact: int
    current_likelihood: int
    asset_category: str
    notes: list = dataclasses.field(default_factory=list)  # list[str], untrusted free text, may be empty

    def __post_init__(self):
        _require_positive_int(self.index, "index")
        _require_str(self.title, "title")
        _require_str(self.exposure, "exposure")
        _require_str(self.threat_event, "threat_event")
        _require_str(self.vulnerability, "vulnerability")
        _require_str(self.consequence, "consequence")
        _require_int_range(self.current_impact, "current_impact", MIN_RATING, MAX_RATING)
        _require_int_range(self.current_likelihood, "current_likelihood", MIN_RATING, MAX_RATING)
        _require_str(self.asset_category, "asset_category")
        _require_str_list(self.notes, "notes", allow_empty=True)

    def to_wire_dict(self) -> dict:
        """Exactly what is sent to the model for this candidate (see
        `ai_platform.prompts.risk_interpretation_v1.build_messages`) - the
        opaque per-call `index` plus only descriptive, non-identifying
        fields. No `Risk.id`, no `key_asset` id, no `scenario_id`."""
        return {
            "index": self.index,
            "title": self.title,
            "exposure": self.exposure,
            "threat_event": self.threat_event,
            "vulnerability": self.vulnerability,
            "consequence": self.consequence,
            "current_impact": self.current_impact,
            "current_likelihood": self.current_likelihood,
            "asset_category": self.asset_category,
            "notes": list(self.notes),
        }


@dataclasses.dataclass(frozen=True)
class InterpretationRequest:
    """What goes INTO one interpretation call.

    `organisation_id` is carried here (like `GroundingPayload.
    organisation_id`) purely as call metadata for
    `ai_platform.interpretation_orchestration.interpret_candidates` to
    scope the `AIInvocationRecord` it creates to the right tenant - it is
    NOT part of the outbound wire payload (see
    `InterpretationCandidate.to_wire_dict`; the model is never told which
    organisation it is looking at, since nothing about the interpretation
    task needs that and every field sent is one more thing PID §16's
    tenant-isolation test must prove never leaks cross-tenant).

    `candidates` must be the small, sequential, gap-free integer indices
    1..N with no duplicates (PID's explicit index-scheme requirement) -
    enforced here, not left to the caller's discipline, and not left to be
    discovered only once a response comes back mismatched.
    """

    organisation_id: str
    candidates: list  # list[InterpretationCandidate], indices 1..N, no gaps, no duplicates

    def __post_init__(self):
        _require_str(self.organisation_id, "organisation_id")
        if not isinstance(self.candidates, list) or not self.candidates or not all(
            isinstance(c, InterpretationCandidate) for c in self.candidates
        ):
            raise ContractValidationError(
                "'candidates' must be a non-empty list of InterpretationCandidate"
            )
        if len(self.candidates) > MAX_INTERPRETATION_CANDIDATES:
            raise ContractValidationError(
                f"InterpretationRequest carries {len(self.candidates)} candidates, "
                f"more than the PID §14 execution-safety cap of "
                f"{MAX_INTERPRETATION_CANDIDATES} - the caller must select/batch "
                f"candidates before constructing this request."
            )
        indices = [c.index for c in self.candidates]
        if len(indices) != len(set(indices)):
            raise ContractValidationError(
                f"InterpretationRequest candidate indices must be unique, got {indices!r}"
            )
        if sorted(indices) != list(range(1, len(indices) + 1)):
            raise ContractValidationError(
                "InterpretationRequest candidate indices must be the small sequential "
                f"integers 1..N with no gaps - got {sorted(indices)!r}"
            )

    @property
    def expected_indices(self) -> frozenset:
        return frozenset(c.index for c in self.candidates)


@dataclasses.dataclass(frozen=True)
class InterpretationOutcome:
    """One candidate's interpretation, keyed by the same `index` it was
    given (PID's explicit index scheme - never a UUID)."""

    index: int
    suggested_impact: int
    suggested_likelihood: int
    rationale: str
    suggested_treatment: str
    clarification_questions: list = dataclasses.field(default_factory=list)  # list[ClarificationQuestion]
    priority_note: Optional[str] = None

    def __post_init__(self):
        _require_positive_int(self.index, "index")
        _require_int_range(self.suggested_impact, "suggested_impact", MIN_RATING, MAX_RATING)
        _require_int_range(self.suggested_likelihood, "suggested_likelihood", MIN_RATING, MAX_RATING)
        _require_str(self.rationale, "rationale")
        _require_str(self.suggested_treatment, "suggested_treatment")
        if not isinstance(self.clarification_questions, list) or not all(
            isinstance(q, ClarificationQuestion) for q in self.clarification_questions
        ):
            raise ContractValidationError(
                "'clarification_questions' must be a list of ClarificationQuestion"
            )
        if self.priority_note is not None:
            _require_str(self.priority_note, "priority_note")

    @classmethod
    def from_dict(cls, data: Any) -> "InterpretationOutcome":
        if not isinstance(data, dict):
            raise ContractValidationError(f"interpretation outcome must be an object, got {data!r}")
        try:
            index = data["index"]
            suggested_impact = data["suggested_impact"]
            suggested_likelihood = data["suggested_likelihood"]
            rationale = data["rationale"]
            suggested_treatment = data["suggested_treatment"]
        except KeyError as exc:
            raise ContractValidationError(
                f"interpretation outcome missing required field: {exc}"
            ) from exc

        raw_questions = _require_dict_list(
            data.get("clarification_questions", []) or [], "clarification_questions"
        )
        questions = [ClarificationQuestion.from_dict(q) for q in raw_questions]

        return cls(
            index=index,
            suggested_impact=suggested_impact,
            suggested_likelihood=suggested_likelihood,
            rationale=rationale,
            suggested_treatment=suggested_treatment,
            clarification_questions=questions,
            priority_note=data.get("priority_note") or None,
        )


@dataclasses.dataclass(frozen=True)
class InterpretationResponse:
    """What comes OUT of one interpretation call.

    `outcomes` carries exactly one `InterpretationOutcome` per index the
    request supplied - see `from_response_dict`'s index-matching
    validation, the specific check the M002-3c dispatch requires.

    `additional_observations` (PID §0.7 third bullet) is a SEPARATE,
    top-level, NOT-per-index list of free-text practitioner commentary -
    never attached to a candidate, never a new `Risk` row or new catalogue
    truth. `risk_register.interpretation_service` never reads this field
    to build/update a `Risk`; only `ai_platform.interpretation_orchestration.
    interpret_candidates` persists it, onto the `AIInvocationRecord` itself
    (see that model's `additional_observations` field docstring) - keeping
    it structurally separate from anything that could become risk-register
    state.
    """

    outcomes: list  # list[InterpretationOutcome], one per input index, exact match enforced below
    additional_observations: list = dataclasses.field(default_factory=list)  # list[str]
    resolved_model: Optional[str] = None
    prompt_version: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def __post_init__(self):
        if not isinstance(self.outcomes, list) or not all(
            isinstance(o, InterpretationOutcome) for o in self.outcomes
        ):
            raise ContractValidationError("'outcomes' must be a list of InterpretationOutcome")
        _require_str_list(self.additional_observations, "additional_observations", allow_empty=True)

    def outcome_for_index(self, index: int) -> InterpretationOutcome:
        """Look up the one outcome for `index`. Unreachable-if-called-after-
        `from_response_dict` to raise `KeyError` in normal use, since that
        classmethod has already proven every expected index has exactly
        one outcome - kept as a real lookup (not an unchecked assumption)
        so a caller building its own `InterpretationResponse` by hand
        (e.g. a test) still gets a clear error rather than silently
        matching the wrong outcome."""
        for outcome in self.outcomes:
            if outcome.index == index:
                return outcome
        raise KeyError(index)

    @classmethod
    def from_response_dict(
        cls,
        data: Any,
        *,
        expected_indices,
        resolved_model: Optional[str],
        prompt_version: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> "InterpretationResponse":
        """Parse+validate a raw gateway JSON payload into an
        `InterpretationResponse`, enforcing the exact index-matching rule
        the M002-3c dispatch requires: every index in `expected_indices`
        must appear in the response exactly once - no missing index, no
        unknown/invented index, no duplicate index. Any mismatch raises
        `ContractValidationError` - nothing downstream ever sees a
        partially-matched result (mirrors PID §9.3's "invalid/unparseable
        output is a failed generation, not partially trusted data",
        extended to this task's own failure mode).
        """
        payload = _require_dict(data, "interpretation response")

        raw_outcomes = payload.get("interpretations")
        if raw_outcomes is None:
            raise ContractValidationError("interpretation response missing 'interpretations' array")
        raw_outcomes = _require_dict_list(raw_outcomes, "interpretations")
        outcomes = [InterpretationOutcome.from_dict(o) for o in raw_outcomes]

        # --- The critical index-matching validation ---------------------
        seen_indices = [o.index for o in outcomes]
        seen_set = set(seen_indices)
        expected_set = set(expected_indices)

        duplicates = sorted({i for i in seen_set if seen_indices.count(i) > 1})
        if duplicates:
            raise ContractValidationError(
                f"interpretation response contains duplicate index/indices: {duplicates!r}"
            )
        unknown = sorted(seen_set - expected_set)
        if unknown:
            raise ContractValidationError(
                "interpretation response references index/indices that were not "
                f"sent in this call's request: {unknown!r}"
            )
        missing = sorted(expected_set - seen_set)
        if missing:
            raise ContractValidationError(
                f"interpretation response is missing outcomes for index/indices: {missing!r}"
            )
        # seen_set == expected_set, no duplicates -> exactly one outcome per
        # expected index. No partial credit for "close enough".

        raw_observations = payload.get("additional_observations", []) or []
        additional_observations = _require_str_list(
            raw_observations, "additional_observations", allow_empty=True
        )

        return cls(
            outcomes=outcomes,
            additional_observations=additional_observations,
            resolved_model=resolved_model,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
