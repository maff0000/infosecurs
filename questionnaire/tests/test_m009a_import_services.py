"""
M009A governed lifecycle service tests (`questionnaire.import_services`) -
the full pipeline: ingest -> security gate -> scanner -> extraction, and
the retry operation. Uses a deterministic fake scanner (monkeypatched
`get_scanner`) for every test except the dedicated real-ClamAV tests in
test_m009a_scanner.py (WO-M009A: a fake scanner is explicitly allowed in
unit/evaluation tests).
"""
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from questionnaire import import_services
from questionnaire.eval import m009a_ingestion_corpus as corpus
from questionnaire.models import (
    QuestionnaireImport,
    QuestionnaireImportQuestion,
    QuestionnaireImportValidationError,
    QuestionnaireQuestion,
)
from questionnaire.scanner import STATE_CLEAN, STATE_ERROR, STATE_INFECTED, STATE_UNAVAILABLE, ScanResult

pytestmark = pytest.mark.django_db


class _FixedScanner:
    def __init__(self, state, signature=None):
        self.state = state
        self.signature = signature
        self.calls = 0

    def scan_file(self, file_path):
        self.calls += 1
        return ScanResult(
            state=self.state,
            provenance={"backend": "fake", "raw_response": self.state},
            infected_signature=self.signature,
        )


def _patch_scanner(monkeypatch, scanner):
    monkeypatch.setattr(import_services, "get_scanner", lambda: scanner)


def _upload(data: bytes, name="q.xlsx"):
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


class TestHappyPath:
    def test_clean_scan_leads_to_extracted_with_linked_questions(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="supplier-questionnaire.xlsx",
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED
        assert import_record.status == QuestionnaireImport.STATUS_EXTRACTED
        assert import_record.extraction_summary["question_count"] == 3

        links = QuestionnaireImportQuestion.objects.filter(import_record=import_record)
        assert links.count() >= 3
        question_links = links.filter(disposition=QuestionnaireImportQuestion.DISPOSITION_QUESTION)
        assert question_links.count() == 3
        for link in question_links:
            assert link.question is not None
            assert QuestionnaireQuestion.objects.filter(pk=link.question_id, organisation=org_a).exists()


class TestDeterministicRejection:
    def test_non_zip_bytes_rejected_without_running_container_gate(self, org_a, user_a, monkeypatch):
        scanner = _FixedScanner(STATE_CLEAN)
        _patch_scanner(monkeypatch, scanner)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.non_xlsx_file_bytes()),
            original_filename="renamed.xlsx",
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED
        assert import_record.status == QuestionnaireImport.STATUS_SECURITY_GATE_REJECTED
        assert scanner.calls == 0  # never reached the scanner at all

    def test_hostile_container_rejected_before_scanner(self, org_a, user_a, monkeypatch):
        scanner = _FixedScanner(STATE_CLEAN)
        _patch_scanner(monkeypatch, scanner)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.macro_enabled_workbook()),
            original_filename="macro.xlsx",
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED
        assert scanner.calls == 0

    def test_malware_detected_is_rejected_not_failed(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_INFECTED, signature="Test.Signature"))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED
        assert import_record.status == QuestionnaireImport.STATUS_SECURITY_GATE_REJECTED
        assert import_record.security_gate_result["signature"] == "Test.Signature"


