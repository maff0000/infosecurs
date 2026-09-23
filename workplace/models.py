"""
Tenant-owned Workplace domain (ADR-0002 §5,
docs/pids/M004-POLICY-FOUNDATION.md §9).

`OrganisationProfile.working_model` (organisations/models.py) is too coarse
to represent real SME working context - it is a single "office / remote /
hybrid / unknown" enum with no notion of *where* or *how many people*. This
app adds `Workplace`: a tenant-owned row per distinct working context an
organisation actually has. An organisation may have zero, one, or several
active `Workplace` rows (PID §9.1's "several locations" example: a
20-person organisation with a London office *and* home working as two
separate rows).

Once at least one `Workplace` row exists for an organisation, this app
becomes the sole authority for `OrganisationProfile.working_model` - it
becomes a derived, read-only summary rather than an independently editable
fact (ADR-0002 §5.2, PID §9.2). See `workplace.services.
sync_working_model` for the derivation and the one code path that writes
it, and `organisations.forms.OrganisationProfileForm` for how the normal
product UI is prevented from independently contradicting it.

This is deliberately NOT a physical-security module (ADR §5, PID §9.1's
explicit non-goal): no floor plans, no visitor management, no
physical-security control questions - just a short human label, a type,
a human-level location, an approximate headcount, and primary/active
flags.
"""
import uuid

from django.core.validators import MinValueValidator
from django.db import models

from organisations.models import Organisation


class Workplace(models.Model):
    # V1 workplace types (ADR-0002 §5, PID §9). A plain closed CharField
    # enum, not a configurable catalogue - matching this codebase's
    # existing choice-set convention (see organisations.models,
    # key_assets.models).
    TYPE_DISTRIBUTED_HOME = "distributed_home"
    TYPE_DEDICATED_OFFICE = "dedicated_office"
    TYPE_SHARED_OFFICE = "shared_office"
    TYPE_COWORKING_SPACE = "coworking_space"
    TYPE_OTHER = "other"
    TYPE_CHOICES = [
        (TYPE_DISTRIBUTED_HOME, "Distributed / home-based"),
        (TYPE_DEDICATED_OFFICE, "Dedicated office"),
        (TYPE_SHARED_OFFICE, "Shared office"),
        (TYPE_COWORKING_SPACE, "Coworking space"),
        (TYPE_OTHER, "Other"),
    ]

    # Stable UUID primary key - this codebase's existing convention for
    # every tenant-owned model (see evidence.EvidenceItem, key_assets.KeyAsset).
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="workplaces"
    )

    name = models.CharField(
        max_length=255,
        help_text="Short human label, e.g. 'London Head Office' or 'Home / remote working'.",
    )
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)

    # Human-level location, not a structured/validated postal address (PID
    # §9: "A full postal address is not required for V1"). Not required at
    # the model layer at all - the onboarding flow never asks for it for
    # the distributed_home pattern (PID §9.1's own examples show
    # "Home / remote working" with no location given).
    location_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-level location, e.g. 'Woking, Surrey' or 'London'. Optional.",
    )

    # Nullable/optional, same pattern as organisations.OrganisationProfile.
    # staff_count - "approximate", not a precise/mandatory headcount.
    approx_people_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Approximate number of people normally using this workplace. Leave blank if not known.",
    )

    # Informational only - which workplace is "the main one" for display
    # purposes. Deliberately not database-enforced as a unique-per-organisation
    # flag: PID/ADR do not require it, and enforcing it would add
    # complexity (e.g. an implicit "unset the previous primary" side
    # effect) beyond what either document asks for.
    is_primary = models.BooleanField(default=False)

    # Only active workplaces feed the working_model derivation (ADR-0002
    # §5.2, PID §9.2: "no active workplace context -> unknown", "active
    # contexts" throughout). Deactivating rather than deleting keeps
    # history rather than silently destroying a past workplace record.
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]
        indexes = [
            models.Index(fields=["organisation", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.organisation})"
