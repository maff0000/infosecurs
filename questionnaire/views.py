"""
Minimal Questionnaire Assurance views (M005 PID §4, §25 - m005-1-foundation
dispatch).

This dispatch's scope, per its own instructions, is deliberately narrow: a
view that lets a Customer Zero user paste one question and see the
persisted draft response's fields (outcome, draft text, selected keys,
review warnings). The full PID §25 result-card UX (edit/accept/regenerate/
"Why this answer?" panel, "What needs attention?" panel, navigation to the
relevant Security State/control/action) is a later dispatch's job.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from organisations.views import get_member_organisation_or_404

from activity.models import ActivityEvent
from activity.services import record_event

from ai_platform.questionnaire_drafting_orchestration import QuestionnaireDraftingFailed
from ai_platform.questionnaire_interpretation_orchestration import (
    QuestionnaireInterpretationFailed,
)

from questionnaire.forms import QuestionnaireResponseEditForm
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.presentation import grounding_facts_for_display, outcome_presentation
from questionnaire.services import (
    accept_questionnaire_response,
    edit_questionnaire_response_text,
    generate_questionnaire_response,
)


def _get_member_response_or_404(user, organisation_id, response_id):
    """Tenant-scoped questionnaire-response fetch, mirroring
    `policy.views._get_member_policy_version_or_404`: membership is
    verified first, then the response is looked up scoped to that
    organisation - a foreign/manipulated response id in the URL is an
    ordinary 404, never a path to another organisation's questionnaire
    response (PID §23 tenant isolation)."""
    organisation = get_member_organisation_or_404(user, organisation_id)
    response = get_object_or_404(QuestionnaireResponse, id=response_id, organisation=organisation)
    return organisation, response


@login_required
def questionnaire_list(request, organisation_id):
    """Organisation-level questionnaire overview: the paste-a-question form
    plus every question asked so far, most recent first."""
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    questions = list(
        QuestionnaireQuestion.objects.filter(organisation=organisation).prefetch_related(
            "responses"
        )
    )
    # Prefer showing the currently ACCEPTED response, so a stale draft link
    # never hides an existing accepted answer (PID §18). Filtered in Python
    # over the already-`prefetch_related`d `responses` list, not a fresh
    # `.filter()` query per question, to avoid an N+1 explosion -
    # `question.responses.all()` reuses the prefetch cache;
    # `question.responses.filter(...)` would not.
    question_rows = []
    for question in questions:
        all_responses = list(question.responses.all())  # already ordered -created_at
        accepted = next(
            (r for r in all_responses if r.status == QuestionnaireResponse.STATUS_ACCEPTED), None
        )
        latest = all_responses[0] if all_responses else None
        display_response = accepted if accepted is not None else latest
        question_rows.append(
            {
                "question": question,
                "display_response": display_response,
                "is_accepted": accepted is not None and display_response is accepted,
            }
        )
    return render(
        request,
        "questionnaire/list.html",
        {"organisation": organisation, "question_rows": question_rows},
    )


@login_required
def questionnaire_analyse(request, organisation_id):
    """Create a `QuestionnaireQuestion` from the pasted text, then run the
    full interpret -> ground -> derive-outcome -> draft pipeline (PID §22:
    the question is saved FIRST, independently of whether generation
    subsequently succeeds - see `questionnaire.services` module docstring).
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    question_text = (request.POST.get("question_text") or "").strip()
    source_label = (request.POST.get("source_label") or "").strip()
    if not question_text:
        messages.error(request, "Enter a question to analyse.")
        return redirect("questionnaire:list", organisation_id=organisation.id)

    question = QuestionnaireQuestion.objects.create(
        organisation=organisation,
        question_text=question_text,
        source_label=source_label,
        created_by=request.user,
    )
    record_event(
        organisation,
        ActivityEvent.EVENT_QUESTION_CREATED,
        actor=request.user,
        related_object_type="questionnaire_question",
        related_object_id=str(question.id),
        metadata={"has_source_label": bool(source_label)},
    )

    try:
        response = generate_questionnaire_response(organisation, question, actor=request.user)
    except (QuestionnaireInterpretationFailed, QuestionnaireDraftingFailed):
        # PID §22: never fabricate a mapping/outcome on failure. The raw
        # question is already saved above; nothing else was persisted (see
        # questionnaire.services module docstring for exactly what each
        # failure mode does and does not persist).
        messages.error(
            request,
            "Infosecurs could not analyse this question right now. The question has "
            "been saved and you can try again.",
        )
        return redirect("questionnaire:list", organisation_id=organisation.id)

    return redirect(
        "questionnaire:response_detail", organisation_id=organisation.id, response_id=response.id
    )


