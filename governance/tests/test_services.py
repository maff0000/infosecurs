import pytest

from activity.models import ActivityEvent

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import GovernanceServiceError, assign_role, ensure_account_holder_person


@pytest.mark.django_db
class TestEnsureAccountHolderPerson:
    def test_creates_a_linked_person_for_the_account_holder(self, org_a, user_a, member_a):
        person = ensure_account_holder_person(org_a, user_a)
        assert person.organisation_id == org_a.id
        assert person.user_id == user_a.id

    def test_calling_twice_does_not_create_a_second_person(self, org_a, user_a, member_a):
        first = ensure_account_holder_person(org_a, user_a)
        second = ensure_account_holder_person(org_a, user_a)
        assert first.pk == second.pk
        assert OrganisationPerson.objects.filter(organisation=org_a, user=user_a).count() == 1

    def test_calling_twice_does_not_duplicate_or_corrupt_role_assignments(
        self, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        ensure_account_holder_person(org_a, user_a)
        assert GovernanceRoleAssignment.objects.filter(organisation=org_a).count() == 3

    def test_default_governance_roles_all_point_to_the_account_holder(
        self, org_a, user_a, member_a
    ):
        person = ensure_account_holder_person(org_a, user_a)
        roles = set(
            GovernanceRoleAssignment.objects.filter(organisation=org_a).values_list(
                "role", flat=True
            )
        )
        assert roles == {
            GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
            GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
        }
        for assignment in GovernanceRoleAssignment.objects.filter(organisation=org_a):
            assert assignment.person_id == person.id

    def test_a_second_call_does_not_clobber_a_manual_reassignment_in_between(
        self, org_a, user_a, member_a
    ):
        """
        Idempotency is "does not duplicate/corrupt", not "resets to
        defaults every time". If the Account Holder has already
        reassigned a role via governance.services.assign_role before this
        function is called again (e.g. a second sign-in), that
        reassignment must survive.
        """
        account_holder = ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=other_person,
            assigned_by=user_a,
        )

        ensure_account_holder_person(org_a, user_a)

        assignment = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        assert assignment.person_id == other_person.id
        assert account_holder.id != other_person.id

    def test_blank_first_and_last_name_falls_back_to_username(self, org_a, member_a, make_user):
        """
        This project's User model may be Django's stock auth.User, whose
        first_name/last_name are blank for a synthetic user created with
        only a username (see make_user's create_user(username=...) call) -
        full_name must never end up empty.
        """
        from organisations.models import OrganisationMembership

        user = make_user("blank_name_user")
        assert user.first_name == ""
        assert user.last_name == ""
        OrganisationMembership.objects.create(organisation=org_a, user=user)

        person = ensure_account_holder_person(org_a, user)
        assert person.full_name == "blank_name_user"

    def test_first_and_last_name_are_used_when_present(self, org_a, member_a, make_user):
        from organisations.models import OrganisationMembership

        user = make_user("named_user")
        user.first_name = "Ada"
        user.last_name = "Lovelace"
        user.save()
        OrganisationMembership.objects.create(organisation=org_a, user=user)

        person = ensure_account_holder_person(org_a, user)
        assert person.full_name == "Ada Lovelace"

    def test_refuses_to_link_a_user_who_is_not_a_member_of_the_organisation(
        self, org_a, user_b
    ):
        """
        PID §7 same-organisation constraint, enforced at the service
        layer (not solely a form/model check) - user_b has no
        OrganisationMembership for org_a at all.
        """
        with pytest.raises(GovernanceServiceError):
            ensure_account_holder_person(org_a, user_b)
        assert not OrganisationPerson.objects.filter(organisation=org_a, user=user_b).exists()

    # --- Activity events (M004-1d-closeout, PID §22) ---------------------
    def test_first_call_emits_one_person_created_and_three_role_changed_events(
        self, org_a, user_a, member_a
    ):
        person = ensure_account_holder_person(org_a, user_a)

        person_events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_ORGANISATION_PERSON_CREATED
        )
        assert person_events.count() == 1
        event = person_events.get()
        assert event.actor_id == user_a.id
        assert event.related_object_type == "organisation_person"
        assert event.related_object_id == str(person.id)
        assert event.metadata == {"full_name": person.full_name}

        role_events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_GOVERNANCE_ROLE_CHANGED
        )
        assert role_events.count() == 3
        for role_event in role_events:
            assert role_event.actor_id == user_a.id
            assert role_event.metadata["previous_person_id"] is None
            assert role_event.metadata["previous_person_name"] is None
            assert role_event.metadata["new_person_id"] == str(person.id)
            assert role_event.metadata["new_person_name"] == person.full_name

    def test_second_call_for_the_same_organisation_and_user_emits_no_further_events(
        self, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        ensure_account_holder_person(org_a, user_a)

        assert (
            ActivityEvent.objects.filter(
                organisation=org_a, event_type=ActivityEvent.EVENT_ORGANISATION_PERSON_CREATED
            ).count()
            == 1
        )
        assert (
            ActivityEvent.objects.filter(
                organisation=org_a, event_type=ActivityEvent.EVENT_GOVERNANCE_ROLE_CHANGED
            ).count()
            == 3
        )


@pytest.mark.django_db
class TestAssignRole:
    def test_reassignment_changes_only_the_targeted_role(self, org_a, user_a, member_a):
        account_holder = ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")

        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=other_person,
            assigned_by=user_a,
        )

        policy_authoriser = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        security_responsible = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE
        )
        senior_leadership = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP
        )
        assert policy_authoriser.person_id == other_person.id
        assert security_responsible.person_id == account_holder.id
        assert senior_leadership.person_id == account_holder.id

    def test_one_person_can_hold_all_roles_by_default(self, org_a, user_a, member_a):
        account_holder = ensure_account_holder_person(org_a, user_a)
        assert (
            GovernanceRoleAssignment.objects.filter(organisation=org_a, person=account_holder).count()
            == 3
        )

    def test_a_different_person_can_also_hold_all_roles_if_reassigned(self, org_a, user_a, member_a):
        ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")
        for role, _label in GovernanceRoleAssignment.ROLE_CHOICES:
            assign_role(organisation=org_a, role=role, person=other_person, assigned_by=user_a)

        assert (
            GovernanceRoleAssignment.objects.filter(organisation=org_a, person=other_person).count()
            == 3
        )
        # And it did not create duplicate OrganisationPerson rows.
        assert OrganisationPerson.objects.filter(organisation=org_a, full_name="Jane Smith").count() == 1

    def test_cross_tenant_assignment_is_rejected_at_the_service_layer(
        self, org_a, org_b, user_a, user_b, member_a, member_b
    ):
        """
        PID §26: "cross-tenant assignment impossible... must be rejected
        at the service layer, not just the form" - calls the service
        function directly with a cross-org person, not only over HTTP.
        """
        ensure_account_holder_person(org_a, user_a)
        person_from_org_b = ensure_account_holder_person(org_b, user_b)

        with pytest.raises(GovernanceServiceError):
            assign_role(
                organisation=org_a,
                role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                person=person_from_org_b,
                assigned_by=user_a,
            )

        # org_a's role must be untouched by the rejected attempt.
        assignment = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        assert assignment.person.organisation_id == org_a.id

    # --- Activity events (M004-1d-closeout, PID §22) ---------------------
    def test_reassigning_a_role_emits_exactly_one_event_with_correct_before_after(
        self, org_a, user_a, member_a
    ):
        account_holder = ensure_account_holder_person(org_a, user_a)
        ActivityEvent.objects.filter(organisation=org_a).delete()  # isolate this call's event
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")

        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=other_person,
            assigned_by=user_a,
        )

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_GOVERNANCE_ROLE_CHANGED
        )
        assert events.count() == 1
        event = events.get()
        assert event.actor_id == user_a.id
        assert event.metadata == {
            "role": GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            "previous_person_id": str(account_holder.id),
            "previous_person_name": account_holder.full_name,
            "new_person_id": str(other_person.id),
            "new_person_name": other_person.full_name,
        }

    def test_reassigning_to_the_already_assigned_person_emits_no_event(
        self, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=other_person,
            assigned_by=user_a,
        )
        ActivityEvent.objects.filter(organisation=org_a).delete()  # isolate the no-op call

        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=other_person,
            assigned_by=user_a,
        )

        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_GOVERNANCE_ROLE_CHANGED
        ).exists()
