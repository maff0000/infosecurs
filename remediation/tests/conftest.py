"""
Local fixtures for remediation tests, mirroring
organisations/tests/conftest.py, key_assets/tests/conftest.py and
risk_register/tests/conftest.py 1:1 (two synthetic organisations, two
users, one membership each, two logged-in clients) so remediation tests do
not depend on importing fixtures across an app boundary from apps that are
read-only to this dispatch.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from key_assets.models import KeyAsset
from organisations.models import Organisation, OrganisationMembership
from risk_register.models import Risk


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


@pytest.fixture
def confirmed_asset_a(db, org_a):
    return KeyAsset.objects.create(
        organisation=org_a,
        name="Org A confirmed asset",
        category="endpoint",
        criticality="medium",
        status=KeyAsset.STATUS_CONFIRMED,
    )


def _risk(org, **overrides):
    defaults = dict(
        organisation=org,
        title="Org risk",
        threat="t",
        vulnerability="v",
        impact=3,
        likelihood=3,
        rationale="r",
        proposed_treatment="Do the treatment thing.",
        status=Risk.STATUS_CONFIRMED,
    )
    defaults.update(overrides)
    return Risk.objects.create(**defaults)


@pytest.fixture
def risk_a(db, org_a):
    return _risk(org_a, title="Org A risk", proposed_treatment="Org A proposed treatment.")


@pytest.fixture
def risk_b(db, org_b):
    return _risk(org_b, title="Org B risk", proposed_treatment="Org B proposed treatment.")
