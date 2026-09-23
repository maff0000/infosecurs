import pytest
from django.db import IntegrityError, transaction

from governance.models import GovernanceRoleAssignment, OrganisationPerson


@pytest.mark.django_db
class TestOrganisationPerson:
    def test_person_can_be_created_without_a_linked_user(self, org_a):
        person = OrganisationPerson.objects.create(
            organisation=org_a, full_name="Jane Smith", job_title="Managing Director"
        )
        assert person.user is None
        assert person.is_active is True

    def test_two_unlinked_people_are_allowed_in_the_same_organisation(self, org_a):
        OrganisationPerson.objects.create(organisation=org_a, full_name="Person One")
        OrganisationPerson.objects.create(organisation=org_a, full_name="Person Two")
        assert OrganisationPerson.objects.filter(organisation=org_a).count() == 2

    def test_same_user_cannot_be_linked_twice_within_one_organisation(self, org_a, user_a):
        OrganisationPerson.objects.create(organisation=org_a, user=user_a, full_name="User A")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                OrganisationPerson.objects.create(
                    organisation=org_a, user=user_a, full_name="User A duplicate"
                )

    def test_losing_the_user_link_does_not_delete_the_person(self, org_a, user_a):
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="User A"
        )
        user_a.delete()
        person.refresh_from_db()
        assert person.user_id is None
        assert OrganisationPerson.objects.filter(pk=person.pk).exists()


@pytest.mark.django_db
class TestGovernanceRoleAssignment:
    def test_exactly_one_assignment_per_role_per_organisation(self, org_a):
        person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")
        GovernanceRoleAssignment.objects.create(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER, person=person
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                GovernanceRoleAssignment.objects.create(
                    organisation=org_a,
                    role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                    person=person,
                )

    def test_deleting_an_assigned_person_is_protected(self, org_a):
        person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")
        GovernanceRoleAssignment.objects.create(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER, person=person
        )
        from django.db.models import ProtectedError

        with pytest.raises(ProtectedError):
            person.delete()

    def test_assignee_is_inactive_reflects_the_persons_active_state(self, org_a):
        """
        PID §26 'inactive-person handling explicit' - documented chosen
        behaviour (see GovernanceRoleAssignment.assignee_is_inactive's
        docstring): marking the assigned person inactive leaves the
        assignment row untouched; assignee_is_inactive is how that is
        surfaced rather than silently hidden.
        """
        person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")
        assignment = GovernanceRoleAssignment.objects.create(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER, person=person
        )
        assert assignment.assignee_is_inactive is False

        person.is_active = False
        person.save()
        assignment.refresh_from_db()
        assert assignment.person_id == person.id  # assignment left untouched
        assert assignment.assignee_is_inactive is True
