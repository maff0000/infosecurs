"""
Bounded execution + retry orchestration for AI QUESTIONNAIRE ANSWER
DRAFTING (M005 PID §14 (by extension), §21 - m005-1-foundation dispatch).

`draft_questionnaire_answer` mirrors `ai_platform.
questionnaire_interpretation_orchestration.interpret_questionnaire_question`
(and every other task's own orchestration module) exactly - one call, at
most one bounded retry for a retryable failure only, an
`AIInvocationRecord` lifecycle, and the same "never partially persists"
guarantee - but over
`QuestionnaireDraftingRequest`/`QuestionnaireDraft` and against
`AIInvocationRecord.TASK_QUESTIONNAIRE_DRAFTING`.

This module never touches `questionnaire.QuestionnaireQuestion`/
`QuestionnaireResponse` - `questionnaire.services` is the only caller and
the only place a `QuestionnaireResponse` row is ever created.
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from ai_platform.gateway import (
    DEFAULT_MODEL_ALIAS,
    GatewayError,
    QuestionnaireDraftingGateway,
    RetryableGatewayError,
)
from ai_platform.models import AIInvocationRecord
from ai_platform.orchestration import _error_category_for
from ai_platform.questionnaire_drafting_contracts import (
    QuestionnaireDraft,
    QuestionnaireDraftingRequest,
)


class QuestionnaireDraftingFailed(Exception):
    """Raised by `draft_questionnaire_answer` when drafting could not be
    completed. Mirrors `QuestionnaireInterpretationFailed` and every other
    task's own `*Failed` exception exactly.

    The associated `AIInvocationRecord` has already been marked `failed`
    with an `error_category` before this is raised - no partial draft data
    exists anywhere, and no `QuestionnaireResponse` row is ever created by
    this module (it never touches `questionnaire` models at all).
    """

    def __init__(
        self, message: str, *, invocation_record: AIInvocationRecord, cause: Optional[Exception]
    ):
        super().__init__(message)
        self.invocation_record = invocation_record
        if cause is not None:
            self.__cause__ = cause


def draft_questionnaire_answer(
    gateway: QuestionnaireDraftingGateway,
    request: QuestionnaireDraftingRequest,
    prompt_version: str,
    *,
    model_alias: str = DEFAULT_MODEL_ALIAS,
) -> tuple:
    """Run one questionnaire-answer-drafting call, with at most one bounded
    retry for a retryable gateway failure, and record the outcome on a new
    `AIInvocationRecord`.

    Returns `(result, invocation_record)` on success.

    Tenant scoping: the invocation record's organisation is taken solely
    from `request.organisation_id` (PID §23).

    Retry policy: identical to every other task's orchestration module -
    exactly one retry, only for `RetryableGatewayError`.
    """
    record = AIInvocationRecord.objects.create(
        organisation_id=request.organisation_id,
        task_type=AIInvocationRecord.TASK_QUESTIONNAIRE_DRAFTING,
        prompt_version=prompt_version,
        model_alias=model_alias,
        input_snapshot_hash=AIInvocationRecord.hash_questionnaire_drafting_request(request),
        status=AIInvocationRecord.STATUS_PENDING,
    )

    max_attempts = 2  # one initial attempt + at most one bounded retry
    result: Optional[QuestionnaireDraft] = None
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = gateway.draft_questionnaire_answer(request, prompt_version)
            last_exc = None
            break
        except RetryableGatewayError as exc:
            last_exc = exc
            if attempt < max_attempts:
                continue
            break
        except GatewayError as exc:
            last_exc = exc
            break

    if result is None:
        record.status = AIInvocationRecord.STATUS_FAILED
        record.error_category = _error_category_for(last_exc)
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_category", "completed_at"])
        raise QuestionnaireDraftingFailed(
            f"AI questionnaire answer drafting failed after {attempt} attempt(s): {last_exc}",
            invocation_record=record,
            cause=last_exc,
        )

    record.status = AIInvocationRecord.STATUS_SUCCEEDED
    record.resolved_model = result.resolved_model
    record.prompt_tokens = result.prompt_tokens
    record.completion_tokens = result.completion_tokens
    record.candidate_count = len(result.grounding_handles_used)
    record.completed_at = timezone.now()
    record.save(
        update_fields=[
            "status",
            "resolved_model",
            "prompt_tokens",
            "completion_tokens",
            "candidate_count",
            "completed_at",
        ]
    )

    return result, record


__all__ = ["draft_questionnaire_answer", "QuestionnaireDraftingFailed"]
