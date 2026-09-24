"""
Structured contracts for the AI QUESTIONNAIRE-ANSWER-DRAFTING task (M005 PID
§13, §20 - m005-1-foundation dispatch).

Sibling module to `ai_platform.questionnaire_interpretation_contracts` - see
that module's docstring for the shared "why this is a new, narrower
contract module rather than a bolt-on to an existing one" reasoning
(identical here: a different request/response shape doing a materially
different job).

== The architectural rule this module exists to enforce (PID §2, §13) ==
"The application tells the model the outcome. The model cannot upgrade it."
`QuestionnaireDraftingRequest.outcome` is supplied BY THE CALLER as a fixed
instruction (already derived by `questionnaire.outcome.derive_outcome`,
deterministic application code) - it is never something this task's AI
response can set or change. `QuestionnaireDraft` (the response) carries no
outcome field at all; there is nothing in this contract's output shape an
AI response could even populate to attempt an upgrade. The SECOND safety
boundary PID §20 describes ("The application-owned outcome provides a
second safety boundary: drafting output cannot upgrade a GAP to SUPPORTED")
is enforced structurally here, at the type level, not merely by prompt
instruction (the prompt module's own instruction is the first, defence-in-
depth layer - see `ai_platform.prompts.questionnaire_drafting_v1`).

== `grounding_handles_used` subset validation ==
Mirrors `QuestionnaireInterpretation.from_response_dict`'s "AI may only
reference what it was actually given" discipline, applied to a different
question: not "which canonical keys may the model SELECT" (that was the
interpretation task's contract), but "which of the keys the interpretation
ALREADY selected did the model claim to reference while drafting". Every
entry in `grounding_handles_used` must be a member of the
`interpretation.selected_keys` this drafting call was given - inventing a
reference to a key that was never selected (and therefore never in the
grounding snapshot the model was shown) is rejected the same way an
invented `selected_keys` entry is rejected upstream: `ContractValidationError`,
not a soft warning.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from ai_platform.contracts import (
    ContractValidationError,
    _require_dict,
    _require_str,
    _require_str_allow_blank,
)
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation

# The four application-derived outcomes this call may be told (PID §12).
# Never chosen by the AI response - only ever supplied inbound, as a fixed
# instruction, by the caller (questionnaire.services).
OUTCOME_SUPPORTED = "SUPPORTED"
OUTCOME_CONFIRM = "CONFIRM"
OUTCOME_GAP = "GAP"
OUTCOME_NOT_APPLICABLE = "NOT_APPLICABLE"

ALLOWED_OUTCOMES = [OUTCOME_SUPPORTED, OUTCOME_CONFIRM, OUTCOME_GAP, OUTCOME_NOT_APPLICABLE]
_ALLOWED_OUTCOME_SET = frozenset(ALLOWED_OUTCOMES)


@dataclasses.dataclass(frozen=True)
class QuestionnaireDraftingRequest:
    """What goes INTO one questionnaire-answer-drafting call (PID §13).

    `outcome` is APPLICATION-DERIVED (see module docstring) - a fixed
    instruction, never a choice offered to the model. `interpretation` is
    the already-validated `QuestionnaireInterpretation` from the prior call
    (never re-derived here). `grounding_snapshot` is the bounded grounding
    facts for `interpretation.selected_keys`
    (`questionnaire.grounding.build_questionnaire_grounding_snapshot`'s
    output) - inert JSON data, same untrusted-question framing as the
    interpretation task's own request (the raw question is carried again
    here, since the drafting prompt also needs it for tone/context - see
    `ai_platform.prompts.questionnaire_drafting_v1`).
    """

    organisation_id: str
    question_text: str
    interpretation: QuestionnaireInterpretation
    outcome: str
    grounding_snapshot: dict

    def __post_init__(self):
        _require_str(self.organisation_id, "organisation_id")
        _require_str(self.question_text, "question_text")
        if not isinstance(self.interpretation, QuestionnaireInterpretation):
            raise ContractValidationError(
                "'interpretation' must be a QuestionnaireInterpretation"
            )
        if self.outcome not in _ALLOWED_OUTCOME_SET:
            raise ContractValidationError(
                f"'outcome' must be one of {ALLOWED_OUTCOMES!r}, got {self.outcome!r}"
            )
        _require_dict(self.grounding_snapshot, "grounding_snapshot")


@dataclasses.dataclass(frozen=True)
class QuestionnaireDraft:
    """What comes OUT of one questionnaire-answer-drafting call (PID §13).

    Deliberately carries no outcome field of any kind - see module
    docstring. `grounding_handles_used` is validated as a subset of
    `interpretation.selected_keys` in `from_response_dict` below - see
    module docstring for why.
    """

    answer_text: str
    answer_summary: str  # may be ""
    grounding_handles_used: list  # list[str], subset of interpretation.selected_keys
    customer_review_note: str  # may be ""
    resolved_model: Optional[str] = None
    prompt_version: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def __post_init__(self):
        _require_str(self.answer_text, "answer_text")
        _require_str_allow_blank(self.answer_summary, "answer_summary")
        if not isinstance(self.grounding_handles_used, list) or not all(
            isinstance(h, str) for h in self.grounding_handles_used
        ):
            raise ContractValidationError("'grounding_handles_used' must be a list of strings")
        _require_str_allow_blank(self.customer_review_note, "customer_review_note")

    @classmethod
    def from_response_dict(
        cls,
        data: Any,
        *,
        selected_keys: list,
        resolved_model: Optional[str],
        prompt_version: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> "QuestionnaireDraft":
        """Parse+validate a raw gateway JSON payload into a
        `QuestionnaireDraft`, enforcing that every `grounding_handles_used`
        entry is a member of `selected_keys` (the interpretation's own
        already-validated selection) - any reference to a key that was
        never selected (and so never appeared in the grounding snapshot the
        model was shown) raises `ContractValidationError`.
        """
        payload = _require_dict(data, "questionnaire drafting response")

        answer_text = payload.get("answer_text")
        if answer_text is None:
            raise ContractValidationError("questionnaire drafting response missing 'answer_text'")

        answer_summary = payload.get("answer_summary", "") or ""
        customer_review_note = payload.get("customer_review_note", "") or ""

        raw_handles = payload.get("grounding_handles_used", []) or []
        if not isinstance(raw_handles, list) or not all(isinstance(h, str) for h in raw_handles):
            raise ContractValidationError("'grounding_handles_used' must be a list of strings")

        selected_key_set = set(selected_keys)
        invented = sorted(set(raw_handles) - selected_key_set)
        if invented:
            raise ContractValidationError(
                "questionnaire drafting response referenced grounding handle(s) that "
                f"were not among the interpretation's selected_keys: {invented!r}"
            )

        return cls(
            answer_text=answer_text,
            answer_summary=answer_summary,
            grounding_handles_used=list(raw_handles),
            customer_review_note=customer_review_note,
            resolved_model=resolved_model,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
