"""
Tenant-owned risk domain (M002 PID §8).

`Risk` is the confirmed/draft product output of M002. Every AI-generated
row starts life as `STATUS_DRAFT_AI_SUGGESTED` / `SOURCE_AI`, FK'd to the
`ai_platform.AIInvocationRecord` that produced it - it never becomes
`STATUS_CONFIRMED` except through an explicit customer action recorded on
this row (`confirmed_by`/`confirmed_at`), matching PID §2's core invariant:
"AI may propose. AI may not silently establish organisational truth."

The numeric score and its qualitative band (PID §8.2) are deliberately
**not** AI-settable, persisted values: they are computed properties derived
from `impact`/`likelihood` alone, so there is no code path - AI response,
form submission, or otherwise - that can desynchronise a stored score from
the two ratings that are supposed to define it.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ai_platform.models import AIInvocationRecord
from key_assets.models import KeyAsset
from organisations.models import Organisation

MIN_RATING = 1
MAX_RATING = 5

IMPACT_CHOICES = [
    (1, "1 - Negligible"),
    (2, "2 - Minor"),
    (3, "3 - Moderate"),
    (4, "4 - Major"),
    (5, "5 - Severe"),
]

LIKELIHOOD_CHOICES = [
    (1, "1 - Rare"),
    (2, "2 - Unlikely"),
    (3, "3 - Possible"),
    (4, "4 - Likely"),
    (5, "5 - Almost certain"),
]

BAND_LOW = "low"
BAND_MEDIUM = "medium"
BAND_HIGH = "high"
BAND_CRITICAL = "critical"

RISK_BAND_LABELS = {
    BAND_LOW: "Low",
    BAND_MEDIUM: "Medium",
    BAND_HIGH: "High",
    BAND_CRITICAL: "Critical",
}


def score_for(impact: int, likelihood: int) -> int:
    """Deterministic score = impact x likelihood (PID §8.2)."""
    return impact * likelihood


def band_for(score: int) -> str:
    """Qualitative band for a score, per PID §8.2's starter bands:

    1-4 Low, 5-9 Medium, 10-16 High, 17-25 Critical.
    """
    if score <= 4:
        return BAND_LOW
    if score <= 9:
        return BAND_MEDIUM
    if score <= 16:
        return BAND_HIGH
    return BAND_CRITICAL


class Risk(models.Model):
    """A single tenant-owned risk-register entry (PID §8)."""

    SOURCE_AI = "ai"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [
        (SOURCE_AI, "AI suggested"),
        (SOURCE_MANUAL, "Manual"),
    ]

    STATUS_DRAFT_AI_SUGGESTED = "draft_ai_suggested"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_DRAFT_AI_SUGGESTED, "AI suggested (draft)"),
        (STATUS_CONFIRMED, "Customer confirmed"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="risks"
    )

    # --- Asset / context reference -----------------------------------------
    # `key_asset` is the resolved link when the AI (or a customer) referenced
    # a real, tenant-owned KeyAsset. `asset_reference` is always kept as the
    # raw string the candidate/response carried (e.g. "asset:<uuid>" or a
    # profile-fact path such as "profile.endpoint_management") - a generated
    # risk need not resolve to a real asset row to be a valid, groundable
    # suggestion (see risk_register/services.py resolution rules).
    key_asset = models.ForeignKey(
        KeyAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risks",
    )
    asset_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Raw asset/context reference this risk was generated or recorded against.",
    )

    # --- Risk content --------------------------------------------------------
    title = models.CharField(max_length=255)
    threat = models.TextField()
    vulnerability = models.TextField(
        help_text="The vulnerability/exposure this risk is about."
    )

    impact = models.IntegerField(
        choices=IMPACT_CHOICES,
        validators=[MinValueValidator(MIN_RATING), MaxValueValidator(MAX_RATING)],
        help_text="1 (negligible) to 5 (severe). AI may suggest this; the customer can change it before confirmation.",
    )
    likelihood = models.IntegerField(
        choices=LIKELIHOOD_CHOICES,
        validators=[MinValueValidator(MIN_RATING), MaxValueValidator(MAX_RATING)],
        help_text="1 (rare) to 5 (almost certain). AI may suggest this; the customer can change it before confirmation.",
    )

    rationale = models.TextField()
    proposed_treatment = models.TextField(
        help_text="Proposed next action / treatment. A concise proposal, not a full remediation workflow (PID §4)."
    )

    grounding_refs = models.JSONField(
        default=list,
        help_text="List of fact/asset references this risk was grounded in (PID §10).",
    )
    assumptions = models.JSONField(
        default=list,
        help_text="List of unresolved assumptions/unknowns (PID §11).",
    )

    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT_AI_SUGGESTED
    )

    ai_invocation_record = models.ForeignKey(
        AIInvocationRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_risks",
        help_text="The AI generation run that produced this risk. Null for a manually-created risk.",
    )

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_risks",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    dismissed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dismissed_risks",
    )
    dismissed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.organisation}) [{self.status}]"

    # --- Deterministic scoring (PID §8.2) -----------------------------------
    # Properties, not stored columns: there is no save-path anywhere - AI
    # persistence, manual edit, admin - that can write a score/band value
    # independently of impact/likelihood, so a stale or AI-supplied score can
    # never exist.
    @property
    def score(self) -> int:
        return score_for(self.impact, self.likelihood)

    @property
    def risk_band(self) -> str:
        return band_for(self.score)

    @property
    def risk_band_label(self) -> str:
        return RISK_BAND_LABELS[self.risk_band]
