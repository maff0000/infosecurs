"""
M009A Customer Zero reset reconciliation tests
(WO-M009A-SECURE-INGESTION-XLSX.md "Customer Zero reset reconciliation").

Mirrors `organisations/tests/test_reset_service.py`'s own established
real-file-on-disk discipline (`_create_evidence_item`'s docstring) -
`_create_questionnaire_import` below creates a REAL `QuestionnaireImport`
via the real `questionnaire.import_services.ingest_questionnaire_import`
pipeline, with real bytes on disk, not a hand-rolled DB row.
"""
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from organisations.reset_service import reset_customer_zero_organisation
from questionnaire import import_services
from questionnaire.eval import m009a_ingestion_corpus as corpus
from questionnaire.models import QuestionnaireImport, QuestionnaireImportQuestion
from questionnaire.scanner import STATE_CLEAN, ScanResult

pytestmark = pytest.mark.django_db


def _patch_clean_scanner(monkeypatch):
    class _Scanner:
        def scan_file(self, file_path):
            return ScanResult(state=STATE_CLEAN, provenance={"backend": "fake"})

    monkeypatch.setattr(import_services, "get_scanner", lambda: _Scanner())


def _create_questionnaire_import(organisation, user, monkeypatch):
    _patch_clean_scanner(monkeypatch)
    return import_services.ingest_questionnaire_import(
        organisation=organisation,
        actor=user,
        uploaded_file=SimpleUploadedFile(
            "q.xlsx", corpus.valid_multi_sheet_workbook(), content_type="application/octet-stream"
        ),
        original_filename="q.xlsx",
    )


class TestResetRemovesQuestionnaireImportsAndFiles:
    def test_reset_removes_db_rows_and_storage_directory(
        self, customer_zero_bootstrap, questionnaire_storage_root, monkeypatch
    ):
        user, organisation = customer_zero_bootstrap
        import_record = _create_questionnaire_import(organisation, user, monkeypatch)
        file_path = os.path.join(
            str(questionnaire_storage_root), str(organisation.id), import_record.stored_filename
        )
        assert os.path.isfile(file_path)
        assert QuestionnaireImportQuestion.objects.filter(import_record=import_record).exists()

        reset_customer_zero_organisation(organisation, performed_by=user)

        assert not QuestionnaireImport.objects.filter(organisation=organisation).exists()
        assert not QuestionnaireImportQuestion.objects.filter(import_record_id=import_record.id).exists()
        assert not os.path.exists(file_path)
        assert not os.path.isdir(
            os.path.join(str(questionnaire_storage_root), str(organisation.id))
        )

    def test_reset_result_reports_questionnaire_directory_removed(
        self, customer_zero_bootstrap, questionnaire_storage_root, monkeypatch
    ):
        user, organisation = customer_zero_bootstrap
        _create_questionnaire_import(organisation, user, monkeypatch)
        result = reset_customer_zero_organisation(organisation, performed_by=user)
        assert result.questionnaire_directory_removed is True

    def test_reset_is_a_safe_noop_with_no_questionnaire_imports(self, customer_zero_bootstrap):
        user, organisation = customer_zero_bootstrap
        result = reset_customer_zero_organisation(organisation, performed_by=user)
        assert result.questionnaire_directory_removed is False


class TestResetLeavesOtherTenantUntouched:
    def test_other_organisations_questionnaire_rows_and_files_unchanged(
        self,
        customer_zero_bootstrap,
        org_a,
        user_a,
        member_a,
        questionnaire_storage_root,
        monkeypatch,
    ):
        cz_user, cz_org = customer_zero_bootstrap
        _create_questionnaire_import(cz_org, cz_user, monkeypatch)

        other_import = _create_questionnaire_import(org_a, user_a, monkeypatch)
        other_path = os.path.join(
            str(questionnaire_storage_root), str(org_a.id), other_import.stored_filename
        )
        with open(other_path, "rb") as fh:
            other_bytes_before = fh.read()

        reset_customer_zero_organisation(cz_org, performed_by=cz_user)

        assert QuestionnaireImport.objects.filter(pk=other_import.pk).exists()
        assert os.path.isfile(other_path)
        with open(other_path, "rb") as fh:
            assert fh.read() == other_bytes_before
