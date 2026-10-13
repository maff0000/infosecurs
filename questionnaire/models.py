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
        help_text=(
            "Editable answer text. For outcome CONFIRM or SUPPORTED, starts "
            "equal to a fixed, application-owned safe sentence (never the "
            "raw AI draft) - see questionnaire.services."
            "CONFIRM_APPLICATION_SAFE_ANSWER_TEXT / "
            "SUPPORTED_APPLICATION_SAFE_ANSWER_TEXT. For GAP or "
            "NOT_APPLICABLE, starts equal to ai_draft_text."
        ),
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


# ===========================================================================
# M009A - Secure questionnaire artifact ingestion + XLSX normalisation/
# provenance (WO-M009A-SECURE-INGESTION-XLSX.md).
#
# Lives inside this SAME app, alongside the M005 truth engine above, per
# WO-M009A's "Domain placement - frozen (Correction 1)": a distinct
# conceptual domain (the uploaded *artifact* and its extracted *candidate*
# questions), never a new Django app, and never a second truth engine -
# `QuestionnaireQuestion`/`QuestionnaireResponse` above are completely
# untouched by everything below. `QuestionnaireImportQuestion.question`
# (a nullable, SET_NULL bridge - see below) is the ONLY point of contact,
# and even that is one-directional and optional.
# ===========================================================================

IMPORT_FILE_FORMAT_XLSX = "xlsx"
IMPORT_FILE_FORMAT_CHOICES = [
    (IMPORT_FILE_FORMAT_XLSX, "XLSX"),
]

IMPORT_SECURITY_GATE_PENDING = "pending"
IMPORT_SECURITY_GATE_PASSED = "passed"
IMPORT_SECURITY_GATE_REJECTED = "rejected"
IMPORT_SECURITY_GATE_FAILED = "failed"
IMPORT_SECURITY_GATE_STATUS_CHOICES = [
    (IMPORT_SECURITY_GATE_PENDING, "Pending"),
    (IMPORT_SECURITY_GATE_PASSED, "Passed"),
    (IMPORT_SECURITY_GATE_REJECTED, "Rejected"),
    (IMPORT_SECURITY_GATE_FAILED, "Failed"),
]

IMPORT_STATUS_UPLOADED = "uploaded"
IMPORT_STATUS_SECURITY_GATE_PENDING = "security_gate_pending"
IMPORT_STATUS_SECURITY_GATE_REJECTED = "security_gate_rejected"
IMPORT_STATUS_SECURITY_GATE_FAILED = "security_gate_failed"
IMPORT_STATUS_EXTRACTING = "extracting"
IMPORT_STATUS_EXTRACTED = "extracted"
IMPORT_STATUS_EXTRACTION_FAILED = "extraction_failed"
IMPORT_STATUS_CHOICES = [
    (IMPORT_STATUS_UPLOADED, "Uploaded"),
    (IMPORT_STATUS_SECURITY_GATE_PENDING, "Security gate pending"),
    (IMPORT_STATUS_SECURITY_GATE_REJECTED, "Security gate rejected"),
    (IMPORT_STATUS_SECURITY_GATE_FAILED, "Security gate failed"),
    (IMPORT_STATUS_EXTRACTING, "Extracting"),
    (IMPORT_STATUS_EXTRACTED, "Extracted"),
    (IMPORT_STATUS_EXTRACTION_FAILED, "Extraction failed"),
]

# Artifact-identity fields: WO-M009A's frozen model contract -
# "organisation, stored_filename, original_filename, sha256_hash,
# size_bytes, detected_content_type, file_format must be model/
# service-layer immutable after creation." Enforced in
# `QuestionnaireImport.save()` below, mirroring `evidence.models.
# EvidenceItem.save()`'s identical IMMUTABLE_FILE_FIELDS pattern exactly.
IMPORT_IMMUTABLE_FIELDS = (
    "organisation_id",
    "stored_filename",
    "original_filename",
    "sha256_hash",
    "size_bytes",
    "detected_content_type",
    "file_format",
)

