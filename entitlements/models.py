"""
M007-WI1 governed product/commercial metadata (PID §4, §10).

Both models here are versioned product methodology, seeded exclusively via
data migrations (PID §22) - never an admin-editable commercial
configuration surface (§4.3), and never a store for a customer's own
computed state (§10.4). Small integer auto-increment primary keys are
deliberate and documented here rather than following `Organisation`'s
`UUIDField` convention: these rows are governed product metadata that
nothing external ever references by a guessable/stable external identifier
(the FK from `FoundationRequirement.product_area` is an ordinary internal
Django FK, not a customer-facing handle) - `code` is the stable *semantic*
identifier per PID §22, not the numeric primary key. A tenant-scoped model
that customers or external systems address directly (like `Organisation`)
has a different threat model and keeps the UUID convention.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from entitlements.tiers import MAX_TIER, MIN_TIER


class ProductAreaQuerySet(models.QuerySet):
    def active(self):
        """Inactive rows do not render (PID §4.2) - the one queryset helper
        every consumer (WI2's navigation service, the entitlement service
        below) must reuse rather than reimplementing `is_active=True`
        ad hoc."""
        return self.filter(is_active=True)

    def for_tier(self, tier: int):
        """
        Active rows a session at `tier` is entitled to. This is genuinely
        small, defensible shared plumbing (a single filter clause), not the
        navigation-tree-assembly algorithm itself (parent/child ordering,
        grouping) - that assembly is explicitly WI2's own scope (PID §35,
        §4.4). WI1 stops here: a queryset any WI2 view can further order/
        group without reimplementing the tier filter.
        """
        return self.active().filter(min_package_tier__lte=tier)


class ProductAreaManager(models.Manager.from_queryset(ProductAreaQuerySet)):
    pass


class ProductArea(models.Model):
    """Database-driven product area/navigation registry entry (PID §4)."""

    code = models.SlugField(
        max_length=64,
        unique=True,
        help_text="Stable, unique machine identifier. Never renamed once published.",
    )
    label = models.CharField(max_length=128, help_text="Customer-facing navigation label.")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        help_text="Nullable self-FK for nested menu structure.",
    )
    destination_view_name = models.CharField(
        max_length=255,
        help_text=(
            "A Django named route (as passed to django.urls.reverse()) - "
            "never an arbitrary external URL, template fragment or Python "
            "import path (PID §4.1)."
        ),
    )
    min_package_tier = models.PositiveSmallIntegerField(
        help_text="Minimum package tier (0-3) required to see/access this area."
    )
    display_order = models.PositiveIntegerField(default=0)
    show_in_navigation = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    objects = ProductAreaManager()

    class Meta:
        ordering = ["display_order", "code"]  # deterministic ordering (PID §4.2)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_package_tier__gte=MIN_TIER) & models.Q(min_package_tier__lte=MAX_TIER),
                name="productarea_min_package_tier_in_range",
            ),
            # A row cannot parent itself (PID §4.2). Enforced at the
            # database level, not merely in application code, so it holds
            # even against a raw INSERT/UPDATE, an admin-editable future
            # surface, or a bug in application validation. NULL parent_id
            # never violates this: SQL's `parent = id` is UNKNOWN (not
            # TRUE) when parent_id IS NULL, and a CHECK constraint treats
            # an UNKNOWN result as satisfied, exactly like every other
            # nullable-column CHECK in a normal Postgres schema.
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("id")),
                name="productarea_cannot_parent_itself",
            ),
        ]

    def clean(self):
        super().clean()
        if self.parent_id is not None and self.pk is not None and self.parent_id == self.pk:
            raise ValidationError({"parent": "A product area cannot parent itself."})

    def __str__(self):
        return self.label


# Versioned Foundations methodology identifier (PID §10.3). Every seeded
# FoundationRequirement row's `methodology_version` references this
# constant, so a future change to weights/requirements is never silently
# indistinguishable from the version this WI landed under.
FOUNDATION_METRIC_VERSION = "2026-09-v1"


class RequirementKind(models.TextChoices):
    """
    Controlled kinds only (PID §10.2) - never a free string, and never a
    stored Python callable path. `source_key` (below) is the safe, inert
    string a later resolver registry (WI4) dispatches on.
    """

    BASELINE_CONTROL = "BASELINE_CONTROL", "Baseline control"
    DERIVED_MILESTONE = "DERIVED_MILESTONE", "Derived milestone"


class FoundationRequirement(models.Model):
    """
    Requirement/methodology registry entry (PID §10). Pure product
    methodology metadata - this table must never store a customer's own
    computed posture/completion state or an editable "done" flag (§10.4).
    The resolver functions that turn a `source_key` into a live
    complete/incomplete or earned/available value are explicitly WI4's job,
    not this WI's (see this app's `capabilities.py`/`session.py` for what
    WI1 *does* own instead).
    """

    code = models.SlugField(
        max_length=64,
        unique=True,
        help_text="Stable, unique machine identifier. Never renamed once published.",
    )
    title = models.CharField(max_length=255)
    product_area = models.ForeignKey(
        ProductArea,
        on_delete=models.PROTECT,
        related_name="foundation_requirements",
    )
    methodology_version = models.CharField(max_length=32, default=FOUNDATION_METRIC_VERSION)
    requirement_kind = models.CharField(max_length=32, choices=RequirementKind.choices)
    source_key = models.SlugField(
        max_length=64,
        help_text=(
            "A short, stable, self-documenting string a later resolver "
            "registry (WI4) dispatches on - never a Python import path or "
            "callable reference (PID §10.2)."
        ),
    )
    min_package_tier = models.PositiveSmallIntegerField()
    counts_toward_posture = models.BooleanField(default=False)
    counts_toward_completion = models.BooleanField(default=True)
    security_weight = models.PositiveSmallIntegerField(
        default=0,
        help_text="5=critical, 3=important, 1=supporting (PID §11.4). Not meaningful for DERIVED_MILESTONE rows.",
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_package_tier__gte=MIN_TIER) & models.Q(min_package_tier__lte=MAX_TIER),
                name="foundationrequirement_min_package_tier_in_range",
            ),
        ]

    def __str__(self):
        return self.title
