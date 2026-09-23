"""
Governance domain service functions (ADR-0002 §4, PID §7-8).

Two entry points, mirroring this codebase's single-writer-function
discipline (evidence.link_services, remediation.services,
security_baseline.services):

- `ensure_account_holder_person` - this app's whole public contract with
  the rest of the product for Round 1 (see the PL dispatch note this
  function was built against). The PL wires this in with one line inside
  `organisations.views.organisation_create`'s existing transaction, right
  after the `OrganisationMembership` is created - keep this signature
  stable.
- `assign_role` - the one write path for `GovernanceRoleAssignment`,
  used by both the role-assignment view (governance.views) and
  `ensure_account_holder_person`'s own default-all-three-roles step, so
  the same-organisation guard and the "exactly one row per role" upsert
  behaviour live in exactly one place.
"""
from __future__ import annotations

from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
from organisations.models import OrganisationMembership

from governance.models import GovernanceRoleAssignment, OrganisationPerson


class GovernanceServiceError(Exception):
    """
    Raised when a governance-domain service function must refuse an
    operation - mirrors `remediation.services.RemediationServiceError`: a
    defence-in-depth guard a service function enforces for itself, not
    only trusted to form/view validation (PID §7 "linked User... must
    belong to the same organisation"; PID §26 "cross-tenant assignment
    impossible... rejected at the service layer, not just the form").
    """


def _require_user_organisation_membership(organisation, user):
    """
    PID §7's same-organisation constraint on `OrganisationPerson.user`.
    See `OrganisationPerson`'s docstring for why this cannot be a single
    model-level constraint instead.
    """
    if user is None:
        return
    if not OrganisationMembership.objects.filter(organisation=organisation, user=user).exists():
        raise GovernanceServiceError(
            "Cannot link a user to an OrganisationPerson unless they are a member of that organisation."
        )


