"""
Minimal draft-generation trigger + read-only draft view (M004 PID §3.9-11,
§14 - m004-2a-policy-foundation dispatch).

Deliberately minimal, mirroring `risk_register.interpretation_views`'s
"small, additive trigger view" shape: a "Generate policy" action plus a
plain read-only view of the resulting draft's sections/review_warnings.
The full section-editor/approval UX is explicitly out of scope for this
dispatch - a later dispatch's job (see `policy/models.py`'s module
docstring).
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from organisations.views import get_member_organisation_or_404

from ai_platform.policy_orchestration import PolicyGenerationFailed
from policy.models import PolicyVersion
from policy.services import generate_policy_draft


@login_required
def policy_detail(request, organisation_id):
    """Read-only view of this organisation's most recent `PolicyVersion`
    (if any), tenant-scoped the usual way."""
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    latest_version = (
        PolicyVersion.objects.filter(organisation=organisation)
        .order_by("-version_number")
        .first()
    )
    return render(
        request,
        "policy/detail.html",
        {"organisation": organisation, "version": latest_version},
    )


@login_required
def policy_generate(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    try:
        generate_policy_draft(organisation, actor=request.user)
    except PolicyGenerationFailed:
        # PID §14 / policy.services module docstring point 5: a failed call
        # creates nothing - never surface the raw exception (a
        # GatewayError message, safe but internal/technical) directly to
        # the end user.
        messages.error(
            request,
            "AI policy generation could not be completed right now, so "
            "nothing was created. You can try again later.",
        )
        return redirect("policy:detail", organisation_id=organisation.id)

    messages.success(request, "A new draft Information Security Policy has been generated.")
    return redirect("policy:detail", organisation_id=organisation.id)


__all__ = ["policy_detail", "policy_generate"]
