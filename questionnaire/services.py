"""
Minimal end-to-end questionnaire-assurance generation pipeline (M005 PID §4,
§22 - m005-1-foundation dispatch).

`generate_questionnaire_response` is the single entrypoint the view layer
calls, wiring together every piece this dispatch built:

1. interpret the raw question against the full `questionnaire.catalogue`
   (bounded retry, `AIInvocationRecord` - `ai_platform.
   questionnaire_interpretation_orchestration.
   interpret_questionnaire_question`);
2. assemble the bounded grounding snapshot for the validated
   `selected_keys` (`questionnaire.grounding.
   build_questionnaire_grounding_snapshot`);
3. derive the application-owned outcome (`questionnaire.outcome.
   derive_outcome`) - deterministic, no AI call;
4. draft a concise answer constrained by that FIXED outcome (bounded
   retry, `AIInvocationRecord` - `ai_platform.
   questionnaire_drafting_orchestration.draft_questionnaire_answer`);
5. persist exactly one new `QuestionnaireResponse(status=draft, ...)` in a
   single atomic block.

Both AI calls happen OUTSIDE `transaction.atomic()` (they are external HTTP
calls, and each already owns its own `AIInvocationRecord` lifecycle/commit
independently of this function - identical discipline to
`policy.services.generate_policy_draft`/`risk_register.
interpretation_service.interpret_draft_risks`). Only the final persistence
step is wrapped, so a `QuestionnaireResponse` write can never partially
apply.

== Failure-mode scope (PID §22) - two deliberate simplifications, recorded
here explicitly rather than silently implemented ==

**Interpretation unavailable/invalid** (PID §22 "Save raw question; show
recoverable failure; do not fabricate mapping/outcome"): this function
never creates the `QuestionnaireQuestion` itself - the caller
(`questionnaire.views.questionnaire_analyse`) creates and persists that row
FIRST, independently of whether generation subsequently succeeds, so a
failed interpretation still leaves the raw question saved. On
`QuestionnaireInterpretationFailed`, this function creates no
`QuestionnaireResponse` at all and lets the exception propagate - the view
is responsible for showing a recoverable-failure message.

**Drafting unavailable** (PID §22 "Preserve interpretation/outcome/
grounding and allow retry"): PID's ideal behaviour is a genuine two-phase
resume that persists the interpretation/outcome/grounding even if drafting
subsequently fails, so a retry does not have to re-run interpretation. For
this dispatch's minimal scope, `generate_questionnaire_response` does NOT
do this - on `QuestionnaireDraftingFailed`, it persists nothing at all (no
`QuestionnaireResponse` row, interpretation/outcome/grounding included) and
lets the exception propagate; a caller must retry the WHOLE
`generate_questionnaire_response` call, which re-runs interpretation too.
This is a deliberate, documented scope simplification (per the dispatch's
own explicit instruction) - not an accidental gap. A later dispatch may
optimise this into a genuine two-phase resume if real product usage shows
the extra interpretation re-run cost matters.
"""
from __future__ import annotations

import hashlib
import json

from django.db import transaction

from ai_platform.gateway import LiteLLMGateway, QuestionnaireDraftingGateway, QuestionnaireInterpretationGateway
from ai_platform.prompts.questionnaire_drafting_v1 import PROMPT_VERSION as DRAFTING_PROMPT_VERSION
from ai_platform.prompts.questionnaire_interpretation_v1 import (
    PROMPT_VERSION as INTERPRETATION_PROMPT_VERSION,
)
from ai_platform.questionnaire_drafting_contracts import QuestionnaireDraftingRequest
from ai_platform.questionnaire_drafting_orchestration import draft_questionnaire_answer
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretationRequest
from ai_platform.questionnaire_interpretation_orchestration import (
    interpret_questionnaire_question,
)

from questionnaire.catalogue import CATALOGUE
from questionnaire.grounding import build_questionnaire_grounding_snapshot
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.outcome import derive_outcome


