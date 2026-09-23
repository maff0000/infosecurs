import pytest
from django.urls import reverse

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import ensure_account_holder_person


@pytest.mark.django_db
class TestRoleAssignmentsView:
    def test_page_shows_the_account_holder_as_default_assignee_for_all_three_roles(
        self, client_a, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert content.count(user_a.username) >= 3 or content.count("Currently assigned to") == 3

    def test_reassign_to_a_newly_created_person(self, client_a, org_a, user_a, member_a):
        ensure_account_holder_person(org_a, user_a)
        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            {
                "role": GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                "person": "",
                "new_person_full_name": "Jane Smith",
                "new_person_job_title": "Managing Director",
            },
        )
        assert response.status_code == 302

        person = OrganisationPerson.objects.get(organisation=org_a, full_name="Jane Smith")
        assignment = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        assert assignment.person_id == person.id
        assert person.user is None

    def test_reassign_to_an_existing_person(self, client_a, org_a, user_a, member_a):
        ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")

        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            {
                "role": GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
                "person": str(other_person.pk),
                "new_person_full_name": "",
                "new_person_job_title": "",
            },
        )
        assert response.status_code == 302
        assignment = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE
        )
        assert assignment.person_id == other_person.id

    def test_reassigning_one_role_leaves_the_other_two_untouched(
        self, client_a, org_a, user_a, member_a
    ):
        account_holder = ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")

        client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            {
                "role": GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
                "person": str(other_person.pk),
                "new_person_full_name": "",
                "new_person_job_title": "",
            },
        )

        policy_authoriser = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        security_responsible = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE
        )
        assert policy_authoriser.person_id == account_holder.id
        assert security_responsible.person_id == account_holder.id

    def test_submitting_both_an_existing_and_a_new_person_is_a_validation_error(
        self, client_a, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")

        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            {
                "role": GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                "person": str(other_person.pk),
                "new_person_full_name": "Another Person",
                "new_person_job_title": "",
            },
        )
        assert response.status_code == 200
        assert not OrganisationPerson.objects.filter(full_name="Another Person").exists()

    def test_submitting_neither_an_existing_nor_a_new_person_is_a_validation_error(
        self, client_a, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            {
                "role": GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                "person": "",
                "new_person_full_name": "",
                "new_person_job_title": "",
            },
        )
        assert response.status_code == 200

    def test_inactive_assignee_is_surfaced_on_the_page(self, client_a, org_a, user_a, member_a):
        person = ensure_account_holder_person(org_a, user_a)
        person.is_active = False
        person.save()

        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        assert response.status_code == 200
        assert b"marked inactive" in response.content
