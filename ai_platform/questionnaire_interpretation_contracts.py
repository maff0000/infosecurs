"""
Structured contracts for the AI QUESTIONNAIRE-INTERPRETATION task (M005 PID
§10, §20 - m005-1-foundation dispatch).

This is a NEW, sibling contract module for a FOURTH task type, following the
same pattern `ai_platform.interpretation_contracts` (risk interpretation,
task two) and `ai_platform.policy_contracts` (policy generation, task three)
already established: a new, narrower request/response shape lives in its
own module, while the generic, task-shape-independent validation helpers
(`_require_str`, `_require_dict`, `_require_dict_list`, `_require_bool`,
`ContractValidationError`) are imported and reused from `ai_platform.
contracts` rather than reimplemented.

== The architectural rule this module exists to enforce (PID §2, §10) ==
"AI interprets and writes. Application code owns truth and assurance
outcome." This task's whole job is to turn one arbitrary, untrusted external
question into a structured statement of WHAT IT IS ASKING - never whether
the organisation actually satisfies it. `QuestionnaireInterpretation` never
carries an outcome/assurance field of any kind; `questionnaire.outcome.
derive_outcome` (deterministic application code, not this contract) is the
only place an outcome is ever produced, over a grounding snapshot this
interpretation's own `selected_keys` make possible to assemble.

== "AI may select only canonical semantic keys supplied by the application"
(PID §10, §F) ==
This is `ai_platform.interpretation_contracts.InterpretationResponse.
from_response_dict`'s own index-matching discipline, adapted from integer
indices to string catalogue keys: every entry in `selected_keys` MUST be one
of the keys actually offered in this specific call's `available_keys` (see
`QuestionnaireInterpretationRequest.available_keys`) - not merely "a key
that exists somewhere in `questionnaire.catalogue.CATALOGUE`", but a key
that was genuinely offered THIS call. In practice `available_keys` is always
the full catalogue (PID §10: "small enough that no relevance-filtering step
is needed" - see `questionnaire.catalogue`'s own docstring), but validating
against the exact offered set rather than the whole catalogue module keeps
this contract's guarantee independent of that catalogue-sizing decision, the
same way `InterpretationResponse.from_response_dict` validates against
`expected_indices` (what THIS request actually carried) rather than some
global index range. An invented/unrecognised key - one that was never
offered - is a hard validation gate (`ContractValidationError`), never a
soft warning: this is the second of the two safety boundaries PID §20
describes (prompt-injection framing in the prompt module is the first; this
structural validation gate is the one that cannot be talked around by
adversarial question text, since it is enforced in Python after the model's
response comes back, regardless of what the model was persuaded to claim).

== `evidence_explicitly_requested` - a deliberate, PID-consistent addition
beyond PID §10's literal minimum field list ==
PID §10 lists intent_type/requirement_scope/requirement_summary/selected
keys/ambiguity flag/note as the interpretation call's minimum output fields
- "minimum", not an exhaustive/closed list. PID §12.1 requires: "If the
external question explicitly asks for evidence/proof and there is no
suitable active support evidence, do not return SUPPORTED; return CONFIRM."
PID §12.2 separately lists "explicit evidence/verification request backed
only by customer statement" as its own CONFIRM trigger. Both of these are
about a semantic property of the RAW, untrusted external question text -
"did this question explicitly ask for evidence/proof" - that only the
interpretation step, which actually reads that free text, can honestly
determine. Nothing else in the pipeline ever looks at the raw question text
again (grounding assembly and outcome derivation only ever see the already-
validated interpretation and the grounding snapshot - see
`questionnaire.outcome.derive_outcome`). Without this field, PID §12.1/§12.2
could not be implemented at all as a deterministic, application-owned rule;
adding it here is therefore a necessary extension of PID §10's minimum, not
scope creep, and is recorded here explicitly so a future reader understands
why it exists.

`unclear` intent still returns a well-formed interpretation, never a
contract failure (PID §8: "`unclear` must result in `CONFIRM`" - that
aggregation rule belongs to `questionnaire.outcome.derive_outcome`, applied
AFTER a valid interpretation already exists; the interpretation step's own
job is only to honestly report that the question was unclear, with
`selected_keys` possibly empty).
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from ai_platform.contracts import (
    ContractValidationError,
    _require_bool,
    _require_dict,
    _require_dict_list,
    _require_str,
    _require_str_allow_blank,
)

INTENT_IMPLEMENTATION = "implementation"
INTENT_POLICY_REQUIREMENT = "policy_requirement"
INTENT_ARTEFACT_EXISTENCE = "artefact_existence"
INTENT_ORGANISATION_FACT = "organisation_fact"
INTENT_CERTIFICATION = "certification"
INTENT_MIXED = "mixed"
INTENT_UNCLEAR = "unclear"

INTENT_TYPES = [
    INTENT_IMPLEMENTATION,
    INTENT_POLICY_REQUIREMENT,
    INTENT_ARTEFACT_EXISTENCE,
    INTENT_ORGANISATION_FACT,
    INTENT_CERTIFICATION,
    INTENT_MIXED,
    INTENT_UNCLEAR,
]
_INTENT_TYPE_SET = frozenset(INTENT_TYPES)

SCOPE_ALL = "all"
SCOPE_SOME = "some"
SCOPE_EXISTENCE = "existence"
SCOPE_NOT_APPLICABLE_TEST = "not_applicable_test"
SCOPE_UNSPECIFIED = "unspecified"

REQUIREMENT_SCOPES = [
    SCOPE_ALL,
    SCOPE_SOME,
    SCOPE_EXISTENCE,
    SCOPE_NOT_APPLICABLE_TEST,
    SCOPE_UNSPECIFIED,
]
_REQUIREMENT_SCOPE_SET = frozenset(REQUIREMENT_SCOPES)


@dataclasses.dataclass(frozen=True)
class QuestionnaireInterpretationRequest:
    """What goes INTO one questionnaire-interpretation call (PID §10).

    `question_text` and `source_label` are untrusted external content
    (PID §7.1, §20) - carried here as plain strings, sent as inert JSON data
    in the prompt's user message, never concatenated into the system prompt
    (see `ai_platform.prompts.questionnaire_interpretation_v1`).

    `available_keys` is the exact catalogue entries offered THIS call - see
    module docstring for why `QuestionnaireInterpretation.from_response_dict`
    validates against this list specifically, not the whole
    `questionnaire.catalogue.CATALOGUE` module.
    """

    organisation_id: str
    question_text: str
    source_label: str  # may be ""
    available_keys: list  # list[dict] - {"key": ..., "description": ...}

    def __post_init__(self):
        _require_str(self.organisation_id, "organisation_id")
        _require_str(self.question_text, "question_text")
        _require_str_allow_blank(self.source_label, "source_label")
        _require_dict_list(self.available_keys, "available_keys")
        for entry in self.available_keys:
            if "key" not in entry or "description" not in entry:
                raise ContractValidationError(
                    "every 'available_keys' entry must have 'key' and 'description'"
                )

    @property
    def available_key_set(self) -> frozenset:
        return frozenset(entry["key"] for entry in self.available_keys)


@dataclasses.dataclass(frozen=True)
class QuestionnaireInterpretation:
    """What comes OUT of one questionnaire-interpretation call (PID §10).

    See module docstring for `evidence_explicitly_requested`'s rationale,
    and for why `selected_keys` is validated against the request's own
    `available_keys` rather than the whole catalogue.
    """

    intent_type: str
    requirement_scope: str
    requirement_summary: str
    selected_keys: list  # list[str] - subset of the offered available_keys
    evidence_explicitly_requested: bool
    ambiguous: bool
    ambiguity_note: str  # may be ""
    resolved_model: Optional[str] = None
    prompt_version: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def __post_init__(self):
        if self.intent_type not in _INTENT_TYPE_SET:
            raise ContractValidationError(
                f"'intent_type' must be one of {INTENT_TYPES!r}, got {self.intent_type!r}"
            )
        if self.requirement_scope not in _REQUIREMENT_SCOPE_SET:
            raise ContractValidationError(
                f"'requirement_scope' must be one of {REQUIREMENT_SCOPES!r}, "
                f"got {self.requirement_scope!r}"
            )
        _require_str(self.requirement_summary, "requirement_summary")
        if not isinstance(self.selected_keys, list) or not all(
            isinstance(k, str) for k in self.selected_keys
        ):
            raise ContractValidationError("'selected_keys' must be a list of strings")
        _require_bool(self.evidence_explicitly_requested, "evidence_explicitly_requested")
        _require_bool(self.ambiguous, "ambiguous")
        _require_str_allow_blank(self.ambiguity_note, "ambiguity_note")

    @classmethod
    def from_response_dict(
        cls,
        data: Any,
        *,
        available_keys: list,
        resolved_model: Optional[str],
        prompt_version: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> "QuestionnaireInterpretation":
        """Parse+validate a raw gateway JSON payload into a
        `QuestionnaireInterpretation`, enforcing the "AI may select only
        supplied allowlisted keys" gate (PID §10/§F): every entry in
        `selected_keys` must be a key that appears in `available_keys` -
        any invented/unknown key raises `ContractValidationError` and the
        whole interpretation is rejected (mirrors
        `InterpretationResponse.from_response_dict`'s index-matching
        discipline - see module docstring).
        """
        payload = _require_dict(data, "questionnaire interpretation response")

        try:
            intent_type = payload["intent_type"]
            requirement_scope = payload["requirement_scope"]
            requirement_summary = payload["requirement_summary"]
        except KeyError as exc:
            raise ContractValidationError(
                f"questionnaire interpretation response missing required field: {exc}"
            ) from exc

        raw_selected_keys = payload.get("selected_keys", []) or []
        if not isinstance(raw_selected_keys, list) or not all(
            isinstance(k, str) for k in raw_selected_keys
        ):
            raise ContractValidationError("'selected_keys' must be a list of strings")

        offered_key_set = {entry["key"] for entry in available_keys}
        invented = sorted(set(raw_selected_keys) - offered_key_set)
        if invented:
            raise ContractValidationError(
                "questionnaire interpretation response selected key(s) that were not "
                f"offered in this call's available_keys: {invented!r}"
            )

        evidence_explicitly_requested = payload.get("evidence_explicitly_requested", False)
        ambiguous = payload.get("ambiguous", False)
        ambiguity_note = payload.get("ambiguity_note", "") or ""

        return cls(
            intent_type=intent_type,
            requirement_scope=requirement_scope,
            requirement_summary=requirement_summary,
            selected_keys=list(raw_selected_keys),
            evidence_explicitly_requested=evidence_explicitly_requested,
            ambiguous=ambiguous,
            ambiguity_note=ambiguity_note,
            resolved_model=resolved_model,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
