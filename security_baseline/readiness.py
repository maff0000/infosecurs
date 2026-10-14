"""
M009B Increment 1 - Assurance Readiness Gate
(WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md amendment §3.1/
§3.2, Work Order §2.2/§2.9).

`evaluate_assurance_readiness(organisation) -> AssuranceReadinessResult` is
built DIRECTLY on the unmodified `entitlements.metrics.
get_security_foundations_completion` - the SAME canonical Foundations
completion calculation the Foundations workspace/Home dashboard already
render, never a second, independently-derived readiness percentage
(binding global STOP condition: "Any readiness computation not built on
get_security_foundations_completion").

The threshold is fixed at 100% (amendment §3.2) - an organisation is
"ready" only once EVERY active, counts-toward-completion
`FoundationRequirement` row is complete. The gate decision itself
(`is_ready`) is computed from the exact-count `blockers` tuple (every
requirement state that is NOT complete) being empty, never from the
already-ROUNDED `completion.percentage` integer alone - rounding could, in
principle, round a value just under 100 up to the display figure "100"
without every single item actually being complete; the exact per-item
count is the only correct gate signal, with the rounded percentage kept
purely for display/evidence purposes.

This module performs NO membership check, NO write of any kind, and
caches nothing - it is read-only and re-derives the verdict fresh on every
call, exactly like `entitlements.metrics` itself. Callers MUST have
already validated tenant membership before calling this (see
`questionnaire.upload_handler`'s pipeline-level `process_view` hook for
the mandatory membership-before-readiness ordering this Work Order
requires).
"""
from __future__ import annotations

import dataclasses

from entitlements.metrics import (
    RequirementState,
    SecurityFoundationsCompletion,
    get_security_foundations_completion,
)

# Amendment §3.2 - frozen for M009B Increment 1, not a tunable/config value.
READINESS_THRESHOLD_PERCENTAGE = 100


@dataclasses.dataclass(frozen=True)
class AssuranceReadinessResult:
    """
    What `questionnaire.upload_handler`'s pipeline-level readiness hook
    needs to decide whether to let a request reach the view, and what a
    blocker page needs to render.

    `is_ready` is the single boolean gate decision. `blockers` is the
    subset of `completion.requirement_states` that are NOT yet complete,
    already in `display_order` (the same order
    `get_foundations_requirement_states` returns), so the blocker UI can
    list exactly what remains without any second query/derivation of its
    own.
    """

    organisation_id: str
    is_ready: bool
    completion: SecurityFoundationsCompletion
    blockers: tuple[RequirementState, ...]


def evaluate_assurance_readiness(organisation) -> AssuranceReadinessResult:
    """
    The one canonical readiness decision (amendment §3.1/§3.2). Tenant-
    scoped entirely through `organisation` - this function performs no
    membership check of its own (see module docstring).
    """
    completion = get_security_foundations_completion(organisation)
    blockers = tuple(
        state for state in completion.requirement_states if not state.is_completion_complete
    )
    return AssuranceReadinessResult(
        organisation_id=str(organisation.id),
        is_ready=not blockers,
        completion=completion,
        blockers=blockers,
    )


__all__ = [
    "READINESS_THRESHOLD_PERCENTAGE",
    "AssuranceReadinessResult",
    "evaluate_assurance_readiness",
]
