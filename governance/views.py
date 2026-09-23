from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from organisations.views import get_member_organisation_or_404

from governance import services
from governance.forms import RoleAssignmentForm
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
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        role = request.POST.get("role")
        form = RoleAssignmentForm(request.POST, organisation=organisation)
        if form.is_valid():
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
        role = None

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
                # Re-render the submitted form against the row that failed
                # validation; every other row gets a fresh, blank form.
                "form": form if (form is not None and role == role_key) else RoleAssignmentForm(
                    initial={"role": role_key}, organisation=organisation
                ),
            }
        )

    return render(
        request,
        "governance/role_assignments.html",
        {"organisation": organisation, "rows": rows},
    )
