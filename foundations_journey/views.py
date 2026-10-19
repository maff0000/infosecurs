"""
Guided Stage 4 card + task-handoff + pause/resume views (M010B PID §2/§4/
§5). Thin views: every mutation goes through `foundations_journey.
services`, which itself writes exclusively through `security_baseline.
services.record_structured_baseline_answer` and `security_tasks.services.
create_task` - never a direct model write here.

Same established three-layer access-control stack every other
organisation-scoped view in this codebase already uses
(`@login_required` + `@require_capability()` +
`organisations.views.get_member_organisation_or_404` as the view's own
first action) - verified by direct read of `security_baseline.views`/
`security_tasks.views` before writing this file. A non-member gets the
same ordinary `Http404` every other route in this codebase already
gives.
"""
from __future__ import annotations

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from entitlements.decorators import require_capability
from organisations.views import get_member_organisation_or_404

from foundations_journey import services
from foundations_journey.exceptions import (
    ConcurrentCheckpointModificationError,
    InvalidFoundationsOptionError,
    NoFollowUpTaskAvailableError,
)
from foundations_journey.forms import CheckpointTransitionForm, OfferFollowUpTaskForm
from security_baseline.catalogue import CATALOGUE_BY_KEY
from security_baseline.forms import confirm_field_name, option_field_name


def _is_checked(post_data, field_name) -> bool:
    """Same truthy-checkbox convention `security_tasks.forms`/Django's own
    `CheckboxInput.value_from_datadict` use - a raw request.POST read
    here (this view does not bind `security_baseline.forms.
    StructuredAnswerForm` itself; `services.submit_foundations_option`
    does, from the dict this function helps build)."""
    return post_data.get(field_name) in ("on", "true", "1", "True", True)


@login_required
@require_capability()
def guided_question(request, organisation_id, question_key):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if question_key not in CATALOGUE_BY_KEY:
        raise Http404(f"{question_key!r} is not a real security_baseline control key.")

    form_errors = None
    if request.method == "POST":
        option_code = request.POST.get(option_field_name(question_key), "")
        confirmed = _is_checked(request.POST, confirm_field_name(question_key))
        try:
            services.submit_foundations_option(
                organisation,
                request.user,
                question_key=question_key,
                option_code=option_code,
                confirmation=confirmed,
            )
        except InvalidFoundationsOptionError as exc:
            form_errors = exc.form_errors
            messages.error(
                request, "That answer could not be saved. Please check the errors below."
            )
        else:
            messages.success(request, "Answer saved.")
            return redirect(
                "foundations_journey:guided_question",
                organisation_id=organisation.id,
                question_key=question_key,
            )

    view_model = services.get_foundations_question(organisation, request.user, question_key)
    checkpoint = services.get_journey_checkpoint(organisation, request.user)

    return render(
        request,
        "foundations_journey/guided_question.html",
        {
            "organisation": organisation,
            "view_model": view_model,
            "form_errors": form_errors,
            "option_field_name": option_field_name(question_key),
            "confirm_field_name": confirm_field_name(question_key),
            "offer_task_form": OfferFollowUpTaskForm(initial={"idempotency_key": uuid.uuid4()}),
            "checkpoint": checkpoint,
            "checkpoint_form": CheckpointTransitionForm(
                initial={"expected_version": checkpoint.version}
            ),
        },
    )


@login_required
@require_capability()
def offer_followup_task(request, organisation_id, question_key):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    if question_key not in CATALOGUE_BY_KEY:
        raise Http404(f"{question_key!r} is not a real security_baseline control key.")
    if request.method != "POST":
        return redirect(
            "foundations_journey:guided_question",
            organisation_id=organisation.id,
            question_key=question_key,
        )

    form = OfferFollowUpTaskForm(request.POST)
    idempotency_key = (
        form.data.get("idempotency_key") if form.is_valid() else str(uuid.uuid4())
    ) or str(uuid.uuid4())

    try:
        services.offer_foundations_followup_task(
            organisation,
            request.user,
            question_key=question_key,
            idempotency_key=idempotency_key,
        )
    except NoFollowUpTaskAvailableError:
        messages.info(request, "No follow-up task is needed for this control's current answer.")
    else:
        messages.success(request, "A follow-up task has been added to your Tasks list.")

    return redirect(
        "foundations_journey:guided_question",
        organisation_id=organisation.id,
        question_key=question_key,
    )


@login_required
@require_capability()
def pause_journey(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    if request.method != "POST":
        return redirect("organisations:detail", organisation_id=organisation.id)

    form = CheckpointTransitionForm(request.POST)
    if form.is_valid():
        try:
            services.update_checkpoint(
                organisation,
                request.user,
                expected_version=form.cleaned_data["expected_version"],
                transition="pause",
            )
            messages.success(request, "Paused. Resume any time from where you left off.")
        except ConcurrentCheckpointModificationError:
            messages.error(request, "Your journey position changed elsewhere - refreshed.")

    return redirect("organisations:detail", organisation_id=organisation.id)


@login_required
@require_capability()
def resume_journey(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    if request.method != "POST":
        return redirect("organisations:detail", organisation_id=organisation.id)

    form = CheckpointTransitionForm(request.POST)
    if form.is_valid():
        try:
            checkpoint = services.update_checkpoint(
                organisation,
                request.user,
                expected_version=form.cleaned_data["expected_version"],
                transition="resume",
            )
            messages.success(request, "Resumed.")
        except ConcurrentCheckpointModificationError:
            messages.error(request, "Your journey position changed elsewhere - refreshed.")
            checkpoint = services.get_journey_checkpoint(organisation, request.user)
        if checkpoint.current_question_key:
            return redirect(
                "foundations_journey:guided_question",
                organisation_id=organisation.id,
                question_key=checkpoint.current_question_key,
            )

    return redirect("organisations:detail", organisation_id=organisation.id)
