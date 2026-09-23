"""
Local fixtures for risk_register tests, mirroring
organisations/tests/conftest.py and key_assets/tests/conftest.py 1:1 (two
synthetic organisations, two users, one membership each, two logged-in
clients) so risk_register tests do not depend on importing fixtures across
an app boundary from apps that are read-only to this dispatch.

Additionally provides a "fully set up" organisation (profile + baseline
answers + a confirmed key asset) for each of org_a/org_b, so grounding and
generation tests have real, tenant-scoped facts to work with without every
test file re-building them from scratch.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from key_assets.models import KeyAsset
from organisations.models import Organisation, OrganisationMembership, OrganisationProfile
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


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


def _make_profile(organisation, *, description, driver):
    return OrganisationProfile.objects.create(
        organisation=organisation,
        legal_trading_name=f"{organisation.name} (legal)",
        description=description,
        staff_count=12,
        working_model="hybrid",
        endpoint_management="byod",
        productivity_platform="microsoft_365",
        primary_cloud_provider="azure",
        develops_hosts_own_software="no",
        handles_personal_data="yes",
        handles_confidential_business_data="yes",
        handles_payment_card_data="no",
        handles_special_category_data="no",
        receives_security_questionnaires="yes",
        cyber_essentials_status="not_certified",
        iso27001_status="unknown",
        commercial_security_driver=driver,
    )


def _make_baseline(organisation, *, note):
    assessment = BaselineAssessment.objects.create(
        organisation=organisation, catalogue_version=CATALOGUE_VERSION
    )
    BaselineAnswer.objects.create(
        assessment=assessment, question_key="mfa_user_accounts", answer="no", note=note
    )
    BaselineAnswer.objects.create(
        assessment=assessment, question_key="backups", answer="unknown", note=""
    )
    return assessment


@pytest.fixture
def profile_a(db, org_a):
    return _make_profile(
        org_a, description="Org A does synthetic consulting work.", driver="A customer asked about MFA."
    )


@pytest.fixture
def profile_b(db, org_b):
    return _make_profile(
        org_b, description="Org B does unrelated synthetic manufacturing.", driver="Org B's own driver."
    )


@pytest.fixture
def baseline_a(db, org_a, profile_a):
    return _make_baseline(org_a, note="Org A's own baseline note.")


@pytest.fixture
def baseline_b(db, org_b, profile_b):
    return _make_baseline(org_b, note="Org B's own baseline note - never for org A.")


@pytest.fixture
def confirmed_asset_a(db, org_a):
    return KeyAsset.objects.create(
        organisation=org_a,
        name="Org A confirmed asset",
        category="endpoint",
        criticality="medium",
        status=KeyAsset.STATUS_CONFIRMED,
    )


@pytest.fixture
def confirmed_asset_b(db, org_b):
    return KeyAsset.objects.create(
        organisation=org_b,
        name="Org B confirmed asset",
        category="endpoint",
        criticality="medium",
        status=KeyAsset.STATUS_CONFIRMED,
    )
