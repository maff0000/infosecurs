from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from organisations.views import get_member_organisation_or_404

from workplace import services
from workplace.forms import (
    PATTERN_ALL_REMOTE,
    PATTERN_OFFICE_AND_HOME,
    PATTERN_ONE_OFFICE,
    PATTERN_SEVERAL_LOCATIONS,
    PATTERN_SHARED_COWORKING,
    AllRemoteOnboardingForm,
    OfficeAndHomeOnboardingForm,
    OneOfficeOnboardingForm,
    SharedCoworkingOnboardingForm,
    WorkplaceForm,
    WorkplacePatternForm,
)
from workplace.models import Workplace

# Where each onboarding pattern choice sends the user next (PID §9.1).
# "several_locations" is the one pattern PID explicitly says "reasonably
# needs a fuller add-another-workplace flow" - it goes straight to the
# general list/create views rather than a dedicated one-shot step-2 form.
_PATTERN_NEXT_URL_NAME = {
    PATTERN_ALL_REMOTE: "workplace:onboarding_all_remote",
    PATTERN_ONE_OFFICE: "workplace:onboarding_one_office",
    PATTERN_SHARED_COWORKING: "workplace:onboarding_shared_coworking",
    PATTERN_OFFICE_AND_HOME: "workplace:onboarding_office_and_home",
    PATTERN_SEVERAL_LOCATIONS: "workplace:list",
}


def _get_member_workplace_or_404(user, organisation_id, workplace_id):
    """
    Tenant-scoped workplace fetch, mirroring
    organisations.views.get_member_organisation_or_404 /
    key_assets.views._get_member_key_asset_or_404: membership is verified
    first, then the workplace is looked up scoped to that organisation -
    so a foreign/manipulated workplace id in the URL is an ordinary 404,
    never a path to another organisation's workplace.
    """
    organisation = get_member_organisation_or_404(user, organisation_id)
    workplace = get_object_or_404(Workplace, id=workplace_id, organisation=organisation)
    return organisation, workplace