# State-consistency contract between `security_gate_status` and `status`
# (WO-M009A Final Correction J): the exhaustive set of (security_gate_
# status, status) combinations the lifecycle diagram in WO-M009A's "Import
# lifecycle" section permits. Anything not listed here is a contradictory
# state (e.g. gate `rejected` + lifecycle `extracting`) and is refused by
# `QuestionnaireImport.save()` below, BEFORE it ever reaches the database -
# never merely documented, never left to a view to get right by convention.
IMPORT_ALLOWED_STATE_COMBINATIONS = frozenset(
    {
        (IMPORT_SECURITY_GATE_PENDING, IMPORT_STATUS_UPLOADED),
        (IMPORT_SECURITY_GATE_PENDING, IMPORT_STATUS_SECURITY_GATE_PENDING),
        (IMPORT_SECURITY_GATE_REJECTED, IMPORT_STATUS_SECURITY_GATE_REJECTED),
        (IMPORT_SECURITY_GATE_FAILED, IMPORT_STATUS_SECURITY_GATE_FAILED),
        (IMPORT_SECURITY_GATE_PASSED, IMPORT_STATUS_EXTRACTING),
        (IMPORT_SECURITY_GATE_PASSED, IMPORT_STATUS_EXTRACTED),
        (IMPORT_SECURITY_GATE_PASSED, IMPORT_STATUS_EXTRACTION_FAILED),
    }
)


class QuestionnaireImportValidationError(Exception):
    """Raised for an M009A import-domain rule violation that a view/service
    should treat as a clean failure rather than a 500 - mirrors
    `evidence.exceptions.EvidenceValidationError`'s role for the sibling
    evidence domain."""


class QuestionnaireImportImmutableFieldError(QuestionnaireImportValidationError):
    """Raised by `QuestionnaireImport.save()` if a caller attempts to
    change one of `IMPORT_IMMUTABLE_FIELDS` after creation (WO-M009A frozen
    model contract). A programming-error guard, not a form-validation
    error - no product code path should ever construct an update that hits
    this; mirrors `evidence.models.EvidenceImmutableFieldError` exactly."""


class QuestionnaireImportStateConsistencyError(QuestionnaireImportValidationError):
    """Raised by `QuestionnaireImport.save()` if a caller attempts to
    persist a (`security_gate_status`, `status`) combination outside
    `IMPORT_ALLOWED_STATE_COMBINATIONS` (WO-M009A Final Correction J) -
    e.g. gate `rejected` with lifecycle `extracting`. Views never mutate
    these fields directly (Correction 14); only
    `questionnaire.import_services` does, through its own governed
    transition functions - this is the fail-closed backstop underneath
    that discipline, not a substitute for it."""


