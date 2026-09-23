from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

import governance.services

from organisations.forms import OrganisationCreateForm, OrganisationProfileForm
from organisations.models import AuditEvent, Organisation, OrganisationMembership, OrganisationProfile


def get_member_organisation_or_404(user, organisation_id):
    """
    Fetch an organisation, scoped to the requesting user's membership, in a
    single query.

    This is deliberate: the tenant scope is baked into the query itself
    (memberships__user=user) rather than fetched-then-checked, so there is
    no code path where the object exists but the caller forgets to verify
    membership before using it. A non-member (or a manipulated/foreign
    UUID in the URL) gets an ordinary 404, not a 403 - callers never learn
    whether an organisation they cannot access exists at all.
    """
    return get_object_or_404(
        Organisation, id=organisation_id, memberships__user=user
    )


@login_required
def organisation_list(request):
    organisations = Organisation.objects.filter(memberships__user=request.user).order_by("name")
    return render(
        request,
        "organisations/list.html",
        {"organisations": organisations},
    )


@login_required
def organisation_create(request):
    if request.method == "POST":
        form = OrganisationCreateForm(request.POST)
        if form.is_valid():
            # Atomic (PID §6-7): an organisation must never be left without
            # its Account Holder's governance person/role rows - this is
            # one transaction, not a best-effort follow-up call.
            with transaction.atomic():
                organisation = form.save()
                OrganisationMembership.objects.create(
                    organisation=organisation,
                    user=request.user,
                    role=OrganisationMembership.ROLE_OWNER,
                )
                governance.services.ensure_account_holder_person(organisation, request.user)
            messages.success(request, f'Organisation "{organisation.name}" created.')
            return redirect("organisations:detail", organisation_id=organisation.id)
    else:
        form = OrganisationCreateForm()
    return render(request, "organisations/create.html", {"form": form})


@login_required
def organisation_detail(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    profile_exists = OrganisationProfile.objects.filter(organisation=organisation).exists()
    return render(
        request,
        "organisations/detail.html",
        {"organisation": organisation, "profile_exists": profile_exists},
    )


@login_required
def organisation_profile(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    instance = OrganisationProfile.objects.filter(organisation=organisation).first()
    is_new = instance is None

    if request.method == "POST":
        form = OrganisationProfileForm(request.POST, instance=instance)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.organisation = organisation
            profile.save()
            AuditEvent.objects.create(
                organisation=organisation,
                action=(
                    AuditEvent.ACTION_PROFILE_CREATED
                    if is_new
                    else AuditEvent.ACTION_PROFILE_UPDATED
                ),
                actor=request.user,
            )
            messages.success(request, "Organisation profile saved.")
            return redirect("organisations:profile", organisation_id=organisation.id)
        messages.error(request, "The profile could not be saved. Please check the errors below.")
    else:
        form = OrganisationProfileForm(instance=instance)

    return render(
        request,
        "organisations/profile_form.html",
        {"organisation": organisation, "form": form, "is_new": is_new},
    )
