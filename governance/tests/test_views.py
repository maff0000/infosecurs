import pytest
from django.urls import reverse

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import ensure_account_holder_person


def _prefixed(role_key, **fields):
    """
    Build POST data for one row's form the way a real browser actually
    submits it now each row has `prefix=role_key` (M004 post-audit repair,
    Finding 2). Always includes the hidden `role` field, since the view
    determines which row was submitted by checking for
    `f"{role_key}-role"` in `request.POST`.
    """
    data = {"role": role_key, "person": "", "new_person_full_name": "", "new_person_job_title": ""}
    data.update(fields)
    return {f"{role_key}-{name}": value for name, value in data.items()}


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

    def test_each_rows_fields_have_distinct_ids(self, client_a, org_a, user_a, member_a):
        # M004 post-audit repair, Finding 2 (accessibility): the Auditor
        # proved via document.querySelectorAll('[id="id_person"]') that
        # all three rows rendered identical ids. Each row must now render
        # a unique, correctly-prefixed id exactly once.
        ensure_account_holder_person(org_a, user_a)
        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()

        for field_name in ["person", "role", "new_person_full_name", "new_person_job_title"]:
            # The old, unprefixed id must not appear at all.
            assert content.count(f'id="id_{field_name}"') == 0, field_name
            for role_key, _label in GovernanceRoleAssignment.ROLE_CHOICES:
                expected_id = f'id="id_{role_key}-{field_name}"'
                assert content.count(expected_id) == 1, (field_name, role_key, content.count(expected_id))

    def test_reassign_to_a_newly_created_person(self, client_a, org_a, user_a, member_a):
        ensure_account_holder_person(org_a, user_a)
        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            _prefixed(
                GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                new_person_full_name="Jane Smith",
                new_person_job_title="Managing Director",
            ),
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
            _prefixed(
                GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
                person=str(other_person.pk),
            ),
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
            _prefixed(
                GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
                person=str(other_person.pk),
            ),
        )

        policy_authoriser = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        security_responsible = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE
        )
        assert policy_authoriser.person_id == account_holder.id
        assert security_responsible.person_id == account_holder.id

    def test_reassigning_the_second_row_updates_only_that_row_not_the_first(
        self, client_a, org_a, user_a, member_a
    ):
        # M004 post-audit repair, Finding 2: proves the POST-branch's
        # which-row-was-submitted logic actually keys off the submitted
        # prefix, not always row 1 - the exact regression the missing
        # prefix caused (unprefixed POST data was ambiguous about which
        # row it belonged to).
        account_holder = ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")

        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            _prefixed(
                GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
                person=str(other_person.pk),
            ),
        )
        assert response.status_code == 302

        security_responsible = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE
        )
        policy_authoriser = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        senior_leadership = GovernanceRoleAssignment.objects.get(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP
        )
        assert security_responsible.person_id == other_person.id
        assert policy_authoriser.person_id == account_holder.id
        assert senior_leadership.person_id == account_holder.id

    def test_submitting_both_an_existing_and_a_new_person_is_a_validation_error(
        self, client_a, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")

        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            _prefixed(
                GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                person=str(other_person.pk),
                new_person_full_name="Another Person",
            ),
        )
        assert response.status_code == 200
        assert not OrganisationPerson.objects.filter(full_name="Another Person").exists()

    def test_submitting_neither_an_existing_nor_a_new_person_is_a_validation_error(
        self, client_a, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)
        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            _prefixed(GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER),
        )
        assert response.status_code == 200

    def test_inactive_assignee_is_surfaced_on_the_page(self, client_a, org_a, user_a, member_a):
        person = ensure_account_holder_person(org_a, user_a)
        person.is_active = False
        person.save()

        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        assert response.status_code == 200
        assert b"marked inactive" in response.content

    # --- M006-AUDIT-0001 F1: the "you are currently listed..." banner must
    # reflect genuine current assignment state, not an unconditional claim
    # (the Auditor's finding: it said this even when every role fieldset
    # below correctly said "Not yet assigned"). ------------------------------
    def test_banner_lists_all_three_roles_when_genuinely_assigned_all_three(
        self, client_a, org_a, user_a, member_a
    ):
        ensure_account_holder_person(org_a, user_a)  # defaults all three to the account holder
        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        content = response.content.decode()
        assert "you are currently listed as" in content.lower()
        assert "policy authoriser" in content.lower()
        assert "security responsible person" in content.lower()
        assert "senior leadership representative" in content.lower()

    def test_banner_says_not_listed_when_no_governance_person_exists_for_the_user(
        self, client_a, org_a, user_a, member_a
    ):
        # Defensive edge case, same class ensure_account_holder_person's own
        # docstring and role_assignments' own docstring already document: a
        # synthetic/test organisation reached without going through
        # ensure_account_holder_person at all - no OrganisationPerson, no
        # role assignments, so the banner must not claim any role for this
        # user (it also must not error).
        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "you are not currently listed" in content.lower()
        # And every role fieldset below genuinely says "Not yet assigned" -
        # the banner and the fieldsets must never contradict each other.
        assert content.count("Not yet assigned.") == 3

    def test_banner_only_lists_roles_actually_assigned_to_the_signed_in_user(
        self, client_a, org_a, user_a, member_a
    ):
        account_holder = ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jane Smith")
        from governance.services import assign_role

        # Reassign one of the three roles away from the signed-in user.
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=other_person,
            assigned_by=user_a,
        )

        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        content = response.content.decode()
        lowered = content.lower()
        assert "you are currently listed as" in lowered
        # Still-held roles are named...
        assert "security responsible person" in lowered
        assert "senior leadership representative" in lowered
        # ...but the reassigned-away role is not claimed for this user in
        # the banner's own comma-joined list (it still appears once, lower
        # in the page, inside that role's own "Currently assigned to Jane
        # Smith" fieldset text - this checks the banner sentence itself).
        banner_start = lowered.index("you are currently listed as")
        banner_sentence_end = lowered.index(".", banner_start)
        banner_sentence = lowered[banner_start:banner_sentence_end]
        assert "policy authoriser" not in banner_sentence
        assert account_holder.id != other_person.id


