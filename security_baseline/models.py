from django.db import models

from organisations.models import Organisation

# ---------------------------------------------------------------------------
# Answer states (docs/pids/M002-SECURITY-BASELINE-AND-INITIAL-RISK.md §6.2)
# ---------------------------------------------------------------------------
# Same enum-not-blank discipline as M001's tri-state fields
# (organisations/models.py): a <select> always submits a value, and
# "unknown" is a deliberate, visible state - never conflated with a blank/
# missing answer. There is no empty choice in ANSWER_CHOICES.
ANSWER_YES = "yes"
ANSWER_PARTIAL = "partial"
ANSWER_NO = "no"
ANSWER_UNKNOWN = "unknown"
ANSWER_NOT_APPLICABLE = "not_applicable"

ANSWER_CHOICES = [
    (ANSWER_UNKNOWN, "Not confirmed"),
    (ANSWER_YES, "Yes"),
    (ANSWER_PARTIAL, "Partially"),
    (ANSWER_NO, "No"),
    (ANSWER_NOT_APPLICABLE, "Not applicable"),
]


class BaselineAssessment(models.Model):
    """
    A tenant-owned security-baseline assessment (PID §6).

    One per organisation. Holds the catalogue/methodology version the
    answers below were captured against (§6.4) so historical answers stay
    interpretable even after the catalogue in security_baseline/catalogue.py
    evolves. The individual per-question answers live in BaselineAnswer.
    """

    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, related_name="baseline_assessment"
    )
    catalogue_version = models.CharField(
        max_length=64,
        help_text="The security_baseline catalogue version these answers were captured against.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Security baseline for {self.organisation} ({self.catalogue_version})"


class BaselineAnswer(models.Model):
    """
    One answer to one catalogue question, within one organisation's
    BaselineAssessment.

    `question_key` matches a `key` in security_baseline.catalogue.CATALOGUE.
    These are customer-confirmed statements, not system-verified controls
    (PID §6.2) - the UI must say so, and application code must never treat
    an answer here as independently verified evidence.
    """

    assessment = models.ForeignKey(
        BaselineAssessment, on_delete=models.CASCADE, related_name="answers"
    )
    question_key = models.CharField(max_length=64)
    answer = models.CharField(
        max_length=16, choices=ANSWER_CHOICES, default=ANSWER_UNKNOWN,
        help_text="Customer-confirmed statement, not a system-verified control.",
    )
    note = models.TextField(
        blank=True,
        help_text=(
            "Optional short note explaining the answer. Untrusted free text "
            "(PID §6.3, §12) - never treated as an instruction to any AI system."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "question_key"], name="unique_answer_per_question"
            )
        ]

    def __str__(self):
        return f"{self.question_key} = {self.answer} ({self.assessment.organisation})"
