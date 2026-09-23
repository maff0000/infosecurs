"""
Local fixtures for evidence tests, mirroring
key_assets/tests/conftest.py / organisations/tests/conftest.py 1:1 (two
synthetic organisations, two users, one membership each, two logged-in
clients), plus an isolated, per-test EVIDENCE_STORAGE_ROOT so file tests
never touch a shared/real evidence directory and never leak state between
tests.
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


@pytest.fixture(autouse=True)
def evidence_storage_root(tmp_path, monkeypatch):
    """
    Every evidence test gets its own throwaway storage directory via
    EVIDENCE_STORAGE_ROOT, so tests never depend on (or pollute) a shared
    path and never need Docker's real /data/evidence volume to run.
    """
    root = tmp_path / "evidence-storage"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_STORAGE_ROOT", str(root))
    return root
