from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

import governance.services

from organisations.forms import OrganisationCreateForm, OrganisationProfileForm
from organisations.models import AuditEvent, Organisation, OrganisationMembership, OrganisationProfile
from organisations.overview import build_overview


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
    """
    The Overview / journey page (M006 PID §6). This used to render a flat
    "does X exist yet" card list gated only by a crude `profile_exists`
    boolean; it now renders `organisations.overview.build_overview`'s
    derived per-area state - recomputed fresh on every request, never
    stored - which is the URL/view every "Overview" primary-nav link
    (templates/base.html) and `core.context_processors.active_nav` point
    at. The URL name (`organisations:detail`) and this view's name are
    both left unchanged: only what the page shows has changed.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    overview_areas = build_overview(organisation)
    return render(
        request,
        "organisations/detail.html",
        {"organisation": organisation, "overview_areas": overview_areas},
    )


@login_required
def organisation_hub(request, organisation_id):
    """
    The "Organisation" primary-nav landing page (M006 PID §5): Profile,
    Governance roles and Workplace used to live as three of the flat card
    list on `organisations:detail` (now the Overview page, above); they
    need a single home now that they are no longer there. Deliberately
    minimal - three links, mirroring the existing `summary-card` style
    already used across this codebase - not a new CRUD surface of its own.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    return render(
        request,
        "organisations/organisation_hub.html",
        {"organisation": organisation},
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
