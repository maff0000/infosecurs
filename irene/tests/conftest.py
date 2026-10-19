"""
Local fixtures for `irene` tests, mirroring `security_tasks/tests/
conftest.py`/`foundations_journey/tests/conftest.py` 1:1 (this codebase's
own established per-app fixture-duplication convention).
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

from entitlements.session import issue_context
from entitlements.tiers import TIER_MONTHLY
from organisations.models import Organisation, OrganisationMembership


@pytest.fixture
def make_user(db):
    def _make_user(username, password="a-strong-test-password-123"):
        User = get_user_model()
        return User.objects.create_user(username=username, password=password)

    return _make_user


@pytest.fixture
def org_a(db):
    return Organisation.objects.create(name="IRENE Org A Synthetic Ltd")


@pytest.fixture
def org_b(db):
    return Organisation.objects.create(name="IRENE Org B Synthetic Ltd")


@pytest.fixture
def user_a(make_user):
    return make_user("irene_user_a")


@pytest.fixture
def user_b(make_user):
    return make_user("irene_user_b")


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
    """A second member of org_a."""
    return make_user("irene_user_c")


@pytest.fixture
def member_c(db, org_a, user_c):
    return OrganisationMembership.objects.create(
        organisation=org_a, user=user_c, role=OrganisationMembership.ROLE_OWNER
    )


class FakeRequest:
    """A minimal stand-in for `django.http.HttpRequest`, carrying exactly
    what `entitlements.capabilities.has_capability`/`irene.tools.
    _revalidate` read (`.session`, `.user`) - the SAME pattern
    `entitlements/tests/test_capabilities.py`'s own `FakeRequest`/
    `request_at_tier` already establish, reused here rather than
    reinvented, for tool/service-layer tests that need a real, capability-
    checkable `AuthorizedContext` without going through the full HTTP
    view stack."""

    def __init__(self, session, user):
        self.session = session
        self.user = user


def request_at_tier(user, tier=TIER_MONTHLY, organisation_id=None):
    store = SessionStore()
    store.save()
    request = FakeRequest(store, user)
    issue_context(request, user, package_tier=tier, auth_source="test_fixture", organisation_id=organisation_id)
    return request


@pytest.fixture
def idempotency_key():
    return str(uuid.uuid4())
