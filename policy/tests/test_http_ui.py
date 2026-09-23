"""
HTTP-level tests for the minimal draft-generation trigger + read-only view
(`policy/views.py`, m004-2a-policy-foundation dispatch). Uses
`ai_platform.testing.FakePolicyGateway` throughout, via monkeypatching
`policy.services.LiteLLMGateway` (the view never passes a `gateway`
explicitly, so this is the seam a test controls) - no live AI credential
needed, matching this project's existing test discipline
(`AI_GATEWAY_BASE_URL`/`AI_GATEWAY_API_KEY_FILE` unset throughout).
"""
import pytest
from django.urls import reverse

from ai_platform.testing import FakePolicyGateway
from policy.models import PolicyVersion


def _patch_gateway(monkeypatch, mode="valid"):
    monkeypatch.setattr("policy.services.LiteLLMGateway", lambda: FakePolicyGateway(mode=mode))


@pytest.mark.django_db
class TestPolicyDetailView:
    def test_no_draft_yet_shows_empty_state(self, client_a, org_a):
        response = client_a.get(reverse("policy:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert b"No policy draft has been generated yet." in response.content

    def test_shows_latest_draft_sections_and_warnings(self, client_a, org_a, user_a, monkeypatch):
        _patch_gateway(monkeypatch)
        response = client_a.post(reverse("policy:generate", args=[org_a.id]))
        assert response.status_code == 302

        response = client_a.get(reverse("policy:detail", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Fixture Ltd Information Security Policy" in content
        assert "Backups" in content  # the fixture's review warning subject


@pytest.mark.django_db
class TestPolicyGenerateView:
    def test_successful_generation_creates_draft_and_redirects(self, client_a, org_a, monkeypatch):
        _patch_gateway(monkeypatch)
        response = client_a.post(reverse("policy:generate", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url == reverse("policy:detail", args=[org_a.id])
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 1

    def test_failed_generation_creates_nothing_and_shows_error(self, client_a, org_a, monkeypatch):
        _patch_gateway(monkeypatch, mode="invalid_schema")
        response = client_a.post(reverse("policy:generate", args=[org_a.id]), follow=True)
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0
        messages = [str(m) for m in response.context["messages"]]
        assert any("could not be completed" in m for m in messages)

    def test_generate_rejects_get(self, client_a, org_a):
        response = client_a.get(reverse("policy:generate", args=[org_a.id]))
        assert response.status_code == 405

    def test_generate_requires_login(self, client, org_a):
        response = client.post(reverse("policy:generate", args=[org_a.id]))
        assert response.status_code in (302, 403)
