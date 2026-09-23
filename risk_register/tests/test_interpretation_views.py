import uuid

import pytest
from django.urls import reverse

from ai_platform.models import AIInvocationRecord


@pytest.mark.django_db
class TestInterpretViewTenantIsolation:
    """PID §16: the new `risk_register:interpret` URL/view
    (`risk_register/interpretation_views.py`, M002-3c dispatch) gets the
    same tenant-isolation discipline as every other risk_register URL -
    mirrors `TestRiskTenantIsolation`'s pattern in test_tenant_isolation.py
    exactly (membership verified via `get_member_organisation_or_404`
    before anything else runs)."""

    def test_member_can_trigger_interpretation_on_own_organisation(self, client_a, org_a):
        # No draft risks exist yet - interpret_draft_risks returns [] before
        # ever constructing/calling a real gateway, so this exercises the
        # full view/service wiring without needing AI gateway configuration.
        response = client_a.post(reverse("risk_register:interpret", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url == reverse("risk_register:list", args=[org_a.id])

    def test_member_cannot_trigger_interpretation_on_other_organisation(self, client_b, org_a):
        response = client_b.post(reverse("risk_register:interpret", args=[org_a.id]))
        assert response.status_code == 404
        assert AIInvocationRecord.objects.filter(organisation=org_a).count() == 0

    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.post(reverse("risk_register:interpret", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_interpret_url_rejects_get(self, client_a, org_a):
        response = client_a.get(reverse("risk_register:interpret", args=[org_a.id]))
        assert response.status_code == 405

    def test_interpret_requires_login(self, client, org_a):
        response = client.post(reverse("risk_register:interpret", args=[org_a.id]))
        assert response.status_code in (302, 403)  # redirected to login (never 200)
