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

# M008B (docs/design/M008B-STAGES-1-3-CATALOGUE.md §1.2): replaces the old
# free-text "what you do in a few words" label entirely - a finite choice
# list, not a bounded text field. "Not sure yet" is listed first, matching
# this module's own UNKNOWN-first convention for every other enum above.
SECTOR_NOT_SURE = "not_sure"
SECTOR_PROFESSIONAL_CONSULTING = "professional_consulting"
SECTOR_RETAIL_ECOMMERCE = "retail_ecommerce"
SECTOR_FINANCIAL_ACCOUNTING = "financial_accounting"
SECTOR_HEALTHCARE_CARE = "healthcare_care"
SECTOR_TECHNOLOGY_SOFTWARE = "technology_software"
SECTOR_MANUFACTURING_LOGISTICS = "manufacturing_logistics"
SECTOR_CONSTRUCTION_TRADES = "construction_trades"
SECTOR_EDUCATION_TRAINING = "education_training"
SECTOR_LEGAL_SERVICES = "legal_services"
SECTOR_HOSPITALITY = "hospitality"
SECTOR_OTHER = "other"

SECTOR_CHOICES = [
    (SECTOR_NOT_SURE, "Not sure yet"),
    (SECTOR_PROFESSIONAL_CONSULTING, "Professional or consulting services"),
    (SECTOR_RETAIL_ECOMMERCE, "Retail or e-commerce"),
    (SECTOR_FINANCIAL_ACCOUNTING, "Financial or accounting services"),
    (SECTOR_HEALTHCARE_CARE, "Healthcare or care services"),
    (SECTOR_TECHNOLOGY_SOFTWARE, "Technology or software"),
    (SECTOR_MANUFACTURING_LOGISTICS, "Manufacturing or logistics"),
    (SECTOR_CONSTRUCTION_TRADES, "Construction or trades"),
    (SECTOR_EDUCATION_TRAINING, "Education or training"),
    (SECTOR_LEGAL_SERVICES, "Legal services"),
    (SECTOR_HOSPITALITY, "Hospitality"),
    (SECTOR_OTHER, "Other / not listed"),
]

# M008B (docs/design/M008B-STAGES-1-3-CATALOGUE.md §1.4; docs/design/
# M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 2): replaces the old open
# "why security matters to you" free text with a finite choice list.
DRIVER_NOT_SURE = "not_sure"
DRIVER_CUSTOMER_SUPPLIER = "customer_supplier"
DRIVER_SENSITIVE_DATA = "sensitive_data"
DRIVER_CERTIFICATION_CONTRACT = "certification_contract"
DRIVER_GENERAL_RISK = "general_risk"

DRIVER_CHOICES = [
    (DRIVER_NOT_SURE, "Not sure yet"),
    (DRIVER_CUSTOMER_SUPPLIER, "A customer or supplier has asked us to"),
    (DRIVER_SENSITIVE_DATA, "We handle sensitive or confidential information"),
    (DRIVER_CERTIFICATION_CONTRACT, "We need it for a certification or contract"),
    (DRIVER_GENERAL_RISK, "We want to reduce cyber risk generally"),
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


class CustomerZeroFixture(models.Model):
    """
    Marks exactly one Organisation as the trusted, synthetic Customer Zero
    test fixture - the ONLY organisation a destructive dev-only reset
    (M008A) may ever target. Created exclusively by
    `create_customer_zero` (a management command, never reachable over
    HTTP) inside its own transaction, alongside the Organisation row
    itself. No form, view, serializer, or other user-facing write path in
    this codebase may create, update, or delete this row - if you are
    tempted to expose it anywhere reachable by an authenticated request,
    stop: that would defeat the entire point of this model, which is that
    "is this the trusted fixture" can never be made true by anything a
    client can submit.
    """

    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, related_name="customer_zero_fixture"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Customer Zero fixture marker for {self.organisation}"


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
    # M008B (docs/design/M008B-STAGES-1-3-CATALOGUE.md §1.2; docs/design/
    # M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 1): the `description`
    # field above is retired from the Foundation form entirely (existing
    # values, if any, stay read-only) - this new, additive, finite-choice
    # field is its replacement, not a second copy of the same fact.
    sector = models.CharField(
        max_length=32, choices=SECTOR_CHOICES, default=SECTOR_NOT_SURE,
        help_text="Which best describes what the organisation does.",
    )
    staff_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Approximate headcount. Leave blank if not yet confirmed.",
    )
    # M008B (docs/design/M008B-STAGES-1-3-CATALOGUE.md §2.3): the sole
    # authority for `security_baseline`'s `joiner_mover_leaver` control's
    # NOT_APPLICABLE gate - deliberately distinct from `staff_count`,
    # which is never sufficient authority for that gate on its own.
    people_with_system_access_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "How many people - including contractors or anyone else, not "
            "just staff - have access to the organisation's business "
            "systems or accounts. Leave blank if not yet confirmed."
        ),
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
    # M008B (docs/design/M008B-STAGES-1-3-CATALOGUE.md §2.4): the sole
    # authority for `security_baseline`'s `remote_access_control` control's
    # NOT_APPLICABLE gate - deliberately never inferred from `working_model`
    # or `primary_cloud_provider`. Reuses the existing TRI_STATE_CHOICES
    # value set rather than inventing a new one.
    has_remote_or_offsite_access = models.CharField(
        max_length=8, choices=TRI_STATE_CHOICES, default=UNKNOWN,
        help_text=(
            "Does anyone access business systems or data from outside the "
            "organisation's normal workplace(s), even occasionally (e.g. "
            "from home, while travelling)?"
        ),
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
    # M008B (docs/design/M008B-STAGES-1-3-CATALOGUE.md §1.4; docs/design/
    # M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 2): corrected from a free
    # TextField to a finite-choice CharField - a genuine field-type change,
    # not a no-op. No data migration/backfill mapping is attempted: Beta
    # has zero real customer rows today (confirmed with the PL), so a
    # plain AlterField with no data migration is correct and sufficient.
    commercial_security_driver = models.CharField(
        max_length=32, choices=DRIVER_CHOICES, default=DRIVER_NOT_SURE,
        help_text="Why the organisation is working on security now.",
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
