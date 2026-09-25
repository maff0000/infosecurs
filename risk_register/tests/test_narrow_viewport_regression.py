"""
Real-browser regression test for M006-AUDIT-0001 F2.

Finding (fresh independent Auditor, real-browser measurement at a 375px
viewport): `GET /organisations/<id>/risks/` overflowed horizontally
(`document.documentElement.scrollWidth` > `clientWidth`, ~34% overflow
observed). Root cause: the risk-card title link's text - which includes
the linked asset's name, customer-controlled - had no wrap opportunity as
a flex item, so a long/unbroken title pushed the card, and with it the
whole page, wider than the viewport. See
`risk_register/templates/risk_register/list.html`'s `.risk-card__title a`
rule for the fix (`min-width: 0` + `overflow-wrap: anywhere`, scoped to
that one element only).

Matches this project's own established real-browser acceptance
convention - a real Playwright/Chromium browser driving a
`pytest-django` `live_server` in the same process (real HTTP, real
cookies/session/CSRF, real DB, real static assets - WhiteNoise serves
STATICFILES_DIRS directly under DJANGO_ENV=test, see
config/settings.py's "Static files" section) - see
`identity/testing.py`'s "REAL-BROWSER ACCEPTANCE" note and
`identity/tests/test_federated_login.py` for the same pattern used
elsewhere in this codebase, and `docs/evidence/M005-AUDIT-0001.md` /
`docs/evidence/M001-AUDIT-0001.md` for this project's own audits using
exactly this `live_server` + Playwright/Chromium combination.

Playwright is not a pinned project dependency - this codebase's own
audits install it disposably per run (see `docs/evidence/M001-AUDIT-0001.md`
"Staying lightweight" note), rather than adding a browser-binary
dependency to the pinned, hash-locked `requirements-dev.txt`/CI image
graph. `pytest.importorskip` below keeps this file collectible, and this
test reported as SKIPPED rather than an import error, in any environment
that has not installed it (e.g. default CI, which does not currently
provision Chromium). The M006-AUDIT-0001 F1/F2 dispatch report documents
a real disposable `pip install playwright && playwright install
chromium` run that exercised this test for real end to end, not just as
a skip - see that report for the observed scrollWidth/clientWidth values
and the before/after reproduction against the pre-fix template.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402
from risk_register.models import Risk  # noqa: E402

# A long, realistic asset name (as it would appear embedded in a risk
# title generated against a genuinely long-named customer asset) - a
# single run with no natural word-wrap-defeating length by itself, the
# exact shape that pushed the card (and the page) wider than the
# viewport pre-fix.
LONG_ASSET_NAME = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - East Wing Warehouse Annex 3 Backup Controller Unit"
)

# Hostile/markup-shaped text, similar in class to the Auditor's own
# XSS-test payload (M006-AUDIT-0001.md §28's
# `<script>...</script><img src=x onerror=...>MARK` shape) - customer-
# controlled asset names can legitimately be long AND contain characters
# that defeat ordinary word-boundary wrapping. Deliberately written with
# no space/hyphen break opportunities at all (real browsers may still
# find a break point at a hyphen or a slash) and repeated well past
# 375px's worth of characters, so this reproduces the underlying "one
# long unbreakable run" defect deterministically, independent of exact
# font metrics.
HOSTILE_ASSET_NAME = (
    "<script>alert(document.cookie)</script><img/src=x/onerror=alert(document.cookie)>"
    "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
)

USERNAME = "viewport_regression_user"
PASSWORD = "a-strong-synthetic-test-password-123"


def _make_risk(organisation, *, title):
    return Risk.objects.create(
        organisation=organisation,
        title=title,
        threat="Synthetic threat text for the narrow-viewport regression test.",
        vulnerability="Synthetic vulnerability text.",
        impact=3,
        likelihood=3,
        rationale="Synthetic rationale.",
        proposed_treatment="Synthetic proposed treatment.",
        status=Risk.STATUS_CONFIRMED,
        source=Risk.SOURCE_AI,
    )


@pytest.mark.django_db(transaction=True)
def test_risk_register_list_has_no_horizontal_overflow_at_375px(live_server):
    User = get_user_model()
    user = User.objects.create_user(username=USERNAME, password=PASSWORD)
    organisation = Organisation.objects.create(name="Viewport Regression Synthetic Ltd")
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )

    long_title_risk = _make_risk(
        organisation, title=f"Unpatched software on {LONG_ASSET_NAME}"
    )
    hostile_title_risk = _make_risk(
        organisation, title=f"Exposed management endpoint on {HOSTILE_ASSET_NAME}"
    )

    list_url = f"{live_server.url}{reverse('risk_register:list', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )

            # Real login through the real local-dev-account form (a
            # `<details>` disclosure on the login page - must be expanded
            # before its fields are interactable in a real browser).
            page.goto(f"{live_server.url}{reverse('login')}")
            page.click("summary")
            page.fill("#id_username", USERNAME)
            page.fill("#id_password", PASSWORD)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")

            page.goto(list_url)
            page.wait_for_load_state("networkidle")

            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width, (
                f"Horizontal overflow reproduced at 375px viewport: "
                f"scrollWidth={scroll_width} > clientWidth={client_width}"
            )

            # Both titles remain visible/readable and their links remain
            # genuinely interactable at this viewport - not just present
            # in the DOM. Playwright's .click() performs real
            # actionability checks (attached, visible, stable, receives
            # events) before clicking, and a real navigation is the
            # strongest proof the link is truly clickable here.
            for risk in (long_title_risk, hostile_title_risk):
                detail_url = reverse("risk_register:detail", args=[organisation.id, risk.id])
                # Scoped to the title link specifically (`.risk-card__title
                # a`) - the same card also has a second "View" button
                # linking to the same URL, which a bare `a[href=...]`
                # selector would also match.
                link = page.locator(f'.risk-card__title a[href="{detail_url}"]')
                assert link.count() == 1
                assert link.is_visible()
                box = link.bounding_box()
                assert box is not None
                assert box["width"] > 0 and box["height"] > 0

                link.click()
                page.wait_for_load_state("networkidle")
                assert page.url.rstrip("/") == f"{live_server.url}{detail_url}".rstrip("/")
                page.go_back()
                page.wait_for_load_state("networkidle")

            assert console_errors == []
        finally:
            browser.close()
