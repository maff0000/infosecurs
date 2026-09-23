"""
Bounded execution + retry orchestration for AI risk INTERPRETATION (M002
PID §14, applied to the M002-3c dispatch's narrower interpretation task).

`interpret_candidates` mirrors `ai_platform.orchestration.generate_risks`'s
shape exactly - one call, at most one bounded retry for a retryable
failure only, an `AIInvocationRecord` lifecycle, and the same "never
partially persists" guarantee - but over
`InterpretationRequest`/`InterpretationResponse` rather than
`GroundingPayload`/`GenerationResult`, and against
`AIInvocationRecord.TASK_RISK_INTERPRETATION` rather than
`TASK_INITIAL_RISK_GENERATION`.

This module still never touches `risk_register.Risk` - exactly like
`ai_platform.orchestration.generate_risks` never did, even back when it
fed the (now-retired) open-generation flow. `risk_register.
interpretation_service.interpret_draft_risks` is the caller that builds
the `InterpretationCandidate` list from real `Risk` rows, calls this
function, and - only once this function has returned a fully validated
`InterpretationResponse` (never a partially-matched one; see
`ai_platform.interpretation_contracts.InterpretationResponse.
from_response_dict`) - applies each outcome to the `Risk` row it already
holds a reference to. Keeping that update entirely out of this module
preserves the same layering `ai_platform.orchestration` already has:
`ai_platform` is Risk-domain-agnostic AI infrastructure; `risk_register`
is the only app that imports `risk_register.models.Risk`.
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from ai_platform.gateway import (
    DEFAULT_MODEL_ALIAS,
    GatewayError,
    RetryableGatewayError,
    RiskInterpretationGateway,
)
from ai_platform.interpretation_contracts import InterpretationRequest, InterpretationResponse
from ai_platform.models import AIInvocationRecord

# Reused, not reimplemented: the same generic exception -> error_category
# mapping ai_platform.orchestration.generate_risks already uses for the
# generation task. It is intentionally generic (keyed on GatewayError
# subclasses, which are task-agnostic transport/auth/response failures) -
# duplicating it here for the interpretation task would be exactly the
# kind of needless second implementation the M002-3c dispatch instructions
# warn against.
from ai_platform.orchestration import _error_category_for


class InterpretationFailed(Exception):
    """Raised by `interpret_candidates` when interpretation could not be
    completed. Mirrors `ai_platform.orchestration.GenerationFailed`
    exactly.

    The associated `AIInvocationRecord` has already been marked `failed`
    with an `error_category` before this is raised - no partial
    interpretation data exists anywhere, no caller can observe a
    half-updated record, and (by construction, since this module never
    touches `risk_register.Risk` at all) no `Risk` row is ever touched
    either.
    """

    def __init__(
        self, message: str, *, invocation_record: AIInvocationRecord, cause: Optional[Exception]
    ):
        super().__init__(message)
        self.invocation_record = invocation_record
        if cause is not None:
            self.__cause__ = cause


def interpret_candidates(
    gateway: RiskInterpretationGateway,
    organisation_id: str,
    candidates: list,
    prompt_version: str,
    *,
    model_alias: str = DEFAULT_MODEL_ALIAS,
) -> tuple:
    """Run one interpretation call, with at most one bounded retry for a
    retryable gateway failure, and record the outcome on a new
    `AIInvocationRecord`.

    Returns `(result, invocation_record)` on success - the caller
    (`risk_register.interpretation_service`) needs the record's primary
    key to FK each updated `Risk` row back to the interpretation run that
    produced it, exactly the same "PL integration note" reason
    `ai_platform.orchestration.generate_risks` documents for the
    generation task.

    `candidates` is plain `InterpretationCandidate` objects, not yet an
    `InterpretationRequest` - constructing the `InterpretationRequest` here
    (rather than requiring the caller to do it) means the PID's index-
    scheme validation (unique, gap-free, 1..N integers - see
    `InterpretationRequest.__post_init__`) and the PID §14 candidate-count
    cap both run automatically as part of calling this function, not as a
    separate step a caller could forget.

    Tenant scoping: the invocation record's organisation is taken solely
    from the `organisation_id` this function was called with - the single
    source of truth for "whose data was this call made with" - mirroring
    `generate_risks`'s reasoning (PID §16: a cross-tenant fact appearing in
    an AI prompt/request is a catastrophic defect; the record must be
    equally trustworthy about whose call it was).

    Retry policy: exactly one retry, and only for a `RetryableGatewayError`
    (timeout / connection / rate-limit) - identical to `generate_risks`.
    `GatewayAuthError` and `InvalidResponseError` (which includes an
    index-mismatched response - see `InterpretationResponse.
    from_response_dict`) never retry: an identical retry is not more
    likely to fix a bad credential or produce a correctly-matched index
    set.

    Unlike `generate_risks`, there is no candidate-count TRUNCATION here:
    an over-cap request is rejected outright by
    `InterpretationRequest.__post_init__` before any gateway call is even
    attempted (see that class's docstring) - the cap is a caller-contract
    violation for this task (the caller controls exactly how many
    `Risk` rows it selects to interpret), not a model-output quirk to
    tolerate the way `generate_risks`'s over-cap AI-authored candidate list
    was.
    """
    request = InterpretationRequest(organisation_id=organisation_id, candidates=candidates)

    record = AIInvocationRecord.objects.create(
        organisation_id=organisation_id,
        task_type=AIInvocationRecord.TASK_RISK_INTERPRETATION,
        prompt_version=prompt_version,
        model_alias=model_alias,
        input_snapshot_hash=AIInvocationRecord.hash_interpretation_request(request),
        status=AIInvocationRecord.STATUS_PENDING,
    )

    max_attempts = 2  # one initial attempt + at most one bounded retry
    result: Optional[InterpretationResponse] = None
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = gateway.interpret(request, prompt_version)
            last_exc = None
            break
        except RetryableGatewayError as exc:
            last_exc = exc
            if attempt < max_attempts:
                continue
            break
        except GatewayError as exc:
            # Not retryable (auth error, invalid/index-mismatched response,
            # or any other non-retryable GatewayError a gateway
            # implementation defines).
            last_exc = exc
            break

    if result is None:
        record.status = AIInvocationRecord.STATUS_FAILED
        record.error_category = _error_category_for(last_exc)
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_category", "completed_at"])
        raise InterpretationFailed(
            f"AI risk interpretation failed after {attempt} attempt(s): {last_exc}",
            invocation_record=record,
            cause=last_exc,
        )

    record.status = AIInvocationRecord.STATUS_SUCCEEDED
    record.resolved_model = result.resolved_model
    record.prompt_tokens = result.prompt_tokens
    record.completion_tokens = result.completion_tokens
    record.candidate_count = len(result.outcomes)
    # PID §0.7 third bullet: unvalidated practitioner commentary, kept
    # structurally separate from any Risk row - see AIInvocationRecord.
    # additional_observations's own field docstring.
    record.additional_observations = result.additional_observations
    record.completed_at = timezone.now()
    record.save(
        update_fields=[
            "status",
            "resolved_model",
            "prompt_tokens",
            "completion_tokens",
            "candidate_count",
            "additional_observations",
            "completed_at",
        ]
    )

    return result, record


__all__ = ["interpret_candidates", "InterpretationFailed"]
