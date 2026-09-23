"""
Local fixtures for key_assets tests, mirroring organisations/tests/conftest.py
1:1 (two synthetic organisations, two users, one membership each, two logged
-in clients) so key_assets tests do not depend on importing fixtures across
the app boundary from the organisations package (read-only to this
dispatch).
"""
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