class TestScannerFailureDistinctFromRejection:
    """WO-M009A Final Correction A - the central contract this whole
    pipeline exists to prove."""

    @pytest.mark.parametrize("state", [STATE_UNAVAILABLE, STATE_ERROR])
    def test_scanner_unavailable_or_error_lands_in_security_gate_failed_not_rejected(
        self, org_a, user_a, monkeypatch, questionnaire_storage_root, state
    ):
        _patch_scanner(monkeypatch, _FixedScanner(state))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_FAILED
        assert import_record.status == QuestionnaireImport.STATUS_SECURITY_GATE_FAILED
        # Bytes retained privately for retry - never deleted.
        path = os.path.join(
            str(questionnaire_storage_root), str(org_a.id), import_record.stored_filename
        )
        assert os.path.isfile(path)

    def test_retry_after_scanner_recovers_reaches_extracted(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_UNAVAILABLE))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_FAILED

        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_services.retry_security_gate(import_record, actor=user_a)
        import_record.refresh_from_db()
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED
        assert import_record.status == QuestionnaireImport.STATUS_EXTRACTED

    def test_retry_on_a_non_failed_import_raises(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        with pytest.raises(import_services.SecurityGateTransitionError):
            import_services.retry_security_gate(import_record, actor=user_a)


class TestImmutableOriginalRetentionThreeWay:
    """WO-M009A Final Correction H - passed/rejected/security_gate_failed
    retention proof."""

    def test_passed_import_bytes_remain_byte_identical(
        self, org_a, user_a, monkeypatch, questionnaire_storage_root
    ):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        data = corpus.valid_multi_sheet_workbook()
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a, actor=user_a, uploaded_file=_upload(data), original_filename="q.xlsx"
        )
        path = os.path.join(
            str(questionnaire_storage_root), str(org_a.id), import_record.stored_filename
        )
        with open(path, "rb") as fh:
            assert fh.read() == data

    def test_rejected_import_bytes_are_removed(
        self, org_a, user_a, monkeypatch, questionnaire_storage_root
    ):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.macro_enabled_workbook()),
            original_filename="macro.xlsx",
        )
        path = os.path.join(
            str(questionnaire_storage_root), str(org_a.id), import_record.stored_filename
        )
        assert not os.path.isfile(path)
        # Audit metadata permanent regardless.
        assert import_record.sha256_hash

    def test_failed_import_bytes_retained_until_resolved(
        self, org_a, user_a, monkeypatch, questionnaire_storage_root
    ):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_ERROR))
        data = corpus.valid_multi_sheet_workbook()
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a, actor=user_a, uploaded_file=_upload(data), original_filename="q.xlsx"
        )
        path = os.path.join(
            str(questionnaire_storage_root), str(org_a.id), import_record.stored_filename
        )
        with open(path, "rb") as fh:
            assert fh.read() == data


class TestZeroAiInvocations:
    def test_ingest_never_imports_ai_orchestration(self, org_a, user_a, monkeypatch):
        """WO-M009A: zero AI invocations anywhere in M009A's own
        application paths. Proven by asserting no AIInvocationRecord is
        ever created by this pipeline."""
        from ai_platform.models import AIInvocationRecord

        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        before = AIInvocationRecord.objects.count()
        import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook()),
            original_filename="q.xlsx",
        )
        assert AIInvocationRecord.objects.count() == before


