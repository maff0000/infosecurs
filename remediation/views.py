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
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_event
from entitlements.decorators import require_capability
from organisations.views import get_member_organisation_or_404
from remediation import services
from remediation.forms import ActionEvidenceAttachForm, RemediationActionForm
from remediation.models import RemediationAction
from remediation.services import RemediationServiceError
from risk_register.methodology import CATALOGUE_BY_ID
from risk_register.models import Risk


def _get_member_action_or_404(user, organisation_id, action_id):
    organisation = get_member_organisation_or_404(user, organisation_id)
    action = get_object_or_404(RemediationAction, id=action_id, organisation=organisation)
    return organisation, action


@login_required
@require_capability()
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
@require_capability()
def action_create(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = RemediationActionForm(request.POST, organisation=organisation)
        if form.is_valid():
            action = form.save(commit=False)
            action.organisation = organisation
            action.created_by = request.user
            # M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 10: no risk/
            # scenario to derive curated text from on this general,
            # no-risk path - left blank rather than reintroducing any
            # customer-typed free text (see RemediationActionForm's own
            # docstring for this dispatch's documented judgement call).
            action.description = ""
            with transaction.atomic():
                action.save()
                record_event(
                    organisation,
                    ActivityEvent.EVENT_ACTION_CREATED,
                    actor=request.user,
                    control_key=action.control_key,
                    related_object_type="remediation_action",
                    related_object_id=str(action.id),
                    metadata={"title": action.title, "created_from_risk": False},
                )
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


def _scenario_description_for(risk) -> str:
    """
    The curated, verbatim, non-editable action description for an action
    created from `risk` (M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 10):
    the matched `risk_register.methodology` scenario's own
    `suggested_treatment` text - NOT `risk.proposed_treatment` (that column
    now stores a closed-form treatment-CATEGORY code, per row 9's own
    replacement, not the treatment text itself; reading it here post-WI3
    would silently store a code string like "treatment_mitigate_suggested"
    as the action's description, which this function exists to avoid).

    Returns `""` if `risk.scenario_id` doesn't resolve in the current
    catalogue (a retired scenario, or a manually-created risk with no
    scenario at all) - the same "no scenario to derive curated text from"
    case `action_create`'s own no-risk path hits, handled identically
    (blank, never a fallback to open text).
    """
    scenario = CATALOGUE_BY_ID.get(risk.scenario_id)
    return scenario.suggested_treatment if scenario is not None else ""


@login_required
@require_capability()
def action_create_from_risk(request, organisation_id, risk_id):
    """
    Explicit "create action from risk" flow (PID §13):

        Risk -> Create action -> description verbatim from the matched
        scenario's suggested_treatment -> user reviews/edits title etc. ->
        Open action

    Creation only happens on an explicit POST that the user reviewed via
    this real form - never automatically for every risk (PID §13
    "Creation is explicit").

    M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 10: `description` is no
    longer a form field at all (see `RemediationActionForm`'s own
    docstring) - it is set programmatically, verbatim, from
    `_scenario_description_for(risk)` on every save below, regardless of
    anything a POST body claims for a "description" key (there is no such
    form field left to even bind it to).
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    risk = get_object_or_404(Risk, id=risk_id, organisation=organisation)
    description = _scenario_description_for(risk)

    if request.method == "POST":
        form = RemediationActionForm(request.POST, organisation=organisation)
        if form.is_valid():
            action = form.save(commit=False)
            action.organisation = organisation
            action.risk = risk
            action.created_by = request.user
            action.description = description
            with transaction.atomic():
                action.save()
                record_event(
                    organisation,
                    ActivityEvent.EVENT_ACTION_CREATED,
                    actor=request.user,
                    control_key=action.control_key,
                    related_object_type="remediation_action",
                    related_object_id=str(action.id),
                    metadata={
                        "title": action.title,
                        "created_from_risk": True,
                        "risk_id": str(risk.id),
                    },
                )
            messages.success(
                request, f'Remediation action "{action.title}" created from this risk.'
            )
            return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)
        messages.error(request, "The action could not be created. Please check the errors below.")
    else:
        # Pre-filled, not auto-created - the user still reviews/edits
        # title/priority/control/asset/assignment and submits this form
        # explicitly (PID §13). `description` is shown read-only on the
        # template (see remediation/templates/remediation/form.html), not
        # as an initial form value - there is no form field for it any
        # more to pre-fill.
        initial = {"title": risk.title}
        if risk.key_asset_id:
            initial["key_asset"] = risk.key_asset_id
        form = RemediationActionForm(initial=initial, organisation=organisation)

    return render(
        request,
        "remediation/form.html",
        {
            "organisation": organisation,
            "form": form,
            "is_new": True,
            "risk": risk,
            "description_preview": description,
        },
    )


@login_required
@require_capability()
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
@require_capability()
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
@require_capability()
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
@require_capability()
def action_start(request, organisation_id, action_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)

    if action.status != RemediationAction.STATUS_OPEN:
        messages.error(request, "Only an open action can be moved to in progress.")
        return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)

    previous_status = action.status
    action.status = RemediationAction.STATUS_IN_PROGRESS
    with transaction.atomic():
        action.save(update_fields=["status", "updated_at"])
        record_event(
            organisation,
            ActivityEvent.EVENT_ACTION_STATUS_CHANGED,
            actor=request.user,
            control_key=action.control_key,
            related_object_type="remediation_action",
            related_object_id=str(action.id),
            metadata={"previous_status": previous_status, "new_status": action.status},
        )
    messages.success(request, f'Action "{action.title}" is now in progress.')
    return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)


@login_required
@require_capability()
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
    previous_status = action.status
    action.status = RemediationAction.STATUS_DONE
    action.completed_by = request.user
    action.completed_at = timezone.now()
    with transaction.atomic():
        action.save(update_fields=["status", "completed_by", "completed_at", "updated_at"])
        record_event(
            organisation,
            ActivityEvent.EVENT_ACTION_STATUS_CHANGED,
            actor=request.user,
            control_key=action.control_key,
            related_object_type="remediation_action",
            related_object_id=str(action.id),
            metadata={"previous_status": previous_status, "new_status": action.status},
        )
    messages.success(
        request,
        f'Action "{action.title}" marked done. This does not automatically change the '
        "linked risk or security-baseline answer — update those separately if appropriate.",
    )
    return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)


@login_required
@require_capability()
def action_accept(request, organisation_id, action_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, action = _get_member_action_or_404(request.user, organisation_id, action_id)

    if action.status not in RemediationAction.ACTIVE_STATUSES:
        messages.error(request, "Only an open or in-progress action can be accepted.")
        return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)

    # Same non-negotiable invariant as action_complete above: this touches
    # ONLY this row, never Risk or BaselineAnswer.
    previous_status = action.status
    action.status = RemediationAction.STATUS_ACCEPTED
    action.completed_by = request.user
    action.completed_at = timezone.now()
    with transaction.atomic():
        action.save(update_fields=["status", "completed_by", "completed_at", "updated_at"])
        record_event(
            organisation,
            ActivityEvent.EVENT_ACTION_STATUS_CHANGED,
            actor=request.user,
            control_key=action.control_key,
            related_object_type="remediation_action",
            related_object_id=str(action.id),
            metadata={"previous_status": previous_status, "new_status": action.status},
        )
    messages.success(
        request,
        f'Action "{action.title}" accepted. This means the organisation consciously '
        "accepts this issue for now — it does not mean the underlying control "
        "requirement is met.",
    )
    return redirect("remediation:detail", organisation_id=organisation.id, action_id=action.id)
