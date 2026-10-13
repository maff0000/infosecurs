"""
M009A real-browser acceptance (WO-M009A-SECURE-INGESTION-XLSX.md
Correction 15 - "Real Chromium acceptance at 1280px/768px/375px is
required"; Final Correction I - the XSS-inertness proof), mirroring
`core/tests/test_wi6_xss_browser_acceptance.py`'s own established
methodology (hostile payload families carrying a detectable global
execution flag, a live-DOM execution-flag read, plus DOM inspection
confirming inert rendering) and `evidence/tests/test_narrow_viewport_
regression.py`'s own multi-viewport pattern.
"""
import tempfile

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402
from questionnaire import import_services  # noqa: E402
from questionnaire.eval import m009a_ingestion_corpus as corpus  # noqa: E402
from questionnaire.models import QuestionnaireImportQuestion  # noqa: E402
from questionnaire.scanner import STATE_CLEAN, ScanResult  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"

_MARK = "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
SCRIPT_PAYLOAD = "<script>window.__auditXssFired = true;</script>"
IMG_ONERROR_PAYLOAD = '<img src=x onerror="window.__auditXssFired = true;">'
SVG_ONLOAD_PAYLOAD = '<svg onload="window.__auditXssFired = true;">'
LONG_STRING_PAYLOAD = "Q" * 5000
QUOTE_ENTITY_PAYLOAD = "\"'&amp;&lt;&gt;&quot;" + _MARK


def _new_org_and_user(username, org_name="Hostile Content Synthetic Ltd"):
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


class _CleanScanner:
    def scan_file(self, file_path):
        return ScanResult(state=STATE_CLEAN, provenance={"backend": "fake"})


def _ingest_hostile_workbook(organisation, user, monkeypatch):
    import io

    import openpyxl
    from django.core.files.uploadedfile import SimpleUploadedFile

    monkeypatch.setattr(import_services, "get_scanner", lambda: _CleanScanner())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Question", "Answer"])
    ws.append([SCRIPT_PAYLOAD + " " + _MARK, ""])
    ws.append([IMG_ONERROR_PAYLOAD, ""])
    ws.append([SVG_ONLOAD_PAYLOAD, ""])
    ws.append([LONG_STRING_PAYLOAD, ""])
    ws.append([QUOTE_ENTITY_PAYLOAD, ""])
    buf = io.BytesIO()
    wb.save(buf)

    return import_services.ingest_questionnaire_import(
        organisation=organisation,
        actor=user,
        uploaded_file=SimpleUploadedFile(
            "hostile.xlsx", buf.getvalue(), content_type="application/octet-stream"
        ),
        original_filename="hostile.xlsx",
    )


@pytest.mark.django_db(transaction=True)
class TestXssInertness:
    """Final Correction I - proves in real Chromium that extracted
    workbook content renders as inert text at 375px, with no script/event
    execution and no horizontal overflow."""

    def test_hostile_extracted_content_is_inert_at_375px(self, live_server, monkeypatch):
        user, organisation = _new_org_and_user("wi_m009a_xss")
        import_record = _ingest_hostile_workbook(organisation, user, monkeypatch)
        assert import_record.status == "extracted"
        assert QuestionnaireImportQuestion.objects.filter(import_record=import_record).count() >= 5

        detail_url = (
            f"{live_server.url}"
            f"{reverse('questionnaire:import_detail', args=[organisation.id, import_record.id])}"
        )

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
                page.goto(detail_url)
                page.wait_for_load_state("networkidle")

                assert not page.evaluate("() => window.__auditXssFired"), (
                    "hostile extracted question text executed live in the DOM - XSS"
                )
                assert page_errors == []

                body_text = page.locator("body").inner_text()
                assert _MARK in body_text

                live_script_texts = page.evaluate(
                    "() => Array.from(document.querySelectorAll('script'))"
                    ".map(s => s.textContent)"
                )
                assert not any("__auditXssFired" in (t or "") for t in live_script_texts)

                scroll_width = page.evaluate("document.documentElement.scrollWidth")
                client_width = page.evaluate("document.documentElement.clientWidth")
                assert scroll_width <= client_width, (
                    f"hostile content broke layout at 375px: scrollWidth={scroll_width} "
                    f"> clientWidth={client_width}"
                )
            finally:
                browser.close()


@pytest.mark.django_db(transaction=True)
class TestUploadAndStatusAcceptance:
    """Correction 15 - real Chromium acceptance of the upload control and
    the status page at 1280/768/375."""

    @pytest.mark.parametrize("width,height", [(1280, 800), (768, 1024), (375, 812)])
    def test_upload_and_view_status(self, live_server, monkeypatch, width, height):
        user, organisation = _new_org_and_user(f"wi_m009a_accept_{width}")
        monkeypatch.setattr(import_services, "get_scanner", lambda: _CleanScanner())

        upload_url = (
            f"{live_server.url}{reverse('questionnaire:import_upload', args=[organisation.id])}"
        )

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                page_errors = []
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))

                _login(page, live_server, user.username)
                page.goto(upload_url)
                page.wait_for_load_state("networkidle")

                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fh:
                    fh.write(corpus.valid_multi_sheet_workbook())
                    tmp_path = fh.name

                page.set_input_files("input[type=file]", tmp_path)
                # Scoped to the upload form itself - `application_shell.
                # html`'s own header also renders a `button[type=submit]`
                # (the "Log out" form), which a bare `button[type=
                # submit]` selector matches FIRST in DOM order (confirmed
                # directly: an earlier, unscoped version of this selector
                # submitted the header's logout form instead, landing on
                # /accounts/login/ after the resulting logout).
                page.locator("form[enctype='multipart/form-data'] button[type='submit']").click()
                page.wait_for_load_state("networkidle")

                assert "/imports/" in page.url
                assert page_errors == []

                scroll_width = page.evaluate("document.documentElement.scrollWidth")
                client_width = page.evaluate("document.documentElement.clientWidth")
                assert scroll_width <= client_width
            finally:
                browser.close()
