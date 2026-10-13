"""
M009A entitlement matrix (WO-M009A-SECURE-INGESTION-XLSX.md Correction 15:
"Direct URL entitlement tests must prove: PAUSED denied; FOUNDATION
denied; MONTHLY allowed; PRO allowed"), mirroring
`entitlements/tests/test_decorators.py`'s own established pattern exactly
- the `questionnaire` URL namespace already maps to the `customer_
assurance` ProductArea (min_package_tier=2/MONTHLY), unchanged by M009A.
"""
import pytest
from django.urls import reverse

from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED, TIER_PRO

pytestmark = pytest.mark.django_db


class TestImportUploadEntitlementMatrix:
    def test_paused_denied(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 403

    def test_foundation_denied(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 403

    def test_monthly_allowed(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_MONTHLY, organisation_id=org_a.id)
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 200

    def test_pro_allowed(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PRO, organisation_id=org_a.id)
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 200

    def test_copied_url_does_not_bypass_tier_check(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        url = reverse("questionnaire:import_upload", args=[org_a.id])
        assert client_a.get(url).status_code == 403
