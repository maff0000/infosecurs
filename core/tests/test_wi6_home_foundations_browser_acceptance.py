"""
WI6 (docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md §28 -
"Required UI/browser acceptance") - real-browser acceptance for the Home
dashboard (`organisations:detail`) and the Foundations workspace
(`organisations:foundations`) at all three PID §28 widths: 375px, 768px,
1280px.

This is a PROOF work item, not a feature work item - every test here drives
a real Chromium browser (Playwright) against a real `pytest-django`
`live_server`, matching this codebase's own established real-browser
acceptance convention (see `risk_register/tests/test_narrow_viewport_
regression.py`'s docstring for the full rationale). `pytest.importorskip`
keeps this file collectible/SKIPPED wherever Playwright is not installed.

Scope, deliberately bounded:
  - Home's two metric cards + Needs Attention (PID §13/§14), at a normal
    entitled (Monthly) tier and at Paused (PID §13.1).
  - Foundations' requirement rows/badges/actions (PID §15) at the two
    desktop widths this file's own sibling `core/tests/test_badge_narrow_
    viewport_regression.py` does not already cover (that file already
    proves Foundations badges/no-overflow at 375px in depth - this file
    adds the 768px/1280px legs of PID §28's three-width requirement rather
    than duplicating the 375px case).
  - Sidebar/hamburger presence around Home/Foundations content at each
    width (no layout collision) - the drawer's own open/close/focus/
    keyboard behaviour has its own dedicated proof in `core/tests/
    test_wi6_sidebar_drawer_acceptance.py`, not repeated here.
  - Organisation-name-in-header-and-subtitle hostile-token/XSS proof lives
    in `core/tests/test_wi6_xss_browser_acceptance.py`, not here - this
    file uses a LONG-but-not-hostile organisation name for the wrap/layout
    proof, to keep this file's own concern to layout/stacking, not
    escaping.

A Paused session cannot be reached through a real "log in as Paused" flow
(logging in always issues a real MONTHLY `infosecurs_context` -
`entitlements/signals.py` - there is no production tier-switch endpoint,
by design, PID §7.2). `_provision_paused_session_key` below uses PID §7.1's own
explicitly-sanctioned "a test helper that directly creates server-side
session context is also acceptable" seam - the exact same technique
`entitlements/tests/conftest.py`'s `set_session_tier` already uses for
Django test `Client` sessions - but writes the session BEFORE any
Playwright browser/context exists, then hands the browser a real cookie
for that session, so the resulting page load is still a genuine browser
HTTP request/response cycle, not a Django test-client render. Writing the
session INSIDE an open `sync_playwright()` block was tried first and
tripped Django's `SynchronousOnlyOperation` guard (the exact same
discovery `test_policy_approval_summary_wraps_with_long_governance_name_at_375px`
in `core/tests/test_badge_narrow_viewport_regression.py` already documents
for ORM calls made from the pytest thread while Playwright's own event
loop is alive in the same process) - doing the ORM write first, then only
touching the browser, avoids that trap entirely.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client as DjangoTestClient  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone as django_timezone  # noqa: E402

from entitlements.session import ENTITLEMENT_VERSION, SCHEMA_VERSION, SESSION_KEY  # noqa: E402
from entitlements.tiers import TIER_PAUSED, tier_code  # noqa: E402
from organisations.models import Organisation, OrganisationMembership  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"

VIEWPORTS = [
    (375, 812),
    (768, 1024),
    (1280, 900),
]

LONG_ORG_NAME = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster Holdings International Limited"
)


def _new_org_and_user(username, org_name):
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


def _assert_no_overflow(page, label=""):
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width, (
        f"Horizontal overflow{' (' + label + ')' if label else ''}: "
        f"scrollWidth={scroll_width} > clientWidth={client_width}"
    )


def _assert_sidebar_no_collision(page, width):
    """Confirms the sidebar/hamburger present themselves correctly around
    whatever content the page renders, at this exact width, per PID §16.1/
    §16.2 - never both a visible in-flow sidebar AND a visible hamburger at
    once, and never neither."""
    hamburger_visible = page.locator("#shell-nav-toggle").is_visible()
    sidebar_box = page.locator("#shell-sidebar").bounding_box()
    assert sidebar_box is not None, "sidebar element missing from the DOM"

    if width <= 640:
        assert hamburger_visible, f"hamburger should be visible at {width}px"
        # Off-canvas: translateX(-100%) pushes the sidebar fully outside
        # the left edge of the viewport until opened.
        assert sidebar_box["x"] + sidebar_box["width"] <= 0, (
            f"sidebar should be off-canvas at {width}px, got box={sidebar_box}"
        )
    else:
        assert not hamburger_visible, f"hamburger should be hidden at {width}px"
        assert sidebar_box["x"] >= 0 and sidebar_box["width"] > 0, (
            f"sidebar should be visible in-flow at {width}px, got box={sidebar_box}"
        )
        # In-flow desktop sidebar must not overlap main content start.
        main_box = page.locator("#main-content").bounding_box()
        assert main_box is not None
        assert main_box["x"] >= sidebar_box["x"] + sidebar_box["width"] - 1, (
            "sidebar and main content collide at "
            f"{width}px: sidebar={sidebar_box} main={main_box}"
        )


# --- Home: Monthly tier -----------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_home_monthly_tier_at_all_three_pid28_widths(live_server):
    user, organisation = _new_org_and_user("wi6_home_monthly", LONG_ORG_NAME)
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

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

            for width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                page.goto(home_url)
                page.wait_for_load_state("networkidle")

                _assert_no_overflow(page, f"Home @ {width}px")
                _assert_sidebar_no_collision(page, width)

                # Exactly two metric cards, always both present regardless
                # of width (PID §13 - no third card, nothing conditional).
                cards = page.locator(".metric-card")
                assert cards.count() == 2
                for i in range(2):
                    assert cards.nth(i).is_visible()
                titles = [cards.nth(i).locator(".metric-card__title").inner_text() for i in range(2)]
                assert "Foundational Security Posture" in titles
                assert "Security Foundations Completion" in titles

                box0 = cards.nth(0).bounding_box()
                box1 = cards.nth(1).bounding_box()
                assert box0 is not None and box1 is not None
                if width <= 640:
                    # Stacked: second card starts below the first, roughly
                    # same left edge.
                    assert box1["y"] >= box0["y"] + box0["height"] - 1, (
                        f"cards should stack at {width}px: {box0} / {box1}"
                    )
                else:
                    # Side-by-side: same top edge, second card starts to
                    # the right of the first.
                    assert abs(box1["y"] - box0["y"]) < 5, (
                        f"cards should be side-by-side at {width}px: {box0} / {box1}"
                    )
                    assert box1["x"] >= box0["x"] + box0["width"] - 1

                # Needs Attention: a brand-new organisation has every
                # baseline control "Not sure" and every Foundations item
                # incomplete by default (entitlements.metrics.
                # get_needs_attention's own documented defaults), so this
                # section is populated with zero extra setup.
                lines = page.locator(".needs-attention__line")
                assert lines.count() >= 1
                for i in range(lines.count()):
                    line = lines.nth(i)
                    anchors = line.locator("a")
                    # PID §14.1 - exactly one <a>, and its own text is
                    # exactly "click here" - the rest of the line is never
                    # itself a link.
                    assert anchors.count() == 1
                    assert anchors.first.inner_text().strip() == "click here"
                    full_text = line.inner_text()
                    assert full_text.strip() != "click here", (
                        "the whole Needs Attention line must not collapse "
                        "to just the link text - there must be real "
                        "non-link wording before it"
                    )
                    assert anchors.first.is_visible()

                # Long organisation name renders (and wraps, not
                # overflows) in both the shared header and the new
                # page-header subtitle Home itself adds (M007-WI5) -
                # confirmed via real-browser measurement, not source
                # inspection.
                assert organisation.name in page.locator(".app-header__context-name").inner_text()
                assert organisation.name in page.locator(".page-header__subtitle").inner_text()

                # Top-right account/logout area remains usable (PID §28).
                assert page.locator(".shell-account__placeholder").is_visible()
                logout_button = page.locator('.app-header__logout button[type="submit"]')
                assert logout_button.is_visible()

            assert console_errors == []
        finally:
            browser.close()


# --- Home: Paused tier -------------------------------------------------------


def _provision_paused_session_key(user, organisation):
    """Provisions a real DB session at Paused tier (PID §7.1's own
    sanctioned test-only seam) and returns its session key. Pure ORM/
    Django-test-Client work only - the caller MUST call this BEFORE
    entering `sync_playwright()`, never from inside that `with` block:
    doing so was tried first and tripped Django's `SynchronousOnlyOperation`
    guard (see this file's own module docstring for the full discovery -
    the exact same trap `test_policy_approval_summary_wraps_with_long_
    governance_name_at_375px` in `core/tests/test_badge_narrow_viewport_
    regression.py` already documents for ORM calls made from the pytest
    thread while Playwright's own event loop is alive in the same
    process)."""
    django_client = DjangoTestClient()
    django_client.force_login(user)  # issues a real MONTHLY context first
    session = django_client.session
    session[SESSION_KEY] = {
        "schema_version": SCHEMA_VERSION,
        "subject_id": str(user.pk),
        "organisation_id": str(organisation.id),
        "package_tier": TIER_PAUSED,
        "package_code": tier_code(TIER_PAUSED),
        "entitlement_version": ENTITLEMENT_VERSION,
        "issued_at": django_timezone.now().isoformat(),
        "auth_source": "wi6_browser_test_fixture",
    }
    session.save()
    return session.session_key


@pytest.mark.django_db(transaction=True)
def test_home_paused_tier_at_all_three_pid28_widths(live_server):
    user, organisation = _new_org_and_user("wi6_home_paused", "WI6 Paused Synthetic Ltd")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    # Provisioned BEFORE `sync_playwright()` is entered - see
    # `_provision_paused_session_key`'s own docstring for why.
    session_key = _provision_paused_session_key(user, organisation)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context()
            context.add_cookies(
                [
                    {
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": session_key,
                        "url": live_server.url,
                    }
                ]
            )
            page = context.new_page()
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )

            for width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                page.goto(home_url)
                page.wait_for_load_state("networkidle")

                _assert_no_overflow(page, f"Home Paused @ {width}px")
                _assert_sidebar_no_collision(page, width)

                # PID §13.1 - a Paused session gets ONLY the minimal
                # state: no metric cards, no Needs Attention at all.
                assert page.locator(".metric-card").count() == 0
                assert page.locator(".needs-attention").count() == 0

                paused = page.locator(".paused-state")
                assert paused.is_visible()
                assert "currently paused" in paused.inner_text()

                # Sidebar itself is genuinely tier-filtered too (not just
                # Home's own content) - a Paused session's sidebar has no
                # Foundation-or-higher links (entitlements/tests/
                # test_navigation.py's own exhaustive matrix covers the
                # tree-building function; this just spot-checks the real
                # rendered HTML at this exact width isn't different).
                sidebar_html = page.locator("#shell-sidebar").inner_html()
                assert reverse("security_state:list", args=[organisation.id]) not in sidebar_html

            assert console_errors == []
        finally:
            browser.close()


# --- Foundations: the 768px/1280px legs of PID §28's three-width proof -----


@pytest.mark.django_db(transaction=True)
def test_foundations_workspace_at_768_and_1280(live_server):
    """`core/tests/test_badge_narrow_viewport_regression.py`'s own
    `test_organisation_foundations_badges_no_overflow_at_375px` already
    proves Foundations badges/actions/no-overflow at 375px in depth. PID
    §28 requires proof at 768px and 1280px too - this test adds exactly
    those two, on the same real page, without duplicating the 375px
    case."""
    user, organisation = _new_org_and_user("wi6_foundations_desktop", LONG_ORG_NAME)
    foundations_url = f"{live_server.url}{reverse('organisations:foundations', args=[organisation.id])}"

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

            for width, height in VIEWPORTS[1:]:  # 768px, 1280px only
                page.set_viewport_size({"width": width, "height": height})
                page.goto(foundations_url)
                page.wait_for_load_state("networkidle")

                _assert_no_overflow(page, f"Foundations @ {width}px")
                _assert_sidebar_no_collision(page, width)

                rows = page.locator(".foundations-row")
                assert rows.count() > 0
                badges = page.locator(".foundations-row .badge")
                assert badges.count() == rows.count()
                for i in range(badges.count()):
                    badge = badges.nth(i)
                    assert badge.is_visible()
                    box = badge.bounding_box()
                    assert box is not None and box["width"] > 0 and box["height"] > 0

                actions = page.locator(".foundations-row__action a")
                assert actions.count() == rows.count()
                assert actions.first.is_visible()

                assert organisation.name in page.locator(".page-header__subtitle").first.inner_text()

            assert console_errors == []
        finally:
            browser.close()
