"""
Tenant-owned Remediation Action domain (docs/pids/M003-EVIDENCE-AND-SECURITY-STATE.md
§6.5, §6.6, §13).

This app builds `RemediationAction` and `ActionEvidenceLink` (§6.6 -
deliberately minimal compared to evidence's `ControlEvidenceLink`: no
relationship type, just "this evidence is associated with this action,
especially completion evidence"). It still does not build `EvidenceItem`
or `ControlEvidenceLink` themselves (owned by the `evidence` app), the
Current Security State projection (§7), or the Activity timeline (§12,
owned by the `activity` app).

Core invariant this file exists to protect (§6.5, §13 - "non-negotiable"):
completing a `RemediationAction` (status -> `done` or `accepted`) must
NEVER automatically:
  - change a `security_baseline.BaselineAnswer` - enforced simply by this
    app never importing or writing to that model anywhere, full stop;
  - mark the linked `risk_register.Risk` resolved - enforced the same way:
    this app never writes to `Risk.status` anywhere, full stop;
  - claim a control is implemented - this is a UI-wording discipline (see
    remediation/templates/remediation/*.html and the STATUS_CHOICES labels
    below), not just a code discipline (PID §19 "AI suggested" / "Customer
    confirmed" wording-honesty precedent, applied here to "Accepted" vs
    "Done").

`status=accepted` specifically means the organisation consciously accepts
the issue/risk for now - it does NOT mean the underlying control
requirement is met (PID §6.5). This distinction is visible in the product,
not only in code comments - but (M006-AUDIT-0004 J1) as page copy next to
the status, not stuffed into the `STATUS_CHOICES` label itself: that label
is rendered inside a `.badge` pill (remediation/templates/remediation/
{list,detail}.html), so it stays a concise status token ("Accepted"), and
the fuller "not the same as done" wording lives as ordinary explanatory
text alongside it on both templates instead.
"""
import uuid

from django.conf import settings
from django.db import models

from key_assets.models import KeyAsset
from organisations.models import Organisation
from risk_register.models import Risk
from security_baseline.catalogue import CATALOGUE_BY_KEY


class RemediationAction(models.Model):
    """
    A tenant-owned remediation action (PID §6.5).

    Deliberately small: a fixed 4-state status field with ordinary
    transitions, not a configurable workflow engine (PID §6.5's explicit
    non-goal).
    """

    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_ACCEPTED = "accepted"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_DONE, "Done"),
        # M006-AUDIT-0004 J1: this label is rendered inside `.badge`
        # (remediation/templates/remediation/{list,detail}.html's
        # `{{ action.get_status_display }}`), so it must stay a concise
        # status token, not a full sentence - a sentence-length label
        # forced horizontal overflow at 375px (Central Architecture's own
        # bounded correction: "A badge should ideally carry the concise
        # state: 'Accepted'"). The "not the same as done" distinction
        # this label used to carry by itself is NOT lost - it already
        # exists, verbatim, as page copy OUTSIDE the badge on both
        # templates: list.html's "Accepted" section intro ("Consciously
        # accepted for now — this does not mean the underlying control
        # requirement is met.") and detail.html's `.accepted-note` block
        # ("Accepted, not resolved... The organisation has consciously
        # accepted this issue for now."). See this dispatch's report for
        # confirmation neither of those was touched.
        (STATUS_ACCEPTED, "Accepted"),
    ]
    # Statuses from which the action can still be actively worked.
    ACTIVE_STATUSES = (STATUS_OPEN, STATUS_IN_PROGRESS)
    # Statuses that leave the action's active pipeline. Both are terminal
    # dispositions for the *action*; neither one, by itself, is a claim
    # about the underlying control or risk (see module docstring).
    CLOSED_STATUSES = (STATUS_DONE, STATUS_ACCEPTED)

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_CRITICAL = "critical"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_CRITICAL, "Critical"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="remediation_actions"
    )

    title = models.CharField(max_length=255)
    description = models.TextField(
        blank=True,
        default="",
        help_text="What needs to be done. Pre-filled from a risk's proposed treatment when created from a risk.",
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    # --- Optional context references ---------------------------------------
    risk = models.ForeignKey(
        Risk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="remediation_actions",
        help_text="The risk this action addresses, if created from one (PID §13).",
    )
    control_key = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=(
            "Optional reference to a security_baseline catalogue control "
            "key. A plain CharField, not a ForeignKey - same convention as "
            "risk_register.Risk.scenario_id, since the catalogue is "
            "versioned Python data (security_baseline/catalogue.py), not a "
            "database table."
        ),
    )
    key_asset = models.ForeignKey(
        KeyAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="remediation_actions",
    )

    # --- People / dates -------------------------------------------------
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_remediation_actions",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_remediation_actions",
    )
    target_date = models.DateField(null=True, blank=True)

    # Set only when the action leaves the active pipeline (status ->
    # done or accepted) - see STATUS_TRANSITION views in remediation/views.py.
    # Never set by the general create/edit form.
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_remediation_actions",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.organisation}) [{self.status}]"

    @property
    def is_closed(self) -> bool:
        return self.status in self.CLOSED_STATUSES

    def control_key_label(self) -> str:
        """
        Human-readable label for `control_key`, looked up from the
        security_baseline catalogue (read-only reference - this app never
        writes to security_baseline). Falls back to the raw key if the
        catalogue does not (or no longer) contain it, so a historical
        action never renders blank/broken just because the catalogue
        evolved.
        """
        if not self.control_key:
            return ""
        entry = CATALOGUE_BY_KEY.get(self.control_key)
        return entry["area"] if entry else self.control_key


class ActionEvidenceLink(models.Model):
    """
    Associates an `evidence.EvidenceItem` with a `RemediationAction` (PID
    §6.6), "especially completion evidence". Deliberately minimal compared
    to evidence's own `ControlEvidenceLink`: no relationship type (support/
    contradict/context) - just "this evidence is associated with this
    action". Attach-only for M003 V1 (PID §19's Actions mechanical-test
    list requires only "evidence can attach"; no unlink capability exists
    here).

    This association does not, by itself or via any code path in this app,
    change `RemediationAction.status`, `risk_register.Risk.status`, or any
    `security_baseline.BaselineAnswer` (PID §6.6, §13) - see this module's
    docstring for how that invariant is protected app-wide.

    Cross-app FK to `evidence.EvidenceItem` via the string form
    ("evidence.EvidenceItem") rather than a direct import. Checked the
    actual app-import graph before choosing this: `evidence` does not
    import anything from `remediation` (no circular-import risk exists
    either way), but this is the first link from `remediation` to
    `evidence` at all, and the PID's own §6.6 minimum shape specifies the
    string form. Direct imports (`risk_register.Risk`, `key_assets.
    KeyAsset` above) remain the established in-file convention for
    apps `remediation` already depended on before this dispatch; the
    string form here keeps `remediation`'s import-time dependency on
    `evidence` from being introduced as a hard requirement, so a future
    app-ordering change on either side can't turn this into a real
    circular import by surprise.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="action_evidence_links"
    )
    action = models.ForeignKey(
        RemediationAction, on_delete=models.CASCADE, related_name="evidence_links"
    )
    evidence = models.ForeignKey(
        "evidence.EvidenceItem", on_delete=models.CASCADE, related_name="action_links"
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="action_evidence_links",
    )
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-linked_at"]
        indexes = [
            models.Index(fields=["organisation", "action"]),
        ]

    def __str__(self):
        return f"{self.evidence_id} -> {self.action_id} ({self.organisation})"
