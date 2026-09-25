"""
Real-browser regression test for M006-AUDIT-0002 Finding G2's bounded
audit (Remediation actions list).

`remediation/templates/remediation/list.html`'s (via the shared
`_action_card.html` partial) `.action-card__title a` only carried
`color`/`text-decoration` overrides, not the `min-width: 0`/
`overflow-wrap: anywhere` pair `risk_register/templates/risk_register/
list.html`'s `.risk-card__title a` needed for the identical M006-AUDIT-0001
F2 defect - the remediation action title link's text is customer-controlled
(the action's own title, often carried over from a customer-controlled
risk/asset title) and can be a single long unbreakable run. Confirmed by
real-browser measurement (see this dispatch's own report) before the
matching rule was added.

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
from remediation.models import RemediationAction  # noqa: E402

LONG_ACTION_TITLE = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - Replace unsupported firmware on all East Wing units"
)

HOSTILE_ACTION_TITLE = (
    "<script>alert(document.cookie)</script><img/src=x/onerror=alert(document.cookie)>"
    "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
)

# Deliberately short - see key_assets/tests/test_narrow_viewport_regression.py's
# USERNAME comment for why: a separate, pre-existing, out-of-scope
# `.app-header__nav` overflow defect (driven by username length alone,
# nothing to do with remediation cards) was found while writing these
# tests and is flagged in this dispatch's report rather than fixed here.
USERNAME = "viewport_regression_user_rem"
PASSWORD = "a-strong-synthetic-test-password-123"


def _make_action(organisation, *, title):
    return RemediationAction.objects.create(
        organisation=organisation,
        title=title,
        status=RemediationAction.STATUS_OPEN,
        priority=RemediationAction.PRIORITY_MEDIUM,
    )


@pytest.mark.django_db(transaction=True)
def test_remediation_list_has_no_horizontal_overflow_at_375px(live_server):
    User = get_user_model()
    user = User.objects.create_user(username=USERNAME, password=PASSWORD)
    organisation = Organisation.objects.create(
        name="Viewport Regression Synthetic Remediation Ltd"
    )
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )

    long_action = _make_action(organisation, title=LONG_ACTION_TITLE)
    hostile_action = _make_action(organisation, title=HOSTILE_ACTION_TITLE)

    list_url = f"{live_server.url}{reverse('remediation:list', args=[organisation.id])}"

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

            for action in (long_action, hostile_action):
                detail_url = reverse("remediation:detail", args=[organisation.id, action.id])
                link = page.locator(f'.action-card__title a[href="{detail_url}"]')
                assert link.count() == 1
                assert link.is_visible()
                box = link.bounding_box()
                assert box is not None
                assert box["width"] > 0 and box["height"] > 0

            assert console_errors == []
        finally:
            browser.close()
