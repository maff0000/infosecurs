"""
PID §9: has_capability's default-deny matrix, and the invariant that
package entitlement and tenant scoping are separate, never-substitutable
gates (§9.3).
"""
import inspect

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore

from entitlements import capabilities
from entitlements.models import ProductArea
from entitlements.session import issue_context
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED, TIER_PRO

pytestmark = pytest.mark.django_db


class FakeRequest:
    def __init__(self, session, user):
        self.session = session
        self.user = user


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="alice", password="not-a-real-password-123")


def request_at_tier(user, tier):
    store = SessionStore()
    store.save()
    request = FakeRequest(store, user)
    issue_context(request, user, package_tier=tier, auth_source="test_fixture")
    return request


class TestHasCapabilitySignatureNeverTakesATenantArgument:
    def test_signature_is_exactly_request_and_capability_code(self):
        """
        PID §9.3's own invariant, made mechanically checkable: this
        function must never grow an organisation/tenant parameter that
        could be misused as a substitute for
        organisations.views.get_member_organisation_or_404.
        """
        parameters = list(inspect.signature(capabilities.has_capability).parameters)
        assert parameters == ["request", "capability_code"]


class TestDefaultDenyMatrix:
    """Uses the real seeded ProductArea rows (home=0, foundations=1,
    customer_assurance=2) rather than fixtures, since proving the tier
    matrix against the actual governed seed data is the point."""

    @pytest.mark.parametrize(
        "tier,code,expected",
        [
            (TIER_PAUSED, "home", True),
            (TIER_PAUSED, "foundations", False),
            (TIER_PAUSED, "customer_assurance", False),
            (TIER_FOUNDATION, "home", True),
            (TIER_FOUNDATION, "foundations", True),
            (TIER_FOUNDATION, "customer_assurance", False),
            (TIER_MONTHLY, "foundations", True),
            (TIER_MONTHLY, "customer_assurance", True),
            (TIER_PRO, "foundations", True),
            (TIER_PRO, "customer_assurance", True),
        ],
    )
    def test_matrix(self, user, tier, code, expected):
        request = request_at_tier(user, tier)
        assert capabilities.has_capability(request, code) is expected

    def test_pro_inherits_every_area_foundation_and_monthly_unlock(self, user):
        request = request_at_tier(user, TIER_PRO)
        for code in ProductArea.objects.values_list("code", flat=True):
            assert capabilities.has_capability(request, code) is True

    def test_unknown_capability_code_is_denied_not_an_exception(self, user):
        request = request_at_tier(user, TIER_PRO)
        assert capabilities.has_capability(request, "this-capability-does-not-exist") is False

    def test_inactive_product_area_denied_regardless_of_tier(self, user):
        area = ProductArea.objects.get(code="foundations")
        area.is_active = False
        area.save(update_fields=["is_active"])

        request = request_at_tier(user, TIER_PRO)
        assert capabilities.has_capability(request, "foundations") is False

    def test_missing_session_context_is_denied(self, user):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, user)
        assert capabilities.has_capability(request, "home") is False

    def test_unauthenticated_request_is_denied(self):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, AnonymousUser())
        assert capabilities.has_capability(request, "home") is False

    def test_tampered_tier_in_raw_session_is_denied(self, user):
        """A hand-edited/tampered session dict (as if a client somehow
        wrote package_tier=3 directly) must still fail closed, because
        subject_id/schema alone are not enough - but here we go further:
        even a well-formed-looking tampered context that fails any single
        check must deny."""
        from entitlements.session import SCHEMA_VERSION, SESSION_KEY

        store = SessionStore()
        store.save()
        store[SESSION_KEY] = {
            "schema_version": SCHEMA_VERSION,
            "subject_id": str(user.pk),
            "organisation_id": None,
            "package_tier": 3,
            "package_code": "NOT-A-REAL-CODE",
            "entitlement_version": 1,
            "issued_at": "2026-09-27T00:00:00+00:00",
            "auth_source": "tampered",
        }
        store.save()
        request = FakeRequest(store, user)
        assert capabilities.has_capability(request, "customer_assurance") is False


class TestRouteCapabilityMap:
    @pytest.mark.parametrize(
        "namespace,expected_code",
        [
            ("questionnaire", "customer_assurance"),
            ("security_state", "security"),
            ("security_baseline", "security"),
            ("key_assets", "security"),
            ("risk_register", "security"),
            ("evidence", "security"),
            ("remediation", "security"),
            ("policy", "policies"),
            ("governance", "company"),
            ("workplace", "company"),
            ("activity", "company"),
            ("some-unmapped-namespace", None),
        ],
    )
    def test_capability_for_route_by_namespace(self, namespace, expected_code):
        assert capabilities.capability_for_route(namespace) == expected_code

    @pytest.mark.parametrize(
        "url_name,expected_code",
        [
            ("detail", "home"),
            ("profile", "company"),
            ("organisation_hub", "company"),
            ("list", None),
            ("create", None),
        ],
    )
    def test_organisations_namespace_splits_by_url_name(self, url_name, expected_code):
        assert capabilities.capability_for_route("organisations", url_name) == expected_code

    def test_every_mapped_capability_code_is_a_real_product_area(self):
        mapped_codes = set(capabilities.ROUTE_NAMESPACE_TO_CAPABILITY.values()) | set(
            capabilities.ORGANISATIONS_URL_NAME_TO_CAPABILITY.values()
        )
        real_codes = set(ProductArea.objects.values_list("code", flat=True))
        assert mapped_codes <= real_codes