def _hash_grounding_snapshot(grounding_snapshot: dict) -> str:
    """SHA-256 hex digest of the grounding snapshot, mirroring
    `AIInvocationRecord.hash_grounding`/`hash_policy_grounding`'s own
    canonical-JSON convention - an immutable fingerprint of exactly what
    this response's answer was grounded in, without needing a second copy
    of the same discipline duplicated as a model method (this hash is
    stored on `QuestionnaireResponse.grounding_snapshot_hash`, not on an
    `AIInvocationRecord`, since the grounding snapshot itself is assembled
    by deterministic application code, not returned by either AI call)."""
    canonical = json.dumps(grounding_snapshot, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def _persist_response(
    organisation,
    question: QuestionnaireQuestion,
    *,
    interpretation,
    interpretation_record,
    outcome: str,
    outcome_warnings: list,
    grounding_snapshot: dict,
    draft,
    drafting_record,
    actor,
) -> QuestionnaireResponse:
    review_warnings = list(outcome_warnings)
    if draft.customer_review_note:
        review_warnings.append(draft.customer_review_note)

    return QuestionnaireResponse.objects.create(
        organisation=organisation,
        question=question,
        status=QuestionnaireResponse.STATUS_DRAFT,
        interpreted_requirement_summary=interpretation.requirement_summary,
        intent_type=interpretation.intent_type,
        requirement_scope=interpretation.requirement_scope,
        selected_keys=list(interpretation.selected_keys),
        evidence_explicitly_requested=interpretation.evidence_explicitly_requested,
        outcome=outcome,
        ai_draft_text=draft.answer_text,
        current_answer_text=draft.answer_text,
        review_warnings=review_warnings,
        grounding_snapshot=grounding_snapshot,
        grounding_snapshot_hash=_hash_grounding_snapshot(grounding_snapshot),
        interpretation_prompt_version=interpretation.prompt_version,
        drafting_prompt_version=draft.prompt_version,
        interpretation_invocation_record=interpretation_record,
        drafting_invocation_record=drafting_record,
        created_by=actor,
    )


def generate_questionnaire_response(
    organisation,
    question: QuestionnaireQuestion,
    *,
    actor,
    interpretation_gateway: QuestionnaireInterpretationGateway = None,
    drafting_gateway: QuestionnaireDraftingGateway = None,
) -> QuestionnaireResponse:
    """Run one full interpret -> ground -> derive-outcome -> draft ->
    persist pipeline for `question` (which must already exist and belong to
    `organisation` - see module docstring on why this function never
    creates the `QuestionnaireQuestion` itself).

    Raises `ai_platform.questionnaire_interpretation_orchestration.
    QuestionnaireInterpretationFailed` or `ai_platform.
    questionnaire_drafting_orchestration.QuestionnaireDraftingFailed` on
    failure - see module docstring for exactly what is (and is not)
    persisted in each case.

    `interpretation_gateway`/`drafting_gateway` default to a real
    `LiteLLMGateway()` each (constructed lazily inside this call, not at
    import time - PID §14/§21: generation happens only on an explicit user
    action, mirroring every other AI-adapter service's identical default).
    Tests pass `ai_platform.testing.FakeQuestionnaireInterpretationGateway`/
    `FakeQuestionnaireDraftingGateway` explicitly. A single `LiteLLMGateway`
    instance implements both ABCs, so in production the same real gateway
    object may be passed for both, or two independent ones - this function
    does not care which.
    """
    interpretation_gateway = (
        interpretation_gateway if interpretation_gateway is not None else LiteLLMGateway()
    )
    drafting_gateway = drafting_gateway if drafting_gateway is not None else LiteLLMGateway()

    interpretation_request = QuestionnaireInterpretationRequest(
        organisation_id=str(organisation.pk),
        question_text=question.question_text,
        source_label=question.source_label,
        available_keys=CATALOGUE,
    )
    interpretation, interpretation_record = interpret_questionnaire_question(
        interpretation_gateway, interpretation_request, INTERPRETATION_PROMPT_VERSION
    )

    grounding_snapshot = build_questionnaire_grounding_snapshot(
        organisation, interpretation.selected_keys
    )
    outcome, outcome_warnings = derive_outcome(interpretation, grounding_snapshot)

    drafting_request = QuestionnaireDraftingRequest(
        organisation_id=str(organisation.pk),
        question_text=question.question_text,
        interpretation=interpretation,
        outcome=outcome,
        grounding_snapshot=grounding_snapshot,
    )
    draft, drafting_record = draft_questionnaire_answer(
        drafting_gateway, drafting_request, DRAFTING_PROMPT_VERSION
    )

    return _persist_response(
        organisation,
        question,
        interpretation=interpretation,
        interpretation_record=interpretation_record,
        outcome=outcome,
        outcome_warnings=outcome_warnings,
        grounding_snapshot=grounding_snapshot,
        draft=draft,
        drafting_record=drafting_record,
        actor=actor,
    )


__all__ = ["generate_questionnaire_response"]
