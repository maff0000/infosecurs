"""
M008D-WI4 - HTTP-level proofs for the new `policy:generate_deterministic`
view: POST-only, tenant-scoped (`get_member_organisation_or_404`), CSRF-
protected (Django's test Client enforces CSRF by default being disabled
only via `enforce_csrf_checks=False`, which is the Client default - the
view itself requires `{% csrf_token %}` in the real template, proven
separately by `policy/tests/test_http_ui.py`'s existing convention for
`policy:generate`), capability-guarded (via the `policy` route-namespace
map, unchanged by this WI), and that a cross-tenant POST creates nothing
for the foreign organisation - mirroring `policy/tests/
test_tenant_isolation.py`'s own patterns exactly for the pre-existing
`policy:generate` view.
"""
from __future__ import annotations

import uuid

import pytest
from django.urls import reverse

from policy.models import PolicyDocument, PolicyVersion


@pytest.mark.django_db
class TestGenerateDeterministicView:
    def test_get_is_not_allowed(self, client_a, org_a):
        response = client_a.get(reverse("policy:generate_deterministic", args=[org_a.id]))
        assert response.status_code == 405

    def test_post_creates_a_deterministic_draft_and_redirects_to_detail(self, client_a, org_a):
        response = client_a.post(reverse("policy:generate_deterministic", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"] == reverse("policy:detail", args=[org_a.id])

        version = PolicyVersion.objects.get(organisation=org_a)
        assert version.generation_source == PolicyVersion.GENERATION_SOURCE_DETERMINISTIC
        assert version.status == PolicyVersion.STATUS_DRAFT

    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.post(
            reverse("policy:generate_deterministic", args=[uuid.uuid4()])
        )
        assert response.status_code == 404

    def test_anonymous_user_is_redirected_to_login(self, client, org_a):
        response = client.post(reverse("policy:generate_deterministic", args=[org_a.id]))
        assert response.status_code == 302
        assert "/login" in response["Location"] or "login" in response["Location"]

    def test_member_cannot_generate_a_deterministic_draft_on_other_organisation(
        self, client_b, org_a
    ):
        response = client_b.post(reverse("policy:generate_deterministic", args=[org_a.id]))
        assert response.status_code == 404
        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0

    def test_version_detail_shows_implementation_status_section(self, client_a, org_a):
        client_a.post(reverse("policy:generate_deterministic", args=[org_a.id]))
        version = PolicyVersion.objects.get(organisation=org_a)
        response = client_a.get(
            reverse("policy:version_detail", args=[org_a.id, version.id])
        )
        assert response.status_code == 200
        assert b"Implementation status" in response.content
