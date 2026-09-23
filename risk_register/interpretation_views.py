"""
Small, additive trigger view for AI practitioner-interpretation (M002 PID
§0.6/§0.7 - M002-3c dispatch's "wire it in" instruction).

Deliberately a separate file/view, not a second step folded into
`risk_register.views.risk_generate`: the parallel `m002-3d-asset-ux`
dispatch was reworking `risk_register`/`key_assets` UI templates (including
`list.html`/`detail.html`) at the same time this view was built, so this
dispatch kept its own footprint to one new file plus one new `path()` entry
in `risk_register/urls.py`, deliberately not touching those templates
itself, to avoid a concurrent-edit collision.

The PL wired the actual "Ask AI to review drafts" button into
`risk_register/templates/risk_register/list.html` during Phase 3c/3d
integration, once both dispatches had landed and the collision risk no
longer applied - confirmed working end-to-end by a fresh FORGE Auditor's
real-browser pass (`docs/evidence/M002-AUDIT-0002.md`). This view's
contract (POST-only, tenant-scoped, updates existing draft `Risk` rows via
`risk_register.interpretation_service`, never creates one) is unchanged
from how it was built.
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
