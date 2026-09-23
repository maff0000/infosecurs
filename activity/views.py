"""
Minimal read-only Activity timeline (M003 PID §18, §12).

Kept deliberately simple, per this dispatch's own instructions: only
`control_answer_changed` has a real emitter yet, so there is not much to
show. A later integration/UX dispatch may extend this once evidence/action
events exist to display alongside it.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from activity.models import ActivityEvent
from organisations.views import get_member_organisation_or_404

PAGE_SIZE = 50


@login_required
def activity_list(request, organisation_id):
    """
    Tenant-scoped, paginated, read-only activity list for one organisation.

    Uses the same `get_member_organisation_or_404` lookup every other
    org-scoped view in this codebase uses, so the tenant scope is baked
    into the lookup itself. There is no POST/PUT/DELETE handling here or
    anywhere in this app - the timeline is read-only from the product
    (PID §23).
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    events = ActivityEvent.objects.filter(organisation=organisation).select_related("actor")
    paginator = Paginator(events, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "activity/list.html",
        {
            "organisation": organisation,
            "page_obj": page_obj,
        },
    )
