"""
Local fixtures for entitlements tests, mirroring organisations/tests/
conftest.py 1:1 (this codebase's own established convention - see e.g.
policy/tests/conftest.py's docstring - of duplicating small fixtures per
app rather than importing them across an app boundary), plus a
`set_session_tier` helper this app's own WI2 navigation tests use to force
a client's `infosecurs_context` to an exact tier without depending on a
production "switch my tier" endpoint (PID §7.1 - no such endpoint exists;
this directly writes the same shape `entitlements.session.issue_context`
would, the same technique `entitlements/tests/test_capabilities.py`'s own
`request_at_tier` helper already uses for non-Client-based tests).
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone as django_timezone

from entitlements.session import ENTITLEMENT_VERSION, SCHEMA_VERSION, SESSION_KEY
from entitlements.tiers import tier_code
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
    """See organisations/tests/conftest.py's client_a docstring for why
    this is its own independent Client() rather than the shared `client`
    fixture. Logging in issues a real MONTHLY `infosecurs_context` via the
    `user_logged_in` signal (entitlements/signals.py) - tests that need a
    different tier use `set_session_tier` below afterwards."""
    c = Client()
    c.force_login(user_a)
    return c


@pytest.fixture
def client_b(user_b, member_b):
    c = Client()
    c.force_login(user_b)
    return c


def set_session_tier(client, user, tier, organisation_id=None):
    """
    Overwrites the given (already-logged-in) test client's
    `infosecurs_context` to an exact tier - the smallest safe test-only
    seam for proving the 4-tier navigation matrix (PID §7.1's own
    "a test helper that directly creates server-side session context is
    also acceptable"), never a production route. Writes exactly the shape
    `entitlements.session.issue_context` writes so
    `entitlements.session.validate_context` accepts it as genuinely valid,
    not a tampered/malformed context.
    """
    session = client.session
    session[SESSION_KEY] = {
        "schema_version": SCHEMA_VERSION,
        "subject_id": str(user.pk),
        "organisation_id": str(organisation_id) if organisation_id is not None else None,
        "package_tier": tier,
        "package_code": tier_code(tier),
        "entitlement_version": ENTITLEMENT_VERSION,
        "issued_at": django_timezone.now().isoformat(),
        "auth_source": "test_fixture",
    }
    session.save()
