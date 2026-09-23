"""
Product UI for the Remediation Action domain (PID §6.5, §13, §18).

Tenant scoping mirrors organisations.views.get_member_organisation_or_404
and risk_register.views._get_member_risk_or_404 exactly:
`_get_member_action_or_404` below verifies organisation membership first
(an ordinary 404 for a non-member or a manipulated/foreign organisation
id), then looks the action up scoped to that organisation - there is no
code path where an action from a different organisation could be read or
acted on via a mismatched/foreign action id in the URL.

Status-transition views are POST-only, same pattern as
risk_register.views.risk_confirm/risk_dismiss and
key_assets.views.key_asset_confirm/dismiss.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from organisations.views import get_member_organisation_or_404
from remediation import services
from remediation.forms import ActionEvidenceAttachForm, RemediationActionForm
from remediation.models import RemediationAction
from remediation.services import RemediationServiceError
from risk_register.models import Risk


def _get_member_action_or_404(user, organisation_id, action_id):
    organisation = get_member_organisation_or_404(user, organisation_id)
    action = get_object_or_404(RemediationAction, id=action_id, organisation=organisation)
    return organisation, action


@login_required
def action_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    actions = list(
        RemediationAction.objects.filter(organisation=organisation).select_related(
            "risk", "key_asset", "assigned_to", "created_by"
        )
    )

    status_filter = request.GET.get("status", "")
    valid_statuses = dict(RemediationAction.STATUS_CHOICES)
    if status_filter not in valid_statuses:
        status_filter = ""

    def _group(status):
        if status_filter and status_filter != status:
            return []
        return [a for a in actions if a.status == status]

    context = {
        "organisation": organisation,
        "status_filter": status_filter,
        "status_choices": RemediationAction.STATUS_CHOICES,
        "open_actions": _group(RemediationAction.STATUS_OPEN),
        "in_progress_actions": _group(RemediationAction.STATUS_IN_PROGRESS),
        "done_actions": _group(RemediationAction.STATUS_DONE),
        "accepted_actions": _group(RemediationAction.STATUS_ACCEPTED),
    }
    return render(request, "remediation/list.html", context)


@login_required
def action_create(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = RemediationActionForm(request.POST, organisation=organisation)
        if form.is_valid():
            action = form.save(commit=False)
            action.organisation = organisation
            action.created_by = request.user
            action.save()
            messages.success(request, f'Remediation action "{action.title}" created.')
            return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)
        messages.error(request, "The action could not be created. Please check the errors below.")
    else:
        form = RemediationActionForm(organisation=organisation)

    return render(
        request,
        "remediation/form.html",
        {"organisation": organisation, "form": form, "is_new": True, "risk": None},
    )


@login_required
def action_create_from_risk(request, organisation_id, risk_id):
    """
    Explicit "create action from risk" flow (PID §13):

        Risk -> Create action -> pre-filled title/description from
        proposed_treatment -> user reviews/edits -> Open action

    Creation only happens on an explicit POST that the user reviewed via
    this real form - never automatically for every risk (PID §13
    "Creation is explicit").
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    risk = get_object_or_404(Risk, id=risk_id, organisation=organisation)

    if request.method == "POST":
        form = RemediationActionForm(request.POST, organisation=organisation)
        if form.is_valid():
            action = form.save(commit=False)
            action.organisation = organisation
            action.risk = risk
            action.created_by = request.user
            action.save()
            messages.success(
                request, f'Remediation action "{action.title}" created from this risk.'
            )
            return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)
        messages.error(request, "The action could not be created. Please check the errors below.")
    else:
        # Pre-filled, not auto-created - the user still reviews/edits this
        # form and submits it explicitly (PID §13).
        initial = {"title": risk.title, "description": risk.proposed_treatment}
        if risk.key_asset_id:
            initial["key_asset"] = risk.key_asset_id
        form = RemediationActionForm(initial=initial, organisation=organisation)

    return render(
        request,
        "remediation/form.html",
        {"organisation": organisation, "form": form, "is_new": True, "risk": risk},
    )


@login_required
def action_detail(request, organisation_id, action_id):
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)
    evidence_links = action.evidence_links.select_related("evidence", "linked_by")
    attach_form = ActionEvidenceAttachForm(organisation=organisation)
    return render(
        request,
        "remediation/detail.html",
        {
            "organisation": organisation,
            "action": action,
            "evidence_links": evidence_links,
            "attach_evidence_form": attach_form,
        },
    )


@login_required
def action_attach_evidence(request, organisation_id, action_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)

    form = ActionEvidenceAttachForm(request.POST, organisation=organisation)
    if form.is_valid():
        evidence = form.cleaned_data["evidence"]
        try:
            services.attach_evidence_to_action(
                organisation=organisation,
                action=action,
                evidence=evidence,
                linked_by=request.user,
            )
        except RemediationServiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request, f'Evidence "{evidence.title}" attached to "{action.title}".'
            )
    else:
        messages.error(request, "The evidence could not be attached. Please check the errors below.")

    return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)


@login_required
def action_edit(request, organisation_id, action_id):
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)

    if request.method == "POST":
        form = RemediationActionForm(request.POST, instance=action, organisation=organisation)
        if form.is_valid():
            form.save()
            messages.success(request, f'Action "{action.title}" updated.')
            return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)
        messages.error(request, "The action could not be saved. Please check the errors below.")
    else:
        form = RemediationActionForm(instance=action, organisation=organisation)

    return render(
        request,
        "remediation/form.html",
        {"organisation": organisation, "form": form, "action": action, "is_new": False, "risk": action.risk},
    )


@login_required
def action_start(request, organisation_id, action_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)

    if action.status != RemediationAction.STATUS_OPEN:
        messages.error(request, "Only an open action can be moved to in progress.")
        return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)

    action.status = RemediationAction.STATUS_IN_PROGRESS
    action.save(update_fields=["status", "updated_at"])
    messages.success(request, f'Action "{action.title}" is now in progress.')
    return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)


@login_required
def action_complete(request, organisation_id, action_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)

    if action.status not in RemediationAction.ACTIVE_STATUSES:
        messages.error(request, "Only an open or in-progress action can be marked done.")
        return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)

    # Deliberately touches ONLY this RemediationAction row. Never writes to
    # risk_register.Risk or security_baseline.BaselineAnswer - see the
    # module docstring in remediation/models.py for why that is a
    # non-negotiable invariant, not an oversight.
    action.status = RemediationAction.STATUS_DONE
    action.completed_by = request.user
    action.completed_at = timezone.now()
    action.save(update_fields=["status", "completed_by", "completed_at", "updated_at"])
    messages.success(
        request,
        f'Action "{action.title}" marked done. This does not automatically change the '
        "linked risk or security-baseline answer — update those separately if appropriate.",
    )
    return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)


@login_required
def action_accept(request, organisation_id, action_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)

    if action.status not in RemediationAction.ACTIVE_STATUSES:
        messages.error(request, "Only an open or in-progress action can be accepted.")
        return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)

    # Same non-negotiable invariant as action_complete above: this touches
    # ONLY this row, never Risk or BaselineAnswer.
    action.status = RemediationAction.STATUS_ACCEPTED
    action.completed_by = request.user
    action.completed_at = timezone.now()
    action.save(update_fields=["status", "completed_by", "completed_at", "updated_at"])
    messages.success(
        request,
        f'Action "{action.title}" accepted. This means the organisation consciously '
        "accepts this issue for now — it does not mean the underlying control "
        "requirement is met.",
    )
    return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)
