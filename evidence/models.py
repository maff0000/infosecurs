"""
Tenant-owned Evidence domain (PID docs/pids/M003-EVIDENCE-AND-SECURITY-STATE.md
§6.1-6.4, §10, §11).

Core invariant this app must never break (PID §2 "one security truth"):
`security_baseline.BaselineAnswer` remains the sole canonical, independently
editable statement of a control fact. `EvidenceItem` never stores a second
editable answer for the same control - it records an artefact/reference
*about* the organisation's security state. `ControlEvidenceLink` (below,
PID §6.4) is the explicit, tenant-owned association between one
`EvidenceItem` and one catalogue control key - it records a *relationship*
(supports/contradicts/context) between evidence and a control, never a
second copy of the control's answer itself.

Content-mutation discipline (PID §6.2, §10): once a file evidence item is
created, its content-identifying fields - `original_filename`,
`stored_filename`, `file_type`, `byte_size`, `sha256` - are immutable.
"Superseding" is never an in-place edit; it is always a *new* `EvidenceItem`
that the old, retained item may point at via `superseded_by` (PID §6.1).
"""
import uuid

from django.conf import settings
from django.db import models

from organisations.models import Organisation
from security_baseline.catalogue import CATALOGUE_BY_KEY

# ---------------------------------------------------------------------------
# Choice sets
# ---------------------------------------------------------------------------
KIND_FILE = "file"
KIND_EXTERNAL_REFERENCE = "external_reference"
KIND_CHOICES = [
    (KIND_FILE, "File"),
    (KIND_EXTERNAL_REFERENCE, "External reference"),
]

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
STATUS_WITHDRAWN = "withdrawn"
STATUS_CHOICES = [
    (STATUS_ACTIVE, "Active"),
    (STATUS_SUPERSEDED, "Superseded"),
    (STATUS_WITHDRAWN, "Withdrawn"),
]

FILE_TYPE_PDF = "pdf"
FILE_TYPE_PNG = "png"
FILE_TYPE_JPEG = "jpeg"
FILE_TYPE_TEXT = "text"
FILE_TYPE_CHOICES = [
    (FILE_TYPE_PDF, "PDF"),
    (FILE_TYPE_PNG, "PNG"),
    (FILE_TYPE_JPEG, "JPEG"),
    (FILE_TYPE_TEXT, "Plain text"),
]

# Fields that describe *what was actually uploaded*. Once a file evidence
# item exists, none of these may change - see EvidenceItem.save() below.
# Deliberately excludes user-editable metadata (title/description/etc.),
# lifecycle fields (status/superseded_by) and timestamps, which must remain
# writable for the ordinary lifecycle (supersede/withdraw) to work at all.
IMMUTABLE_FILE_FIELDS = (
    "original_filename",
    "stored_filename",
    "file_type",
    "byte_size",
    "sha256",
)


class EvidenceImmutableFieldError(Exception):
    """
    Raised by EvidenceItem.save() if a caller attempts to change a field
    that PID §6.2/§10 requires to stay immutable after creation. This is a
    programming-error guard, not a form-validation error: no product code
    path should ever construct an update that hits it, so the tests that
    prove immutability (evidence/tests/test_models.py) deliberately try to
    trigger it directly against the model/ORM layer.
    """


