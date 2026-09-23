"""
Append-only security-state/evidence activity trail (M003 PID §12, §23).

This is the one durable answer to "what changed, who changed it, and when"
across the whole M003 evidence/assurance domain (PID §1). It is explicitly
history, not a second source of current truth (PID §12: "The timeline is
history, not a second source of current truth") - nothing reads an
`ActivityEvent` to decide the organisation's current security state; that
remains `security_baseline.BaselineAnswer` plus (in later, parallel
dispatches) evidence/link state.

Scope note: this dispatch (m003-1c-activity) builds the event log and its
one real emitter (`control_answer_changed`, wired in
`security_baseline.services.save_baseline_answers`). The other
`evidence_*`/`action_*` event types are defined here now, per PID §12's
fixed list, but are not emitted by anything yet - the parallel/later
dispatches that own `EvidenceItem`/`RemediationAction` will call
`activity.services.record_event` once those models exist. This app does
not build a generic/pluggable event-type registry (deliberately, per this
dispatch's instructions) - `EVENT_TYPE_CHOICES` below is the fixed,
PID-named list.

Identifier representation (PID §12 "relevant stable object/control
identifiers" - "your call on exact representation"): this model uses a
small set of nullable/blank scalar fields -
`control_key` for the baseline/control-key case (the only case this
dispatch's own emitter needs), plus a generic `related_object_type` /
`related_object_id` pair for a future evidence/action row (e.g.
`related_object_type="evidence_item"`, `related_object_id=str(some_uuid)`)
- rather than a polymorphic FK/GenericForeignKey. A GenericForeignKey would
force this app to depend on the evidence/remediation apps' concrete models
before they exist; a plain string pair keeps this app's only dependency on
`organisations`, matches `risk_register.Risk.grounding_refs`'s existing
JSONField-for-loose-references convention in spirit, and is trivial for a
later dispatch to populate without touching this model again. Small
event-specific structured detail (e.g. previous/new answer) lives in
`metadata`, a JSONField - the same convention `risk_register.Risk.
grounding_refs`/`assumptions` already uses in this codebase.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from organisations.models import Organisation


class ActivityEvent(models.Model):
    """
    One append-only activity-trail row (PID §12).

    No update/delete path exists anywhere in this app's code - `services.
    record_event` only ever calls `.objects.create(...)`, there is no admin
    edit form beyond Django admin's own superuser tooling (engineering
    visibility only, matching every other app's `admin.py` in this
    codebase - not the product UI), and no view in this app accepts a
    POST/PUT/DELETE against an existing event (PID §23: "Events are not
    editable from the product UI"). Database-level immutability (triggers,
    a read-only role, etc.) is out of scope for this dispatch - PID §23
    only requires "normal transactional PostgreSQL immutable event rows",
    i.e. no application code path that mutates or deletes one.
    """

    # PID §12's fixed event-type list. Only `control_answer_changed` has a
    # real emitter in this dispatch's own scope (see
    # `security_baseline.services.save_baseline_answers`); the rest are
    # reserved for the parallel/later evidence and remediation dispatches.
    EVENT_CONTROL_ANSWER_CHANGED = "control_answer_changed"
    EVENT_EVIDENCE_CREATED = "evidence_created"
    EVENT_EVIDENCE_LINKED = "evidence_linked"
    EVENT_EVIDENCE_UNLINKED = "evidence_unlinked"
    EVENT_EVIDENCE_SUPERSEDED = "evidence_superseded"
    EVENT_EVIDENCE_WITHDRAWN = "evidence_withdrawn"
    EVENT_ACTION_CREATED = "action_created"
    EVENT_ACTION_STATUS_CHANGED = "action_status_changed"
    EVENT_ACTION_EVIDENCE_LINKED = "action_evidence_linked"

    EVENT_TYPE_CHOICES = [
        (EVENT_CONTROL_ANSWER_CHANGED, "Control answer changed"),
        (EVENT_EVIDENCE_CREATED, "Evidence created"),
        (EVENT_EVIDENCE_LINKED, "Evidence linked"),
        (EVENT_EVIDENCE_UNLINKED, "Evidence unlinked"),
        (EVENT_EVIDENCE_SUPERSEDED, "Evidence superseded"),
        (EVENT_EVIDENCE_WITHDRAWN, "Evidence withdrawn"),
        (EVENT_ACTION_CREATED, "Action created"),
        (EVENT_ACTION_STATUS_CHANGED, "Action status changed"),
        (EVENT_ACTION_EVIDENCE_LINKED, "Action evidence linked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="activity_events"
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES)

    # Nullable: some events may be system-initiated (PID §12), though
    # nothing in this dispatch's own scope emits one without an actor.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    # See module docstring for why these are plain scalar fields rather
    # than a GenericForeignKey.
    control_key = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="The security_baseline catalogue question key this event relates to, if any.",
    )
    related_object_type = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=(
            "A generic, stable label for a related non-control object "
            "(e.g. 'evidence_item', 'remediation_action'), for later "
            "dispatches' event types. Blank for control_answer_changed."
        ),
    )
    related_object_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="The related object's stable identifier (e.g. its UUID as a string), paired with related_object_type.",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Small structured, JSON-safe event detail (e.g. previous/new "
            "answer, a note_changed boolean). Never the free-text note "
            "content itself (PID §12)."
        ),
    )

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["organisation", "-occurred_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} on {self.organisation} at {self.occurred_at:%Y-%m-%d %H:%M} UTC"

    def human_summary(self) -> str:
        """
        A short, human-readable one-line summary for the Activity timeline
        UI (PID §18). Deliberately a small per-event-type template over
        `metadata`/`control_key`, not a generic renderer - only
        `control_answer_changed` has a real producer in this dispatch's
        own scope. A later dispatch adding a real emitter for one of the
        other event types should extend this method alongside its new
        metadata shape rather than leaving it falling back to the generic
        branch below.
        """
        if self.event_type == self.EVENT_CONTROL_ANSWER_CHANGED:
            previous = self.metadata.get("previous_answer", "?")
            new = self.metadata.get("new_answer", "?")
            control = self.control_key or "a control"
            summary = f"Answer for '{control}' changed from '{previous}' to '{new}'"
            if self.metadata.get("note_changed"):
                summary += " (note also changed)"
            return summary
        return self.get_event_type_display()
