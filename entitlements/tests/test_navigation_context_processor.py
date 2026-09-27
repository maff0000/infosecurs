"""
PID §4.4/§18: `entitlements.context_processors.navigation` is the ONE place
`nav_tree` reaches every template - proves the wiring itself (organisation
id sourced correctly off the resolved URL, present only where PID §3 says
the sidebar can ever mean anything, absent everywhere else), as opposed to
`entitlements/tests/test_navigation.py` (the tree-building function in
isolation) or `core/tests/test_application_shell.py` (the shell template
actually rendering the tree).
"""
import pytest
from django.urls import reverse

from entitlements.context_processors import navigation

pytestmark = pytest.mark.django_db


class TestNavigationContextProcessorUnit:
    """Direct calls, mirroring core/tests/test_active_nav.py's own
    "pure unit test of the mapping function" precedent."""

    def test_anonymous_request_gets_no_nav_tree(self, rf):
        from django.contrib.auth.models import AnonymousUser

        request = rf.get("/")
        request.user = AnonymousUser()
        assert navigation(request) == {}

    def test_missing_resolver_match_gets_no_nav_tree(self, rf, django_user_model):
        request = rf.get("/")
        request.user = django_user_model.objects.create_user(
            username="ctx_proc_user", password="a-strong-test-password-123"
        )
        request.resolver_match = None
        assert navigation(request) == {}

    def test_route_with_no_organisation_id_gets_no_nav_tree(self, django_user_model, client):
        """`organisations:list` carries no `organisation_id` converter -
        PID §3's own finding that every seeded destination needs one."""
        user = django_user_model.objects.create_user(
            username="ctx_proc_user_2", password="a-strong-test-password-123"
        )
        client.force_login(user)
        response = client.get(reverse("organisations:list"))
        assert "nav_tree" not in response.context


@pytest.mark.django_db
class TestNavigationContextProcessorIntegration:
    def test_organisation_scoped_page_receives_a_real_nav_tree(self, client_a, org_a):
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert "nav_tree" in response.context
        nav_tree = response.context["nav_tree"]
        assert nav_tree, "expected at least one entitled nav item for a real logged-in session"
        assert any(item.code == "home" for item in nav_tree)

    def test_pre_organisation_pages_receive_no_nav_tree(self, client_a):
        for url_name in ("organisations:list", "organisations:create"):
            response = client_a.get(reverse(url_name))
            assert "nav_tree" not in response.context, url_name

    def test_unauthenticated_request_receives_no_nav_tree_and_is_redirected(self, client, org_a):
        response = client.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 302
