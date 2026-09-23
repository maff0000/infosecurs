"""
The single code path that writes `ActivityEvent` rows (M003 PID §12, §23).

Mirrors this codebase's existing single-writer discipline for
`security_baseline.services.save_baseline_answers` (the one code path that
writes `BaselineAnswer` rows): callers never construct `ActivityEvent`
directly, they call `record_event`.

This function's signature is the real deliverable of this dispatch -
`m003-1a-evidence` and `m003-1b-remediation` (built in parallel, in
separate worktrees) are expected to call it once their own
`EvidenceItem`/`RemediationAction` models exist, for the `evidence_*`/
`action_*` event types `ActivityEvent.EVENT_TYPE_CHOICES` already reserves.
Keep this signature stable; extend by adding new optional keyword
arguments, not by changing the meaning of an existing one.
"""
from __future__ import annotations

from typing import Optional

from activity.models import ActivityEvent
from organisations.models import Organisation

_VALID_EVENT_TYPES = {choice[0] for choice in ActivityEvent.EVENT_TYPE_CHOICES}


def record_event(
    organisation: Organisation,
    event_type: str,
    *,
    actor=None,
    control_key: str = "",
    related_object_type: str = "",
    related_object_id: str = "",
    metadata: Optional[dict] = None,
) -> ActivityEvent:
    """
    Create and return one append-only `ActivityEvent` row.

    Args:
        organisation: the tenant this event belongs to. Required.
        event_type: one of `ActivityEvent.EVENT_TYPE_CHOICES`'s keys (use
            the `ActivityEvent.EVENT_*` constants, e.g.
            `ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED`). Raises
            `ValueError` for anything else - this is a small, closed list
            (PID §12), not an open registry.
        actor: the acting `User`, or `None` for a system-initiated event
            (PID §12 - none exist in this dispatch's own scope, but the
            field is nullable for a future one).
        control_key: the `security_baseline` catalogue question key this
            event relates to, if any (e.g. for `control_answer_changed`).
        related_object_type / related_object_id: a generic, stable
            identifier pair for a related evidence/action row once those
            domains exist (e.g. `related_object_type="evidence_item"`,
            `related_object_id=str(evidence_item.id)`). Leave both blank
            when not applicable.
        metadata: a small JSON-safe dict of event-specific structured
            detail (e.g. `{"previous_answer": ..., "new_answer": ...,
            "note_changed": True}`). Never put free-text note/description
            content here (PID §12) - a boolean/enum/short label only.

    Transactional coherence (PID §17) is the caller's responsibility: call
    this from inside the same `transaction.atomic()` block as the state
    change it documents, so a rolled-back change never leaves an orphaned
    event behind. See `security_baseline.services.save_baseline_answers`
    for the reference implementation.

    No further validation is performed here beyond the `event_type` check
    above - this stays a thin, predictable write path callers can rely on;
    it does not second-guess what its callers pass.
    """
    if event_type not in _VALID_EVENT_TYPES:
        raise ValueError(f"Unknown ActivityEvent event_type: {event_type!r}")

    return ActivityEvent.objects.create(
        organisation=organisation,
        event_type=event_type,
        actor=actor,
        control_key=control_key,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        metadata=metadata if metadata is not None else {},
    )
