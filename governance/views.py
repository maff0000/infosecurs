from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from organisations.views import get_member_organisation_or_404

from governance import services
from governance.forms import MyDetailsForm, RoleAssignmentForm
from governance.models import GovernanceRoleAssignment, OrganisationPerson


@login_required
def role_assignments(request, organisation_id):
    """
    PID §8.1's "Role UX": one page listing the three governance roles and
    their current assignee, with a way to reassign each (create-new-
    person-inline or pick an existing active person) - not a separate
    person-management CRUD subsystem.

    Tenant scoping matches every other app's views in this codebase:
    `get_member_organisation_or_404` (organisations.views) both verifies
    membership and does the lookup in one query, so a non-member or a
    manipulated organisation id in the URL is an ordinary 404.

    `governance.services.ensure_account_holder_person` guarantees all
    three roles already have a row by the time an Account Holder can reach
    this page in the normal product flow (it is wired into
    `organisations.views.organisation_create`); this view still copes if a
    role has no assignment yet (a defensive/edge case, e.g. a synthetic
    test organisation created without going through that flow), showing
    "Not yet assigned" rather than erroring.

    Each row's `RoleAssignmentForm` is constructed with `prefix=role_key`
    (M004 post-audit repair, Finding 2 - accessibility): the view
    instantiates the same form three times, once per row, and with no
    prefix every row rendered identical field ids (`id="id_person"` etc)
    three times over, so a `<label for="...">` on rows 2/3 resolved to row
    1's field instead of its own. `role_key` is already unique and stable
    per row, so it doubles as the prefix.

    That prefix means the submitted POST data now arrives as
    `f"{role_key}-role"`/`f"{role_key}-person"`/etc, not the bare
    `"role"`/`"person"` this view used to read directly - so which row was
    submitted is now determined by checking which of the three known role
    keys' prefixed data is actually present in `request.POST` (only one
    row's `<form>` is ever the one actually submitted, since each row
    renders as its own independent `<form>` tag).
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        submitted_role_key = None
        for candidate_key, _candidate_label in GovernanceRoleAssignment.ROLE_CHOICES:
            if f"{candidate_key}-role" in request.POST:
                submitted_role_key = candidate_key
                break

        form = RoleAssignmentForm(
            request.POST, organisation=organisation, prefix=submitted_role_key
        )
        if submitted_role_key is not None and form.is_valid():
            person = form.cleaned_data["person"]
            new_full_name = form.cleaned_data["new_person_full_name"]
            if person is None:
                person = OrganisationPerson.objects.create(
                    organisation=organisation,
                    full_name=new_full_name,
                    job_title=form.cleaned_data["new_person_job_title"],
                )
            services.assign_role(
                organisation=organisation,
                role=form.cleaned_data["role"],
                person=person,
                assigned_by=request.user,
            )
            role_label = dict(GovernanceRoleAssignment.ROLE_CHOICES)[form.cleaned_data["role"]]
            messages.success(request, f"{role_label} reassigned to {person.full_name}.")
            return redirect("governance:roles", organisation_id=organisation.id)
        messages.error(
            request, "That role could not be reassigned. Please check the errors below."
        )
    else:
        form = None
        submitted_role_key = None

    assignments_by_role = {
        assignment.role: assignment
        for assignment in GovernanceRoleAssignment.objects.filter(
            organisation=organisation
        ).select_related("person")
    }

    rows = []
    for role_key, role_label in GovernanceRoleAssignment.ROLE_CHOICES:
        rows.append(
            {
                "role": role_key,
                "label": role_label,
                "assignment": assignments_by_role.get(role_key),
                # Re-render the submitted form (still correctly prefixed)
                # against the row that failed validation; every other row
                # gets its own fresh, blank form - same prefix scheme as
                # the GET-time default below, so ids never collide.
                "form": form
                if (form is not None and role_key == submitted_role_key)
                else RoleAssignmentForm(
                    initial={"role": role_key}, organisation=organisation, prefix=role_key
                ),
            }
        )

    # M006-AUDIT-0001 F1: the "you are currently listed as..." banner must
    # reflect genuine current assignment state, derived from the same
    # `assignments_by_role` source of truth the three role fieldsets above
    # already use - not a second, parallel representation. A role only
    # counts as "mine" if it is assigned to the OrganisationPerson linked to
    # request.user (there may be none, e.g. a synthetic test organisation
    # created without going through `ensure_account_holder_person`).
    my_person = OrganisationPerson.objects.filter(
        organisation=organisation, user=request.user
    ).first()
    my_role_labels = [
        role_label
        for role_key, role_label in GovernanceRoleAssignment.ROLE_CHOICES
        if my_person is not None
        and assignments_by_role.get(role_key) is not None
        and assignments_by_role[role_key].person_id == my_person.id
    ]

    return render(
        request,
        "governance/role_assignments.html",
        {"organisation": organisation, "rows": rows, "my_role_labels": my_role_labels},
    )


@login_required
def edit_my_details(request, organisation_id):
    """
    PID §3 user outcome #4 ("confirm/edit their name and job title") -
    M004 post-audit repair, Finding 3. Deliberately scoped to exactly one
    row: the requesting user's own linked `OrganisationPerson` in this
    organisation. There is no person id anywhere in this URL/view -
    `person` is looked up by `(organisation, user=request.user)`, so there
    is no way to reach or edit anyone else's record through this endpoint
    (PID §8.1 "not a separate person-management CRUD subsystem" -
    `role_assignments` already covers reassigning roles to *other* named
    people; this stays narrowly "edit my own details").

    `governance.services.ensure_account_holder_person` guarantees this row
    exists by the time an Account Holder can reach this page in the
    ordinary product flow (wired into
    `organisations.views.organisation_create`); this view still 404s
    defensively rather than 500ing if it is somehow missing (e.g. a
    synthetic test organisation created without going through that flow) -
    same defensive posture `role_assignments`'s own docstring documents
    for missing role assignments.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    person = get_object_or_404(
        OrganisationPerson, organisation=organisation, user=request.user
    )

    if request.method == "POST":
        form = MyDetailsForm(request.POST, instance=person)
        if form.is_valid():
            form.save()
            messages.success(request, "Your details have been updated.")
            return redirect("governance:roles", organisation_id=organisation.id)
    else:
        form = MyDetailsForm(instance=person)

    return render(
        request,
        "governance/edit_my_details.html",
        {"organisation": organisation, "form": form},
    )
