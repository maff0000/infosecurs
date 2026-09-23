"""
Bounded execution + retry orchestration for AI POLICY GENERATION (M004 PID
§13, §14 - m004-2a-policy-foundation dispatch).

`generate_policy` mirrors `ai_platform.orchestration.generate_risks` /
`ai_platform.interpretation_orchestration.interpret_candidates`'s shape
exactly - one call, at most one bounded retry for a retryable failure only,
an `AIInvocationRecord` lifecycle, and the same "never partially persists"
guarantee - but over `PolicyGroundingPayload`/`PolicyGenerationResult`
rather than either existing task's own request/response shapes, and against
`AIInvocationRecord.TASK_POLICY_GENERATION`.

This module never touches `policy.PolicyDocument`/`policy.PolicyVersion` -
exactly like `ai_platform.orchestration.generate_risks` never touched
`risk_register.Risk`, and `ai_platform.interpretation_orchestration.
interpret_candidates` never touched it either. `policy.services` (a later,
separate layer in this same dispatch) is the caller that builds the
`PolicyGroundingPayload`, calls this function, and - only once this
function has returned a fully validated `PolicyGenerationResult` - creates
the `PolicyDocument`/`PolicyVersion` rows. Keeping that persistence
entirely out of this module preserves the same layering `ai_platform`
already has for the other two tasks: `ai_platform` is domain-agnostic AI
infrastructure; the domain app (`risk_register`, or here `policy`) is the
only place that imports its own domain models.
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from ai_platform.gateway import (
    DEFAULT_MODEL_ALIAS,
    GatewayError,
    PolicyGenerationGateway,
    RetryableGatewayError,
)
from ai_platform.models import AIInvocationRecord
from ai_platform.policy_contracts import PolicyGenerationResult, PolicyGroundingPayload

# Reused, not reimplemented: the same generic exception -> error_category
# mapping ai_platform.orchestration.generate_risks already uses, and
# ai_platform.interpretation_orchestration.interpret_candidates already
# reuses for the second task. It is intentionally generic (keyed on
# GatewayError subclasses, which are task-agnostic transport/auth/response
# failures) - duplicating it a third time here would be exactly the kind of
# needless second (now third) implementation the interpretation dispatch's
# own docstring already warned against, and this dispatch's instructions
# repeat that warning explicitly for policy generation.
from ai_platform.orchestration import _error_category_for


class PolicyGenerationFailed(Exception):
    """Raised by `generate_policy` when policy generation could not be
    completed. Mirrors `ai_platform.orchestration.GenerationFailed` /
    `ai_platform.interpretation_orchestration.InterpretationFailed`
    exactly.

    The associated `AIInvocationRecord` has already been marked `failed`
    with an `error_category` before this is raised - no partial policy
    data exists anywhere, no caller can observe a half-updated record, and
    (by construction, since this module never touches
    `policy.PolicyDocument`/`policy.PolicyVersion` at all) no
    `PolicyVersion` row is ever created either.
    """

    def __init__(
        self, message: str, *, invocation_record: AIInvocationRecord, cause: Optional[Exception]
    ):
        super().__init__(message)
        self.invocation_record = invocation_record
        if cause is not None:
            self.__cause__ = cause


def generate_policy(
    gateway: PolicyGenerationGateway,
    grounding: PolicyGroundingPayload,
    prompt_version: str,
    *,
    model_alias: str = DEFAULT_MODEL_ALIAS,
) -> tuple:
    """Run one policy-generation call, with at most one bounded retry for a
    retryable gateway failure, and record the outcome on a new
    `AIInvocationRecord`.

    Returns `(result, invocation_record)` on success - the caller
    (`policy.services`) needs the record's primary key to FK the created
    `PolicyVersion` row back to the generation run that produced it, the
    same "PL integration note" reason `ai_platform.orchestration.
    generate_risks` documents for the generation task.

    Tenant scoping: the invocation record's organisation is taken solely
    from `grounding.organisation_id` - the single source of truth for
    "whose data was this call made with" - mirroring `generate_risks`'s /
    `interpret_candidates`'s reasoning (PID §23: a cross-tenant fact
    appearing in an AI prompt/request is catastrophic; the record must be
    equally trustworthy about whose call it was).

    Retry policy: exactly one retry, and only for a `RetryableGatewayError`
    (timeout / connection / rate-limit) - identical to `generate_risks`/
    `interpret_candidates`. `GatewayAuthError` and `InvalidResponseError`
    (which includes any structural/section-key/duplicate/length-cap
    validation failure - see `PolicyGenerationResult.from_response_dict`)
    never retry: an identical retry is not more likely to fix a bad
    credential or produce a structurally valid response.

    No candidate-count-style cap applies here beyond what
    `PolicyGenerationResult.__post_init__` already enforces (non-empty
    sections, no duplicate section_key, total content under
    `MAX_TOTAL_CONTENT_CHARS`) - unlike `generate_risks`'s MAX_CANDIDATES
    truncation, an oversized/invalid policy response is not a "some good
    content + some overflow" situation to salvage; it is rejected outright
    by the contract layer before this function ever sees a `result` to
    return (see `ai_platform.policy_contracts.MAX_TOTAL_CONTENT_CHARS`'s
    own docstring for why).
    """
    record = AIInvocationRecord.objects.create(
        organisation_id=grounding.organisation_id,
        task_type=AIInvocationRecord.TASK_POLICY_GENERATION,
        prompt_version=prompt_version,
        model_alias=model_alias,
        input_snapshot_hash=AIInvocationRecord.hash_policy_grounding(grounding),
        status=AIInvocationRecord.STATUS_PENDING,
    )

    max_attempts = 2  # one initial attempt + at most one bounded retry
    result: Optional[PolicyGenerationResult] = None
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = gateway.generate_policy(grounding, prompt_version)
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
        raise PolicyGenerationFailed(
            f"AI policy generation failed after {attempt} attempt(s): {last_exc}",
            invocation_record=record,
            cause=last_exc,
        )

    record.status = AIInvocationRecord.STATUS_SUCCEEDED
    record.resolved_model = result.resolved_model
    record.prompt_tokens = result.prompt_tokens
    record.completion_tokens = result.completion_tokens
    record.candidate_count = len(result.sections)
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


__all__ = ["generate_policy", "PolicyGenerationFailed"]
