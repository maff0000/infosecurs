import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import assign_role
from organisations.models import Organisation, OrganisationMembership


@pytest.mark.django_db
def test_no_missing_migrations():
    """
    Fails if the models have drifted from the committed migrations - i.e.
    if a fresh `migrate` would NOT leave the schema matching the models.
    (The test suite itself already proves migrations apply cleanly: every
    test run builds the test database from these migrations against an
    empty Postgres instance - see also the docker-compose clean-bootstrap
    proof in the engineering report.)
    """
    out = io.StringIO()
    call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)


@pytest.mark.django_db
def test_create_customer_zero_is_idempotent(monkeypatch):
    """
    M006 PID §16/§I (Round 6): create_customer_zero must be genuinely safe
    to run twice against the same, already-bootstrapped state - the real
    release-artifact/fresh-reproducibility proof runs it once on a fresh
    database, and an operator could plausibly run it again (e.g. after a
    container restart) without meaning to create a duplicate tenant. This
    exercises the real management command (not a hand-rolled equivalent),
    twice, against a real Postgres row set - not just reading the source
    and asserting it "looks" idempotent.
    """
    monkeypatch.setenv("CUSTOMER_ZERO_USERNAME", "test_customerzero")
    monkeypatch.setenv("CUSTOMER_ZERO_EMAIL", "test_customerzero@example.test")
    monkeypatch.setenv("CUSTOMER_ZERO_PASSWORD", "a-synthetic-test-password-12345")
    monkeypatch.setenv("CUSTOMER_ZERO_ORGANISATION_NAME", "Test Customer Zero Org")

    out1 = io.StringIO()
    call_command("create_customer_zero", stdout=out1)

    User = get_user_model()
    assert User.objects.filter(username="test_customerzero").count() == 1
    assert Organisation.objects.filter(name="Test Customer Zero Org").count() == 1
    assert OrganisationMembership.objects.filter(
        organisation__name="Test Customer Zero Org",
        user__username="test_customerzero",
    ).count() == 1

    user_id_after_first_run = User.objects.get(username="test_customerzero").id
    org_id_after_first_run = Organisation.objects.get(name="Test Customer Zero Org").id

    # Run it again against the same already-bootstrapped state.
    out2 = io.StringIO()
    call_command("create_customer_zero", stdout=out2)

    assert User.objects.filter(username="test_customerzero").count() == 1
    assert Organisation.objects.filter(name="Test Customer Zero Org").count() == 1
    assert OrganisationMembership.objects.filter(
        organisation__name="Test Customer Zero Org",
        user__username="test_customerzero",
    ).count() == 1
    # Same underlying rows, not a delete+recreate that happens to net out
    # to the same counts.
    assert User.objects.get(username="test_customerzero").id == user_id_after_first_run
    assert Organisation.objects.get(name="Test Customer Zero Org").id == org_id_after_first_run
    assert "already exists" in out2.getvalue()