class QuestionnaireImport(models.Model):
    """One uploaded questionnaire artifact and its security/extraction
    lifecycle (WO-M009A frozen model contract). The ORIGINAL uploaded
    bytes are immutable once security-gate PASSED (WO-M009A "Original-
    artifact retention"); this model only ever records metadata ABOUT
    those bytes - the bytes themselves live in
    `questionnaire.import_storage`, mirroring `evidence.storage`."""

    FILE_FORMAT_XLSX = IMPORT_FILE_FORMAT_XLSX

    SECURITY_GATE_PENDING = IMPORT_SECURITY_GATE_PENDING
    SECURITY_GATE_PASSED = IMPORT_SECURITY_GATE_PASSED
    SECURITY_GATE_REJECTED = IMPORT_SECURITY_GATE_REJECTED
    SECURITY_GATE_FAILED = IMPORT_SECURITY_GATE_FAILED

    STATUS_UPLOADED = IMPORT_STATUS_UPLOADED
    STATUS_SECURITY_GATE_PENDING = IMPORT_STATUS_SECURITY_GATE_PENDING
    STATUS_SECURITY_GATE_REJECTED = IMPORT_STATUS_SECURITY_GATE_REJECTED
    STATUS_SECURITY_GATE_FAILED = IMPORT_STATUS_SECURITY_GATE_FAILED
    STATUS_EXTRACTING = IMPORT_STATUS_EXTRACTING
    STATUS_EXTRACTED = IMPORT_STATUS_EXTRACTED
    STATUS_EXTRACTION_FAILED = IMPORT_STATUS_EXTRACTION_FAILED

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="questionnaire_imports"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_questionnaire_imports",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # --- Artifact identity - immutable after creation (see
    # IMPORT_IMMUTABLE_FIELDS / save() below). --------------------------
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Safe display filename as supplied at upload. Never used to derive the storage path.",
    )
    stored_filename = models.CharField(
        max_length=128,
        blank=True,
        help_text="Opaque, server-generated storage identifier. Never derived from the original filename.",
    )
    detected_content_type = models.CharField(
        max_length=255,
        blank=True,
        help_text="From content-sniffing only (the security gate) - never the client-supplied Content-Type.",
    )
    file_format = models.CharField(max_length=16, choices=IMPORT_FILE_FORMAT_CHOICES, blank=True)
    sha256_hash = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)

    # --- Lifecycle state - mutable only via questionnaire.import_services'
    # governed transitions (Correction 14); see save() below for the
    # fail-closed state-consistency backstop (Final Correction J). -------
    security_gate_status = models.CharField(
        max_length=16, choices=IMPORT_SECURITY_GATE_STATUS_CHOICES, default=IMPORT_SECURITY_GATE_PENDING
    )
    security_gate_result = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Structured rejection reason(s) / structural inspection summary / scanner "
            "provenance. Never raw file content (WO-M009A Correction 6/Final Correction B)."
        ),
    )
    status = models.CharField(max_length=24, choices=IMPORT_STATUS_CHOICES, default=IMPORT_STATUS_UPLOADED)
    extraction_summary = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Bounded structured summary (sheets discovered/processed/skipped, question/"
            "excluded/failed counts, whether any answer destination was found). Never "
            "arbitrary workbook body content (WO-M009A Correction 13)."
        ),
    )

    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_by_imports",
        help_text="Set when this import is a re-upload intended to replace a prior one. "
        "The prior import and all its questions remain, untouched and inspectable.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["organisation", "uploaded_at"]),
            models.Index(fields=["organisation", "status"]),
        ]

    def __str__(self):
        return f"QuestionnaireImport {self.id} ({self.organisation}) [{self.status}]"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            persisted = (
                QuestionnaireImport.objects.filter(pk=self.pk)
                .values(*IMPORT_IMMUTABLE_FIELDS)
                .first()
            )
            if persisted is not None:
                changed = [
                    field_name
                    for field_name in IMPORT_IMMUTABLE_FIELDS
                    if persisted[field_name] != getattr(self, field_name)
                ]
                if changed:
                    raise QuestionnaireImportImmutableFieldError(
                        f"{changed!r} is immutable once a QuestionnaireImport has been "
                        f"created (attempted change on {self.pk})."
                    )

        combination = (self.security_gate_status, self.status)
        if combination not in IMPORT_ALLOWED_STATE_COMBINATIONS:
            raise QuestionnaireImportStateConsistencyError(
                f"QuestionnaireImport {self.pk} may not be saved with "
                f"security_gate_status={self.security_gate_status!r} and "
                f"status={self.status!r} - that combination is not one of the "
                "contracted (security_gate_status, status) pairs "
                "(WO-M009A Final Correction J)."
            )

        super().save(*args, **kwargs)


IMPORT_QUESTION_DISPOSITION_QUESTION = "question"
IMPORT_QUESTION_DISPOSITION_HEADING = "heading"
IMPORT_QUESTION_DISPOSITION_INSTRUCTIONAL_TEXT = "instructional_text"
IMPORT_QUESTION_DISPOSITION_EXCLUDED_DUPLICATE = "excluded_duplicate"
IMPORT_QUESTION_DISPOSITION_EXCLUDED_AMBIGUOUS = "excluded_ambiguous"
IMPORT_QUESTION_DISPOSITION_EXCLUDED_OTHER = "excluded_other"
IMPORT_QUESTION_DISPOSITION_CHOICES = [
    (IMPORT_QUESTION_DISPOSITION_QUESTION, "Question"),
    (IMPORT_QUESTION_DISPOSITION_HEADING, "Heading"),
    (IMPORT_QUESTION_DISPOSITION_INSTRUCTIONAL_TEXT, "Instructional text"),
    (IMPORT_QUESTION_DISPOSITION_EXCLUDED_DUPLICATE, "Excluded - duplicate"),
    (IMPORT_QUESTION_DISPOSITION_EXCLUDED_AMBIGUOUS, "Excluded - ambiguous"),
    (IMPORT_QUESTION_DISPOSITION_EXCLUDED_OTHER, "Excluded - other"),
]