class TestSupersedesContract:
    """Central Architecture Blocker 1 correction to PR #102 (2026-10-11):
    `supersedes` must be real and tenant-safe. Proves the full domain/
    service contract end to end, at the SERVICE layer only - no UI
    change, per Central Architecture's explicit ruling that M009A adds no
    re-upload/supersession UI (the upload surface stays exactly as
    minimal as it already is). This closes WO-M009A's own required
    "legitimate re-upload/`supersedes` case" evaluation corpus item."""

    def test_second_import_supersedes_first_leaving_first_completely_unchanged(
        self, org_a, user_a, monkeypatch, questionnaire_storage_root
    ):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))

        # 1. Ingest a legitimate original workbook.
        first_data = corpus.valid_multi_sheet_workbook()
        first = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(first_data, name="original.xlsx"),
            original_filename="original.xlsx",
        )
        assert first.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED
        assert first.status == QuestionnaireImport.STATUS_EXTRACTED

        # 2. Record its row identity, SHA-256, stored bytes, and
        # extracted-question state BEFORE the second ingest touches
        # anything.
        first_id = first.id
        first_sha256 = first.sha256_hash
        first_path = os.path.join(
            str(questionnaire_storage_root), str(org_a.id), first.stored_filename
        )
        with open(first_path, "rb") as fh:
            first_bytes_before = fh.read()
        first_question_ids_before = set(
            QuestionnaireImportQuestion.objects.filter(import_record=first).values_list(
                "id", flat=True
            )
        )
        first_question_texts_before = list(
            QuestionnaireImportQuestion.objects.filter(import_record=first)
            .order_by("extraction_order")
            .values_list("raw_extracted_text", flat=True)
        )
        assert first_question_ids_before  # sanity: something was actually extracted

        # 3. Ingest a second, distinct legitimate workbook with
        # supersedes=<first import>.
        second_data = corpus.workbook_with_duplicate_question_text()
        second = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(second_data, name="reupload.xlsx"),
            original_filename="reupload.xlsx",
            supersedes=first,
        )
        assert second.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED

        # 4. Two distinct QuestionnaireImport rows now exist.
        assert second.id != first_id
        assert QuestionnaireImport.objects.filter(organisation=org_a).count() == 2

        # 5. second.supersedes_id == first.id
        assert second.supersedes_id == first_id

        # 6. The first import's row, stored bytes (re-read from disk, not
        # just the DB hash field), and extracted questions are completely
        # unchanged after the second ingest.
        first.refresh_from_db()
        assert first.sha256_hash == first_sha256
        assert first.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED
        assert first.status == QuestionnaireImport.STATUS_EXTRACTED
        assert first.supersedes_id is None

        with open(first_path, "rb") as fh:
            first_bytes_after = fh.read()
        assert first_bytes_after == first_bytes_before == first_data

        first_question_ids_after = set(
            QuestionnaireImportQuestion.objects.filter(import_record=first).values_list(
                "id", flat=True
            )
        )
        first_question_texts_after = list(
            QuestionnaireImportQuestion.objects.filter(import_record=first)
            .order_by("extraction_order")
            .values_list("raw_extracted_text", flat=True)
        )
        assert first_question_ids_after == first_question_ids_before
        assert first_question_texts_after == first_question_texts_before

    def test_supersedes_pointing_at_a_different_organisation_fails_closed(
        self, org_a, org_b, user_a, monkeypatch, questionnaire_storage_root
    ):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))

        foreign = import_services.ingest_questionnaire_import(
            organisation=org_b,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_multi_sheet_workbook(), name="org_b.xlsx"),
            original_filename="org_b.xlsx",
        )
        assert foreign.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED

        before_count = QuestionnaireImport.objects.filter(organisation=org_a).count()

        with pytest.raises(QuestionnaireImportValidationError):
            import_services.ingest_questionnaire_import(
                organisation=org_a,
                actor=user_a,
                uploaded_file=_upload(corpus.valid_multi_sheet_workbook(), name="attempt.xlsx"),
                original_filename="attempt.xlsx",
                supersedes=foreign,
            )

        # The WHOLE ingest attempt failed closed for org_a - no new row
        # was created at all (never a degraded success with
        # supersedes=NULL silently landing instead), and no file was
        # stored/orphaned either.
        assert QuestionnaireImport.objects.filter(organisation=org_a).count() == before_count
        org_a_dir = os.path.join(str(questionnaire_storage_root), str(org_a.id))
        if os.path.isdir(org_a_dir):
            assert os.listdir(org_a_dir) == []

        # No cross-tenant relationship of any kind was created on the
        # foreign import either.
        foreign.refresh_from_db()
        assert not QuestionnaireImport.objects.filter(supersedes=foreign).exists()

    def test_supersedes_an_unpersisted_import_fails_closed(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        unsaved = QuestionnaireImport(organisation=org_a)  # never .save()d - pk is None

        with pytest.raises(QuestionnaireImportValidationError):
            import_services.ingest_questionnaire_import(
                organisation=org_a,
                actor=user_a,
                uploaded_file=_upload(corpus.valid_multi_sheet_workbook(), name="attempt.xlsx"),
                original_filename="attempt.xlsx",
                supersedes=unsaved,
            )
