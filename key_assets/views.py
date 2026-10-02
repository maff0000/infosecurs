from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from organisations.models import OrganisationProfile
from entitlements.decorators import require_capability
from organisations.views import get_member_organisation_or_404

from key_assets.forms import KeyAssetForm
from key_assets.models import KeyAsset
from key_assets.protection_checks import relevant_control_keys_for_category
from key_assets.suggestions import ensure_starter_suggestions
from risk_register.models import Risk
from security_baseline.forms import StructuredAnswerForm, confirm_field_name, option_field_name
from security_baseline.models import BaselineAssessment
from security_baseline.services import record_structured_baseline_answer
from security_baseline.stage4 import QUESTION_COPY, explainer_for
from security_baseline.structured_catalogue import FOUNDATIONS_QUESTION_METHODOLOGY_VERSION

_JML_CONTROL_KEY = "joiner_mover_leaver"


def _get_member_key_asset_or_404(user, organisation_id, asset_id):
    """
    Tenant-scoped asset fetch, mirroring
    organisations.views.get_member_organisation_or_404: membership is
    verified first (raising an ordinary 404 for a non-member or a
    manipulated/foreign organisation id), then the asset is looked up
    scoped to that organisation - so there is no code path where an asset
    from a different organisation could be read or acted on via a
    mismatched/foreign asset id in the URL.
    """
    organisation = get_member_organisation_or_404(user, organisation_id)
    asset = get_object_or_404(KeyAsset, id=asset_id, organisation=organisation)
    return organisation, asset


@login_required
@require_capability()
def key_asset_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    # Deterministic, non-AI starter suggestions (PID.md M002 §7.1). Safe to
    # run on every view of this page: idempotent per (organisation,
    # suggestion_key), so it only ever backfills suggestions that do not
    # already exist - it never re-proposes one that has been confirmed,
    # edited or dismissed.
    ensure_starter_suggestions(organisation)

    try:
        organisation.profile
        profile_exists = True
    except OrganisationProfile.DoesNotExist:
        profile_exists = False

    assets = list(KeyAsset.objects.filter(organisation=organisation))
    context = {
        "organisation": organisation,
        "profile_exists": profile_exists,
        "suggested_assets": [a for a in assets if a.status == KeyAsset.STATUS_SUGGESTED],
        "confirmed_assets": [a for a in assets if a.status == KeyAsset.STATUS_CONFIRMED],
        "dismissed_assets": [a for a in assets if a.status == KeyAsset.STATUS_DISMISSED],
    }
    return render(request, "key_assets/list.html", context)


@login_required
@require_capability()
def key_asset_create(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = KeyAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.organisation = organisation
            # A manually-added asset is the customer's own direct
            # assertion that it exists - it is not a deterministic
            # suggestion awaiting review, so there is nothing to confirm
            # later (PID.md M002 §7.1 only requires the SUGGESTED state for
            # the deterministic starter suggestions).
            asset.status = KeyAsset.STATUS_CONFIRMED
            asset.save()
            messages.success(request, f'Asset "{asset.name}" added.')
            return redirect("key_assets:list", organisation_id=organisation.id)
        messages.error(
            request, "The asset could not be saved. Please check the errors below."
        )
    else:
        form = KeyAssetForm()

    return render(
        request,
        "key_assets/form.html",
        {"organisation": organisation, "form": form, "mode": "create"},
    )


@login_required
@require_capability()
def key_asset_edit(request, organisation_id, asset_id):
    organisation, asset = _get_member_key_asset_or_404(
        request.user, organisation_id, asset_id
    )

    if request.method == "POST":
        form = KeyAssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, f'Asset "{asset.name}" updated.')
            return redirect("key_assets:list", organisation_id=organisation.id)
        messages.error(
            request, "The asset could not be saved. Please check the errors below."
        )
    else:
        form = KeyAssetForm(instance=asset)

    return render(
        request,
        "key_assets/form.html",
        {"organisation": organisation, "form": form, "asset": asset, "mode": "edit"},
    )


