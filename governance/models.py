"""
Tenant-owned Governance domain (ADR-0002 §4, docs/pids/M004-POLICY-FOUNDATION.md
§7-8).

This app extends - it does not replace - `organisations.OrganisationMembership`
(the authenticated tenant/membership boundary). `OrganisationPerson` is a
separate, deliberately lightweight concept: a named human relevant to
governance who does not necessarily have an Infosecurs login (ADR-0002 §3-4,
PID §6, §2.4 "one login does not mean one named person"). The Account
Holder's `OrganisationPerson` is the one row that *is* linked to a real
`User` (see `governance.services.ensure_account_holder_person`); any other
named person this app's role-assignment UX creates has `user=None` by
design - V1 builds no invitations/seat management (ADR-0002 §3).

`GovernanceRoleAssignment` models PID §8's "exactly one active assignee per
role" as one row per (organisation, role), enforced by a database
`UniqueConstraint`. Reassigning a role is therefore just an update of that
row's `person` FK, not a new row plus an end-dated old one - PID §8 asks
for "a small model... or three nullable FK fields... use your judgement";
this shape was chosen because it keeps "exactly one row per role" a single,
mechanically-enforced database fact rather than something a query has to
derive by filtering for "the currently active one" among several historical
rows. `governance.services.assign_role` is the one write path (mirrors
`evidence.link_services`/`remediation.services`'s single-writer-function
discipline elsewhere in this codebase) - no view/form constructs a
`GovernanceRoleAssignment` directly.
"""
import uuid

from django.conf import settings
from django.db import models

from organisations.models import Organisation


class OrganisationPerson(models.Model):
    """
    A named human relevant to governance (ADR-0002 §4, PID §7).

    Deliberately not a second "membership"/permission concept:
    `Organisation Membership` (organisations.models) remains the sole
    authenticated tenant boundary. `user` here is an optional pointer at
    *which* authenticated User this named person happens to be, for the one
    case V1 needs it (the Account Holder) - it is nullable/SET_NULL because
    losing the login link (e.g. a future admin action) must never delete
    the governance record of who this person is (PID §7 "optional linked
    local User").

    Same-organisation enforcement (PID §7 "linked User, where present, must
    belong to the same organisation") lives in
    `governance.services._require_user_organisation_membership`, a service-
    layer check, not solely a form/model validator - the same defence-in-
    depth discipline `evidence.link_services.link_evidence_to_control`
    already applies to its own same-organisation check (see that
    function's docstring). It is intentionally *not* a model-level
    `clean()`/constraint here for the same structural reason
    `ControlEvidenceLink`'s docstring gives for its own equivalent check:
    "this organisation" and "this user's organisation(s)" are two
    independent relations (a FK on this row vs. rows on a different table,
    `OrganisationMembership`), which a single-table database constraint
    cannot express.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="governance_people"
    )

    full_name = models.CharField(max_length=255)
    job_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Leave blank if not yet confirmed - e.g. immediately after sign-up, before the Account Holder has reviewed their details.",
    )
    email = models.EmailField(blank=True, default="")

    # Nullable/SET_NULL, not CASCADE - see class docstring. Only the
    # Account Holder's row is expected to be linked in V1
    # (governance.services.ensure_account_holder_person); other named
    # people this app's role-assignment UX creates have user=None.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="governance_people",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive people remain visible/assignable-history but are excluded from new role assignment.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            # Idempotency backstop (PID §7 "created idempotently") for the
            # one case this app links a person to a login: two
            # OrganisationPerson rows for the same (organisation, user)
            # pair would be ambiguous about "which one is the Account
            # Holder's". A partial constraint (user IS NOT NULL) because
            # every *other* named person in V1 has user=None by design and
            # must not be limited to one row - only the linked-user case
            # needs to be unique.
            models.UniqueConstraint(
                fields=["organisation", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_linked_user_per_organisation",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.organisation})"


class GovernanceRoleAssignment(models.Model):
    """
    "Which OrganisationPerson currently holds this governance role" (PID
    §8). See module docstring for why this is one row per
    (organisation, role) rather than an end-dated history table.
    """

    ROLE_POLICY_AUTHORISER = "policy_authoriser"
    ROLE_SECURITY_RESPONSIBLE = "security_responsible"
    ROLE_SENIOR_LEADERSHIP = "senior_leadership"
    ROLE_CHOICES = [
        (ROLE_POLICY_AUTHORISER, "Policy authoriser"),
        (ROLE_SECURITY_RESPONSIBLE, "Security responsible person"),
        (ROLE_SENIOR_LEADERSHIP, "Senior leadership representative"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="governance_role_assignments"
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    # PROTECT, not CASCADE: this app builds no OrganisationPerson delete
    # path at all (people are deactivated via `is_active`, never removed -
    # PID §7 "do not duplicate... merely because they hold several roles"
    # implies people are a durable record, and PID §26 "inactive-person
    # handling explicit" is answered by leaving the assignment in place,
    # see `assignee_is_inactive` below). PROTECT means that if a delete
    # path is ever added later, it cannot silently leave a role with zero
    # assignees - the very thing PID §8 "exactly one active assignee"
    # rules out.
    person = models.ForeignKey(
        OrganisationPerson, on_delete=models.PROTECT, related_name="role_assignments"
    )
    assigned_at = models.DateTimeField(auto_now=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="governance_role_assignments_made",
    )

    class Meta:
        ordering = ["role"]
        constraints = [
            # PID §8 "each role has exactly one active assignee" - the
            # mechanically-enforced fact this whole model shape exists to
            # guarantee. governance.services.assign_role reassigns by
            # updating this row's `person`, never by inserting a second
            # row for the same (organisation, role).
            models.UniqueConstraint(
                fields=["organisation", "role"], name="unique_active_assignee_per_role"
            ),
        ]

    def __str__(self):
        return f"{self.get_role_display()}: {self.person.full_name} ({self.organisation})"

    @property
    def assignee_is_inactive(self) -> bool:
        """
        PID §26 "inactive-person handling explicit": chosen behaviour is
        that marking the currently-assigned `OrganisationPerson` inactive
        never silently clears or reassigns their role - the assignment row
        is left exactly as it was (governance.services.assign_role is the
        only thing that ever changes `person`, and nothing here calls it
        automatically). This property is how callers (the role-assignment
        view/template, and this app's own tests) surface that explicitly,
        so an inactive assignee is shown as a visible warning rather than
        rendered identically to an active one.
        """
        return not self.person.is_active
