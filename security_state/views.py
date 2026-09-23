"""
Read-only Current Security State views (M003 PID §18).

Tenant scoping mirrors every other org-scoped view in this codebase:
`get_member_organisation_or_404` bakes the membership check into the
lookup itself. There is no POST/PUT/DELETE handling anywhere in this app
- see security_state/models.py's docstring: this app never writes
anything, including to itself (it has no models).
"""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from activity.models import ActivityEvent
from organisations.views import get_member_organisation_or_404
from remediation.models import RemediationAction
from security_baseline.catalogue import CATALOGUE_BY_KEY
from security_state.services import get_security_state


@login_required
def security_state_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    rows = get_security_state(organisation)

    return render(
        request,
        "security_state/list.html",
        {"organisation": organisation, "rows": rows},
    )


@login_required
def security_state_detail(request, organisation_id, control_key):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    catalogue_entry = CATALOGUE_BY_KEY.get(control_key)
    if catalogue_entry is None:
        raise Http404

    # get_security_state already filters everything to `organisation`, so
    # the row for a control key outside this organisation's data simply
    # reflects "no answer yet" (Not confirmed) rather than leaking another
    # organisation's state - there is no cross-tenant lookup path here at
    # all, since control_key is global catalogue data, not a per-tenant id.
    rows = {row["control_key"]: row for row in get_security_state(organisation)}
    row = rows[control_key]

    actions = list(
        RemediationAction.objects.filter(
            organisation=organisation, control_key=control_key
        ).select_related("assigned_to", "created_by")
    )
    events = list(
        ActivityEvent.objects.filter(
            organisation=organisation, control_key=control_key
        ).select_related("actor")
    )

    return render(
        request,
        "security_state/detail.html",
        {
            "organisation": organisation,
            "row": row,
            "open_actions": [a for a in actions if not a.is_closed],
            "closed_actions": [a for a in actions if a.is_closed],
            "events": events,
        },
    )
