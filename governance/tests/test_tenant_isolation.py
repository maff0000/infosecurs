import pytest
from django.urls import reverse

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import GovernanceServiceError, assign_role, ensure_account_holder_person


@pytest.mark.django_db
class TestGovernanceTenantIsolation:
    """
    PID §23 'Every new tenant-owned object must be organisation-scoped';
    PID §26 'cross-tenant assignment impossible'. Two synthetic
    organisations, two users each a member of exactly one, mirroring
    evidence/tests/test_tenant_isolation.py and
    remediation/tests/test_tenant_isolation.py.
    """

    def test_member_cannot_view_other_organisations_role_page(self, client_b, org_a, user_a, member_a):
        ensure_account_holder_person(org_a, user_a)
        response = client_b.get(reverse("governance:roles", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_reassign_a_role_on_another_organisation(
        self, client_b, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        response = client_b.post(
            reverse("governance:roles", args=[org_a.id]),
            {
                "role": GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                "person": "",
                "new_person_full_name": "Hijacked Person",
                "new_person_job_title": "",
            },
        )
        assert response.status_code == 404
        assert not OrganisationPerson.objects.filter(full_name="Hijacked Person").exists()

    def test_member_cannot_use_a_foreign_organisations_person_id_via_their_own_org_url(
        self, client_a, org_a, org_b, user_a, user_b, member_a, member_b
    ):
        """
        user_a IS a member of org_a (the URL organisation is legitimate),
        but the submitted `person` id belongs to org_b. The role-
        assignment form's queryset is already scoped to org_a's active
        people, so this must fail form validation (not silently succeed
        via an ID the form's queryset never offered).
        """
        ensure_account_holder_person(org_a, user_a)
        person_b = ensure_account_holder_person(org_b, user_b)

        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            {
                "role": GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                "person": str(person_b.pk),
                "new_person_full_name": "",
                "new_person_job_title": "",
            },
        )
        assert response.status_code == 200
        assignment = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        assert assignment.person_id != person_b.id

    def test_service_layer_refuses_cross_tenant_assignment_even_with_matching_membership(
        self, org_a, org_b, user_a, user_b, member_a, member_b
    ):
        """
        Direct proof against the service function itself (defence in
        depth), independent of any view/form/URL check - see
        `evidence.tests.test_tenant_isolation`'s equivalent for the same
        pattern in this codebase.
        """
        ensure_account_holder_person(org_a, user_a)
        person_b = ensure_account_holder_person(org_b, user_b)

        with pytest.raises(GovernanceServiceError):
            assign_role(
                organisation=org_a,
                role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
                person=person_b,
                assigned_by=user_a,
            )
        assert not GovernanceRoleAssignment.objects.filter(
            organisation=org_a, person=person_b
        ).exists()

    def test_ensure_account_holder_person_refuses_a_user_with_no_membership_in_that_organisation(
        self, org_a, org_b, user_b
    ):
        """user_b has a membership in org_b, but none in org_a."""
        with pytest.raises(GovernanceServiceError):
            ensure_account_holder_person(org_a, user_b)
        assert not OrganisationPerson.objects.filter(organisation=org_a, user=user_b).exists()

    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        import uuid

        response = client_a.get(reverse("governance:roles", args=[uuid.uuid4()]))
        assert response.status_code == 404
