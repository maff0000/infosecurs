import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


# ---------------------------------------------------------------------------
# Shared choice sets
# ---------------------------------------------------------------------------
# Tri-state facts are modelled as an explicit enum rather than a nullable
# boolean so "not confirmed" is a deliberate, visible state in forms, data
# and tests - never conflated with an empty/blank value (PID.md §3, §9).
UNKNOWN = "unknown"
YES = "yes"
NO = "no"

TRI_STATE_CHOICES = [
    (UNKNOWN, "Not confirmed"),
    (YES, "Yes"),
    (NO, "No"),
]

WORKING_MODEL_CHOICES = [
    (UNKNOWN, "Not confirmed"),
    ("office", "Office-based"),
    ("remote", "Remote"),
    ("hybrid", "Hybrid"),
]

ENDPOINT_MANAGEMENT_CHOICES = [
    (UNKNOWN, "Not confirmed"),
    ("company_managed", "Company-managed devices"),
    ("byod", "Bring your own device (BYOD)"),
    ("both", "Both company-managed and BYOD"),
]

PRODUCTIVITY_PLATFORM_CHOICES = [
    (UNKNOWN, "Not confirmed"),
    ("microsoft_365", "Microsoft 365"),
    ("google_workspace", "Google Workspace"),
    ("other", "Other"),
]

CLOUD_PROVIDER_CHOICES = [
    (UNKNOWN, "Not confirmed"),
    ("none", "None"),
    ("aws", "Amazon Web Services (AWS)"),
    ("azure", "Microsoft Azure"),
    ("gcp", "Google Cloud Platform (GCP)"),
    ("other", "Other"),
]

ASSURANCE_STATUS_CHOICES = [
    (UNKNOWN, "Not confirmed"),
    ("not_certified", "Not certified"),
    ("in_progress", "In progress"),
    ("certified", "Certified"),
]


class Organisation(models.Model):
    """A stable tenant identity. Everything tenant-owned hangs off this."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        help_text="Short name used to identify this organisation when switching context.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganisationMembership(models.Model):
    """Associates an authenticated user with an organisation tenant."""

    ROLE_OWNER = "owner"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
    ]

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organisation_memberships"
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_OWNER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "user"], name="unique_membership_per_org_user"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.organisation} ({self.role})"


class OrganisationProfile(models.Model):
    """
    Current confirmed organisation facts (PID.md §3).

    Typed fields, not a JSON blob. Structured facts use an explicit
    "not confirmed" state rather than being left blank, so the UI and any
    downstream module (e.g. M002 risk generation) can distinguish "we asked
    and the answer is no" from "we have not established this yet".
    """

    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, related_name="profile"
    )

    # --- Identity ---------------------------------------------------------
    legal_trading_name = models.CharField(
        max_length=255,
        help_text="The organisation's legal or trading name.",
    )
    description = models.TextField(
        blank=True,
        help_text="A short description of what the organisation does.",
    )
    staff_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Approximate headcount. Leave blank if not yet confirmed.",
    )

    # --- Working model ------------------------------------------------------
    # These structured facts default to UNKNOWN. They are deliberately NOT
    # blank=True: a <select> always submits a value (the form pre-selects
    # "Not confirmed" as the initial choice from the model default), so
    # requiring the field keeps the choice set to exactly the enum's named
    # values - never a bare empty string that would be ambiguous with the
    # explicit "unknown" state (PID.md §9 "unknown-vs-empty is deliberate").
    working_model = models.CharField(
        max_length=16, choices=WORKING_MODEL_CHOICES, default=UNKNOWN,
        help_text="How staff mainly work.",
    )
    endpoint_management = models.CharField(
        max_length=32, choices=ENDPOINT_MANAGEMENT_CHOICES, default=UNKNOWN,
        help_text="How staff devices/endpoints are managed.",
    )

    # --- Technology ---------------------------------------------------------
    productivity_platform = models.CharField(
        max_length=32, choices=PRODUCTIVITY_PLATFORM_CHOICES, default=UNKNOWN,
        help_text="Primary productivity/email platform.",
    )
    primary_cloud_provider = models.CharField(
        max_length=16, choices=CLOUD_PROVIDER_CHOICES, default=UNKNOWN,
        help_text="Primary cloud provider, if applicable.",
    )
    develops_hosts_own_software = models.CharField(
        max_length=8, choices=TRI_STATE_CHOICES, default=UNKNOWN,
        help_text="Does the organisation develop or host its own software/service?",
    )

    # --- Data -----------------------------------------------------------
    handles_personal_data = models.CharField(
        max_length=8, choices=TRI_STATE_CHOICES, default=UNKNOWN,
        help_text="Does the organisation handle personal data?",
    )
    handles_confidential_business_data = models.CharField(
        max_length=8, choices=TRI_STATE_CHOICES, default=UNKNOWN,
        help_text="Does the organisation handle customer confidential/sensitive business data?",
    )
    handles_payment_card_data = models.CharField(
        max_length=8, choices=TRI_STATE_CHOICES, default=UNKNOWN,
        help_text="Does the organisation handle payment-card data directly?",
    )
    handles_special_category_data = models.CharField(
        max_length=8, choices=TRI_STATE_CHOICES, default=UNKNOWN,
        help_text="Does the organisation handle special-category/highly sensitive personal data?",
    )

    # --- Assurance context ------------------------------------------------
    receives_security_questionnaires = models.CharField(
        max_length=8, choices=TRI_STATE_CHOICES, default=UNKNOWN,
        help_text="Do customers send this organisation security questionnaires?",
    )
    cyber_essentials_status = models.CharField(
        max_length=16, choices=ASSURANCE_STATUS_CHOICES, default=UNKNOWN,
        help_text="Cyber Essentials certification status.",
    )
    iso27001_status = models.CharField(
        max_length=16, choices=ASSURANCE_STATUS_CHOICES, default=UNKNOWN,
        help_text="ISO 27001 certification status.",
    )
    commercial_security_driver = models.TextField(
        blank=True,
        help_text="The immediate commercial/security driver, if known (free text, optional).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.organisation}"


class AuditEvent(models.Model):
    """
    Minimal durable record of profile created/updated (PID.md §4).

    This is intentionally NOT the final evidence/provenance system that a
    later module will build - just enough to answer "who changed what,
    when" for the organisation profile.
    """

    ACTION_PROFILE_CREATED = "profile_created"
    ACTION_PROFILE_UPDATED = "profile_updated"
    ACTION_CHOICES = [
        (ACTION_PROFILE_CREATED, "Profile created"),
        (ACTION_PROFILE_UPDATED, "Profile updated"),
    ]

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="audit_events"
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_events",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} on {self.organisation} at {self.timestamp:%Y-%m-%d %H:%M} UTC"
