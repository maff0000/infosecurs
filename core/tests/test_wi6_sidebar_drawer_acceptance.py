"""
WI6 (docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md
§16.2/§16.3/§28) - real-browser proof of the hamburger/drawer's own
open/close/focus/keyboard behaviour at 375px, and that the drawer is
genuinely the SAME server-rendered markup as the desktop sidebar (never a
second, duplicated, independently-filtered mobile menu - §16.3's own
binding rule).

Real Playwright page interaction throughout (clicks, keyboard events,
`aria-*` attribute reads from the live DOM) - never CSS-only inspection,
per this dispatch's own explicit instruction. `static/organisations/js/
shell.js` (read in full before writing this file) is the only thing under
test here beyond the shared markup itself - it is intentionally tiny
(~70 lines, no framework) and documents its own scope in its header
comment: it only ever toggles presentation, never any entitlement
decision.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"
NARROW = {"width": 375, "height": 812}
DESKTOP = {"width": 1280, "height": 900}


def _new_org_and_user(username, org_name="WI6 Drawer Synthetic Ltd"):
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


def _wait_for_sidebar_transition(page):
    """`.shell-sidebar`'s open/close is an animated `transform` (`static/
    organisations/css/app.css`'s `transition: transform 0.2s ease;`) -
    Playwright's own `.click()`/keyboard actions do not wait for a CSS
    transition to finish, only for the element to be attached/visible/
    stable at the moment of the action itself. A `bounding_box()` read
    immediately after the toggling action can therefore observe a
    mid-transition position. This is a real animation, not something to
    special-case away - wait past its documented 0.2s duration before
    asserting on final position."""
    page.wait_for_timeout(300)


def _nav_links(page):
    """(href, text) pairs for every real nav link currently in the DOM,
    inside `#shell-sidebar` - used to compare the desktop render and the
    narrow-viewport-then-opened-drawer render of the SAME page/session."""
    anchors = page.locator("#shell-sidebar .shell-nav__link")
    return [
        (anchors.nth(i).get_attribute("href"), anchors.nth(i).inner_text().strip())
        for i in range(anchors.count())
    ]


@pytest.mark.django_db(transaction=True)
def test_hamburger_hidden_sidebar_off_canvas_at_narrow_but_visible_at_desktop(live_server):
    user, organisation = _new_org_and_user("wi6_drawer_visibility")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            toggle = page.locator("#shell-nav-toggle")
            assert toggle.is_visible()
            assert toggle.get_attribute("aria-expanded") == "false"

            sidebar_box = page.locator("#shell-sidebar").bounding_box()
            assert sidebar_box is not None
            assert sidebar_box["x"] + sidebar_box["width"] <= 0, (
                f"sidebar must be off-canvas before the drawer is opened: {sidebar_box}"
            )

            page.set_viewport_size(DESKTOP)
            page.reload()
            page.wait_for_load_state("networkidle")
            assert not page.locator("#shell-nav-toggle").is_visible()
            desktop_box = page.locator("#shell-sidebar").bounding_box()
            assert desktop_box is not None and desktop_box["x"] >= 0
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_click_opens_drawer_and_sets_aria_expanded_true(live_server):
    user, organisation = _new_org_and_user("wi6_drawer_open")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            toggle = page.locator("#shell-nav-toggle")
            toggle.click()
            _wait_for_sidebar_transition(page)

            assert toggle.get_attribute("aria-expanded") == "true"
            sidebar_box = page.locator("#shell-sidebar").bounding_box()
            assert sidebar_box is not None and sidebar_box["x"] >= 0, (
                f"drawer should be on-screen once opened: {sidebar_box}"
            )
            assert not page.locator("#shell-nav-overlay").is_hidden()
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_drawer_shows_identical_markup_to_desktop_sidebar_same_session(live_server):
    """The drawer reuses the exact same server-rendered `#shell-sidebar`
    element the desktop sidebar is (PID §16.3) - proven here by comparing
    every (href, text) nav-link pair between a desktop-width render and a
    narrow-width-then-opened-drawer render, for the SAME logged-in
    session. If these ever diverged, that would mean a second, duplicated
    (and separately-filterable) mobile menu implementation exists - which
    §16.3 explicitly forbids."""
    user, organisation = _new_org_and_user("wi6_drawer_parity")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=DESKTOP)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")
            desktop_links = _nav_links(page)
            assert len(desktop_links) > 0

            page.set_viewport_size(NARROW)
            page.reload()
            page.wait_for_load_state("networkidle")
            page.locator("#shell-nav-toggle").click()
            narrow_links = _nav_links(page)

            assert narrow_links == desktop_links, (
                "drawer nav links diverge from the desktop sidebar's own "
                f"links for the same session: desktop={desktop_links} "
                f"narrow={narrow_links}"
            )

            # Confirms there is exactly one `#shell-sidebar` in the DOM at
            # any time (never two competing implementations).
            assert page.locator("#shell-sidebar").count() == 1
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_escape_closes_drawer_and_returns_focus_to_hamburger(live_server):
    user, organisation = _new_org_and_user("wi6_drawer_escape")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            toggle = page.locator("#shell-nav-toggle")
            toggle.click()
            assert toggle.get_attribute("aria-expanded") == "true"

            # Focus moves into the drawer on open, to the first nav link
            # (shell.js's own documented behaviour).
            first_link_href = page.locator("#shell-sidebar .shell-nav__link").first.get_attribute("href")
            active_href = page.evaluate("() => document.activeElement.getAttribute('href')")
            assert active_href == first_link_href

            page.keyboard.press("Escape")
            _wait_for_sidebar_transition(page)

            assert toggle.get_attribute("aria-expanded") == "false"
            sidebar_box = page.locator("#shell-sidebar").bounding_box()
            assert sidebar_box is not None and sidebar_box["x"] + sidebar_box["width"] <= 0

            # Focus returns to the hamburger button on close.
            is_toggle_focused = page.evaluate(
                "() => document.activeElement === document.getElementById('shell-nav-toggle')"
            )
            assert is_toggle_focused
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_overlay_click_closes_drawer(live_server):
    user, organisation = _new_org_and_user("wi6_drawer_overlay")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            toggle = page.locator("#shell-nav-toggle")
            toggle.click()
            _wait_for_sidebar_transition(page)
            assert toggle.get_attribute("aria-expanded") == "true"

            page.locator("#shell-nav-overlay").click(force=True)
            _wait_for_sidebar_transition(page)

            assert toggle.get_attribute("aria-expanded") == "false"
            sidebar_box = page.locator("#shell-sidebar").bounding_box()
            assert sidebar_box is not None and sidebar_box["x"] + sidebar_box["width"] <= 0
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.xfail(
    reason=(
        "PL-confirmed WI6 finding (Low severity, docs/evidence/"
        "M007-BROWSER-ACCEPTANCE.md): shell.js's closeDrawer() calls "
        "toggle.focus() with returnFocus defaulting true on both the "
        "Escape path (test_escape_closes_drawer_and_returns_focus_to_"
        "hamburger, passes) and this overlay-click path, but only the "
        "overlay-click path ends with document.activeElement === <body> "
        "in real Chromium, reproduced deterministically (PL's own fresh "
        "repro, 100%) and independent of two different plausible fixes "
        "tried and rejected (mousedown preventDefault on the overlay; "
        "deferring the focus() call via setTimeout(0) - neither changed "
        "the observed outcome, so the actual browser-internal cause is "
        "not yet correctly diagnosed, not merely unaddressed). The drawer "
        "itself still closes correctly (see test_overlay_click_closes_"
        "drawer, immediately above, which passes) - only the next Tab "
        "press after an overlay-click close starts from <body> instead "
        "of the hamburger button, a minor keyboard-navigation convenience "
        "gap, not a broken or trapped focus. Left as an explicit, visible "
        "xfail (not deleted, not silently skipped) pending a correctly-"
        "diagnosed fix in a future frontend pass."
    ),
    strict=True,
)
def test_overlay_click_returns_focus_to_toggle(live_server):
    """Split out from test_overlay_click_closes_drawer above (PID §16.2/
    §28's own focus-return requirement) so the drawer-closes proof stays a
    clean pass while this one, still-open gap stays honestly visible as
    its own named, reasoned xfail rather than either failing the whole
    class of coverage or silently dropping this specific assertion."""
    user, organisation = _new_org_and_user("wi6_drawer_overlay_focus")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            toggle = page.locator("#shell-nav-toggle")
            toggle.click()
            _wait_for_sidebar_transition(page)

            page.locator("#shell-nav-overlay").click(force=True)
            _wait_for_sidebar_transition(page)

            is_toggle_focused = page.evaluate(
                "() => document.activeElement === document.getElementById('shell-nav-toggle')"
            )
            assert is_toggle_focused
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_hamburger_is_keyboard_operable(live_server):
    """Reachable via Tab, activatable via Enter/Space (PID §16.2 "keyboard
    operation works" + PID §28)."""
    user, organisation = _new_org_and_user("wi6_drawer_keyboard")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            page.locator("#shell-nav-toggle").focus()
            is_focused = page.evaluate(
                "() => document.activeElement === document.getElementById('shell-nav-toggle')"
            )
            assert is_focused

            page.keyboard.press("Enter")
            assert page.locator("#shell-nav-toggle").get_attribute("aria-expanded") == "true"

            page.keyboard.press("Escape")
            assert page.locator("#shell-nav-toggle").get_attribute("aria-expanded") == "false"

            page.locator("#shell-nav-toggle").focus()
            page.keyboard.press(" ")
            assert page.locator("#shell-nav-toggle").get_attribute("aria-expanded") == "true"
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_no_keyboard_trap_in_open_drawer(live_server):
    """Tab cycles through the open drawer's links and back out (a real
    `<button>`/`<a>` set with no `tabindex` manipulation anywhere in
    shell.js - nothing traps focus), and Escape always closes it
    regardless of focus position within it."""
    user, organisation = _new_org_and_user("wi6_drawer_no_trap")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            page.locator("#shell-nav-toggle").click()
            link_count = page.locator("#shell-sidebar .shell-nav__link").count()
            assert link_count > 0

            # Tab all the way through every drawer link plus a few extra
            # presses - focus must keep moving (never stick on one
            # element), proving nothing traps it.
            seen = []
            for _ in range(link_count + 3):
                seen.append(
                    page.evaluate(
                        "() => document.activeElement && document.activeElement.outerHTML.slice(0, 80)"
                    )
                )
                page.keyboard.press("Tab")
            assert len(set(seen)) > 1, "focus never moved - looks like a keyboard trap"

            # Regardless of where focus ended up, Escape still closes the
            # drawer.
            page.keyboard.press("Escape")
            assert page.locator("#shell-nav-toggle").get_attribute("aria-expanded") == "false"
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_selecting_a_drawer_link_navigates_and_does_not_leave_drawer_obscuring_destination(live_server):
    user, organisation = _new_org_and_user("wi6_drawer_navigate")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            page.locator("#shell-nav-toggle").click()
            first_link = page.locator("#shell-sidebar .shell-nav__link").first
            href = first_link.get_attribute("href")
            first_link.click()
            page.wait_for_load_state("networkidle")

            assert page.url.rstrip("/") == f"{live_server.url}{href}".rstrip("/")
            # A real page navigation happened, so the previous page's
            # (now-stale) drawer/overlay DOM is gone entirely with it -
            # nothing can obscure the destination.
            overlay = page.locator("#shell-nav-overlay")
            assert overlay.count() == 1
            assert overlay.is_hidden()
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_no_unauthorised_item_reachable_via_dom_manipulation_of_presentation_state(live_server):
    """The drawer's "open" state is purely a CSS class toggle
    (`shell-sidebar--open`) on the exact same markup the server already
    decided to send - there is no separate/hidden client-side nav-
    filtering logic to defeat. Forcibly adding that class via
    `page.evaluate` (bypassing the hamburger entirely) still only ever
    reveals the identical, already-server-filtered link set a normal
    click would - proving presentation state carries no authority of its
    own (PID §4.5 "no client-side entitlement logic")."""
    user, organisation = _new_org_and_user("wi6_drawer_dom_manip")
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport=NARROW)
            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            via_click = None
            page.locator("#shell-nav-toggle").click()
            via_click = sorted(_nav_links(page))
            page.keyboard.press("Escape")

            page.evaluate(
                "() => document.getElementById('shell-sidebar').classList.add('shell-sidebar--open')"
            )
            via_dom = sorted(_nav_links(page))

            assert via_dom == via_click, (
                "forcing the open CSS class directly must reveal exactly "
                "the same link set the real hamburger click already "
                f"revealed - got via_dom={via_dom} via_click={via_click}"
            )
        finally:
            browser.close()
