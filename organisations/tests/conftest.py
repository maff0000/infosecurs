import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
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
    """
    Its own independent `django.test.Client()`, not pytest-django's shared
    `client` fixture. `client_a`/`client_b` both used to depend on `client`
    and `force_login` onto it - a single shared `Client` instance, so a test
    requesting both fixtures got `client_a` silently logged in as `user_b`
    too, the moment `client_b` was resolved (whichever fixture resolves
    last wins the shared session). Found and documented by the M003-1a
    Evidence dispatch while writing a same-test two-tenant check; fixed
    here so every app's tenant-isolation tests - existing and future - can
    safely request both fixtures in one test.
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


@pytest.fixture(autouse=True)
def evidence_storage_root(tmp_path, monkeypatch):
    """
    M008A: every organisations test gets its own throwaway
    EVIDENCE_STORAGE_ROOT, mirroring evidence/tests/conftest.py's own
    identically-named autouse fixture 1:1 - needed here because the M008A
    reset-service/reset-view tests in this package create real evidence
    files on disk. Autouse and harmless for every other, pre-existing test
    in this package that never touches evidence storage at all.
    """
    root = tmp_path / "evidence-storage"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_STORAGE_ROOT", str(root))
    return root


@pytest.fixture(autouse=True)
def questionnaire_storage_root(tmp_path, monkeypatch):
    """
    M009A: every organisations test gets its own throwaway
    QUESTIONNAIRE_STORAGE_ROOT, mirroring `evidence_storage_root` above
    1:1 - needed here because the M009A Customer Zero reset reconciliation
    tests in this package create real questionnaire-import files on disk.
    """
    root = tmp_path / "questionnaire-storage"
    root.mkdir()
    monkeypatch.setenv("QUESTIONNAIRE_STORAGE_ROOT", str(root))
    return root


@pytest.fixture
def customer_zero_bootstrap(db, monkeypatch):
    """
    M008A (docs/evidence/M008A-RESET-DELETION-MANIFEST.md): bootstraps a
    genuine Customer Zero fixture organisation via the REAL
    `create_customer_zero` management command - not a hand-rolled
    equivalent - so `CustomerZeroFixture`, the Owner `OrganisationMembership`,
    and the Account Holder's `OrganisationPerson` + all three
    `GovernanceRoleAssignment` rows all exist exactly as a real bootstrap
    would leave them. Mirrors the exact pattern already established in
    `organisations/tests/test_bootstrap.py`'s `TestCreateCustomerZeroGovernanceBootstrap`.

    Returns `(user, organisation)`.
    """
    username = "cz_reset_fixture_user"
    monkeypatch.setenv("CUSTOMER_ZERO_USERNAME", username)
    monkeypatch.setenv("CUSTOMER_ZERO_EMAIL", f"{username}@example.test")
    monkeypatch.setenv("CUSTOMER_ZERO_PASSWORD", "a-synthetic-test-password-12345")
    monkeypatch.setenv("CUSTOMER_ZERO_ORGANISATION_NAME", "CZ Reset Fixture Synthetic Org")
    call_command("create_customer_zero", stdout=io.StringIO())

    user = get_user_model().objects.get(username=username)
    organisation = Organisation.objects.get(name="CZ Reset Fixture Synthetic Org")
    return user, organisation


@pytest.fixture
def customer_zero_user(customer_zero_bootstrap):
    return customer_zero_bootstrap[0]


@pytest.fixture
def customer_zero_org(customer_zero_bootstrap):
    return customer_zero_bootstrap[1]


@pytest.fixture
def customer_zero_client(customer_zero_user):
    """Independent `Client()` - see `client_a`'s docstring for why."""
    c = Client()
    c.force_login(customer_zero_user)
    return c
