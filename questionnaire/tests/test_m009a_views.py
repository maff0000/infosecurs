"""
M009A HTTP-level tests: upload/detail/retry views, CSRF, tenant isolation
(WO-M009A-SECURE-INGESTION-XLSX.md Correction 15).
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from questionnaire import import_services
from questionnaire.eval import m009a_ingestion_corpus as corpus
from questionnaire.models import QuestionnaireImport
from questionnaire.scanner import STATE_CLEAN, ScanResult

pytestmark = pytest.mark.django_db


def _patch_clean_scanner(monkeypatch):
    class _Scanner:
        def scan_file(self, file_path):
            return ScanResult(state=STATE_CLEAN, provenance={"backend": "fake"})

    monkeypatch.setattr(import_services, "get_scanner", lambda: _Scanner())


def _upload(data: bytes, name="q.xlsx"):
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


class TestUploadView:
    def test_get_renders_form(self, client_a, org_a):
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 200

    def test_post_valid_file_creates_import_and_redirects(self, client_a, org_a, monkeypatch):
        _patch_clean_scanner(monkeypatch)
        response = client_a.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"file": _upload(corpus.valid_multi_sheet_workbook())},
        )
        assert response.status_code == 302
        assert QuestionnaireImport.objects.filter(organisation=org_a).count() == 1

    def test_requires_csrf(self, org_a, user_a, member_a):
        enforcing_client = Client(enforce_csrf_checks=True)
        enforcing_client.force_login(user_a)
        response = enforcing_client.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"file": _upload(corpus.valid_multi_sheet_workbook())},
        )
        assert response.status_code == 403

    def test_rejected_file_shows_form_error_not_500(self, client_a, org_a, monkeypatch):
        _patch_clean_scanner(monkeypatch)
        response = client_a.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"file": _upload(corpus.non_xlsx_file_bytes())},
        )
        # Rejection is recorded as an import row (deterministic rejection
        # audit trail), and the view still redirects cleanly to its detail
        # page - never a 500.
        assert response.status_code == 302
        import_record = QuestionnaireImport.objects.get(organisation=org_a)
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED


class TestDetailViewTenantIsolation:
    def test_member_can_view_own_import(self, client_a, org_a, user_a, monkeypatch):
        _patch_clean_scanner(monkeypatch)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        response = client_a.get(
            reverse("questionnaire:import_detail", args=[org_a.id, import_record.id])
        )
        assert response.status_code == 200

    def test_foreign_tenant_gets_404_not_403(
        self, client_b, org_a, org_b, user_a, user_b, member_b, monkeypatch
    ):
        """PID §23 tenant isolation, carried over unchanged - a non-member
        gets an ordinary 404, never a 403, never confirms existence."""
        _patch_clean_scanner(monkeypatch)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        response = client_b.get(
            reverse("questionnaire:import_detail", args=[org_a.id, import_record.id])
        )
        assert response.status_code == 404

    def test_foreign_organisation_id_with_real_import_id_also_404s(
        self, client_b, org_a, org_b, user_a, member_b, monkeypatch
    ):
        """client_b IS a genuine member of org_b (the URL's own
        organisation_id), but the import_id in the URL belongs to org_a -
        proves the import is scoped by BOTH the URL's organisation_id AND
        its own FK, not merely by a guessable import UUID."""
        _patch_clean_scanner(monkeypatch)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        response = client_b.get(
            reverse("questionnaire:import_detail", args=[org_b.id, import_record.id])
        )
        assert response.status_code == 404


class TestRetryView:
    def test_get_not_allowed(self, client_a, org_a, user_a, monkeypatch):
        _patch_clean_scanner(monkeypatch)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        response = client_a.get(
            reverse("questionnaire:import_retry", args=[org_a.id, import_record.id])
        )
        assert response.status_code == 405

    def test_cross_tenant_retry_404s(self, client_b, org_a, org_b, user_a, member_b, monkeypatch):
        _patch_clean_scanner(monkeypatch)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        response = client_b.post(
            reverse("questionnaire:import_retry", args=[org_a.id, import_record.id])
        )
        assert response.status_code == 404
