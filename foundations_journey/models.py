"""
M010B - Foundations guided journey: checkpoint + per-user journey
preference (docs/pids/M010B-FOUNDATIONS-GUIDED-JOURNEY.md, docs/
architecture/M010-DATA-WORKFLOW-CONTRACTS.md §1).

This app owns exactly two new models:

- `JourneyCheckpoint` - per (organisation, user, journey_code) navigation
  position. NEVER the source of truth for what was answered - that
  remains `security_baseline.models.BaselineAnswer`/`AnswerSelectionDetail`,
  reached exclusively through `security_baseline.services.
  record_structured_baseline_answer` (see `foundations_journey.services`,
  the sole module that writes this model). This model never stores raw
  answer prose or PII - only a `question_key` (already a stable,
  non-sensitive catalogue identifier, the same one `AnswerSelectionDetail`
  itself stores), a stage code, an enum state, and bookkeeping fields.
- `UserJourneyPreference` - the resume_modal/auto_open preference pair
  M010 data contract §1 asks for ("a small user-preference model/fields
  for resume_modal/auto_open ... in appropriate profile/preferences
  model"). Scoped to the USER only (no `organisation` FK at all) - this
  is "should IRENE's modal auto-open/offer a resume prompt for this
  person", a cross-organisation UI preference, not a per-organisation
  journey fact. Because it carries no FK to `Organisation`, it is
  correctly OUT of `organisations.reset_service`'s per-organisation
  reset manifest entirely - the same "zero FK to Organisation" treatment
  that document already gives `entitlements.ProductArea` (see that
  module's own docstring and `docs/evidence/M008A-RESET-DELETION-
  MANIFEST.md`'s "PRESERVE/no FK" table).

`JourneyCheckpoint.pending_task` is a real FK to `security_tasks.
SecurityTask` (`on_delete=SET_NULL`) rather than a bare UUID column -
referential integrity is free here (`security_tasks` has no dependency
back onto this app, so no import cycle is introduced), and `SET_NULL`
means a deleted/cancelled task never leaves a dangling reference on the
checkpoint.

`JourneyCheckpoint` DOES carry a direct FK to `Organisation` (`CASCADE`),
so it is a new entry in `organisations.reset_service`'s
`EXPECTED_DELETE_DIRECT_FK_MODELS` preflight set - see that module's own
M010B addendum comment and `docs/evidence/M008A-RESET-DELETION-
MANIFEST.md`'s M010B addendum section. Without that registration, the
very first Customer Zero reset run after this app's migration lands
would FAIL CLOSED (the preflight model-graph check aborts the whole
operation the moment it finds an unaccounted-for direct-FK-to-
Organisation model) - this was found and fixed in this same work package,
the same way M010A's own evidence document records finding the
equivalent gap for `security_tasks`.

This app does not duplicate `security_baseline`'s own progress/
completion logic. `current_question_key`/`checkpoint_state` are
deliberately RECONCILED (recomputed from the real `AnswerSelectionDetail`
rows) by `foundations_journey.services` on every read - never trusted as
an independent source of truth for "where is this organisation in
Stage 4" (see that module's `_compute_live_position`/`get_journey_
checkpoint` docstrings for why this also means two browser tabs can
never regress each other: the server always recomputes current position
from the real answers on every read, so there is no client-settable
"jump to question N" write to race in the first place - the only
genuinely client-triggered state transition this app exposes,
pause/resume, DOES use real CAS/`expected_version` locking, in
`update_checkpoint`).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from organisations.models import Organisation
from security_tasks.models import SecurityTask

JOURNEY_CODE_FOUNDATIONS = "foundations"


class CheckpointState(models.TextChoices):
    """M010 data contract §1's exact five values."""

    NEW = "new", "New"
    ACTIVE = "active", "Active"
    WAITING = "waiting", "Waiting"
    PAUSED = "paused", "Paused"
    JOURNEY_COMPLETE = "journey_complete", "Journey complete"


class JourneyCheckpoint(models.Model):
    """Per (organisation, user, journey_code) guided-journey navigation
    position (M010 data contract §1; M010-MASTER-ARCHITECTURE.md §5: "A
    checkpoint is scoped to organisation + user + journey"). One row per
    real-world "this person, in this organisation, is partway through
    this journey" fact - a second member of the same organisation gets
    their OWN row; they share the same underlying canonical answers
    (`security_baseline`'s own models), never a shared checkpoint.

    `journey_code` is deliberately a plain `CharField`, not restricted to
    `JOURNEY_CODE_FOUNDATIONS` by a `choices=` constraint - this package
    only ever creates/reads Foundations-journey rows, but the model
    itself is the generic shape the data contract describes, so a future
    package (higher-tier risk/policy/assurance journeys, per M010-UX-
    CUSTOMER-JOURNEYS.md §8) can reuse this exact table without a
    migration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="journey_checkpoints"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journey_checkpoints",
    )
    journey_code = models.CharField(max_length=32, default=JOURNEY_CODE_FOUNDATIONS)

    stage_code = models.CharField(max_length=32, blank=True, default="")
    current_question_key = models.CharField(max_length=64, null=True, blank=True)
    pending_task = models.ForeignKey(
        SecurityTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The last follow-up task explicitly offered for the current question, if any.",
    )
    checkpoint_state = models.CharField(
        max_length=20, choices=CheckpointState.choices, default=CheckpointState.NEW
    )
    methodology_version = models.CharField(max_length=64, blank=True, default="")
    last_domain_revision = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=(
            "A cheap, non-PII fingerprint ('<reviewed>:<still_need_confirmation>') "
            "of the real security_baseline progress this checkpoint was last "
            "reconciled against - never raw answer content."
        ),
    )
    last_interaction_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(
        default=1,
        help_text="Optimistic-concurrency version, incremented on every persisted write.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "user", "journey_code"],
                name="journeycheckpoint_unique_per_org_user_journey",
            )
        ]
        indexes = [
            models.Index(fields=["organisation", "user", "journey_code"]),
        ]

    def __str__(self):
        return (
            f"{self.journey_code} checkpoint for {self.user} @ "
            f"{self.organisation} [{self.checkpoint_state}]"
        )


class UserJourneyPreference(models.Model):
    """Cross-organisation UI preference (M010 data contract §1; M010-UX-
    CUSTOMER-JOURNEYS.md §1/§4): whether IRENE's modal should auto-open
    on a fresh login session, and whether a "Continue where you left
    off" resume prompt should be offered at all. Deliberately scoped to
    the user only, with no `organisation` FK - see this module's own
    docstring for why that keeps it out of the per-organisation reset
    manifest entirely, correctly.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journey_preference",
    )
    auto_open_enabled = models.BooleanField(default=True)
    resume_modal_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Journey preference for {self.user}"
