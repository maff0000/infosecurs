from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from organisations.views import get_member_organisation_or_404

from risk_register.forms import RiskEditForm
from risk_register.models import Risk
from risk_register.services import generate_draft_risks


def _get_member_risk_or_404(user, organisation_id, risk_id):
    """
    Tenant-scoped risk fetch, mirroring
    organisations.views.get_member_organisation_or_404 and
    key_assets.views._get_member_key_asset_or_404: membership is verified
    first (an ordinary 404 for a non-member or a manipulated/foreign
    organisation id), then the risk is looked up scoped to that
    organisation - there is no code path where a risk from a different
    organisation could be read or acted on via a mismatched/foreign risk id
    in the URL (PID.md M002 §16).
    """
    organisation = get_member_organisation_or_404(user, organisation_id)
    risk = get_object_or_404(Risk, id=risk_id, organisation=organisation)
    return organisation, risk


@login_required
def risk_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    risks = list(Risk.objects.filter(organisation=organisation))
    context = {
        "organisation": organisation,
        "draft_risks": [r for r in risks if r.status == Risk.STATUS_DRAFT_AI_SUGGESTED],
        "confirmed_risks": [r for r in risks if r.status == Risk.STATUS_CONFIRMED],
        "dismissed_risks": [r for r in risks if r.status == Risk.STATUS_DISMISSED],
    }
    return render(request, "risk_register/list.html", context)


@login_required
def risk_generate(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    # PID §0.6/§0.7 (M002-3b dispatch): generation is now a deterministic
    # scenario-instantiation pass - no AI call, no gateway, and therefore
    # nothing here that can fail with a gateway/network error. It can only
    # ever add new draft Risk rows or find nothing new to propose; existing
    # confirmed/dismissed risks are structurally untouched either way (see
    # risk_register.scenario_engine's dedup rule).
    created = generate_draft_risks(organisation)
    if created:
        messages.success(
            request,
            f"Generated {len(created)} new AI-suggested risk(s) for review.",
        )
    else:
        messages.success(
            request,
            "Risk generation completed but did not propose any new risks. "
            "This can happen if there are no confirmed key assets yet, or "
            "every applicable scenario for your confirmed assets and "
            "baseline answers was already generated previously.",
        )

    return redirect("risk_register:list", organisation_id=organisation.id)


@login_required
def risk_detail(request, organisation_id, risk_id):
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)
    return render(
        request,
        "risk_register/detail.html",
        {"organisation": organisation, "risk": risk},
    )


@login_required
def risk_edit(request, organisation_id, risk_id):
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)

    if risk.status != Risk.STATUS_DRAFT_AI_SUGGESTED:
        messages.error(
            request,
            "Only AI-suggested draft risks can be edited here. This risk has "
            "already been confirmed or dismissed.",
        )
        return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)

    if request.method == "POST":
        form = RiskEditForm(request.POST, instance=risk)
        if form.is_valid():
            form.save()
            messages.success(request, f'Risk "{risk.title}" updated.')
            return redirect(
                "risk_register:detail", organisation_id=organisation.id, risk_id=risk.id
            )
        messages.error(request, "The risk could not be saved. Please check the errors below.")
    else:
        form = RiskEditForm(instance=risk)

    return render(
        request,
        "risk_register/form.html",
        {"organisation": organisation, "risk": risk, "form": form},
    )


@login_required
def risk_confirm(request, organisation_id, risk_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)

    if risk.status != Risk.STATUS_DRAFT_AI_SUGGESTED:
        messages.error(request, "Only a draft AI suggestion can be confirmed.")
        return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)

    risk.status = Risk.STATUS_CONFIRMED
    risk.confirmed_by = request.user
    risk.confirmed_at = timezone.now()
    risk.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
    messages.success(request, f'Risk "{risk.title}" confirmed into the risk register.')
    return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)


@login_required
def risk_dismiss(request, organisation_id, risk_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)

    if risk.status != Risk.STATUS_DRAFT_AI_SUGGESTED:
        messages.error(request, "Only a draft AI suggestion can be dismissed.")
        return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)

    risk.status = Risk.STATUS_DISMISSED
    risk.dismissed_by = request.user
    risk.dismissed_at = timezone.now()
    risk.save(update_fields=["status", "dismissed_by", "dismissed_at", "updated_at"])
    messages.success(request, f'Risk "{risk.title}" dismissed.')
    return redirect("risk_register:list", organisation_id=organisation.id)
