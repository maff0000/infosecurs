"""
Remediation domain service functions (PID §6.6, §13, §17). Views call
these rather than constructing/writing an `ActionEvidenceLink` directly, so
the same-organisation check and the event emission stay in exactly one
place - mirroring `evidence.services`/`security_baseline.services`'
single-writer discipline in this codebase.
"""
from __future__ import annotations

from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
from remediation.models import ActionEvidenceLink


class RemediationServiceError(Exception):
    """
    Raised when a remediation service function is asked to do something it
    must refuse - currently just the cross-tenant attach guard below. A
    plain exception, not a form-validation error: this is a defence-in-depth
    check a service function must enforce for itself, not only trust to the
    view/form layer (PID §16).
    """


@transaction.atomic
def attach_evidence_to_action(*, organisation, action, evidence, linked_by):
    """
    Attach an existing `EvidenceItem` to a `RemediationAction` (PID §6.6).

    Verifies both `action.organisation` and `evidence.organisation` equal
    `organisation` *before* writing anything - a mismatch on either side
    raises `RemediationServiceError` and nothing is persisted (PID §16
    tenant isolation, PID §17: no orphaned `ActivityEvent` for a change
    that did not happen).

    Attach-only: this function has no unlink/detach counterpart by design
    for M003 V1 (PID §19's Actions mechanical-test list requires only
    "evidence can attach").

    Never touches `RemediationAction.status`, `risk_register.Risk.status`
    or any `security_baseline.BaselineAnswer` - this function writes only
    the new `ActionEvidenceLink` row and its `ActivityEvent`.
    """
    if action.organisation_id != organisation.id:
        raise RemediationServiceError(
            "Cannot attach evidence to an action belonging to a different organisation."
        )
    if evidence.organisation_id != organisation.id:
        raise RemediationServiceError(
            "Cannot attach evidence belonging to a different organisation to this action."
        )

    link = ActionEvidenceLink.objects.create(
        organisation=organisation,
        action=action,
        evidence=evidence,
        linked_by=linked_by,
    )

    record_event(
        organisation,
        ActivityEvent.EVENT_ACTION_EVIDENCE_LINKED,
        actor=linked_by,
        control_key=action.control_key,
        related_object_type="remediation_action",
        related_object_id=str(action.id),
        metadata={"evidence_id": str(evidence.id)},
    )

    return link
