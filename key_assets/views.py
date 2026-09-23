from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from organisations.models import OrganisationProfile
from organisations.views import get_member_organisation_or_404

from key_assets.forms import KeyAssetForm
from key_assets.models import KeyAsset
from key_assets.suggestions import ensure_starter_suggestions


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
