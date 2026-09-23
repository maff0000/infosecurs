from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_event
from organisations.views import get_member_organisation_or_404

from risk_register.forms import RiskEditForm
from risk_register.models import Risk
from risk_register.services import generate_draft_risks

# The RiskEditForm fields whose before/after values are worth preserving as
# structured delta (Learning Signal Capture Addendum §3/§7): every field the
# form actually lets a customer change. Kept as an explicit list, mirrored
# from RiskEditForm.Meta.fields, rather than introspected from the form, so
# it is obvious at a glance which fields this event type covers.
_RISK_EDIT_DELTA_FIELDS = [
    "title",
    "threat",
    "vulnerability",
    "impact",
    "likelihood",
    "rationale",
    "proposed_treatment",
]


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

        # Snapshot the pre-change value of every editable field now, before
        # `form.is_valid()` is even called below - not merely before
        # `form.save()`. Django's `ModelForm._post_clean()` (invoked from
        # inside `full_clean()`, which `is_valid()` triggers) already calls
        # `construct_instance()` and sets the new field values directly
        # onto `self.instance` - i.e. onto `risk` - as a side effect of
        # validation itself, well before `.save()` persists anything. A
        # snapshot taken after `is_valid()` would already see the *new*
        # values on `risk`, not the "before" this event needs (Learning
        # Signal Capture Addendum §3/§7 - the same discipline
        # security_baseline.services.save_baseline_answers already uses for
        # control_answer_changed, where the previous answer is read from
        # the database before the write, not from a form-mutated instance).
        previous_values = {
            field: getattr(risk, field) for field in _RISK_EDIT_DELTA_FIELDS
        }

        if form.is_valid():
            with transaction.atomic():
                form.save()

                delta = {}
                for field in _RISK_EDIT_DELTA_FIELDS:
                    new_value = getattr(risk, field)
                    if new_value != previous_values[field]:
                        delta[field] = {
                            "previous": previous_values[field],
                            "new": new_value,
                        }

                if delta:
                    record_event(
                        organisation,
                        ActivityEvent.EVENT_RISK_SUGGESTION_EDITED,
                        actor=request.user,
                        related_object_type="risk",
                        related_object_id=str(risk.id),
                        metadata=delta,
                    )

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

    with transaction.atomic():
        risk.status = Risk.STATUS_DISMISSED
        risk.dismissed_by = request.user
        risk.dismissed_at = timezone.now()
        risk.save(update_fields=["status", "dismissed_by", "dismissed_at", "updated_at"])

        record_event(
            organisation,
            ActivityEvent.EVENT_RISK_SUGGESTION_DISMISSED,
            actor=request.user,
            related_object_type="risk",
            related_object_id=str(risk.id),
            metadata={
                "title": risk.title,
                "impact": risk.impact,
                "likelihood": risk.likelihood,
                "risk_band": risk.risk_band,
            },
        )

    messages.success(request, f'Risk "{risk.title}" dismissed.')
    return redirect("risk_register:list", organisation_id=organisation.id)
