import uuid

from django.db import models

from organisations.models import Organisation

# ---------------------------------------------------------------------------
# Shared choice sets (PID.md M002 §7)
# ---------------------------------------------------------------------------
CATEGORY_PEOPLE = "people"
CATEGORY_ENDPOINT = "endpoint"
CATEGORY_IDENTITY_OR_PRODUCTIVITY = "identity_or_productivity"
CATEGORY_CLOUD_SERVICE = "cloud_service"
CATEGORY_BUSINESS_APPLICATION = "business_application"
CATEGORY_INFORMATION = "information"
CATEGORY_NETWORK_OR_LOCATION = "network_or_location"
CATEGORY_OTHER = "other"

CATEGORY_CHOICES = [
    (CATEGORY_PEOPLE, "People"),
    (CATEGORY_ENDPOINT, "Endpoint"),
    (CATEGORY_IDENTITY_OR_PRODUCTIVITY, "Identity / productivity"),
    (CATEGORY_CLOUD_SERVICE, "Cloud service"),
    (CATEGORY_BUSINESS_APPLICATION, "Business application"),
    (CATEGORY_INFORMATION, "Information"),
    (CATEGORY_NETWORK_OR_LOCATION, "Network / location"),
    (CATEGORY_OTHER, "Other"),
]

CRITICALITY_LOW = "low"
CRITICALITY_MEDIUM = "medium"
CRITICALITY_HIGH = "high"
CRITICALITY_CRITICAL = "critical"

CRITICALITY_CHOICES = [
    (CRITICALITY_LOW, "Low"),
    (CRITICALITY_MEDIUM, "Medium"),
    (CRITICALITY_HIGH, "High"),
    (CRITICALITY_CRITICAL, "Critical"),
]


class KeyAsset(models.Model):
    """
    Tenant-owned key-asset baseline (PID.md M002 §7).

    A KeyAsset is created either:
      - as a deterministic, non-AI starter SUGGESTED row (§7.1, see
        key_assets.suggestions) that the customer must explicitly confirm,
        edit or dismiss - it never becomes CONFIRMED on its own; or
      - directly as CONFIRMED, when a customer adds a manual asset - a
        manual entry is the customer's own direct assertion, not a
        suggestion awaiting review.

    This mirrors the tri-state / explicit-state discipline already
    established in organisations.models (UNKNOWN as a deliberate, visible
    state rather than blank) and M002's core invariant that AI/deterministic
    output cannot silently establish organisational truth (PID.md M002 §2).
    """

    STATUS_SUGGESTED = "suggested"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_SUGGESTED, "Suggested"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="key_assets"
    )
    name = models.CharField(
        max_length=255,
        help_text="What the asset is, in plain language.",
    )
    category = models.CharField(
        max_length=32,
        choices=CATEGORY_CHOICES,
        help_text="The kind of thing this asset is.",
    )
    description = models.TextField(
        blank=True,
        help_text="A short description of the asset. Optional.",
    )
    criticality = models.CharField(
        max_length=16,
        choices=CRITICALITY_CHOICES,
        help_text="How important this asset is to the business.",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_SUGGESTED
    )

    # Populated only for deterministic starter suggestions (§7.1). Identifies
    # which suggestion rule produced this row, so ensure_starter_suggestions()
    # is idempotent per (organisation, suggestion_key) - an asset that has
    # already been suggested (and may since have been confirmed, edited or
    # dismissed) is never silently recreated by revisiting the page. Blank
    # for manually-added assets.
    suggestion_key = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.organisation})"
