"""
M007-WI2 (docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md
§2.1/§16/§17/§18): the new canonical `templates/application_shell.html`
itself - sidebar/topbar/drawer markup, account/logout preservation,
accessibility scaffolding, and "one shell, rendered once, no duplicated
menu DOM" (§16.3) - as distinct from:

  - `entitlements/tests/test_navigation.py` - the tree-BUILDING function
    (`entitlements.navigation.build_navigation_tree`) in isolation;
  - `entitlements/tests/test_navigation_context_processor.py` - the
    context-processor wiring;
  - each app's own existing test suite - full functional regression of
    that app's own domain behaviour (untouched by this dispatch).

This file deliberately does NOT re-test per-tier navigation FILTERING in
depth (that is `test_navigation.py`'s job) - only that the shell actually
renders what the tree gives it, correctly, in real HTML, for a
representative spread of tiers and pages.
"""
import pytest
from django.urls import reverse

from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED, TIER_PRO

pytestmark = pytest.mark.django_db


# --- Pre-organisation pages keep the OLD shell untouched --------------------


class TestPreOrganisationPagesAreUnaffected:
    """PID §18's own "valid end-state": templates/base.html keeps serving
    exactly the four pre-organisation-selection pages, unchanged."""

    def test_organisation_list_has_no_shell_sidebar_or_hamburger(self, client_a):
        response = client_a.get(reverse("organisations:list"))
        content = response.content.decode()
        assert 'id="shell-sidebar"' not in content
        assert "shell-hamburger" not in content

    def test_login_page_has_no_shell_sidebar_or_hamburger(self, client):
        content = client.get(reverse("login")).content.decode()
        assert 'id="shell-sidebar"' not in content
        assert "shell-hamburger" not in content


# --- Organisation-scoped pages use the new shell, not the old top nav -------


class TestOrganisationScopedPagesUseTheNewShell:
    def test_overview_page_has_the_new_sidebar_and_hamburger(self, client_a, org_a):
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert content.count('id="shell-sidebar"') == 1
        assert content.count('id="shell-nav-toggle"') == 1

    def test_old_flat_top_nav_is_completely_gone(self, client_a, org_a):
        """The old M006 `.app-header__nav-primary` 7-item flat bar is
        superseded by the sidebar, not rendered alongside it (PID §2.1 -
        "must not copy menu markup...global application layout")."""
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "app-header__nav-primary" not in content

    def test_hamburger_has_correct_aria_wiring(self, client_a, org_a):
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert 'aria-controls="shell-sidebar"' in content
        assert 'aria-expanded="false"' in content

    def test_skip_link_and_main_content_landmark_preserved(self, client_a, org_a):
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert 'class="skip-link"' in content
        assert 'href="#main-content"' in content
        assert 'id="main-content"' in content

    def test_organisation_name_still_uses_the_hardened_selector(self, client_a, org_a):
        """core/tests/test_responsive_text_regression.py's own real-browser
        375px proof locates `.app-header__context-name` - kept as the exact
        same class in the new topbar (not forked/renamed) so that existing
        proof stays valid untouched."""
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert content.count('class="app-header__context-name"') == 1
        assert org_a.name in content

    def test_account_placeholder_is_a_disabled_control_not_a_dead_link(self, client_a, org_a):
        """PID §17: a placeholder must never look like a working
        destination it is not."""
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert '<button type="button" class="shell-account__placeholder" disabled' in content
        assert 'aria-label="Open navigation menu"' in content

    def test_logout_is_still_a_real_csrf_protected_post_form(self, client_a, org_a):
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        logout_url = reverse("logout")
        assert f'action="{logout_url}"' in content
        assert 'method="post"' in content
        assert "csrfmiddlewaretoken" in content

    def test_logout_still_actually_destroys_the_session(self, client_a, org_a):
        # An entitled page is reachable before logout.
        before = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert before.status_code == 200

        client_a.post(reverse("logout"))

        after = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert after.status_code == 302
        assert after["Location"].startswith(reverse("login"))

    def test_exactly_one_item_marked_active_on_the_overview_page(self, client_a, org_a):
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert content.count('aria-current="page"') == 1


# --- No duplicated menu DOM across different domains (PID §16.3) -----------