@pytest.mark.django_db
class TestEditMyDetailsView:
    def test_get_renders_current_values(self, client_a, org_a, user_a, member_a):
        person = ensure_account_holder_person(org_a, user_a)
        response = client_a.get(reverse("governance:edit_my_details", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert person.full_name in content

    def test_post_updates_full_name_and_job_title(self, client_a, org_a, user_a, member_a):
        person = ensure_account_holder_person(org_a, user_a)
        response = client_a.post(
            reverse("governance:edit_my_details", args=[org_a.id]),
            {"full_name": "Ada Holder", "job_title": "Chief Executive"},
        )
        assert response.status_code == 302
        person.refresh_from_db()
        assert person.full_name == "Ada Holder"
        assert person.job_title == "Chief Executive"

    def test_missing_full_name_is_a_validation_error_and_does_not_save(
        self, client_a, org_a, user_a, member_a
    ):
        person = ensure_account_holder_person(org_a, user_a)
        original_name = person.full_name
        response = client_a.post(
            reverse("governance:edit_my_details", args=[org_a.id]),
            {"full_name": "", "job_title": "Chief Executive"},
        )
        assert response.status_code == 200
        person.refresh_from_db()
        assert person.full_name == original_name

    def test_missing_linked_person_is_a_404_not_a_500(self, client_a, org_a, user_a, member_a):
        # Defensive edge case: a synthetic/test organisation reached
        # without going through ensure_account_holder_person, so the
        # requesting user has no linked OrganisationPerson row yet.
        response = client_a.get(reverse("governance:edit_my_details", args=[org_a.id]))
        assert response.status_code == 404

    def test_cross_tenant_user_cannot_reach_or_edit_another_organisations_account_holder(
        self, client_b, org_a, org_b, user_a, user_b, member_a, member_b
    ):
        ensure_account_holder_person(org_a, user_a)
        ensure_account_holder_person(org_b, user_b)

        # org_b's member requesting org_a's URL is an ordinary 404 (not a
        # member of org_a at all) - same tenant-scoping as every other
        # view in this codebase (get_member_organisation_or_404).
        response = client_b.get(reverse("governance:edit_my_details", args=[org_a.id]))
        assert response.status_code == 404

        post_response = client_b.post(
            reverse("governance:edit_my_details", args=[org_a.id]),
            {"full_name": "Hijacked Name", "job_title": ""},
        )
        assert post_response.status_code == 404
        org_a_person = OrganisationPerson.objects.get(organisation=org_a, user=user_a)
        assert org_a_person.full_name != "Hijacked Name"

    def test_endpoint_takes_no_person_id_so_cannot_target_another_person_in_the_same_org(
        self, client_a, org_a, user_a, member_a
    ):
        # There is deliberately no person-id parameter anywhere in this
        # URL/form to manipulate: editing always resolves to the
        # requesting user's own linked person, never another named person
        # in the same organisation (PID §8.1's "not a separate
        # person-management CRUD subsystem").
        account_holder = ensure_account_holder_person(org_a, user_a)
        other_person = OrganisationPerson.objects.create(
            organisation=org_a, full_name="Someone Else"
        )

        response = client_a.post(
            reverse("governance:edit_my_details", args=[org_a.id]),
            {"full_name": "Still Me", "job_title": ""},
        )
        assert response.status_code == 302
        account_holder.refresh_from_db()
        other_person.refresh_from_db()
        assert account_holder.full_name == "Still Me"
        assert other_person.full_name == "Someone Else"
