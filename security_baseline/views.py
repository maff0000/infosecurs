from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from organisations.views import get_member_organisation_or_404
from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.forms import BaselineAssessmentForm, answer_field_name, note_field_name
from security_baseline.models import ANSWER_UNKNOWN, BaselineAnswer, BaselineAssessment


@login_required
def baseline_view(request, organisation_id):
    """
    View/answer the organisation's security baseline (PID §6).

    Tenant-scoped via the same `get_member_organisation_or_404` helper M001
    uses for its own profile view (organisations/views.py) - the tenant
    scope is baked into that lookup itself, not checked afterwards.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    existing_answers = {}
    if assessment is not None:
        existing_answers = {a.question_key: a for a in assessment.answers.all()}

    if request.method == "POST":
        form = BaselineAssessmentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                if assessment is None:
                    assessment = BaselineAssessment.objects.create(
                        organisation=organisation, catalogue_version=CATALOGUE_VERSION
                    )
                else:
                    assessment.catalogue_version = CATALOGUE_VERSION
                    assessment.save(update_fields=["catalogue_version", "updated_at"])

                for item in CATALOGUE:
                    key = item["key"]
                    BaselineAnswer.objects.update_or_create(
                        assessment=assessment,
                        question_key=key,
                        defaults={
                            "answer": form.cleaned_data[answer_field_name(key)],
                            "note": form.cleaned_data[note_field_name(key)],
                        },
                    )
            messages.success(request, "Security baseline saved.")
            return redirect("security_baseline:baseline", organisation_id=organisation.id)
        messages.error(
            request, "The security baseline could not be saved. Please check the errors below."
        )
    else:
        initial = {}
        for item in CATALOGUE:
            key = item["key"]
            existing = existing_answers.get(key)
            initial[answer_field_name(key)] = existing.answer if existing else ANSWER_UNKNOWN
            initial[note_field_name(key)] = existing.note if existing else ""
        form = BaselineAssessmentForm(initial=initial)

    # Pair each catalogue item with its bound field so the template can
    # render grouped, labelled questions without knowing the field-naming
    # scheme (answer_field_name/note_field_name) itself.
    questions = [
        {
            "item": item,
            "answer_field": form[answer_field_name(item["key"])],
            "note_field": form[note_field_name(item["key"])],
        }
        for item in CATALOGUE
    ]

    return render(
        request,
        "security_baseline/baseline_form.html",
        {
            "organisation": organisation,
            "form": form,
            "questions": questions,
            "catalogue_version": CATALOGUE_VERSION,
            "assessment_exists": assessment is not None,
        },
    )
