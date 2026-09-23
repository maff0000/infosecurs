"""
Release-blocking tenant isolation tests (PID §23, §26 "Policy lifecycle" /
"Policy grounding" - m004-2a-policy-foundation dispatch). Two synthetic
organisations, two users each a member of exactly one, proving organisation
A cannot view/generate/read organisation B's policy draft, and that a
foreign/manipulated organisation id in the URL is an ordinary 404 - never a
path to another organisation's policy.
"""
import uuid

import pytest
from django.urls import reverse

from ai_platform.models import AIInvocationRecord
from ai_platform.testing import FakePolicyGateway
from policy.models import PolicyDocument, PolicyVersion
from policy.services import generate_policy_draft


@pytest.mark.django_db
class TestPolicyTenantIsolation:
    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_own_organisations_policy_detail(self, client_a, org_a):
        response = client_a.get(reverse("policy:detail", args=[org_a.id]))
        assert response.status_code == 200

    # --- cross-tenant read negative ---------------------------------------
    def test_member_cannot_read_other_organisations_policy_detail(self, client_b, org_a, user_a):
        generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="valid"))
        response = client_b.get(reverse("policy:detail", args=[org_a.id]))
        assert response.status_code == 404

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_generate_policy_on_other_organisation(self, client_b, org_a, monkeypatch):
        monkeypatch.setattr(
            "policy.services.LiteLLMGateway", lambda: FakePolicyGateway(mode="valid")
        )
        response = client_b.post(reverse("policy:generate", args=[org_a.id]))
        assert response.status_code == 404
        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0
        assert AIInvocationRecord.objects.filter(organisation=org_a).count() == 0

    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("policy:detail", args=[uuid.uuid4()]))
        assert response.status_code == 404
        response = client_a.post(reverse("policy:generate", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_organisation_b_draft_generation_never_creates_a_row_for_organisation_a(
        self, org_a, org_b, user_b
    ):
        generate_policy_draft(org_b, actor=user_b, gateway=FakePolicyGateway(mode="valid"))
        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0