class EvidenceItem(models.Model):
    # Re-exposed as class attributes (module-level constants above remain
    # the source of truth used by forms/choices) so callers can write the
    # conventional `EvidenceItem.KIND_FILE` / `EvidenceItem.STATUS_ACTIVE`
    # style already used throughout this codebase (see key_assets.KeyAsset).
    KIND_FILE = KIND_FILE
    KIND_EXTERNAL_REFERENCE = KIND_EXTERNAL_REFERENCE
    STATUS_ACTIVE = STATUS_ACTIVE
    STATUS_SUPERSEDED = STATUS_SUPERSEDED
    STATUS_WITHDRAWN = STATUS_WITHDRAWN
    FILE_TYPE_PDF = FILE_TYPE_PDF
    FILE_TYPE_PNG = FILE_TYPE_PNG
    FILE_TYPE_JPEG = FILE_TYPE_JPEG
    FILE_TYPE_TEXT = FILE_TYPE_TEXT

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="evidence_items"
    )

    kind = models.CharField(max_length=32, choices=KIND_CHOICES)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Where this evidence came from, e.g. 'Microsoft 365 admin centre export'.",
    )

    observed_at = models.DateField(
        null=True,
        blank=True,
        help_text="When this evidence was captured/observed, if known. Leave blank if not known.",
    )
    valid_until = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "When this evidence stops being considered current, if known. "
            "Leave blank if there is no known expiry - none is invented."
        ),
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    # Self-FK, not a status value: an item's replacement is a distinct row
    # (PID §6.1). related_name reads naturally from either end -
    # `old.superseded_by` / `new.superseded_items`.
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_items",
    )

    # --- File evidence (kind=file) - PID §6.2. Immutable after creation. --
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
    file_type = models.CharField(max_length=16, choices=FILE_TYPE_CHOICES, blank=True)
    byte_size = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)

    # --- External reference evidence (kind=external_reference) - PID §6.3 -
    reference_url = models.URLField(
        max_length=2048,
        blank=True,
        help_text="A syntactically valid URL. Infosecurs does not fetch or crawl it.",
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_evidence_items",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.organisation})"

    def save(self, *args, **kwargs):
        if self.pk:
            previous = EvidenceItem.objects.filter(pk=self.pk).values(*IMMUTABLE_FILE_FIELDS).first()
            if previous is not None:
                for field_name in IMMUTABLE_FILE_FIELDS:
                    if previous[field_name] != getattr(self, field_name):
                        raise EvidenceImmutableFieldError(
                            f"'{field_name}' is immutable once an EvidenceItem has been "
                            f"created (attempted change on {self.pk})."
                        )
        super().save(*args, **kwargs)


class ControlEvidenceLink(models.Model):
    """
    Explicit, tenant-owned association: one `EvidenceItem` -> one
    `security_baseline.catalogue` control key (PID §6.4).

    `control_key` is a plain `CharField`, not a `ForeignKey` - the
    catalogue is versioned Python data (`security_baseline/catalogue.py`),
    not a database table. Same convention `remediation.RemediationAction.
    control_key` already uses in this codebase (see that model's docstring).

    Same-organisation enforcement (PID §6.4 "The link operation must
    verify all referenced objects belong to the same organisation"):
    `control_key` is not itself an organisation-scoped object, so the real
    check is that `evidence.organisation` matches `organisation` on this
    row. That check lives in `evidence.link_services.
    link_evidence_to_control` (a service function, not just form
    validation, so it cannot be bypassed by a caller that skips the form)
    - it is intentionally *not* re-derived here as a model-level
    constraint, because `organisation` and `evidence.organisation_id` are
    two independent FK columns and Django/PostgreSQL cannot express
    "these two FKs' targets must match" as a single-table constraint.

    Duplicate-link behaviour (PID §19 "duplicate-link behaviour
    deterministic"): this dispatch's chosen behaviour is to REJECT an
    exact duplicate - the same (evidence, control_key, relationship)
    triple - with a friendly, deterministic error, enforced at both the
    database layer (the unique constraint below) and the service layer
    (`link_evidence_to_control` checks first and raises
    `EvidenceValidationError`, so a form resubmission is a normal
    user-facing validation error, not a 500 from an `IntegrityError`). A
    *different* relationship (e.g. the same evidence linked as both
    "supports" and, separately, "context") on the same control is allowed
    and is a different, independent link.
    """

    RELATIONSHIP_SUPPORTS = "supports"
    RELATIONSHIP_CONTRADICTS = "contradicts"
    RELATIONSHIP_CONTEXT = "context"
    RELATIONSHIP_CHOICES = [
        (RELATIONSHIP_SUPPORTS, "Supports"),
        (RELATIONSHIP_CONTRADICTS, "Contradicts"),
        (RELATIONSHIP_CONTEXT, "Context"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="control_evidence_links"
    )
    evidence = models.ForeignKey(
        EvidenceItem, on_delete=models.CASCADE, related_name="control_links"
    )
    control_key = models.CharField(
        max_length=64,
        help_text="A security_baseline catalogue control key. Plain CharField - the catalogue is Python data, not a database table.",
    )
    relationship = models.CharField(max_length=16, choices=RELATIONSHIP_CHOICES)
    rationale = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Optional short note explaining why this evidence supports/contradicts/contextualises this control.",
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="control_evidence_links",
    )
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-linked_at"]
        indexes = [
            # The Current Security State projection's query pattern
            # (security_state.services.get_security_state): "all links for
            # this organisation's control X".
            models.Index(fields=["organisation", "control_key"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["evidence", "control_key", "relationship"],
                name="unique_evidence_control_relationship",
            )
        ]

    def __str__(self):
        return f"{self.evidence_id} --{self.relationship}--> {self.control_key} ({self.organisation})"

    def control_key_label(self) -> str:
        """
        Human-readable label for `control_key`, looked up from the
        security_baseline catalogue (read-only reference - this app never
        writes to security_baseline). Falls back to the raw key if the
        catalogue does not (or no longer) contain it, so a historical link
        never renders blank/broken just because the catalogue evolved. Same
        pattern as `remediation.RemediationAction.control_key_label`.
        """
        entry = CATALOGUE_BY_KEY.get(self.control_key)
        return entry["area"] if entry else self.control_key
