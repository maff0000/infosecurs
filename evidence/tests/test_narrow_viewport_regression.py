"""
Real-browser regression test for M006-AUDIT-0002 Finding G2's bounded
audit (Evidence list).

`evidence/templates/evidence/list.html`'s `.evidence-card__title a` shared
the identical missing-wrap pattern `risk_register/templates/risk_register/
list.html`'s `.risk-card__title a` had before the M006-AUDIT-0001 F2 fix:
the evidence title link's text is customer-controlled and can be a single
long unbreakable run, with no `min-width: 0`/`overflow-wrap: anywhere`
rule to let it wrap inside the card's flex row. Confirmed by real-browser
measurement (see this dispatch's own report) before the matching rule was
added.

Matches this project's own established real-browser acceptance convention
- see `risk_register/tests/test_narrow_viewport_regression.py`'s docstring
for the full rationale.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from evidence.models import EvidenceItem  # noqa: E402
from organisations.models import Organisation, OrganisationMembership  # noqa: E402

LONG_EVIDENCE_TITLE = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - Annual Penetration Test Executive Summary Report"
)

HOSTILE_EVIDENCE_TITLE = (
    "<script>alert(document.cookie)</script><img/src=x/onerror=alert(document.cookie)>"
    "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
)

# Deliberately short - see key_assets/tests/test_narrow_viewport_regression.py's
# USERNAME comment for why: a separate, pre-existing, out-of-scope
# `.app-header__nav` overflow defect (driven by username length alone,
# nothing to do with evidence cards) was found while writing these tests
# and is flagged in this dispatch's report rather than fixed here.
USERNAME = "viewport_regression_user_ev"
PASSWORD = "a-strong-synthetic-test-password-123"


def _make_evidence(organisation, *, title):
    return EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title=title,
        reference_url="https://example.test/evidence-reference",
        status=EvidenceItem.STATUS_ACTIVE,
    )


@pytest.mark.django_db(transaction=True)
def test_evidence_list_has_no_horizontal_overflow_at_375px(live_server):
    User = get_user_model()
    user = User.objects.create_user(username=USERNAME, password=PASSWORD)
    organisation = Organisation.objects.create(name="Viewport Regression Synthetic Evidence Ltd")
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )

    long_item = _make_evidence(organisation, title=LONG_EVIDENCE_TITLE)
    hostile_item = _make_evidence(organisation, title=HOSTILE_EVIDENCE_TITLE)

    list_url = f"{live_server.url}{reverse('evidence:list', args=[organisation.id])}"

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

            for item in (long_item, hostile_item):
                detail_url = reverse("evidence:detail", args=[organisation.id, item.id])
                link = page.locator(f'.evidence-card__title a[href="{detail_url}"]')
                assert link.count() == 1
                assert link.is_visible()
                box = link.bounding_box()
                assert box is not None
                assert box["width"] > 0 and box["height"] > 0

            assert console_errors == []
        finally:
            browser.close()