# ---------------------------------------------------------------------------
# Onboarding wizard (PID §9.1)
# ---------------------------------------------------------------------------
@login_required
def workplace_onboarding_start(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = WorkplacePatternForm(request.POST)
        if form.is_valid():
            next_url_name = _PATTERN_NEXT_URL_NAME[form.cleaned_data["pattern"]]
            return redirect(next_url_name, organisation_id=organisation.id)
    else:
        form = WorkplacePatternForm()

    return render(
        request,
        "workplace/onboarding_start.html",
        {"organisation": organisation, "form": form},
    )


@login_required
def workplace_onboarding_all_remote(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = AllRemoteOnboardingForm(request.POST)
        if form.is_valid():
            services.create_workplace(
                organisation=organisation,
                name="Home / remote working",
                type=Workplace.TYPE_DISTRIBUTED_HOME,
                location_label="",
                approx_people_count=form.cleaned_data["approx_people_count"],
                is_primary=True,
                actor=request.user,
            )
            messages.success(request, "Workplace saved: everyone works from home.")
            return redirect("workplace:list", organisation_id=organisation.id)
    else:
        form = AllRemoteOnboardingForm()

    return render(
        request,
        "workplace/onboarding_all_remote.html",
        {"organisation": organisation, "form": form},
    )


@login_required
def workplace_onboarding_one_office(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = OneOfficeOnboardingForm(request.POST)
        if form.is_valid():
            services.create_workplace(
                organisation=organisation,
                name=form.cleaned_data["name"],
                type=Workplace.TYPE_DEDICATED_OFFICE,
                location_label=form.cleaned_data["location_label"],
                approx_people_count=form.cleaned_data["approx_people_count"],
                is_primary=True,
                actor=request.user,
            )
            messages.success(request, "Workplace saved: one office.")
            return redirect("workplace:list", organisation_id=organisation.id)
    else:
        form = OneOfficeOnboardingForm()

    return render(
        request,
        "workplace/onboarding_one_office.html",
        {"organisation": organisation, "form": form},
    )


@login_required
def workplace_onboarding_shared_coworking(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = SharedCoworkingOnboardingForm(request.POST)
        if form.is_valid():
            services.create_workplace(
                organisation=organisation,
                name=form.cleaned_data["name"],
                type=form.cleaned_data["subtype"],
                location_label=form.cleaned_data["location_label"],
                approx_people_count=form.cleaned_data["approx_people_count"],
                is_primary=True,
                actor=request.user,
            )
            messages.success(request, "Workplace saved: shared/coworking office.")
            return redirect("workplace:list", organisation_id=organisation.id)
    else:
        form = SharedCoworkingOnboardingForm()

    return render(
        request,
        "workplace/onboarding_shared_coworking.html",
        {"organisation": organisation, "form": form},
    )


@login_required
def workplace_onboarding_office_and_home(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = OfficeAndHomeOnboardingForm(request.POST)
        if form.is_valid():
            # Two rows, one step (PID §9.1's twenty-person example) - each
            # create_workplace() call is its own atomic write+resync
            # (workplace.services), so this is two ordinary, independently
            # correct writes rather than a special-cased bulk path.
            services.create_workplace(
                organisation=organisation,
                name=form.cleaned_data["office_name"],
                type=Workplace.TYPE_DEDICATED_OFFICE,
                location_label=form.cleaned_data["office_location_label"],
                approx_people_count=form.cleaned_data["office_approx_people_count"],
                is_primary=True,
                actor=request.user,
            )
            services.create_workplace(
                organisation=organisation,
                name="Home / remote working",
                type=Workplace.TYPE_DISTRIBUTED_HOME,
                location_label="",
                approx_people_count=form.cleaned_data["home_approx_people_count"],
                is_primary=False,
                actor=request.user,
            )
            messages.success(request, "Workplace saved: office plus home working.")
            return redirect("workplace:list", organisation_id=organisation.id)
    else:
        form = OfficeAndHomeOnboardingForm()

    return render(
        request,
        "workplace/onboarding_office_and_home.html",
        {"organisation": organisation, "form": form},
    )


# ---------------------------------------------------------------------------
# General list / create / edit / deactivate / activate
# ---------------------------------------------------------------------------
@login_required
def workplace_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    workplaces = list(Workplace.objects.filter(organisation=organisation))
    context = {
        "organisation": organisation,
        "active_workplaces": [w for w in workplaces if w.is_active],
        "inactive_workplaces": [w for w in workplaces if not w.is_active],
    }
    return render(request, "workplace/list.html", context)


@login_required
def workplace_create(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = WorkplaceForm(request.POST)
        if form.is_valid():
            services.create_workplace(
                organisation=organisation,
                name=form.cleaned_data["name"],
                type=form.cleaned_data["type"],
                location_label=form.cleaned_data["location_label"],
                approx_people_count=form.cleaned_data["approx_people_count"],
                is_primary=form.cleaned_data["is_primary"],
                actor=request.user,
            )
            messages.success(request, "Workplace added.")
            return redirect("workplace:list", organisation_id=organisation.id)
        messages.error(request, "The workplace could not be saved. Please check the errors below.")
    else:
        form = WorkplaceForm()

    return render(
        request,
        "workplace/form.html",
        {"organisation": organisation, "form": form, "mode": "create"},
    )


@login_required
def workplace_edit(request, organisation_id, workplace_id):
    organisation, workplace = _get_member_workplace_or_404(
        request.user, organisation_id, workplace_id
    )
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = WorkplaceForm(request.POST, instance=workplace)
        if form.is_valid():
            services.update_workplace(
                workplace,
                actor=request.user,
                name=form.cleaned_data["name"],
                type=form.cleaned_data["type"],
                location_label=form.cleaned_data["location_label"],
                approx_people_count=form.cleaned_data["approx_people_count"],
                is_primary=form.cleaned_data["is_primary"],
            )
            messages.success(request, "Workplace updated.")
            return redirect("workplace:list", organisation_id=organisation.id)
        messages.error(request, "The workplace could not be saved. Please check the errors below.")
    else:
        form = WorkplaceForm(instance=workplace)

    return render(
        request,
        "workplace/form.html",
        {"organisation": organisation, "form": form, "workplace": workplace, "mode": "edit"},
    )


@login_required
def workplace_deactivate(request, organisation_id, workplace_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, workplace = _get_member_workplace_or_404(
        request.user, organisation_id, workplace_id
    )
    services.deactivate_workplace(workplace, actor=request.user)
    messages.success(request, f'Workplace "{workplace.name}" deactivated.')
    return redirect("workplace:list", organisation_id=organisation.id)


@login_required
def workplace_activate(request, organisation_id, workplace_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, workplace = _get_member_workplace_or_404(
        request.user, organisation_id, workplace_id
    )
    services.activate_workplace(workplace, actor=request.user)
    messages.success(request, f'Workplace "{workplace.name}" reactivated.')
    return redirect("workplace:list", organisation_id=organisation.id)
