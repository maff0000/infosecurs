"""Local fixtures, mirroring organisations/tests/conftest.py and
security_tasks/tests/conftest.py 1:1 - this codebase's own established
per-app fixture-duplication convention."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from organisations.models import Organisation, OrganisationMembership


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
    return OrganisationMembership.objects.create(
        organisation=org_a, user=user_a, role=OrganisationMembership.ROLE_OWNER
    )


@pytest.fixture
def member_b(db, org_b, user_b):
    return OrganisationMembership.objects.create(
        organisation=org_b, user=user_b, role=OrganisationMembership.ROLE_OWNER
    )


@pytest.fixture
def client_a(user_a, member_a):
    c = Client()
    c.force_login(user_a)
    return c


@pytest.fixture
def client_b(user_b, member_b):
    c = Client()
    c.force_login(user_b)
    return c


@pytest.fixture
def user_c(make_user):
    """A second member of org_a - used to prove a colleague shares the
    same canonical answers but has an independent navigation
    checkpoint."""
    return make_user("user_c")


@pytest.fixture
def member_c(db, org_a, user_c):
    return OrganisationMembership.objects.create(
        organisation=org_a, user=user_c, role=OrganisationMembership.ROLE_OWNER
    )


@pytest.fixture
def client_c(user_c, member_c):
    c = Client()
    c.force_login(user_c)
    return c
