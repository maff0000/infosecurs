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

from ai_platform.questionnaire_drafting_orchestration import QuestionnaireDraftingFailed
from ai_platform.questionnaire_interpretation_orchestration import (
    QuestionnaireInterpretationFailed,
)

from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.services import generate_questionnaire_response


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
    return render(
        request,
        "questionnaire/list.html",
        {"organisation": organisation, "questions": questions},
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
    canonical keys and review warnings."""
    organisation, response = _get_member_response_or_404(request.user, organisation_id, response_id)
    return render(
        request,
        "questionnaire/response_detail.html",
        {"organisation": organisation, "response": response, "question": response.question},
    )
