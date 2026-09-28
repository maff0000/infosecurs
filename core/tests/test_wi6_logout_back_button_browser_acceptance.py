"""
WI6 (docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md §28 -
"logout from real browser destroys access" / "Back button after logout does
not re-authorise protected content", and §8's session-destruction
requirement) - real-browser proof, via the actual shell's real "Log out"
form, not a Django test-client POST.

`core/tests/test_application_shell.py`'s own `test_logout_still_actually_
destroys_the_session` already proves this mechanically (Django test
`Client`, a real HTTP round trip but not a real browser). This file is the
real-Chromium version PID §28 explicitly asks for, including the
real-browser-specific "Back button after logout" case a test-client
assertion cannot exercise at all (there is no browser history/cache/
bfcache to prove anything about from a test client).
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"


def _new_org_and_user(username, org_name="WI6 Logout Synthetic Ltd"):
    User = get_user_model()
    user = User.objects.create_user(username=username, password=PASSWORD)
    organisation = Organisation.objects.create(name=org_name)
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )
    return user, organisation


def _login(page, live_server, username, password=PASSWORD):
    page.goto(f"{live_server.url}{reverse('login')}")
    page.click("summary")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


@pytest.mark.django_db(transaction=True)
def test_real_browser_logout_destroys_access_and_back_button_does_not_reauthorise(live_server):
    user, organisation = _new_org_and_user("wi6_logout_browser")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"
    login_url = f"{live_server.url}{reverse('login')}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            _login(page, live_server, user.username)

            page.goto(home_url)
            page.wait_for_load_state("networkidle")
            assert page.locator(".metric-card").count() == 2, "should be genuinely authenticated"

            # The real "Log out" form - scoped selector (not a bare
            # button[type=submit]), matching this codebase's own already-
            # documented lesson (core/tests/test_badge_narrow_viewport_
            # regression.py's policy test docstring) about an unscoped
            # submit-button selector accidentally matching this exact
            # logout form elsewhere.
            page.click('.app-header__logout button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # A fresh direct navigation to the same protected page is
            # denied post-logout.
            response = page.goto(home_url)
            page.wait_for_load_state("networkidle")
            assert page.url.startswith(login_url), (
                f"expected a redirect to login after logout, landed on {page.url}"
            )

            # Back button: navigate to login (current state), then use
            # the browser's real back button to return to what was
            # previously the authenticated Home page in this tab's
            # history, and confirm it does NOT show protected content
            # (either the browser re-fetches and the server redirects
            # again, or a cached bfcache page is shown but the session
            # is still genuinely dead server-side - proven by a fresh
            # reload of that same history entry).
            page.go_back()
            page.wait_for_load_state("networkidle")
            page.reload()
            page.wait_for_load_state("networkidle")
            assert page.url.startswith(login_url), (
                f"Back button + reload after logout re-authorised protected content: {page.url}"
            )
            assert page.locator(".metric-card").count() == 0, (
                "protected Home content visible after logout via Back button"
            )
        finally:
            browser.close()
