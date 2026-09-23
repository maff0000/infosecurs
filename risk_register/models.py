"""
Tenant-owned risk domain (M002 PID §8, amended by PID §0).

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

Schema consequences of PID §0's derivation-spine correction (Asset ->
Exposure/Vulnerability/Control Gap -> Threat Event -> Consequence -> Risk
Scenario -> Likelihood x Impact -> Treatment), added by the M002-3a-schema
dispatch:

- `exposure`, `threat_event`, `consequence` are new fields naming the
  spine's distinct steps (PID §0.2's worked example). `vulnerability`
  already existed pre-amendment; it is reused/repurposed in place (its
  `help_text` is corrected below to the precise §0.2 sense - "what turns
  an exposure into something exploitable" - rather than being treated as
  a near-synonym of `exposure`, which is what its original help_text said).
- **Note for whoever builds the deterministic scenario-instantiation
  engine (a separate, later dispatch):** the pre-existing `threat` field
  (TextField, no help_text, part of the original pre-amendment shape) and
  the new `threat_event` field below look like they may end up meaning the
  same thing once that engine exists. This dispatch's scope is additive/
  corrective only, and its instructions named `threat_event` as a new
  field without saying to touch `threat` - so both exist here, side by
  side, deliberately unresolved. Flagged in this dispatch's report rather
  than guessed at.
- `scenario_id` is a new, plain (non-FK) `CharField` tracing a persisted
  risk back to the methodology-catalogue scenario that produced it - see
  the field's own `help_text` for why it is not a `ForeignKey`.
- `asset_reference` (the free-text field an AI response used to populate
  directly) is retired per PID §0.6/§0.7: application code owns asset
  identity going forward, and `key_asset` (the FK) is the only asset link.
  `key_asset` itself is unchanged.
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
    # `key_asset` is the only asset link (PID §0.6/§0.7): application code
    # populates it deterministically. The previous `asset_reference`
    # free-text field - which used to carry whatever raw string an AI
    # response supplied (e.g. "asset:<uuid>" or a profile-fact path such as
    # "profile.endpoint_management") - is retired: AI never originates an
    # identifier that becomes application state, so there is no longer a
    # raw/unresolved string for this field to preserve alongside the FK.
    key_asset = models.ForeignKey(
        KeyAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risks",
    )

    # --- Risk content --------------------------------------------------------
    title = models.CharField(max_length=255)

    exposure = models.TextField(
        default="",
        help_text=(
            "The inherent characteristic of the asset/context that creates "
            "the opportunity for a threat event (PID §0.2 derivation "
            "spine) - e.g. 'portable / leaves controlled premises' for a "
            "laptop. Distinct from `vulnerability`: an exposure alone is "
            "not yet exploitable."
        ),
    )
    threat = models.TextField()
    threat_event = models.TextField(
        default="",
        help_text=(
            "The specific event that could act on the exposure (PID §0.2 "
            "derivation spine) - e.g. 'loss or theft'. See this file's "
            "module docstring for a note on its relationship to the "
            "pre-existing `threat` field."
        ),
    )
    vulnerability = models.TextField(
        help_text=(
            "The vulnerability/control gap that turns `exposure` into "
            "something exploitable (PID §0.2 derivation spine) - e.g. the "
            "*absence* of full-disk encryption on a portable laptop. Not a "
            "synonym for `exposure`: an inherent characteristic (portable) "
            "is not itself a vulnerability - the missing/failed control is."
        )
    )
    consequence = models.TextField(
        default="",
        help_text=(
            "The consequence type if the risk scenario materialises (PID "
            "§0.2 derivation spine) - e.g. 'confidential information "
            "disclosure'."
        ),
    )
    scenario_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=(
            "Stable reference to the methodology-catalogue scenario (PID "
            "§0.4) that produced this risk. A plain CharField, not a "
            "ForeignKey: the catalogue is a Python data module, not a "
            "database table (intentional - the catalogue itself is built "
            "by a separate, parallel dispatch this schema does not depend "
            "on). Blank/nullable for a risk that doesn't (yet) trace to a "
            "specific catalogue scenario - but per PID §0.7, in M002 V1 "
            "every *persisted* Risk row should in practice always have "
            "one. This field is only where that trace lives; it is not "
            "itself the enforcement mechanism - that is a later "
            "dispatch's service-layer concern."
        ),
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