@pytest.mark.django_db
class TestCreateCustomerZeroGovernanceBootstrap:
    """
    M006-AUDIT-0001 F1: `create_customer_zero` must wire in
    `governance.services.ensure_account_holder_person` exactly as
    `organisations.views.organisation_create` already does, so a Customer
    Zero organisation is never left without its Account Holder's governance
    person/role rows.

    The Auditor's finding, reproduced live: for a `create_customer_zero`-
    bootstrapped org, no `OrganisationPerson` existed at all, so the
    Account Holder could not select themselves in the governance role-
    assignment dropdown, and "Approve directly" (policy.services.
    approve_policy_directly, which refuses any actor who is not the
    genuinely assigned Policy Authoriser) was unreachable. Six proof
    points below exercise the real management command (and, for the last
    one, the real HTTP approval view) end to end - not just reading the
    source and asserting it "should" work.
    """

    ORG_NAME = "CZ Gov Synthetic Org"
    USERNAME = "cz_gov_user"

    def _bootstrap(self, monkeypatch):
        monkeypatch.setenv("CUSTOMER_ZERO_USERNAME", self.USERNAME)
        monkeypatch.setenv("CUSTOMER_ZERO_EMAIL", f"{self.USERNAME}@example.test")
        monkeypatch.setenv("CUSTOMER_ZERO_PASSWORD", "a-synthetic-test-password-12345")
        monkeypatch.setenv("CUSTOMER_ZERO_ORGANISATION_NAME", self.ORG_NAME)
        call_command("create_customer_zero", stdout=io.StringIO())

    def _user(self):
        return get_user_model().objects.get(username=self.USERNAME)

    def _organisation(self):
        return Organisation.objects.get(name=self.ORG_NAME)

    # --- Proof point 1 -----------------------------------------------------
    def test_fresh_bootstrap_creates_exactly_one_linked_organisation_person(self, monkeypatch):
        self._bootstrap(monkeypatch)
        user = self._user()
        organisation = self._organisation()
        assert (
            OrganisationPerson.objects.filter(organisation=organisation, user=user).count() == 1
        )

    # --- Proof point 2 -----------------------------------------------------
    def test_fresh_bootstrap_assigns_all_three_default_governance_roles(self, monkeypatch):
        self._bootstrap(monkeypatch)
        user = self._user()
        organisation = self._organisation()
        person = OrganisationPerson.objects.get(organisation=organisation, user=user)

        roles = set(
            GovernanceRoleAssignment.objects.filter(organisation=organisation).values_list(
                "role", flat=True
            )
        )
        assert roles == {
            GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
            GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
        }
        for assignment in GovernanceRoleAssignment.objects.filter(organisation=organisation):
            assert assignment.person_id == person.id

    # --- Proof point 3 -----------------------------------------------------
    def test_rerunning_bootstrap_creates_no_duplicate_organisation_person(self, monkeypatch):
        self._bootstrap(monkeypatch)
        first_person_id = OrganisationPerson.objects.get(
            organisation=self._organisation(), user=self._user()
        ).id

        self._bootstrap(monkeypatch)  # rerun against the same already-bootstrapped state

        organisation = self._organisation()
        user = self._user()
        assert OrganisationPerson.objects.filter(organisation=organisation, user=user).count() == 1
        assert (
            OrganisationPerson.objects.get(organisation=organisation, user=user).id
            == first_person_id
        )

    # --- Proof point 4 -----------------------------------------------------
    def test_rerunning_bootstrap_creates_no_duplicate_or_corrupted_role_assignments(
        self, monkeypatch
    ):
        self._bootstrap(monkeypatch)
        self._bootstrap(monkeypatch)

        organisation = self._organisation()
        assignments = GovernanceRoleAssignment.objects.filter(organisation=organisation)
        assert assignments.count() == 3
        assert assignments.values_list("role", flat=True).distinct().count() == 3
        person = OrganisationPerson.objects.get(organisation=organisation, user=self._user())
        for assignment in assignments:
            assert assignment.person_id == person.id

    # --- Proof point 5 -----------------------------------------------------
    def test_explicit_reassignment_survives_a_further_bootstrap_rerun(self, monkeypatch):
        """
        Idempotency is "does not duplicate/corrupt", not "resets to
        defaults every rerun" - mirrors governance/tests/test_services.py's
        equivalent proof at the service level, exercised here through the
        real management command instead.
        """
        self._bootstrap(monkeypatch)
        organisation = self._organisation()
        account_holder_user = self._user()
        account_holder = OrganisationPerson.objects.get(
            organisation=organisation, user=account_holder_user
        )

        other_person = OrganisationPerson.objects.create(
            organisation=organisation, full_name="Jane Smith"
        )
        assign_role(
            organisation=organisation,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=other_person,
            assigned_by=account_holder_user,
        )

        self._bootstrap(monkeypatch)  # rerun again

        assignment = GovernanceRoleAssignment.objects.get(
            organisation=organisation, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        assert assignment.person_id == other_person.id
        assert assignment.person_id != account_holder.id

    # --- Proof point 6 -----------------------------------------------------
    def test_direct_policy_approval_succeeds_end_to_end_for_a_bootstrapped_org(self, monkeypatch):
        """
        Before the fix, a create_customer_zero-bootstrapped org had no
        linked OrganisationPerson/role assignment at all, so "Approve
        directly" was unreachable - policy.services.approve_policy_directly
        (untouched by this dispatch) refuses any actor who is not the
        genuinely assigned Policy Authoriser (see
        policy/tests/test_approval.py's own equivalent refusal test).
        Proves the whole chain end to end through the real HTTP view: real
        management-command bootstrap -> real login -> real "Approve
        directly" POST -> STATUS_APPROVED / APPROVAL_MODE_DIRECT.
        """
        from policy.models import PolicyDocument, PolicyVersion

        self._bootstrap(monkeypatch)
        user = self._user()
        organisation = self._organisation()

        document = PolicyDocument.objects.create(organisation=organisation)
        version = PolicyVersion.objects.create(
            document=document,
            organisation=organisation,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org Information Security Policy",
            sections=[{"section_key": "purpose_and_scope", "content": "Purpose text."}],
            review_warnings=[],
        )

        client = Client()
        client.force_login(user)
        response = client.post(
            reverse("policy:version_approve_direct", args=[organisation.id, version.id]),
            data={"next_review_date": "2027-01-01"},
        )
        assert response.status_code == 302

        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_APPROVED
        assert version.approval_mode == PolicyVersion.APPROVAL_MODE_DIRECT
        assert version.approved_by_id == user.id
        assert version.policy_authoriser_id == OrganisationPerson.objects.get(
            organisation=organisation, user=user
        ).id