IMPORT_QUESTION_EXTRACTION_STATUS_PENDING = "pending"
IMPORT_QUESTION_EXTRACTION_STATUS_EXTRACTED = "extracted"
IMPORT_QUESTION_EXTRACTION_STATUS_FAILED = "failed"
IMPORT_QUESTION_EXTRACTION_STATUS_CHOICES = [
    (IMPORT_QUESTION_EXTRACTION_STATUS_PENDING, "Pending"),
    (IMPORT_QUESTION_EXTRACTION_STATUS_EXTRACTED, "Extracted"),
    (IMPORT_QUESTION_EXTRACTION_STATUS_FAILED, "Failed"),
]

# Excel's own per-cell character maximum (WO-M009A Correction 9) - the
# contractual cap on `raw_extracted_text`, enforced here (TextField's own
# `max_length` is a form/validator-level constraint on Postgres, not a DB
# column constraint - see questionnaire.xlsx_extraction for the actual
# truncation/fail-closed enforcement at write time).
RAW_EXTRACTED_TEXT_MAX_LENGTH = 32767

# Source-location contract schema version in use (WO-M009A Correction 10,
# "XLSX schema v1"). A future format (DOCX, out of scope for M009A) would
# introduce schema_version=2 with its own, separately-validated shape -
# never overloading this one.
SOURCE_LOCATION_SCHEMA_VERSION = 1


class QuestionnaireImportQuestion(models.Model):
    """One candidate row extracted from a `QuestionnaireImport`'s workbook,
    in original document order, with full source-location provenance
    (WO-M009A frozen model contract). Every extracted row gets one of
    these - never silently dropped - with an explicit, auditable
    `disposition`."""

    DISPOSITION_QUESTION = IMPORT_QUESTION_DISPOSITION_QUESTION
    DISPOSITION_HEADING = IMPORT_QUESTION_DISPOSITION_HEADING
    DISPOSITION_INSTRUCTIONAL_TEXT = IMPORT_QUESTION_DISPOSITION_INSTRUCTIONAL_TEXT
    DISPOSITION_EXCLUDED_DUPLICATE = IMPORT_QUESTION_DISPOSITION_EXCLUDED_DUPLICATE
    DISPOSITION_EXCLUDED_AMBIGUOUS = IMPORT_QUESTION_DISPOSITION_EXCLUDED_AMBIGUOUS
    DISPOSITION_EXCLUDED_OTHER = IMPORT_QUESTION_DISPOSITION_EXCLUDED_OTHER

    EXTRACTION_STATUS_PENDING = IMPORT_QUESTION_EXTRACTION_STATUS_PENDING
    EXTRACTION_STATUS_EXTRACTED = IMPORT_QUESTION_EXTRACTION_STATUS_EXTRACTED
    EXTRACTION_STATUS_FAILED = IMPORT_QUESTION_EXTRACTION_STATUS_FAILED

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    import_record = models.ForeignKey(
        QuestionnaireImport, on_delete=models.CASCADE, related_name="questions"
    )
    # Nullable, SET_NULL bridge to the EXISTING, completely unmodified M005
    # truth engine above - set only when disposition=question AND
    # normalisation succeeds. If the linked QuestionnaireQuestion later
    # disappears (e.g. a Customer Zero reset deletes it), this row's own
    # source artifact/provenance remains intact with question=NULL - never
    # cascades, never blocks that model's own lifecycle (WO-M009A frozen
    # model contract).
    question = models.ForeignKey(
        QuestionnaireQuestion, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    raw_extracted_text = models.TextField(
        max_length=RAW_EXTRACTED_TEXT_MAX_LENGTH,
        help_text="The literal extracted cell text, always populated regardless of disposition.",
    )
    source_location = models.JSONField(
        help_text="Versioned XLSX schema v1 source-location contract (WO-M009A Correction 10).",
    )
    extraction_order = models.PositiveIntegerField(help_text="Preserves original document order.")
    extraction_status = models.CharField(
        max_length=16,
        choices=IMPORT_QUESTION_EXTRACTION_STATUS_CHOICES,
        default=IMPORT_QUESTION_EXTRACTION_STATUS_PENDING,
    )
    extraction_error = models.TextField(blank=True, default="")
    disposition = models.CharField(max_length=24, choices=IMPORT_QUESTION_DISPOSITION_CHOICES)

    class Meta:
        ordering = ["extraction_order"]
        indexes = [
            models.Index(fields=["import_record", "extraction_order"]),
            models.Index(fields=["import_record", "disposition"]),
        ]

    def __str__(self):
        return f"ImportQuestion {self.id} ({self.import_record_id}) [{self.disposition}]"