@login_required
def questionnaire_response_detail(request, organisation_id, response_id):
    """One specific `QuestionnaireResponse`'s outcome, draft text, selected
    canonical keys and review warnings, plus (PID §16, §25, §26) the
    presentation-ready outcome wording and grounding-fact display list the
    template renders "Why this answer?" from."""
    organisation, response = _get_member_response_or_404(request.user, organisation_id, response_id)
    grounding_facts = grounding_facts_for_display(response)
    return render(
        request,
        "questionnaire/response_detail.html",
        {
            "organisation": organisation,
            "response": response,
            "question": response.question,
            "outcome_presentation": outcome_presentation(response),
            "grounding_facts": grounding_facts,
            "has_policy_fact": any(fact["kind"] == "policy_section" for fact in grounding_facts),
        },
    )


@login_required
def questionnaire_response_accept(request, organisation_id, response_id):
    """PID §17/§18: accept a draft response as the organisation's external
    answer. POST only, mirroring `questionnaire_analyse`'s
    `HttpResponseNotAllowed(["POST"])` pattern."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation, response = _get_member_response_or_404(request.user, organisation_id, response_id)

    if response.status != QuestionnaireResponse.STATUS_DRAFT:
        messages.error(request, "Only a draft response can be accepted.")
        return redirect(
            "questionnaire:response_detail", organisation_id=organisation.id, response_id=response.id
        )

    accept_questionnaire_response(response, actor=request.user)
    messages.success(request, "Response accepted.")
    return redirect(
        "questionnaire:response_detail", organisation_id=organisation.id, response_id=response.id
    )


@login_required
def questionnaire_response_edit(request, organisation_id, response_id):
    """PID §17: edit a draft response's wording only. GET+POST, mirroring
    `policy.views.policy_edit`'s exact shape."""
    organisation, response = _get_member_response_or_404(request.user, organisation_id, response_id)

    if response.status != QuestionnaireResponse.STATUS_DRAFT:
        messages.error(request, "Only a draft response can be edited.")
        return redirect(
            "questionnaire:response_detail", organisation_id=organisation.id, response_id=response.id
        )

    if request.method == "POST":
        form = QuestionnaireResponseEditForm(request.POST)
        if form.is_valid():
            # Reads ONLY current_answer_text from the validated form - see
            # QuestionnaireResponseEditForm's own docstring for why the
            # form structurally cannot carry outcome/selected_keys/
            # grounding_snapshot in the first place.
            edit_questionnaire_response_text(
                response, new_text=form.cleaned_data["current_answer_text"], actor=request.user
            )
            messages.success(request, "Draft response updated.")
            return redirect(
                "questionnaire:response_detail",
                organisation_id=organisation.id,
                response_id=response.id,
            )
        messages.error(request, "The draft could not be saved. Please check the errors below.")
    else:
        form = QuestionnaireResponseEditForm(
            initial={"current_answer_text": response.current_answer_text}
        )

    return render(
        request,
        "questionnaire/response_edit.html",
        {"organisation": organisation, "response": response, "question": response.question, "form": form},
    )


@login_required
def questionnaire_response_regenerate(request, organisation_id, response_id):
    """PID §18: create a brand-new response attempt for the SAME question
    as `response`, leaving `response` itself completely unchanged
    regardless of its current status - draft, accepted or superseded
    (PID §18's whole point is "state changed later -> new attempt" for a
    question that may already have an accepted answer). POST only."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation, response = _get_member_response_or_404(request.user, organisation_id, response_id)
    question = response.question

    try:
        new_response = generate_questionnaire_response(organisation, question, actor=request.user)
    except (QuestionnaireInterpretationFailed, QuestionnaireDraftingFailed):
        messages.error(
            request,
            "Infosecurs could not regenerate this response right now. You can try again.",
        )
        return redirect(
            "questionnaire:response_detail", organisation_id=organisation.id, response_id=response.id
        )

    messages.success(request, "A new draft response has been generated.")
    return redirect(
        "questionnaire:response_detail",
        organisation_id=organisation.id,
        response_id=new_response.id,
    )
