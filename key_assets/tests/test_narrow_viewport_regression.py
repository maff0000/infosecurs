"""
Real-browser regression test for M006-AUDIT-0002 Finding G2.

Finding (fresh independent Auditor, real-browser measurement at a 375px
viewport): `GET /organisations/<id>/assets/` overflowed horizontally
(`document.documentElement.scrollWidth=612` vs `clientWidth=375`, ~63%
overflow observed). Root cause: `.asset-card__title` had no
`overflow-wrap`/`min-width: 0` rule at all, unlike
`risk_register/templates/risk_register/list.html`'s `.risk-card__title a`
(M006-AUDIT-0001 F2) - and, unlike that case, the asset name renders as
plain text, not even inside a link, so there was no child element to
target in the first place. See
`key_assets/templates/key_assets/list.html`'s `.asset-card__title-text`
rule (and the wrapping `<span>` added around `{{ asset.name }}`) for the
fix.

Matches this project's own established real-browser acceptance convention
- see `risk_register/tests/test_narrow_viewport_regression.py`'s docstring
for the full rationale (real `live_server` + Playwright/Chromium in the
same process, disposable Playwright install, `pytest.importorskip` so this
file stays collectible/SKIPPED rather than import-erroring wherever
Playwright is not installed).
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from key_assets.models import CATEGORY_BUSINESS_APPLICATION, CRITICALITY_HIGH, KeyAsset  # noqa: E402
from organisations.models import Organisation, OrganisationMembership  # noqa: E402

# A long, realistic asset name - a single run with no natural
# word-wrap-defeating length by itself, the exact shape that pushed the
# card (and the page) wider than the viewport pre-fix.
LONG_ASSET_NAME = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - East Wing Warehouse Annex 3 Backup Controller Unit"
)

# Hostile/markup-shaped text, same class as the Auditor's own XSS-test
# payload and the risk_register regression test's HOSTILE_ASSET_NAME -
# deliberately no space/hyphen break opportunities at all, repeated well
# past 375px's worth of characters.
HOSTILE_ASSET_NAME = (
    "<script>alert(document.cookie)</script><img/src=x/onerror=alert(document.cookie)>"
    "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
)

# Deliberately short (unlike some sibling narrow-viewport tests) - a
# separate, pre-existing, out-of-scope defect was found while writing this
# test: `.app-header__nav` (templates/base.html / static/organisations/
# css/app.css) has no `flex-wrap` of its own, so a sufficiently long
# username alone (independent of any asset/card content) overflows the
# header at 375px. That is a real, reproducible site-chrome defect, but it
# is not a "title/card/list" pattern this dispatch's bounded audit covers,
# and `templates/base.html` is not one of the directories this dispatch
# was scoped to touch - flagged in this dispatch's report for the PL,
# deliberately not fixed here. Kept short here so this test measures only
# the asset-card G2 fix it exists to prove, not that unrelated header
# issue.
USERNAME = "viewport_regression_user_ka"
PASSWORD = "a-strong-synthetic-test-password-123"


def _make_asset(organisation, *, name):
    return KeyAsset.objects.create(
        organisation=organisation,
        name=name,
        category=CATEGORY_BUSINESS_APPLICATION,
        criticality=CRITICALITY_HIGH,
        status=KeyAsset.STATUS_CONFIRMED,
    )


@pytest.mark.django_db(transaction=True)
def test_key_assets_list_has_no_horizontal_overflow_at_375px(live_server):
    User = get_user_model()
    user = User.objects.create_user(username=USERNAME, password=PASSWORD)
    organisation = Organisation.objects.create(name="Viewport Regression Synthetic Assets Ltd")
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )

    _make_asset(organisation, name=LONG_ASSET_NAME)
    _make_asset(organisation, name=HOSTILE_ASSET_NAME)

    list_url = f"{live_server.url}{reverse('key_assets:list', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )

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

            # Both titles remain visible and readable at this viewport -
            # not just present in the DOM. Scoped to the title text span
            # specifically (`.asset-card__title-text`), since (unlike
            # risk_register) the asset name is plain text, not a link.
            titles = page.locator(".asset-card__title-text")
            assert titles.count() == 2
            for i in range(titles.count()):
                title = titles.nth(i)
                assert title.is_visible()
                box = title.bounding_box()
                assert box is not None
                assert box["width"] > 0 and box["height"] > 0

            assert console_errors == []
        finally:
            browser.close()