REPRESENTATIVE_ORG_SCOPED_ROUTES = [
    "organisations:detail",
    "organisations:organisation_hub",
    "organisations:profile",
    "activity:list",
    "evidence:list",
    "policy:detail",
    "workplace:list",
    "key_assets:list",
    "risk_register:list",
    "security_state:list",
    "questionnaire:list",
    "governance:roles",
]


class TestShellIsRenderedOnceNotDuplicatedPerPage:
    @pytest.mark.parametrize("route_name", REPRESENTATIVE_ORG_SCOPED_ROUTES)
    def test_page_renders_200_through_the_new_shell_with_exactly_one_sidebar(
        self, client_a, org_a, route_name
    ):
        """Spot-checks representative pages across several different
        domains (PID dispatch's own "done" criterion 1) - not exhaustive
        (the full existing per-app test suites, run unmodified against
        this same shell, are the exhaustive regression proof - see this
        dispatch's report)."""
        response = client_a.get(reverse(route_name, args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert content.count('id="shell-sidebar"') == 1
        assert content.count('id="shell-nav-toggle"') == 1
        assert "app-header__nav-primary" not in content


# --- Tier-driven sidebar content, exercised through real rendered HTML -----


class TestSidebarContentMatchesTierThroughRealHtml:
    """`entitlements/tests/test_navigation.py` already proves the tree-
    building function's own tier matrix exhaustively; this proves the
    SAME real, logged-in HTTP response actually contains (or omits) the
    corresponding links - i.e. that the shell template faithfully renders
    what the service decided, not a second/duplicated decision."""

    def _sidebar_html(self, client, org):
        """Scoped to the `<nav class="shell-sidebar">...</nav>` element
        only - NOT the whole page. `organisations/templates/organisations/
        detail.html`'s own pre-existing (M006, untouched by this dispatch)
        Overview cards independently link to several of these same
        destinations (e.g. "Open security state", "Open questionnaire
        assurance") regardless of package tier - a real, pre-existing gap
        this dispatch's own report flags for WI3 (route guards, not
        sidebar visibility, are the actual access-control boundary - PID
        §9's own "hiding a sidebar item is not access control"), but not
        this test's concern: this test proves the SIDEBAR's own tier
        filtering, so it must not be confused by unrelated main-content
        links that happen to share a destination URL."""
        content = client.get(reverse("organisations:detail", args=[org.id])).content.decode()
        start = content.index('<nav class="shell-sidebar"')
        end = content.index("</nav>", start)
        return content[start:end]

    def test_paused_session_sidebar_has_no_foundation_or_higher_links(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED)
        content = self._sidebar_html(client_a, org_a)

        assert reverse("security_state:list", args=[org_a.id]) not in content
        assert reverse("policy:detail", args=[org_a.id]) not in content
        assert reverse("questionnaire:list", args=[org_a.id]) not in content
        assert reverse("organisations:organisation_hub", args=[org_a.id]) not in content

    def test_foundation_session_sidebar_has_security_and_company_but_not_customer_assurance(
        self, client_a, user_a, org_a
    ):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        content = self._sidebar_html(client_a, org_a)

        assert reverse("security_state:list", args=[org_a.id]) in content
        assert reverse("policy:detail", args=[org_a.id]) in content
        assert reverse("organisations:organisation_hub", args=[org_a.id]) in content
        assert reverse("questionnaire:list", args=[org_a.id]) not in content

    def test_monthly_session_sidebar_adds_customer_assurance(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_MONTHLY)
        content = self._sidebar_html(client_a, org_a)

        assert reverse("questionnaire:list", args=[org_a.id]) in content
        assert reverse("security_state:list", args=[org_a.id]) in content

    def test_pro_session_sidebar_has_every_seeded_destination(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PRO)
        content = self._sidebar_html(client_a, org_a)

        for route_name in (
            "security_state:list",
            "security_baseline:baseline",
            "key_assets:list",
            "risk_register:list",
            "evidence:list",
            "remediation:list",
            "policy:detail",
            "organisations:organisation_hub",
            "organisations:profile",
            "governance:roles",
            "workplace:list",
            "activity:list",
            "questionnaire:list",
        ):
            assert reverse(route_name, args=[org_a.id]) in content, route_name
