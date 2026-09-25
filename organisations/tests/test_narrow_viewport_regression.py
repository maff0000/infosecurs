"""
Real-browser regression test for M006-AUDIT-0002 Finding G2's bounded
audit ("Your organisations" list).

`static/organisations/css/app.css`'s shared `.card-list__title` /
`.card-list__link` rules had neither `flex-wrap: wrap` on the link
(unlike every other card pattern audited here, which already wraps) nor
`min-width: 0`/`overflow-wrap: anywhere` on the title - the organisation
name is customer-controlled and can be a single long unbreakable run, the
identical defect class M006-AUDIT-0001 F2 fixed on the Risk register.
Confirmed by real-browser measurement (see this dispatch's own report)
before the matching rules were added.

Matches this project's own established real-browser acceptance convention
- see `risk_register/tests/test_narrow_viewport_regression.py`'s docstring
for the full rationale.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402

LONG_ORG_NAME = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster Holdings International Limited"
)

HOSTILE_ORG_NAME = (
    "<script>alert(document.cookie)</script><img/src=x/onerror=alert(document.cookie)>"
    "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
)

USERNAME = "viewport_regression_user_orgs"
PASSWORD = "a-strong-synthetic-test-password-123"


@pytest.mark.django_db(transaction=True)
def test_organisations_list_has_no_horizontal_overflow_at_375px(live_server):
    User = get_user_model()
    user = User.objects.create_user(username=USERNAME, password=PASSWORD)

    long_org = Organisation.objects.create(name=LONG_ORG_NAME)
    hostile_org = Organisation.objects.create(name=HOSTILE_ORG_NAME)
    for org in (long_org, hostile_org):
        OrganisationMembership.objects.create(
            organisation=org, user=user, role=OrganisationMembership.ROLE_OWNER
        )

    list_url = f"{live_server.url}{reverse('organisations:list')}"

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

            titles = page.locator(".card-list__title")
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
