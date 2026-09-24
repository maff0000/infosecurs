"""
Bounded execution + retry orchestration for AI QUESTIONNAIRE INTERPRETATION
(M005 PID §14 (by extension - this module mirrors the same bounded-retry
discipline every other AI task already uses), §21 - m005-1-foundation
dispatch).

`interpret_questionnaire_question` mirrors `ai_platform.orchestration.
generate_risks` / `ai_platform.interpretation_orchestration.
interpret_candidates` / `ai_platform.policy_orchestration.generate_policy`'s
shape exactly - one call, at most one bounded retry for a retryable failure
only, an `AIInvocationRecord` lifecycle, and the same "never partially
persists" guarantee - but over
`QuestionnaireInterpretationRequest`/`QuestionnaireInterpretation` and
against `AIInvocationRecord.TASK_QUESTIONNAIRE_INTERPRETATION`.

This module never touches `questionnaire.QuestionnaireQuestion`/
`QuestionnaireResponse` - exactly like every other orchestration module
never touches its own domain's persisted rows. `questionnaire.services`
(a later layer in this same dispatch) is the only caller, and is the only
place a `QuestionnaireResponse` row is ever created.
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from ai_platform.gateway import (
    DEFAULT_MODEL_ALIAS,
    GatewayError,
    QuestionnaireInterpretationGateway,
    RetryableGatewayError,
)
from ai_platform.models import AIInvocationRecord
from ai_platform.orchestration import _error_category_for
from ai_platform.questionnaire_interpretation_contracts import (
    QuestionnaireInterpretation,
    QuestionnaireInterpretationRequest,
)


class QuestionnaireInterpretationFailed(Exception):
    """Raised by `interpret_questionnaire_question` when interpretation
    could not be completed. Mirrors `ai_platform.orchestration.
    GenerationFailed` / `ai_platform.interpretation_orchestration.
    InterpretationFailed` / `ai_platform.policy_orchestration.
    PolicyGenerationFailed` exactly.

    The associated `AIInvocationRecord` has already been marked `failed`
    with an `error_category` before this is raised - no partial
    interpretation data exists anywhere, and (by construction, since this
    module never touches `questionnaire` models at all) no
    `QuestionnaireResponse` row is ever created either.
    """

    def __init__(
        self, message: str, *, invocation_record: AIInvocationRecord, cause: Optional[Exception]
    ):
        super().__init__(message)
        self.invocation_record = invocation_record
        if cause is not None:
            self.__cause__ = cause


def interpret_questionnaire_question(
    gateway: QuestionnaireInterpretationGateway,
    request: QuestionnaireInterpretationRequest,
    prompt_version: str,
    *,
    model_alias: str = DEFAULT_MODEL_ALIAS,
) -> tuple:
    """Run one questionnaire-interpretation call, with at most one bounded
    retry for a retryable gateway failure, and record the outcome on a new
    `AIInvocationRecord`.

    Returns `(result, invocation_record)` on success - the caller
    (`questionnaire.services`) needs the record's primary key to FK the
    created `QuestionnaireResponse` row back to the interpretation run that
    produced it (same "PL integration note" reason every other task's
    orchestration module documents).

    Tenant scoping: the invocation record's organisation is taken solely
    from `request.organisation_id` (PID §23: a cross-tenant fact appearing
    in an AI prompt/request is catastrophic; the record must be equally
    trustworthy about whose call it was).

    Retry policy: exactly one retry, and only for a `RetryableGatewayError`
    - identical to every other task's orchestration module. `GatewayAuthError`
    and `InvalidResponseError` (which includes any structural/invented-key
    validation failure - see `QuestionnaireInterpretation.
    from_response_dict`) never retry.
    """
    record = AIInvocationRecord.objects.create(
        organisation_id=request.organisation_id,
        task_type=AIInvocationRecord.TASK_QUESTIONNAIRE_INTERPRETATION,
        prompt_version=prompt_version,
        model_alias=model_alias,
        input_snapshot_hash=AIInvocationRecord.hash_questionnaire_interpretation_request(request),
        status=AIInvocationRecord.STATUS_PENDING,
    )

    max_attempts = 2  # one initial attempt + at most one bounded retry
    result: Optional[QuestionnaireInterpretation] = None
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = gateway.interpret_questionnaire_question(request, prompt_version)
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
        raise QuestionnaireInterpretationFailed(
            f"AI questionnaire interpretation failed after {attempt} attempt(s): {last_exc}",
            invocation_record=record,
            cause=last_exc,
        )

    record.status = AIInvocationRecord.STATUS_SUCCEEDED
    record.resolved_model = result.resolved_model
    record.prompt_tokens = result.prompt_tokens
    record.completion_tokens = result.completion_tokens
    record.candidate_count = len(result.selected_keys)
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


__all__ = ["interpret_questionnaire_question", "QuestionnaireInterpretationFailed"]
