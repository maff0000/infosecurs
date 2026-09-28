"""
WI6 (docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md §28/
§29) - real-browser functional smoke, at 375px/768px/1280px, across every
organisation-scoped area the shell now wraps, proving the WI2 shell
rewrite (§16.3's "one shell, rendered once") did not break the underlying
M006 product for any of them.

This is deliberately SMOKE coverage (page loads through the real shell, no
horizontal overflow, sidebar/hamburger present correctly), not new deep
per-area coverage - this codebase's own existing M006-era narrow-viewport-
regression / badge-regression Playwright files (key_assets, evidence,
risk_register, remediation, organisations-list, plus core/tests/
test_badge_narrow_viewport_regression.py's Evidence/Key-Assets/Risk/
Remediation/Security-State/Questionnaire/Policy/Foundations coverage) are
the real, exhaustive, already-written proof for those specific areas, and
now genuinely RUN (instead of skip) once Playwright is installed - see
docs/evidence/M007-BROWSER-ACCEPTANCE.md for the before/after accounting.

The five areas below have NO existing Playwright coverage anywhere in this
repository (confirmed by grep for `sync_playwright`/`importorskip
("playwright")` across every app before writing this file) - Company/
Profile, Baseline, Governance, Workplace, Activity - so this file adds the
genuine gap: at least one real-browser pass per area, at all three PID §28
widths.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"
VIEWPORTS = [(375, 812), (768, 1024), (1280, 900)]

# (route name, human label) - each reached with `args=[organisation.id]`.
# A real, logged-in MONTHLY-tier session (this codebase's own real-login
# default - entitlements/signals.py) reaches every one of these.
AREAS = [
    ("organisations:profile", "Company / Profile"),
    ("security_baseline:baseline", "Baseline"),
    ("governance:roles", "Governance"),
    ("workplace:list", "Workplace"),
    ("activity:list", "Activity"),
]


def _new_org_and_user(username, org_name="WI6 Area Smoke Synthetic Ltd"):
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


def _assert_no_overflow(page, label):
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width, (
        f"Horizontal overflow ({label}): scrollWidth={scroll_width} > clientWidth={client_width}"
    )


@pytest.mark.django_db(transaction=True)
def test_every_previously_uncovered_organisation_scoped_area_smoke_at_all_widths(live_server):
    user, organisation = _new_org_and_user("wi6_area_smoke")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            for route_name, label in AREAS:
                url = f"{live_server.url}{reverse(route_name, args=[organisation.id])}"
                for width, height in VIEWPORTS:
                    page.set_viewport_size({"width": width, "height": height})
                    response = page.goto(url)
                    page.wait_for_load_state("networkidle")

                    assert response is not None and response.status == 200, (
                        f"{label} ({route_name}) did not return 200 at {width}px: "
                        f"{response.status if response else 'no response'}"
                    )
                    _assert_no_overflow(page, f"{label} @ {width}px")

                    # Rendered through the one canonical shell, exactly
                    # once (§16.3), at every width.
                    assert page.locator("#shell-sidebar").count() == 1
                    assert page.locator("#shell-nav-toggle").count() == 1
                    assert "app-header__nav-primary" not in page.content()

                    if width <= 640:
                        assert page.locator("#shell-nav-toggle").is_visible()
                    else:
                        assert not page.locator("#shell-nav-toggle").is_visible()

            assert console_errors == []
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_organisation_hub_and_policy_and_customer_assurance_smoke_at_all_widths(live_server):
    """`organisation_hub`/`policy:detail`/`questionnaire:list` (Customer
    Assurance) already have some indirect Playwright coverage via `core/
    tests/test_application_shell.py` (Django-test-client HTML assertions,
    not a real browser) and `core/tests/test_badge_narrow_viewport_
    regression.py` (real browser, but 375px/policy-version-detail/
    questionnaire-response-detail specifically, not these exact list/hub
    pages) - this closes the remaining real-browser smoke gap for the
    list/hub pages themselves, at all three PID §28 widths."""
    user, organisation = _new_org_and_user("wi6_area_smoke_hub_policy")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            for route_name, label in [
                ("organisations:organisation_hub", "Organisation Hub"),
                ("policy:detail", "Policy"),
                ("questionnaire:list", "Customer Assurance"),
            ]:
                url = f"{live_server.url}{reverse(route_name, args=[organisation.id])}"
                for width, height in VIEWPORTS:
                    page.set_viewport_size({"width": width, "height": height})
                    response = page.goto(url)
                    page.wait_for_load_state("networkidle")
                    assert response is not None and response.status == 200, (
                        f"{label} did not return 200 at {width}px"
                    )
                    _assert_no_overflow(page, f"{label} @ {width}px")

            assert console_errors == []
        finally:
            browser.close()
