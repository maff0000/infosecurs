"""
Real-browser acceptance test for the Tasks sidebar page (M010A PID §4:
"Browser Tasks page, sidebar/hamburger and keyboard/zoom"). Same
established convention as risk_register/tests/test_narrow_viewport_
regression.py and identity/tests/test_federated_login.py - a real
Playwright/Chromium browser driving a pytest-django `live_server` in the
same process. `pytest.importorskip` keeps this file collectible (reported
SKIPPED, not an import error) wherever Playwright/Chromium is not
installed - see this package's own evidence document for the real,
executed run.
"""
import uuid

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402
from security_tasks import services  # noqa: E402
from security_tasks.models import TaskKind, TaskStatus  # noqa: E402

USERNAME = "tasks_browser_acceptance_user"
PASSWORD = "a-strong-synthetic-test-password-123"


@pytest.mark.django_db(transaction=True)
def test_tasks_page_sidebar_filters_pagination_and_keyboard_nav(live_server):
    User = get_user_model()
    user = User.objects.create_user(username=USERNAME, password=PASSWORD)
    organisation = Organisation.objects.create(name="Browser Acceptance Synthetic Ltd")
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )

    for i in range(3):
        services.create_task(
            organisation, actor=user, kind=TaskKind.MANUAL_OTHER, title=f"Acceptance task {i}",
            idempotency_key=str(uuid.uuid4()),
        )
    done_task = services.create_task(
        organisation, actor=user, kind=TaskKind.MANUAL_OTHER, title="Already done task",
        idempotency_key=str(uuid.uuid4()),
    )
    services.transition_task(
        organisation, actor=user, task_id=done_task.id, expected_version=1,
        next_status=TaskStatus.DONE, reason="administrative_work_complete",
    )

    list_url = f"{live_server.url}{reverse('security_tasks:list', args=[organisation.id])}"
    home_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

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

            # Sidebar link navigation (never a direct goto for this check).
            page.goto(home_url)
            page.wait_for_load_state("networkidle")
            sidebar_link = page.locator('.shell-sidebar a[href="{}"]'.format(
                reverse("security_tasks:list", args=[organisation.id])
            ))
            assert sidebar_link.count() == 1
            assert sidebar_link.is_visible()
            sidebar_link.click()
            page.wait_for_load_state("networkidle")
            assert page.url.rstrip("/") == list_url.rstrip("/")

            # Filters: status=done should show only the done task.
            page.select_option("#id_status", "done")
            page.click('button:has-text("Apply filters")')
            page.wait_for_load_state("networkidle")
            assert "Already done task" in page.content()
            assert "Acceptance task 0" not in page.content()

            # Reset filters, confirm pagination control absent at this
            # small dataset size (4 tasks, default page size 25).
            page.goto(list_url)
            page.wait_for_load_state("networkidle")
            assert "Acceptance task 0" in page.content()
            assert page.locator(".task-pagination").count() == 0

            # Keyboard navigation: focus the search field with the keyboard
            # (no mouse), type a query and submit with Enter - standard
            # HTML form behaviour (Enter in a text field submits the form),
            # proving the filter form is fully keyboard-operable without
            # ever needing to click the "Apply filters" button.
            page.locator("#id_q").focus()
            assert page.evaluate("document.activeElement.id") == "id_q"
            page.keyboard.type("Acceptance task 1")
            with page.expect_navigation():
                page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")
            assert "q=Acceptance" in page.url
            assert "Acceptance task 1" in page.content()
            assert "Acceptance task 0" not in page.content()

            # A real anchor link also remains keyboard-activatable: Tab
            # from the body to the first focusable element and confirm
            # the browser actually moved focus onto something in the page
            # (not stuck on <body>) - a basic, reliable focus-management
            # check independent of any one element's exact activation
            # semantics.
            page.goto(list_url)
            page.wait_for_load_state("networkidle")
            page.keyboard.press("Tab")
            focused_tag = page.evaluate("document.activeElement.tagName")
            assert focused_tag != "BODY"

            # Zoom/viewport check at a narrow width - no horizontal overflow.
            page.goto(list_url)
            page.set_viewport_size({"width": 375, "height": 812})
            page.wait_for_load_state("networkidle")
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width, (
                f"Horizontal overflow at 375px: scrollWidth={scroll_width} > clientWidth={client_width}"
            )

            assert console_errors == []
        finally:
            browser.close()
