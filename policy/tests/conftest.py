"""
Local fixtures for policy tests, mirroring workplace/tests/conftest.py /
key_assets/tests/conftest.py 1:1 (two synthetic organisations, two users,
one membership each, two logged-in clients). Duplicated rather than
imported across the app boundary, matching this codebase's existing
convention.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import assign_role
from organisations.models import Organisation, OrganisationMembership
from policy.models import PolicyDocument, PolicyVersion


@pytest.fixture
def make_user(db):
    def _make_user(username, password="a-strong-test-password-123"):
        User = get_user_model()
        return User.objects.create_user(username=username, password=password)

    return _make_user


@pytest.fixture
def org_a(db):
    return Organisation.objects.create(name="Org A Synthetic Ltd")


@pytest.fixture
def org_b(db):
    return Organisation.objects.create(name="Org B Synthetic Ltd")


@pytest.fixture
def user_a(make_user):
    return make_user("user_a")


@pytest.fixture
def user_b(make_user):
    return make_user("user_b")


@pytest.fixture
def member_a(db, org_a, user_a):
    """user_a is a member of org_a only."""
    return OrganisationMembership.objects.create(
        organisation=org_a, user=user_a, role=OrganisationMembership.ROLE_OWNER
    )


@pytest.fixture
def member_b(db, org_b, user_b):
    """user_b is a member of org_b only."""
    return OrganisationMembership.objects.create(
        organisation=org_b, user=user_b, role=OrganisationMembership.ROLE_OWNER
    )


@pytest.fixture
def client_a(user_a, member_a):
    """Independent django.test.Client() - see organisations/tests/conftest.py's
    client_a docstring for why (a shared-Client bug found by the M003-1a
    Evidence dispatch, fixed identically here)."""
    c = Client()
    c.force_login(user_a)
    return c


@pytest.fixture
def client_b(user_b, member_b):
    """See client_a's docstring."""
    c = Client()
    c.force_login(user_b)
    return c


# --- Governance fixtures (M004 PID §17-18 lifecycle tests - m004-2b) ------------
# Duplicated (not imported) from governance/tests/conftest.py's own
# equivalents, matching this conftest's existing "no cross-app fixture
# import" convention documented at the top of this file.

@pytest.fixture
def person_a(db, org_a, user_a):
    """A named `OrganisationPerson` for org_a, linked to `user_a` - the
    "Account Holder is also Policy Authoriser" case (PID §17.1)."""
    return OrganisationPerson.objects.create(
        organisation=org_a, user=user_a, full_name="Ada Holder", job_title="Managing Director"
    )


@pytest.fixture
def external_person_a(db, org_a):
    """A named `OrganisationPerson` for org_a with NO login - the
    "different named Policy Authoriser" case (PID §17.2)."""
    return OrganisationPerson.objects.create(
        organisation=org_a, user=None, full_name="Jane Smith", job_title="Operations Director"
    )


@pytest.fixture
def assign_policy_authoriser():
    """`assign_policy_authoriser(organisation, person)` - the one write
    path for `GovernanceRoleAssignment` (`governance.services.assign_role`),
    exposed as a fixture so lifecycle tests don't need to import/construct
    it themselves each time."""

    def _assign(organisation, person, assigned_by=None):
        return assign_role(
            organisation=organisation,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=person,
            assigned_by=assigned_by,
        )

    return _assign


# --- Policy version fixtures ----------------------------------------------------

@pytest.fixture
def make_draft_version(db):
    """`make_draft_version(organisation, **overrides)` - a directly-created
    `PolicyVersion` (no AI gateway involved), for lifecycle tests that only
    care about edit/approval/download behaviour, not generation itself.
    Mirrors `policy/tests/test_models.py`'s own `_version` helper. Reuses
    (via `get_or_create`) this organisation's single `PolicyDocument`
    (PID §15 "one active logical Information Security Policy per
    organisation") so a test can call this more than once for the same
    organisation, as long as it passes distinct `version_number`s."""

    def _make(organisation, *, version_number=1, sections=None, title="Org Information Security Policy", **overrides):
        document, _ = PolicyDocument.objects.get_or_create(organisation=organisation)
        defaults = dict(
            document=document,
            organisation=organisation,
            version_number=version_number,
            status=PolicyVersion.STATUS_DRAFT,
            title=title,
            sections=sections
            if sections is not None
            else [
                {"section_key": "purpose_and_scope", "content": "Purpose text."},
                {"section_key": "access_and_authentication", "content": "Access text."},
            ],
            review_warnings=[],
        )
        defaults.update(overrides)
        return PolicyVersion.objects.create(**defaults)

    return _make
