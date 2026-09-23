"""
Small, additive trigger view for AI practitioner-interpretation (M002 PID
§0.6/§0.7 - M002-3c dispatch's "wire it in" instruction).

Deliberately a separate file/view, not a second step folded into
`risk_register.views.risk_generate`, and deliberately NOT wired into
`risk_register/templates/risk_register/list.html` or `detail.html` with a
visible button in this dispatch: the parallel `m002-3d-asset-ux` dispatch
is reworking `risk_register`/`key_assets` UI templates (including these
exact two files) at the same time this dispatch runs, per this dispatch's
own explicit instruction to "keep your view-layer footprint minimal and
additive... to reduce integration collision risk." A new, small, additive
view + one URL line is exactly that: this dispatch adds one new file here
and exactly one new `path()` entry to `risk_register/urls.py` - nothing
existing is restructured, and no template this dispatch does not own is
touched.

This is a real functional gap this report flags explicitly for the PL:
today there is no rendered link/button a browser user can click to reach
`risk_register:interpret` - it is fully exercised by the mechanical test
suite (Django test client POSTs directly to the URL) and by any later live
browser audit that is told to POST to it directly, but a real Customer
Zero user cannot discover it from the UI yet. Wiring an actual button into
`list.html`/`detail.html` is left to whichever dispatch next owns those
templates without a concurrent collision risk (3d's own integration, or a
follow-up dispatch after 3d lands) - not solved here, to avoid touching
files 3d is actively rewriting.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect

from organisations.views import get_member_organisation_or_404

from ai_platform.interpretation_orchestration import InterpretationFailed
from risk_register.interpretation_service import interpret_draft_risks


@login_required
def risk_interpret(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    try:
        updated = interpret_draft_risks(organisation)
    except InterpretationFailed:
        # PID §14 / this module's docstring point 5: a failed call leaves
        # every existing Risk row untouched - never surface the raw
        # exception (a GatewayError message, safe but internal/technical)
        # directly to the end user.
        messages.error(
            request,
            "AI interpretation could not be completed right now, so your "
            "existing risks were left unchanged. You can try again later, or "
            "review and confirm the risks as they are.",
        )
        return redirect("risk_register:list", organisation_id=organisation.id)

    if updated:
        messages.success(
            request,
            f"AI reviewed {len(updated)} draft risk(s) and refined their impact, "
            f"likelihood, rationale and proposed treatment. Still AI suggested - "
            f"nothing was confirmed automatically.",
        )
    else:
        messages.success(
            request,
            "No draft AI-suggested risks were available to interpret. Generate "
            "initial risks first.",
        )

    return redirect("risk_register:list", organisation_id=organisation.id)


__all__ = ["risk_interpret"]
