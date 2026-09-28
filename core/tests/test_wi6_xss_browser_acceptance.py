"""
WI6 (docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md §19.4/
§28) - real-browser XSS execution re-verification against the M007
candidate, per `docs/evidence/M006-SECTION19-XSS-BROWSER-COMPLETION.md`'s
own established methodology (read in full before writing this file):
hostile payload families, each carrying a detectable global execution-flag,
planted through real form submissions / real ORM-seeded fields, checked via
a live-DOM execution-flag read (never response-source/escaped-text
inspection alone) plus a DOM inspection confirming the payload rendered as
inert text.

Scope, established by first checking exactly what M007 touched (`git log
--oneline -- '*.html'` + `git show --stat` for the two M007 template
commits, done as part of this dispatch's own investigation - see this
file's own WI6 evidence report for the full reasoning):

  - M007-WI2 (`templates/application_shell.html`) changed the `{% extends
    %}` line of all 37 pre-existing organisation-scoped templates from
    `base.html` to `application_shell.html` - a MECHANICAL one-line change
    each, confirmed via `git show` diff inspection; every one of those
    templates' own `{% block content %}` body - where all pre-existing
    customer-controlled rendering happens - is byte-identical to what
    `docs/evidence/M006-SECTION19-XSS-BROWSER-COMPLETION.md` already
    proved inert. Those surfaces are therefore CONFIRMED-UNCHANGED, not
    re-executed fresh here (re-running M006's full payload matrix against
    unchanged templates would prove nothing new) - EXCEPT that this
    codebase's own existing narrow-viewport-regression / badge-regression
    Playwright files (which independently embed their own execution-flag
    XSS assertions on several of these same pages: risk/remediation/
    evidence/key-asset/organisation-list/policy/questionnaire) now
    genuinely RUN instead of skip once Playwright is installed - that is
    real, fresh, independent re-execution of a large slice of this
    surface, just living in those files rather than duplicated here.

  - `application_shell.html` itself renders `organisation.name` (in
    `.app-header__context-name`) and `user.username` (in
    `.app-header__user`) - BOTH pre-existing rendering points, unchanged
    in shape from the old `templates/base.html` (confirmed by direct
    comparison - `.app-header__context-name` is literally the same
    selector `core/tests/test_responsive_text_regression.py`'s own
    pre-existing `test_header_organisation_name_no_overflow_at_375px`
    already exercises for both overflow AND the identical execution-flag
    XSS check, which also now genuinely runs). `user.username` cannot
    itself carry a script-shaped payload in the first place - Django's
    default `UnicodeUsernameValidator` (unmodified by M007) rejects `<`/
    `>`/`"`/`'` in a username at the model-validation layer, so there is
    no legitimate way to plant a hostile username to test against; that
    validator-level rejection is the real control here, not escaping.

  - `organisations/templates/organisations/detail.html` (Home, rewritten)
    and `organisations/templates/organisations/foundations.html` (new)
    are where M007 GENUINELY introduces one new rendering location:
    `organisation.name` a SECOND time, in the new `.page-header__subtitle`
    element, on both pages - a location no prior M006 test selector
    covers. This file's own tests below are the fresh, real-browser
    execution proof for exactly that new location. Every other piece of
    Home/Foundations content (posture/completion percentages, Needs
    Attention phrasing, Foundations requirement titles/area labels/answer
    wording) is either a number or governed product metadata - never
    customer-controlled - confirmed by reading `organisations/views.py`'s
    `organisation_detail`/`organisation_foundations`/`_needs_attention_
    lines` and `entitlements/metrics.py`'s `get_needs_attention` in full;
    there is no legitimate customer-input injection point on either page
    beyond the organisation name.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"

# Same payload families `docs/evidence/M006-SECTION19-XSS-BROWSER-
# COMPLETION.md` used, each carrying a detectable global flag - adapted to
# this codebase's own established `window.__auditXssFired` convention
# (core/tests/test_responsive_text_regression.py's own `HOSTILE_TEXT`/
# risk_register's `HOSTILE_ASSET_NAME`), combined into one run since
# `Organisation.name` is a single CharField(max_length=255) and every
# family must fit together within that bound.
_MARK = "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
SCRIPT_PAYLOAD = "<script>window.__auditXssFired = true;</script>"
IMG_ONERROR_PAYLOAD = '<img src=x onerror="window.__auditXssFired = true;">'
SVG_ONLOAD_PAYLOAD = '<svg onload="window.__auditXssFired = true;">'
ATTRIBUTE_BREAKOUT_DOUBLE = '"><script>window.__auditXssFired = true;</script>'
ATTRIBUTE_BREAKOUT_SINGLE = "'><script>window.__auditXssFired = true;</script>"

COMBINED_HOSTILE_ORG_NAME = (
    SCRIPT_PAYLOAD + IMG_ONERROR_PAYLOAD + SVG_ONLOAD_PAYLOAD + " " + _MARK
)
assert len(COMBINED_HOSTILE_ORG_NAME) <= 255

ATTRIBUTE_BREAKOUT_ORG_NAME = (
    "Normal Co " + ATTRIBUTE_BREAKOUT_DOUBLE + " " + ATTRIBUTE_BREAKOUT_SINGLE
)
assert len(ATTRIBUTE_BREAKOUT_ORG_NAME) <= 255


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


def _assert_inert(page, page_errors, console_errors, org_name):
    assert not page.evaluate("() => window.__auditXssFired"), (
        "hostile organisation name executed live in the DOM - XSS"
    )
    assert page_errors == []
    assert console_errors == []

    # DOM inspection, not response-source inspection: the hostile text
    # must be present as literal, inert text content, and there must be
    # zero live <script> elements anywhere in body carrying it.
    assert org_name in page.locator("body").inner_text()
    live_script_texts = page.evaluate(
        "() => Array.from(document.querySelectorAll('script')).map(s => s.textContent)"
    )
    assert not any("__auditXssFired" in (t or "") for t in live_script_texts), (
        "a live <script> element carrying the payload exists in the DOM"
    )


@pytest.mark.django_db(transaction=True)
def test_hostile_organisation_name_inert_on_home_page_subtitle_and_header(live_server):
    """M007's one genuinely new customer-controlled rendering location
    (see this file's own module docstring): `organisation.name` in Home's
    new `.page-header__subtitle`, alongside its pre-existing appearance in
    the shared header."""
    user, organisation = _new_org_and_user(
        "wi6_xss_home_script", COMBINED_HOSTILE_ORG_NAME
    )
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            subtitle = page.locator(".page-header__subtitle")
            assert subtitle.count() == 1
            assert organisation.name in subtitle.inner_text()

            header_name = page.locator(".app-header__context-name")
            assert organisation.name in header_name.inner_text()

            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width, (
                f"hostile organisation name broke the shell layout: "
                f"scrollWidth={scroll_width} > clientWidth={client_width}"
            )

            _assert_inert(page, page_errors, console_errors, organisation.name)
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_hostile_organisation_name_inert_on_foundations_page_subtitle(live_server):
    user, organisation = _new_org_and_user(
        "wi6_xss_foundations_script", COMBINED_HOSTILE_ORG_NAME
    )
    foundations_url = f"{live_server.url}{reverse('organisations:foundations', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            _login(page, live_server, user.username)
            page.goto(foundations_url)
            page.wait_for_load_state("networkidle")

            subtitle = page.locator(".page-header__subtitle").first
            assert organisation.name in subtitle.inner_text()

            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width

            _assert_inert(page, page_errors, console_errors, organisation.name)
        finally:
            browser.close()


@pytest.mark.django_db(transaction=True)
def test_attribute_breakout_organisation_name_inert_on_home_page(live_server):
    """Attribute-breakout family specifically - `organisation.name` is
    only ever rendered as element text content (never interpolated into
    an HTML attribute anywhere on Home/Foundations), so this also
    confirms there is no attribute-context sink for it to break out of."""
    user, organisation = _new_org_and_user(
        "wi6_xss_home_attr_breakout", ATTRIBUTE_BREAKOUT_ORG_NAME
    )
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            _login(page, live_server, user.username)
            page.goto(home_url)
            page.wait_for_load_state("networkidle")

            assert organisation.name in page.locator(".page-header__subtitle").inner_text()
            assert not page.evaluate("() => window.__auditXssFired")
            assert page_errors == []
            assert console_errors == []
        finally:
            browser.close()
