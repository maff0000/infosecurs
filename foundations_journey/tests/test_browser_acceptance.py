"""
Real-browser acceptance test for the guided Foundations card (M010B
"Verification before reporting done": "log in, answer at least one
control via the new guided card, confirm the receipt/explainer render,
pause, resume, and confirm the checkpoint correctly resumes at the right
question"). Same established convention as `security_tasks/tests/
test_browser_acceptance.py` and `risk_register/tests/test_narrow_
viewport_regression.py` - a real Playwright/Chromium browser driving a
pytest-django `live_server` in the same process.
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership, OrganisationProfile  # noqa: E402

USERNAME = "foundations_journey_browser_user"
PASSWORD = "a-strong-synthetic-test-password-123"


@pytest.mark.django_db(transaction=True)
def test_answer_a_control_pause_and_resume_at_the_right_question(live_server):
    User = get_user_model()
    user = User.objects.create_user(username=USERNAME, password=PASSWORD)
    organisation = Organisation.objects.create(name="Browser Acceptance Guided Journey Ltd")
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )
    OrganisationProfile.objects.create(
        organisation=organisation,
        legal_trading_name="Browser Acceptance Guided Journey Ltd",
    )

    first_question_url = (
        f"{live_server.url}"
        f"{reverse('foundations_journey:guided_question', args=[organisation.id, 'mfa_user_accounts'])}"
    )
    second_question_url = (
        f"{live_server.url}"
        f"{reverse('foundations_journey:guided_question', args=[organisation.id, 'mfa_privileged_accounts'])}"
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
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

            # Answer the first guided control.
            page.goto(first_question_url)
            page.wait_for_load_state("networkidle")
            assert "Staff sign-in protection" in page.content()

            page.check('input[type="radio"][value="MFA_USER_NOT_USED"]')
            page.click('button:has-text("Save answer")')
            page.wait_for_load_state("networkidle")

            # Receipt/explainer renders on the same page after save.
            assert "No MFA is in use for staff accounts" in page.content()
            # The previously-selected option is still pre-checked.
            assert page.is_checked('input[type="radio"][value="MFA_USER_NOT_USED"]')

            # Add a follow-up task for this NO answer.
            page.click('button:has-text("Add a follow-up task for this answer")')
            page.wait_for_load_state("networkidle")
            assert "follow-up task has been added" in page.content()

            # Pause.
            page.click('button:has-text("Pause")')
            page.wait_for_load_state("networkidle")

            # Confirm the paused state survives a plain page view (no
            # silent auto-resume merely from looking at the journey
            # again), then click Resume for real in the browser - the
            # resulting redirect must land on the ACTUAL next-unreviewed
            # control (mfa_privileged_accounts, the second catalogue
            # control), never a hardcoded "next in list" guess.
            page.goto(first_question_url)
            page.wait_for_load_state("networkidle")
            assert page.locator('button:has-text("Resume")').count() == 1

            page.click('button:has-text("Resume")')
            page.wait_for_load_state("networkidle")

            assert page.url.rstrip("/") == second_question_url.rstrip("/")
            assert "Admin/privileged account protection" in page.content()

            assert console_errors == []
        finally:
            browser.close()
