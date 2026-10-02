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
    # Display wording only - Central Architecture baseline-UX correction
    # (M006-AUDIT-0002 correction #1/#11): the stored value is still
    # "unknown", completely unchanged; only the customer-facing label
    # changed, from "Not confirmed" to "Not sure". Persistence semantics,
    # the tri-state discipline described above, and every other choice's
    # value/label are untouched.
    (ANSWER_UNKNOWN, "Not sure"),
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


class AnswerSelectionDetail(models.Model):
    """
    M008B (docs/design/M008B-QUESTION-CATALOGUE.md §0): provenance for one
    structured Stage 4 answer - which exact `option_code` the customer
    selected, and which version of the structured option-code scheme
    (`security_baseline.structured_catalogue.
    FOUNDATIONS_QUESTION_METHODOLOGY_VERSION`) was active when it was
    recorded.

    This is deliberately a SEPARATE fact from `BaselineAnswer.answer`
    (the derived canonical five-state answer, still the single thing every
    other part of this codebase - risk generation, policy grounding,
    entitlements metrics - reads): two different `option_code`s can derive
    the exact same canonical answer (e.g. `BACKUPS_RESTORE_UNTESTED` and
    `BACKUPS_COVERAGE_PARTIAL` both derive PARTIAL) while meaning
    materially different things, and only this model remembers which one
    was actually selected.

    Deliberately mirrors `BaselineAnswer`'s own shape exactly: an FK to
    `BaselineAssessment` only (CASCADE), never a direct FK to
    `Organisation` - this is what lets this model cascade-delete
    automatically on an M008A reset (docs/evidence/M008A-RESET-DELETION-
    MANIFEST.md) with zero changes to `organisations.reset_service`'s
    direct-FK-to-Organisation guard sets, exactly like `BaselineAnswer`
    already does. One row per (assessment, question_key), same
    `unique_together` shape as `BaselineAnswer`'s own
    `unique_answer_per_question` constraint - re-answering a question
    updates the existing row rather than accumulating history.

    The sole write path for this model is
    `security_baseline.services.record_structured_baseline_answer` - never
    constructed directly by view code.
    """

    assessment = models.ForeignKey(
        BaselineAssessment, on_delete=models.CASCADE, related_name="selection_details"
    )
    question_key = models.CharField(
        max_length=64,
        help_text="Matches BaselineAnswer.question_key for the same (assessment, question).",
    )
    option_code = models.CharField(
        max_length=64,
        help_text=(
            "The stable option_code the customer selected "
            "(security_baseline.structured_catalogue.STRUCTURED_OPTIONS)."
        ),
    )
    methodology_version = models.CharField(
        max_length=64,
        help_text=(
            "The security_baseline.structured_catalogue."
            "FOUNDATIONS_QUESTION_METHODOLOGY_VERSION active when this "
            "option_code was recorded."
        ),
    )
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "question_key"],
                name="unique_selection_detail_per_question",
            )
        ]

    def __str__(self):
        return (
            f"{self.question_key} = {self.option_code} "
            f"({self.assessment.organisation})"
        )