@login_required
@require_capability()
def key_asset_detail(request, organisation_id, asset_id):
    """
    Asset-specific protection/exposure assessment (PID.md M002 §0.5).

    Surfaces the `security_baseline` control questions relevant to this
    asset's category (derived from the methodology catalogue via
    key_assets.protection_checks - never a hand-maintained second mapping)
    and lets the customer answer them without leaving the asset's context.

    M008C-WI2b: this is explicitly NOT a second question/answer model -
    the form is the same `security_baseline.forms.StructuredAnswerForm`
    the new guided Stage 4 journey uses (filtered to this asset's
    relevant question keys), and saving goes through the exact same
    `security_baseline.services.record_structured_baseline_answer`
    function that journey's view calls, so there is exactly one canonical
    stored `BaselineAnswer` row per control fact, however it was reached
    (PID §0.5's non-negotiable rule) - now with the exact same
    NOT_APPLICABLE server-side gating (`security_baseline.stage4.
    offered_options`) applied here too. This view previously reused
    `BaselineAssessmentForm` (the old free-text-note, ungated
    ANSWER_CHOICES form) - that was a second reachable surface for
    exactly the bypass this WI's dispatch requires closed (an asset
    relevant to CATEGORY_NETWORK_OR_LOCATION or CATEGORY_PEOPLE can
    surface `remote_access_control`/`joiner_mover_leaver`, both of which
    have a NOT_APPLICABLE option that must be gated), so it is converted
    here too, not merely left alongside the new journey. Also links
    onward to the risks already associated with this asset, so this page
    is a step in the PID §0.5 journey ("Organisation -> Assets ->
    relevant protection questions -> scenarios -> risks"), not a dead
    end.
    """
    organisation, asset = _get_member_key_asset_or_404(
        request.user, organisation_id, asset_id
    )
    request.session["current_organisation_id"] = str(organisation.id)

    question_keys = relevant_control_keys_for_category(asset.category)

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    existing_selections = {}
    if assessment is not None:
        existing_selections = {
            d.question_key: d.option_code
            for d in assessment.selection_details.filter(question_key__in=question_keys)
        }

    if request.method == "POST":
        form = StructuredAnswerForm(
            request.POST, organisation=organisation, question_keys=question_keys
        )
        if form.is_valid():
            # Same write path as security_baseline.views.foundations_question
            # - never a second BaselineAnswer writer (PID §0.5).
            for key in question_keys:
                option_code = form.cleaned_data[option_field_name(key)]
                record_structured_baseline_answer(
                    organisation, key, option_code, actor=request.user
                )
            messages.success(request, "Protection checks saved.")
            return redirect(
                "key_assets:detail", organisation_id=organisation.id, asset_id=asset.id
            )
        messages.error(
            request,
            "The protection checks could not be saved. Please check the errors below.",
        )
    else:
        initial = {
            option_field_name(key): existing_selections[key]
            for key in question_keys
            if key in existing_selections
        }
        form = StructuredAnswerForm(
            initial=initial, organisation=organisation, question_keys=question_keys
        )

    questions = []
    for key in question_keys:
        selected_code = existing_selections.get(key)
        explainer = None
        if selected_code is not None:
            answer = assessment.answers.filter(question_key=key).first()
            if answer is not None:
                explainer = explainer_for(key, selected_code, answer.answer)
        questions.append(
            {
                "key": key,
                "item": QUESTION_COPY[key],
                "option_field": form[option_field_name(key)],
                "confirm_field": (
                    form[confirm_field_name(key)] if key == _JML_CONTROL_KEY else None
                ),
                "explainer": explainer,
            }
        )

    risks = list(Risk.objects.filter(organisation=organisation, key_asset=asset))

    return render(
        request,
        "key_assets/detail.html",
        {
            "organisation": organisation,
            "asset": asset,
            "form": form,
            "questions": questions,
            "methodology_version": FOUNDATIONS_QUESTION_METHODOLOGY_VERSION,
            "risks": risks,
        },
    )


@login_required
@require_capability()
def key_asset_confirm(request, organisation_id, asset_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, asset = _get_member_key_asset_or_404(
        request.user, organisation_id, asset_id
    )
    asset.status = KeyAsset.STATUS_CONFIRMED
    asset.save(update_fields=["status", "updated_at"])
    messages.success(request, f'Asset "{asset.name}" confirmed.')
    return redirect("key_assets:list", organisation_id=organisation.id)


@login_required
@require_capability()
def key_asset_dismiss(request, organisation_id, asset_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, asset = _get_member_key_asset_or_404(
        request.user, organisation_id, asset_id
    )
    asset.status = KeyAsset.STATUS_DISMISSED
    asset.save(update_fields=["status", "updated_at"])
    messages.success(request, f'Asset "{asset.name}" dismissed.')
    return redirect("key_assets:list", organisation_id=organisation.id)
