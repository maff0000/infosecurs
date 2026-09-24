"""
`core/tests`-local fixtures for the M006 §11 security-hardening dispatch.

Mirrors `organisations/tests/conftest.py`'s fixtures exactly (same names,
same behaviour, including the independent-`Client`-per-user fix documented
on `client_a`/`client_b` below) rather than importing them: pytest conftest
fixtures are not implicitly shared across app test packages in this
codebase - every app that needs `org_a`/`org_b`/`client_a`/`client_b`
already re-declares its own copy (see `evidence/tests/conftest.py`,
`policy/tests/conftest.py`, `questionnaire/tests/conftest.py`, etc.) -
so `core/tests` follows the same established convention rather than
inventing a new shared-fixtures mechanism.
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
    return make_user("route_matrix_user_a")


@pytest.fixture
def user_b(make_user):
    return make_user("route_matrix_user_b")


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
    """
    Its own independent `django.test.Client()`, not pytest-django's shared
    `client` fixture - see `organisations/tests/conftest.py`'s identical
    fixture docstring for why (a single shared `Client` instance would let
    whichever of `client_a`/`client_b` resolves last silently win the
    session for both).
    """
    c = Client()
    c.force_login(user_a)
    return c


@pytest.fixture
def client_b(user_b, member_b):
    """See `client_a`'s docstring - the same independent-Client fix."""
    c = Client()
    c.force_login(user_b)
    return c
