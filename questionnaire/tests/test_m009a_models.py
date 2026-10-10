"""
M009A model-layer tests (WO-M009A-SECURE-INGESTION-XLSX.md frozen model
contract, Final Correction J state-consistency matrix).
"""
import pytest

from questionnaire.models import (
    QuestionnaireImport,
    QuestionnaireImportImmutableFieldError,
    QuestionnaireImportQuestion,
    QuestionnaireImportStateConsistencyError,
    QuestionnaireQuestion,
)

pytestmark = pytest.mark.django_db


def _make_import(organisation, **overrides):
    defaults = dict(
        organisation=organisation,
        original_filename="q.xlsx",
        stored_filename="abc123.xlsx",
        detected_content_type="application/zip",
        file_format=QuestionnaireImport.FILE_FORMAT_XLSX,
        sha256_hash="0" * 64,
        size_bytes=1234,
        security_gate_status=QuestionnaireImport.SECURITY_GATE_PENDING,
        status=QuestionnaireImport.STATUS_UPLOADED,
    )
    defaults.update(overrides)
    return QuestionnaireImport.objects.create(**defaults)


class TestImmutableFields:
    def test_changing_sha256_after_creation_raises(self, org_a):
        import_record = _make_import(org_a)
        import_record.sha256_hash = "1" * 64
        with pytest.raises(QuestionnaireImportImmutableFieldError):
            import_record.save()

    def test_changing_organisation_after_creation_raises(self, org_a, org_b):
        import_record = _make_import(org_a)
        import_record.organisation = org_b
        with pytest.raises(QuestionnaireImportImmutableFieldError):
            import_record.save()

    def test_changing_original_filename_after_creation_raises(self, org_a):
        import_record = _make_import(org_a)
        import_record.original_filename = "evil.xlsx"
        with pytest.raises(QuestionnaireImportImmutableFieldError):
            import_record.save()

    def test_lifecycle_fields_remain_writable(self, org_a):
        """Artifact-identity fields are immutable; security_gate_status/
        status/security_gate_result/extraction_summary must remain
        writable through a legal state transition."""
        import_record = _make_import(org_a)
        import_record.security_gate_status = QuestionnaireImport.SECURITY_GATE_PASSED
        import_record.status = QuestionnaireImport.STATUS_EXTRACTING
        import_record.save()
        import_record.refresh_from_db()
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED
        assert import_record.status == QuestionnaireImport.STATUS_EXTRACTING


class TestStateConsistency:
    """Final Correction J - the exhaustive (security_gate_status, status)
    matrix. Every ALLOWED combination must save cleanly; every
    contradictory combination named in the Work Order must raise."""

    @pytest.mark.parametrize(
        "gate_status,status",
        [
            (QuestionnaireImport.SECURITY_GATE_PENDING, QuestionnaireImport.STATUS_UPLOADED),
            (
                QuestionnaireImport.SECURITY_GATE_PENDING,
                QuestionnaireImport.STATUS_SECURITY_GATE_PENDING,
            ),
            (
                QuestionnaireImport.SECURITY_GATE_REJECTED,
                QuestionnaireImport.STATUS_SECURITY_GATE_REJECTED,
            ),
            (
                QuestionnaireImport.SECURITY_GATE_FAILED,
                QuestionnaireImport.STATUS_SECURITY_GATE_FAILED,
            ),
            (QuestionnaireImport.SECURITY_GATE_PASSED, QuestionnaireImport.STATUS_EXTRACTING),
            (QuestionnaireImport.SECURITY_GATE_PASSED, QuestionnaireImport.STATUS_EXTRACTED),
            (
                QuestionnaireImport.SECURITY_GATE_PASSED,
                QuestionnaireImport.STATUS_EXTRACTION_FAILED,
            ),
        ],
    )
    def test_every_allowed_combination_saves_cleanly(self, org_a, gate_status, status):
        import_record = _make_import(
            org_a, security_gate_status=gate_status, status=status
        )
        import_record.refresh_from_db()
        assert import_record.security_gate_status == gate_status
        assert import_record.status == status

    @pytest.mark.parametrize(
        "gate_status,status",
        [
            # Named explicitly in WO-M009A Final Correction J.
            (QuestionnaireImport.SECURITY_GATE_REJECTED, QuestionnaireImport.STATUS_EXTRACTING),
            (QuestionnaireImport.SECURITY_GATE_PENDING, QuestionnaireImport.STATUS_EXTRACTED),
            (QuestionnaireImport.SECURITY_GATE_FAILED, QuestionnaireImport.STATUS_EXTRACTING),
            # A few more exhaustive contradictions.
            (QuestionnaireImport.SECURITY_GATE_PASSED, QuestionnaireImport.STATUS_UPLOADED),
            (
                QuestionnaireImport.SECURITY_GATE_REJECTED,
                QuestionnaireImport.STATUS_EXTRACTION_FAILED,
            ),
            (QuestionnaireImport.SECURITY_GATE_FAILED, QuestionnaireImport.STATUS_EXTRACTED),
        ],
    )
    def test_every_contradictory_combination_raises(self, org_a, gate_status, status):
        with pytest.raises(QuestionnaireImportStateConsistencyError):
            _make_import(org_a, security_gate_status=gate_status, status=status)


class TestQuestionnaireImportQuestionBridge:
    def test_question_set_null_on_linked_question_delete(self, org_a, user_a):
        import_record = _make_import(org_a)
        question = QuestionnaireQuestion.objects.create(
            organisation=org_a, question_text="Do you encrypt backups?", created_by=user_a
        )
        link = QuestionnaireImportQuestion.objects.create(
            import_record=import_record,
            question=question,
            raw_extracted_text="Do you encrypt backups?",
            source_location={
                "schema_version": 1,
                "format": "xlsx",
                "sheet_name": "Sheet1",
                "sheet_index": 0,
                "question_cell": "A1",
                "row": 1,
                "question_column": "A",
                "answer_cell": None,
            },
            extraction_order=1,
            extraction_status=QuestionnaireImportQuestion.EXTRACTION_STATUS_EXTRACTED,
            disposition=QuestionnaireImportQuestion.DISPOSITION_QUESTION,
        )
        question.delete()
        link.refresh_from_db()
        assert link.question_id is None
        # The source artifact/provenance remains intact.
        assert link.raw_extracted_text == "Do you encrypt backups?"

    def test_import_delete_cascades_to_questions(self, org_a):
        import_record = _make_import(org_a)
        QuestionnaireImportQuestion.objects.create(
            import_record=import_record,
            raw_extracted_text="x",
            source_location={
                "schema_version": 1,
                "format": "xlsx",
                "sheet_name": "s",
                "sheet_index": 0,
                "question_cell": "A1",
                "row": 1,
                "question_column": "A",
                "answer_cell": None,
            },
            extraction_order=1,
            disposition=QuestionnaireImportQuestion.DISPOSITION_HEADING,
        )
        import_record.delete()
        assert not QuestionnaireImportQuestion.objects.filter(import_record_id=import_record.id).exists()
