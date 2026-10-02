from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from entitlements.decorators import require_capability
from organisations.views import get_member_organisation_or_404
from security_baseline.catalogue import CATALOGUE_BY_KEY, CATALOGUE_KEYS
from security_baseline.forms import (
    StructuredAnswerForm,
    confirm_field_name,
    option_field_name,
)
from security_baseline.models import BaselineAssessment
from security_baseline.services import record_structured_baseline_answer
from security_baseline.stage4 import QUESTION_COPY, explainer_for, progress_copy, stage4_progress
from security_baseline.structured_catalogue import FOUNDATIONS_QUESTION_METHODOLOGY_VERSION

_JML_CONTROL_KEY = "joiner_mover_leaver"


@login_required
@require_capability()
def baseline_view(request, organisation_id):
    """
    Legacy entry point for the security baseline (PID §6; docs/pids/
    M008-...-WI2b dispatch's non-negotiable #1: "old direct-access legacy
    forms must be fixed, not merely concealed").

    This view used to render the full 12-question form directly (one
    giant page, a per-question free-text "note" field, and a plain
    `security_baseline.models.ANSWER_CHOICES` <select> that - unlike the
    new structured Stage 4 journey - let a customer submit
    `not_applicable` (or any other answer) for literally any control,
    including the four controls the corrected M008B-QUESTION-CATALOGUE.md
    Revision 2 catalogue says must NEVER have a NOT_APPLICABLE option at
    all. Converting the Stage 4 questions to go through
    `security_baseline.structured_catalogue`/`stage4.offered_options`
    while leaving this page reachable alongside it would have been
    concealment, not a fix - the bypass would still exist, just no longer
    advertised.

    So this view now does exactly one thing: redirect into the new guided
    journey's entry point. It still performs the same tenant-membership
    lookup/session-binding every other organisation-scoped view in this
    codebase does, for both GET and POST - but it never constructs
    `security_baseline.forms.BaselineAssessmentForm` from request data, so
    a POST to this URL (with or without a `note__<key>` field, with or
    without a forged `not_applicable` answer) is simply never parsed into
    a form at all; nothing can be written through it.

    The URL name `security_baseline:baseline` is deliberately kept
    (not removed/renamed): `entitlements`'s seeded `ProductArea.
    destination_view_name` and `organisations.overview`'s
    `next_action_url_name` already reverse this exact name from Home and
    the Foundations workspace - every existing link into "the security
    baseline" keeps working unchanged, now landing the customer in the
    guided journey instead of the old long-form page.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    return redirect("security_baseline:foundations_start", organisation_id=organisation.id)


@login_required
@require_capability()
def foundations_start(request, organisation_id):
    """
    Stage 4 entry point: redirects to the first control the customer has
    not yet reviewed (no `AnswerSelectionDetail` row at all), or to the
    first control in catalogue order if every control has already been
    reviewed (so revisiting Stage 4 after finishing it lands somewhere
    sensible rather than 404ing or re-deriving nothing).

    GET-only in practice (every caller reaches this via a link/redirect),
    but makes no distinction by method - it never writes anything either
    way.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    reviewed_keys = set()
    if assessment is not None:
        reviewed_keys = set(
            assessment.selection_details.filter(
                question_key__in=CATALOGUE_KEYS
            ).values_list("question_key", flat=True)
        )

    target_key = next(
        (key for key in CATALOGUE_KEYS if key not in reviewed_keys), CATALOGUE_KEYS[0]
    )
    return redirect(
        "security_baseline:foundations_question",
        organisation_id=organisation.id,
        question_key=target_key,
    )


@login_required
@require_capability()
def foundations_question(request, organisation_id, question_key):
    """
    The guided, one-question-at-a-time Stage 4 screen (docs/design/
    M008C-UX-FLOW-DESIGN.md §1/§3; docs/design/prototype.html's
    q-simple/q-conditional/q-notsure screens).

    `question_key` must be one of the 12 real `security_baseline.
    catalogue` control keys - any other value is an ordinary 404, exactly
    like a foreign/invalid id anywhere else in this codebase.

    GET renders the current state: the approved question/why-it-matters
    copy (`security_baseline.stage4.QUESTION_COPY`), the options actually
    offered to this organisation right now (`security_baseline.stage4.
    offered_options` - server-derived, never client-supplied), the
    previously-selected option pre-selected (read back from the real
    `AnswerSelectionDetail.option_code`, never reverse-guessed from the
    canonical `BaselineAnswer.answer` alone), its explainer text if a
    selection exists, and the stage-local REVIEWED/confirmed progress
    pair. GET never writes anything.

    POST validates via `security_baseline.forms.StructuredAnswerForm`
    (whose `option_code` choices are exactly `offered_options`' result -
    see that form's own docstring for why a forged/unoffered option_code
    cannot pass validation) and, only if valid, calls the sole write path
    `security_baseline.services.record_structured_baseline_answer`, then
    redirects back to this same question's GET (not straight to the next
    one) - the customer sees their own answer, pre-selected, plus its
    explainer, before choosing to move on via the explicit Back/Next
    links below. An invalid POST re-renders this same page with form
    errors and writes nothing, exactly like every other form view in this
    codebase.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if question_key not in CATALOGUE_BY_KEY:
        raise Http404(f"{question_key!r} is not a real security_baseline control key.")

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    existing_selection = None
    if assessment is not None:
        existing_selection = assessment.selection_details.filter(
            question_key=question_key
        ).first()

    selected_code = None

    if request.method == "POST":
        form = StructuredAnswerForm(
            request.POST, organisation=organisation, question_keys=[question_key]
        )
        if form.is_valid():
            option_code = form.cleaned_data[option_field_name(question_key)]
            record_structured_baseline_answer(
                organisation, question_key, option_code, actor=request.user
            )
            messages.success(request, "Answer saved.")
            return redirect(
                "security_baseline:foundations_question",
                organisation_id=organisation.id,
                question_key=question_key,
            )
        messages.error(
            request, "That answer could not be saved. Please check the errors below."
        )
    else:
        initial = {}
        if existing_selection is not None:
            initial[option_field_name(question_key)] = existing_selection.option_code
            selected_code = existing_selection.option_code
        form = StructuredAnswerForm(
            initial=initial, organisation=organisation, question_keys=[question_key]
        )

    explainer = None
    if selected_code is not None:
        answer = assessment.answers.filter(question_key=question_key).first()
        if answer is not None:
            explainer = explainer_for(question_key, selected_code, answer.answer)

    progress = stage4_progress(assessment)

    index = CATALOGUE_KEYS.index(question_key)
    previous_key = CATALOGUE_KEYS[index - 1] if index > 0 else None
    next_key = CATALOGUE_KEYS[index + 1] if index + 1 < len(CATALOGUE_KEYS) else None

    return render(
        request,
        "security_baseline/foundations_question.html",
        {
            "organisation": organisation,
            "form": form,
            "question_key": question_key,
            "item": QUESTION_COPY[question_key],
            "option_field": form[option_field_name(question_key)],
            "confirm_field": (
                form[confirm_field_name(question_key)]
                if question_key == _JML_CONTROL_KEY
                else None
            ),
            "explainer": explainer,
            "progress": progress,
            "progress_copy": progress_copy(progress),
            "question_number": index + 1,
            "question_total": len(CATALOGUE_KEYS),
            "previous_key": previous_key,
            "next_key": next_key,
            "methodology_version": FOUNDATIONS_QUESTION_METHODOLOGY_VERSION,
        },
    )
