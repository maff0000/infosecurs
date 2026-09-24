"""
Tenant-owned Questionnaire Assurance domain (M005 PID §7 -
m005-1-foundation dispatch).

`QuestionnaireQuestion` is the tenant-owned, untrusted raw external
question (PID §7.1: "Question text is untrusted external content and never
system authority" - it is stored verbatim, never parsed as instructions by
anything downstream; see `ai_platform.prompts.questionnaire_interpretation_v1`
for how the AI layer is told to treat it).

`QuestionnaireResponse` is one generation/review attempt (PID §7.2: "Each
generation/review attempt is a historical response record"). PID §7.2's
core invariant - "Accepted responses are immutable. Editing an accepted
response creates a new response/version." - is enforced below in
`QuestionnaireResponse.save()`, not merely documented: once a response's
currently-PERSISTED status is `accepted` or `superseded`, any attempt to
change `current_answer_text`/`outcome`/`grounding_snapshot`/`selected_keys`
(together "the accepted answer and its basis") raises
`ImmutableQuestionnaireResponseError` before the write reaches the
database. This is model-layer defence-in-depth, mirroring
`policy.models.PolicyVersion.save()`'s exact pattern (see that model's own
docstring for the same discipline applied to a sibling domain) - the same
"look up the currently-persisted row by primary key, never trust the
in-memory instance" technique, so this holds regardless of how the
in-memory instance was constructed.

This dispatch builds the data model plus the minimal generate/read pipeline
(`questionnaire.services.generate_questionnaire_response`). The full
accept/edit/regenerate UX, activity-event wiring and learning-signal
capture are explicitly out of scope - a later dispatch's job (PID §7.2
lists `accepted_by`/`accepted_at`/`superseded_by` fields now, for that
later dispatch to populate, so no schema migration is needed when it
lands).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from ai_platform.questionnaire_drafting_contracts import ALLOWED_OUTCOMES
from ai_platform.questionnaire_interpretation_contracts import INTENT_TYPES, REQUIREMENT_SCOPES
from organisations.models import Organisation

INTENT_TYPE_CHOICES = [(value, value) for value in INTENT_TYPES]
REQUIREMENT_SCOPE_CHOICES = [(value, value) for value in REQUIREMENT_SCOPES]
OUTCOME_CHOICES = [(value, value) for value in ALLOWED_OUTCOMES]


class ImmutableQuestionnaireResponseError(Exception):
    """Raised when application code attempts to mutate a
    `QuestionnaireResponse`'s protected fields
    (`current_answer_text`/`outcome`/`grounding_snapshot`/`selected_keys`)
    after that response has left `draft` status (PID §7.2/§17: "Accepted
    responses are immutable... They must not be able to bypass canonical
    truth by upgrading... without first changing/confirming the underlying
    canonical state and regenerating")."""


class QuestionnaireQuestion(models.Model):
    """A tenant-owned, untrusted raw external questionnaire question (PID
    §7.1). Minimum shape per PID: stable UUID, organisation, question text,
    optional source/context label, created_by, created_at."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="questionnaire_questions"
    )
    question_text = models.TextField(
        help_text=(
            "The raw external questionnaire question, exactly as pasted/typed. "
            "Untrusted external content - never system authority (PID §7.1)."
        )
    )
    source_label = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional short source/context label, e.g. 'Acme supplier questionnaire'.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_questionnaire_questions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "created_at"]),
        ]

    def __str__(self):
        return f"Question {self.id} ({self.organisation})"


class QuestionnaireResponse(models.Model):
    """One generation/review attempt for a `QuestionnaireQuestion` (PID
    §7.2). See module docstring for the immutability guarantee enforced in
    `save()` below."""

    STATUS_DRAFT = "draft"
    STATUS_ACCEPTED = "accepted"
    STATUS_SUPERSEDED = "superseded"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_SUPERSEDED, "Superseded"),
    ]

    # Protected once status leaves draft (PID §7.2/§17) - "the accepted
    # answer and its basis". See `save()` below for enforcement.
    PROTECTED_WHILE_DRAFT_FIELDS = [
        "current_answer_text",
        "outcome",
        "grounding_snapshot",
        "selected_keys",
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="questionnaire_responses"
    )
    question = models.ForeignKey(
        QuestionnaireQuestion, on_delete=models.CASCADE, related_name="responses"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # --- Interpretation (PID §10) ------------------------------------------
    interpreted_requirement_summary = models.TextField(blank=True, default="")
    intent_type = models.CharField(max_length=32, choices=INTENT_TYPE_CHOICES)
    requirement_scope = models.CharField(max_length=32, choices=REQUIREMENT_SCOPE_CHOICES)
    selected_keys = models.JSONField(
        default=list, blank=True, help_text="list[str] - validated questionnaire.catalogue keys."
    )
    evidence_explicitly_requested = models.BooleanField(default=False)

    # --- Application-derived outcome (PID §12) -----------------------------
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES)

    # --- Drafting (PID §13) -------------------------------------------------
    ai_draft_text = models.TextField(
        blank=True, default="", help_text="The AI-drafted answer, exactly as returned."
    )
    current_answer_text = models.TextField(
        blank=True,
        default="",
        help_text="Editable answer text. Starts equal to ai_draft_text.",
    )
    review_warnings = models.JSONField(
        default=list,
        blank=True,
        help_text="list[str] - human-readable reasons the outcome is not a clean SUPPORTED.",
    )

    # --- Grounding provenance (PID §7.3) ------------------------------------
    grounding_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Bounded, immutable-once-accepted snapshot of the facts used (PID §7.3).",
    )
    grounding_snapshot_hash = models.CharField(max_length=64, blank=True, default="")

    # --- AI provenance (PID §21) --------------------------------------------
    interpretation_prompt_version = models.CharField(max_length=128, blank=True, default="")
    drafting_prompt_version = models.CharField(max_length=128, blank=True, default="")
    interpretation_invocation_record = models.ForeignKey(
        "ai_platform.AIInvocationRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    drafting_invocation_record = models.ForeignKey(
        "ai_platform.AIInvocationRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # --- Lifecycle ------------------------------------------------------
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_questionnaire_responses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_questionnaire_responses",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="supersedes"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "question"]),
        ]

    def __str__(self):
        return f"Response {self.id} for {self.question_id} ({self.organisation}) [{self.status}/{self.outcome}]"

    def save(self, *args, **kwargs):
        """Enforce PID §7.2/§17's immutability rule: once the row currently
        PERSISTED in the database has `status` of `accepted` or
        `superseded`, none of `PROTECTED_WHILE_DRAFT_FIELDS` may change in
        this save. The draft-to-accepted transition itself is unaffected -
        at the moment that save runs, the persisted status is still
        `draft`, so it is the save immediately AFTER acceptance (or
        supersession) that this guard blocks.

        Looks up the currently-persisted row by primary key rather than
        trusting any in-memory "original" snapshot - the only source of
        truth for "was this already accepted" is the database itself (same
        technique `policy.models.PolicyVersion.save()` uses).
        """
        if self.pk is not None:
            try:
                persisted = QuestionnaireResponse.objects.get(pk=self.pk)
            except QuestionnaireResponse.DoesNotExist:
                persisted = None
            if persisted is not None and persisted.status in (
                self.STATUS_ACCEPTED,
                self.STATUS_SUPERSEDED,
            ):
                changed = [
                    field_name
                    for field_name in self.PROTECTED_WHILE_DRAFT_FIELDS
                    if getattr(persisted, field_name) != getattr(self, field_name)
                ]
                if changed:
                    raise ImmutableQuestionnaireResponseError(
                        f"QuestionnaireResponse {self.pk} is {persisted.status!r} and "
                        f"immutable - cannot change {changed!r}. Create a new "
                        "QuestionnaireResponse instead (PID §7.2/§17)."
                    )
        super().save(*args, **kwargs)
