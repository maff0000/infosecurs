"""
The single writer for `Workplace` rows and for the derived
`OrganisationProfile.working_model` summary (ADR-0002 §5.2,
docs/pids/M004-POLICY-FOUNDATION.md §9.2).

Mirrors this codebase's existing single-writer discipline (e.g.
`security_baseline.services.save_baseline_answers`,
`activity.services.record_event`): callers never construct/mutate a
`Workplace` row directly, they call the functions below, so
`sync_working_model` is guaranteed to run - in the same transaction -
every time a workplace is created, edited, deactivated or reactivated.

Derivation rule (ADR-0002 §5.2 / PID §9.2, exact wording):
  - no active Workplace row for the organisation -> `unknown`;
  - all active Workplace rows are `distributed_home` -> `remote`;
  - active Workplace rows contain at least one non-home type and zero
    `distributed_home` rows -> `office`;
  - active Workplace rows contain a mix of `distributed_home` and
    non-home types -> `hybrid`.
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
from organisations.models import UNKNOWN, Organisation, OrganisationProfile

from workplace.models import Workplace

# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------
WORKING_MODEL_REMOTE = "remote"
WORKING_MODEL_OFFICE = "office"
WORKING_MODEL_HYBRID = "hybrid"


def compute_working_model(organisation: Organisation) -> str:
    """
    Pure computation of the derived `working_model` summary from an
    organisation's currently *active* `Workplace` rows. No side effects -
    `sync_working_model` below is the function that persists the result.
    """
    active_types = set(
        Workplace.objects.filter(organisation=organisation, is_active=True).values_list(
            "type", flat=True
        )
    )
    if not active_types:
        return UNKNOWN

    has_home = Workplace.TYPE_DISTRIBUTED_HOME in active_types
    non_home_types = active_types - {Workplace.TYPE_DISTRIBUTED_HOME}

    if has_home and not non_home_types:
        return WORKING_MODEL_REMOTE
    if non_home_types and not has_home:
        return WORKING_MODEL_OFFICE
    # has_home and non_home_types - a genuine mix.
    return WORKING_MODEL_HYBRID


def sync_working_model(organisation: Organisation) -> Optional[str]:
    """
    Recompute the derived `working_model` summary and write it to this
    organisation's `OrganisationProfile`, if one exists.

    Missing-profile handling (M001's `OrganisationProfile` is optional/
    created separately - PID §9.2 doesn't speak to this directly): if no
    `OrganisationProfile` row exists yet for the organisation, this
    silently does nothing and returns `None`. There is no profile row to
    keep synchronised yet, and creating a bare/empty `OrganisationProfile`
    as a side effect of a Workplace write would (a) require inventing a
    value for `legal_trading_name`, the profile's one required field, and
    (b) resurface as a phantom "profile started" state on the M001
    profile page for an organisation that has never actually completed
    its profile. Every M004 workplace write still calls this
    unconditionally (see below) so the summary is *always* correct the
    moment a profile does come to exist - nothing further needs to reach
    back and backfill it.

    Returns the derived value, or `None` if there was no profile to sync.
    """
    profile = OrganisationProfile.objects.filter(organisation=organisation).first()
    if profile is None:
        return None

    derived = compute_working_model(organisation)
    if profile.working_model != derived:
        profile.working_model = derived
        profile.save(update_fields=["working_model", "updated_at"])
    return derived


# ---------------------------------------------------------------------------
# Workplace mutation - every write goes through here, and every write
# resyncs the derived summary inside the same transaction (PID §9.2:
# "All M004 workplace writes must synchronise the derived summary
# transactionally").
# ---------------------------------------------------------------------------
@transaction.atomic
def create_workplace(
    *,
    organisation: Organisation,
    name: str,
    type: str,
    location_label: str = "",
    approx_people_count: Optional[int] = None,
    is_primary: bool = False,
    is_active: bool = True,
    actor,
) -> Workplace:
    """
    `actor` (M004-1d-closeout, PID §22): the user this creation is
    attributed to on the `workplace_created` `ActivityEvent` this function
    emits. A required keyword argument, not optional/defaulted - every
    caller (every `workplace/views.py` call site, and every direct-service
    test) has a real acting user in hand, so there is no legitimate
    system-initiated caller yet that would need a `None` escape hatch.
    """
    workplace = Workplace.objects.create(
        organisation=organisation,
        name=name,
        type=type,
        location_label=location_label,
        approx_people_count=approx_people_count,
        is_primary=is_primary,
        is_active=is_active,
    )
    sync_working_model(organisation)
    record_event(
        organisation,
        ActivityEvent.EVENT_WORKPLACE_CREATED,
        actor=actor,
        related_object_type="workplace",
        related_object_id=str(workplace.id),
        metadata={"name": workplace.name, "type": workplace.type},
    )
    return workplace


@transaction.atomic
def update_workplace(workplace: Workplace, *, actor, **fields) -> Workplace:
    """
    Update arbitrary model fields on an already tenant-scoped `Workplace`
    instance (the caller - a view or a test - is responsible for having
    fetched it scoped to the right organisation; this function does not
    re-derive tenant scope) and resync the derived summary. `fields` may
    include `is_active`, so this is also the code path
    `deactivate_workplace`/`activate_workplace` build on.

    `actor` (M004-1d-closeout, PID §22): required keyword argument, same
    reasoning as `create_workplace`'s - the user this update is attributed
    to on the `workplace_updated` `ActivityEvent`.

    Activity: emits `workplace_updated` only when at least one field's
    value genuinely changes (compared before any `setattr` below), same
    before/after discipline as `governance.services.assign_role`'s
    `governance_role_changed` emitter - a save that resubmits the same
    values is not a meaningful event. An activate/deactivate call is
    itself always a genuine `is_active` change in normal use, so it is
    always captured here too, with no special-casing needed in
    `deactivate_workplace`/`activate_workplace` below.
    """
    changed_fields = [
        field_name
        for field_name, value in fields.items()
        if getattr(workplace, field_name) != value
    ]
    for field_name, value in fields.items():
        setattr(workplace, field_name, value)
    workplace.save()
    sync_working_model(workplace.organisation)
    if changed_fields:
        record_event(
            workplace.organisation,
            ActivityEvent.EVENT_WORKPLACE_UPDATED,
            actor=actor,
            related_object_type="workplace",
            related_object_id=str(workplace.id),
            metadata={"changed_fields": changed_fields, "is_active": workplace.is_active},
        )
    return workplace


def deactivate_workplace(workplace: Workplace, *, actor) -> Workplace:
    return update_workplace(workplace, actor=actor, is_active=False)


def activate_workplace(workplace: Workplace, *, actor) -> Workplace:
    return update_workplace(workplace, actor=actor, is_active=True)
