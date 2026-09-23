"""
Bounded execution + retry orchestration for AI risk generation (M002 PID
§14).

`generate_risks` is the single entrypoint the Risk-domain module (a later,
separate Engineer dispatch) should call. It owns:

- the `AIInvocationRecord` lifecycle (created `pending` up front, updated
  to `succeeded`/`failed` at the end - PID §13);
- the "at most one bounded retry, retryable failures only" policy
  (PID §14);
- the `MAX_CANDIDATES` execution-safety cap;
- the guarantee that a failed/invalid generation never returns, and never
  leaves persisted, anything resembling a partially-valid result
  (PID §9.3, §14) - the caller either gets back a fully validated
  `GenerationResult`, or a `GenerationFailed` exception.

Generation happens only on an explicit call to this function - there is no
autonomous/background invocation here (PID §14). A gateway outage leaves
existing baseline/assets/confirmed-risk state completely untouched, because
this module never touches Risk-domain tables at all.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from django.utils import timezone

from ai_platform.contracts import GenerationResult, GroundingPayload, MAX_CANDIDATES
from ai_platform.gateway import (
    DEFAULT_MODEL_ALIAS,
    GatewayAuthError,
    GatewayError,
    GatewayRateLimitError,
    GatewayTimeoutError,
    InvalidResponseError,
    RetryableGatewayError,
    RiskGenerationGateway,
)
from ai_platform.models import AIInvocationRecord

# Ordered most-specific-first: the first matching exception type wins.
_ERROR_CATEGORY_BY_EXCEPTION = (
    (GatewayTimeoutError, AIInvocationRecord.ERROR_TIMEOUT),
    (GatewayRateLimitError, AIInvocationRecord.ERROR_RATE_LIMIT),
    (GatewayAuthError, AIInvocationRecord.ERROR_AUTH),
    (InvalidResponseError, AIInvocationRecord.ERROR_INVALID_RESPONSE),
    # Any other retryable failure (e.g. GatewayConnectionError) falls back
    # to the generic connection-error category.
    (RetryableGatewayError, AIInvocationRecord.ERROR_CONNECTION),
)


def _error_category_for(exc: Optional[Exception]) -> str:
    if exc is None:
        return AIInvocationRecord.ERROR_UNKNOWN
    for exc_type, category in _ERROR_CATEGORY_BY_EXCEPTION:
        if isinstance(exc, exc_type):
            return category
    return AIInvocationRecord.ERROR_UNKNOWN


class GenerationFailed(Exception):
    """Raised by `generate_risks` when generation could not be completed.

    The associated `AIInvocationRecord` has already been marked `failed`
    with an `error_category` before this is raised - no partial risk data
    exists anywhere, and no caller can observe a half-updated record.
    """

    def __init__(self, message: str, *, invocation_record: AIInvocationRecord, cause: Optional[Exception]):
        super().__init__(message)
        self.invocation_record = invocation_record
        if cause is not None:
            self.__cause__ = cause


def generate_risks(
    gateway: RiskGenerationGateway,
    grounding: GroundingPayload,
    prompt_version: str,
    *,
    model_alias: str = DEFAULT_MODEL_ALIAS,
) -> tuple[GenerationResult, AIInvocationRecord]:
    """Run one generation, with at most one bounded retry for a retryable
    gateway failure, and record the outcome on a new `AIInvocationRecord`.

    Returns `(result, invocation_record)` on success — the caller (the
    Risk-domain module) needs the record's primary key to FK each persisted
    `Risk` row back to the generation that produced it, without requerying
    for "the most recent record for this organisation" (PL integration
    note, added during M002 Phase-1 integration).

    Tenant scoping: the invocation record's organisation is taken solely
    from `grounding.organisation_id` - the single source of truth for
    "whose data was this call made with" - never from a separate caller-
    supplied organisation, so there is no way for a caller to mismatch the
    record's tenant against the tenant whose facts were actually sent
    (PID §16: a cross-tenant fact appearing in an AI prompt/request is a
    catastrophic defect; the record must be equally trustworthy about whose
    call it was).

    Retry policy: exactly one retry, and only for a `RetryableGatewayError`
    (timeout / connection / rate-limit). `GatewayAuthError` and
    `InvalidResponseError` never retry (PID §14: "no retry for
    schema/policy-invalid output"; an identical bad credential will not
    succeed on retry either).

    Candidate cap: PID §14 requires "maximum 8 proposed risks per
    generation" and leaves the truncate-vs-reject choice to the Engineer,
    documented. This function TRUNCATES rather than rejects: every
    surviving candidate individually passed full structured validation, so
    the cap is an execution-safety bound on an otherwise-valid response,
    not a data-quality problem: rejecting the whole generation would throw
    away real, usable, validated signal over a limit the model exceeded,
    not the tenant.
    """
    record = AIInvocationRecord.objects.create(
        organisation_id=grounding.organisation_id,
        task_type=AIInvocationRecord.TASK_INITIAL_RISK_GENERATION,
        prompt_version=prompt_version,
        model_alias=model_alias,
        input_snapshot_hash=AIInvocationRecord.hash_grounding(grounding),
        status=AIInvocationRecord.STATUS_PENDING,
    )

    max_attempts = 2  # one initial attempt + at most one bounded retry
    result: Optional[GenerationResult] = None
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = gateway.generate(grounding, prompt_version)
            last_exc = None
            break
        except RetryableGatewayError as exc:
            last_exc = exc
            if attempt < max_attempts:
                continue
            break
        except GatewayError as exc:
            # Not retryable (auth error, invalid response, or any other
            # non-retryable GatewayError a gateway implementation defines).
            last_exc = exc
            break

    if result is None:
        record.status = AIInvocationRecord.STATUS_FAILED
        record.error_category = _error_category_for(last_exc)
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_category", "completed_at"])
        raise GenerationFailed(
            f"AI risk generation failed after {attempt} attempt(s): {last_exc}",
            invocation_record=record,
            cause=last_exc,
        )

    if len(result.candidates) > MAX_CANDIDATES:
        result = dataclasses.replace(result, candidates=result.candidates[:MAX_CANDIDATES])

    record.status = AIInvocationRecord.STATUS_SUCCEEDED
    record.resolved_model = result.resolved_model
    record.prompt_tokens = result.prompt_tokens
    record.completion_tokens = result.completion_tokens
    record.candidate_count = len(result.candidates)
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
