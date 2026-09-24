"""
Mechanical tests for the new Organisation landing page
(`organisations:organisation_hub`, M006 PID §5's "Organisation" primary-nav
section: Profile, Governance and Workplace).

Follows this codebase's established `client_a`/`client_b`/`org_a`/`org_b`
tenant-isolation fixture convention (organisations/tests/conftest.py).
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestOrganisationHub:
    def test_requires_login(self, client, org_a):
        response = client.get(reverse("organisations:organisation_hub", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_member_can_reach_it(self, client_a, org_a):
        response = client_a.get(reverse("organisations:organisation_hub", args=[org_a.id]))
        assert response.status_code == 200

    def test_non_member_gets_404_not_403(self, client_b, org_a):
        """Same tenant-scoping discipline as every other org-scoped view
        (organisations.views.get_member_organisation_or_404's own
        docstring): a non-member gets an ordinary 404, never a 403 that
        would confirm the organisation exists."""
        response = client_b.get(reverse("organisations:organisation_hub", args=[org_a.id]))
        assert response.status_code == 404

    def test_links_to_profile_governance_and_workplace_are_present(self, client_a, org_a):
        response = client_a.get(reverse("organisations:organisation_hub", args=[org_a.id]))
        content = response.content.decode()
        assert reverse("organisations:profile", args=[org_a.id]) in content
        assert reverse("governance:roles", args=[org_a.id]) in content
        assert reverse("workplace:list", args=[org_a.id]) in content

    def test_does_not_expose_the_raw_organisation_id_as_visible_nav_text(self, client_a, org_a):
        """PID §5: 'Do not expose internal UUIDs as the primary customer
        UX.' The id legitimately appears inside href attribute values
        (every organisation-scoped URL is id-keyed) - what must not happen
        is the raw UUID appearing as the page's own visible heading text."""
        response = client_a.get(reverse("organisations:organisation_hub", args=[org_a.id]))
        content = response.content.decode()
        assert f">{org_a.id}<" not in content