def _derive_full_name(user) -> str:
    """
    Best-effort display name from whatever this project's `User` model
    actually has populated (PID/dispatch note: "this project may be using
    Django's stock auth.User, which has first_name/last_name, possibly
    both blank for a synthetic test user").

    Falls back, in order, to: first_name + last_name -> username ->
    get_username() -> a fixed literal. `full_name` is a required,
    non-blank field on `OrganisationPerson`, so this never returns an
    empty string - even a synthetic test user created with only a
    username must get a usable value.
    """
    first_name = (getattr(user, "first_name", "") or "").strip()
    last_name = (getattr(user, "last_name", "") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name

    username = (getattr(user, "username", "") or "").strip()
    if username:
        return username

    get_username = getattr(user, "get_username", None)
    if callable(get_username):
        fallback = (get_username() or "").strip()
        if fallback:
            return fallback

    return "Account holder"


@transaction.atomic
def assign_role(*, organisation, role, person, assigned_by=None):
    """
    Set `role`'s current assignee for `organisation` to `person` (PID §8).

    Cross-tenant guard (PID §26 "cross-tenant assignment impossible...
    must be rejected at the service layer, not just the form"): raises
    `GovernanceServiceError` if `person.organisation` is not `organisation`
    itself, before anything is written.

    Reassignment is a single atomic upsert of the one
    (organisation, role) row - `update_or_create` against the model's own
    `unique_active_assignee_per_role` constraint, so it is impossible for
    this function to ever leave a role with zero or two active assignees,
    and reassigning one role never touches the row for either of the other
    two roles (each role is its own row, keyed independently).

    Activity (M004-1d-closeout, PID §22): emits a `governance_role_changed`
    `ActivityEvent` (`activity.services.record_event`) whenever the role's
    assignee actually changes - including the very first assignment (no
    prior row for this (organisation, role) at all) and every genuine
    reassignment. The prior assignee is read *before* the
    `update_or_create` call below (same before/after-comparison discipline
    as `security_baseline.services.save_baseline_answers`'s
    `control_answer_changed` emitter), so a call that resolves to the same
    person already holding the role is a true no-op for the event log -
    even though `update_or_create` still refreshes `assigned_at`/
    `assigned_by` on the row itself, only a genuine assignee change is
    "meaningful" enough to record (M003 Learning Signal Capture Addendum
    §3).
    """
    if person.organisation_id != organisation.id:
        raise GovernanceServiceError(
            "Cannot assign a person belonging to a different organisation to a governance role."
        )

    previous_assignment = GovernanceRoleAssignment.objects.filter(
        organisation=organisation, role=role
    ).first()
    previous_person = previous_assignment.person if previous_assignment is not None else None

    assignment, _created = GovernanceRoleAssignment.objects.update_or_create(
        organisation=organisation,
        role=role,
        defaults={"person": person, "assigned_by": assigned_by},
    )

    if previous_person is None or previous_person.id != person.id:
        record_event(
            organisation,
            ActivityEvent.EVENT_GOVERNANCE_ROLE_CHANGED,
            actor=assigned_by,
            metadata={
                "role": role,
                "previous_person_id": str(previous_person.id) if previous_person else None,
                "previous_person_name": previous_person.full_name if previous_person else None,
                "new_person_id": str(person.id),
                "new_person_name": person.full_name,
            },
        )
    return assignment


@transaction.atomic
def ensure_account_holder_person(organisation, user):
    """
    Idempotently create (or return the existing) `OrganisationPerson` for
    `user` within `organisation`, and default all three governance roles
    to that person the first time this is called for the organisation
    (ADR-0002 §4, PID §6-8).

    This is the exact integration point named in the dispatch that built
    this app: the PL calls
    `governance.services.ensure_account_holder_person(organisation,
    request.user)` as a single added line inside
    `organisations.views.organisation_create`, immediately after that
    view's existing `OrganisationMembership.objects.create(...)` call, and
    inside the same transaction. Keep this exact name/signature -
    `(organisation, user)` positional - stable; other code depends on it
    without re-deriving this function's reasoning.

    Idempotency (calling this twice for the same organisation/user must
    not create a second `OrganisationPerson` or duplicate/corrupt the role
    assignments):
      - the person lookup is by (organisation, user) - if one already
        exists it is returned as-is, never re-created or overwritten
        (an Account Holder's own edits to their name/title, made later
        through the product, must never be clobbered by a second sign-in);
      - the role-defaulting step only runs "if no role assignments exist
        yet for this organisation at all" - once any role row exists (from
        this function's own first call, or from a later explicit
        reassignment through `assign_role`), a second call is a safe
        no-op for the role step, and the existing `person` is returned.

    Same-organisation enforcement (PID §7): delegates to
    `_require_user_organisation_membership` before creating or reusing
    anything. In the intended call site this always passes - the PL wires
    this call in *after* the `OrganisationMembership` row already exists
    in the same transaction - but the check still runs for any other
    caller (including this app's own tests).
    """
    _require_user_organisation_membership(organisation, user)

    person = OrganisationPerson.objects.filter(organisation=organisation, user=user).first()
    if person is None:
        person = OrganisationPerson.objects.create(
            organisation=organisation,
            user=user,
            full_name=_derive_full_name(user),
            job_title="",
            email=getattr(user, "email", "") or "",
        )
        # Only on the genuine first creation, never on the idempotent
        # no-op return path above (PID §22 `organisation_person_created`).
        record_event(
            organisation,
            ActivityEvent.EVENT_ORGANISATION_PERSON_CREATED,
            actor=user,
            related_object_type="organisation_person",
            related_object_id=str(person.id),
            metadata={"full_name": person.full_name},
        )

    if not GovernanceRoleAssignment.objects.filter(organisation=organisation).exists():
        for role, _label in GovernanceRoleAssignment.ROLE_CHOICES:
            assign_role(organisation=organisation, role=role, person=person, assigned_by=user)

    return person
