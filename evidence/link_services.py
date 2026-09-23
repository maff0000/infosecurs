"""
ControlEvidenceLink creation and lifecycle operations (PID §6.4). Views call
these rather than touching ControlEvidenceLink.objects.create()/delete()
directly, so the tenant-match check and the activity-event emission live in
exactly one place - the same discipline evidence/services.py already
follows for EvidenceItem.

Kept in its own module rather than folded into evidence/services.py:
`EvidenceItem` creation/lifecycle and `ControlEvidenceLink` creation/
lifecycle are two distinct pieces of the evidence domain (PID §6.1 vs
§6.4) with no shared internal state, and separating them keeps each
module's docstring/import list focused on the model it actually writes.
"""
from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
from evidence.exceptions import EvidenceValidationError
from evidence.models import ControlEvidenceLink


@transaction.atomic
def link_evidence_to_control(organisation, evidence, control_key, relationship, rationale, linked_by):
    """
    Create a `ControlEvidenceLink` and emit `EVENT_EVIDENCE_LINKED`, inside
    one transaction (PID §17 - a rolled-back link must never leave an
    orphaned activity event behind).

    Same-organisation enforcement (PID §6.4): verifies `evidence.
    organisation` matches `organisation` here, in the service layer, not
    only in form validation - so this check cannot be bypassed by any
    caller that constructs a link without going through the form (see
    `ControlEvidenceLink`'s docstring for why this can't be a model-level
    constraint instead).

    Duplicate-link behaviour (PID §19): raises `EvidenceValidationError`,
    a normal user-facing validation error, for an exact-duplicate
    (evidence, control_key, relationship) triple - see
    `ControlEvidenceLink`'s docstring for the chosen deterministic
    behaviour. This check happens before the `create()` call so the
    friendly error path is taken instead of an `IntegrityError` from the
    database-level unique constraint (defence in depth: the constraint is
    the backstop against a race, not the primary UX).
    """
    if evidence.organisation_id != organisation.id:
        raise EvidenceValidationError(
            "Cannot link evidence belonging to a different organisation."
        )
    if ControlEvidenceLink.objects.filter(
        evidence=evidence, control_key=control_key, relationship=relationship
    ).exists():
        raise EvidenceValidationError(
            "This evidence is already linked to this control with this relationship."
        )

    link = ControlEvidenceLink.objects.create(
        organisation=organisation,
        evidence=evidence,
        control_key=control_key,
        relationship=relationship,
        rationale=rationale,
        linked_by=linked_by,
    )

    record_event(
        organisation,
        ActivityEvent.EVENT_EVIDENCE_LINKED,
        actor=linked_by,
        control_key=control_key,
        related_object_type="evidence_item",
        related_object_id=str(evidence.id),
        metadata={"relationship": relationship, "rationale_provided": bool(rationale)},
    )
    return link


@transaction.atomic
def unlink_evidence_from_control(link, actor):
    """
    Delete a `ControlEvidenceLink` row and emit `EVENT_EVIDENCE_UNLINKED`,
    inside one transaction (PID §17).

    PID §19 "unlink does not delete evidence": this removes only the
    *link* row. `link.evidence` (the underlying `EvidenceItem`) is never
    touched, deleted, or mutated here.

    The event's `metadata` mirrors `link_evidence_to_control`'s shape
    (`relationship`, `rationale_provided`) so the activity timeline can
    render either event type the same way; the values are read from the
    link *before* it is deleted, since the row no longer exists afterwards.
    """
    organisation = link.organisation
    control_key = link.control_key
    evidence_id = str(link.evidence_id)
    relationship = link.relationship
    rationale_provided = bool(link.rationale)

    link.delete()

    record_event(
        organisation,
        ActivityEvent.EVENT_EVIDENCE_UNLINKED,
        actor=actor,
        control_key=control_key,
        related_object_type="evidence_item",
        related_object_id=evidence_id,
        metadata={"relationship": relationship, "rationale_provided": rationale_provided},
    )
