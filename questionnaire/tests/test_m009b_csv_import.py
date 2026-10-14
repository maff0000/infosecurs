"""
M009B Increment 1 - CSV V1 ingestion tests
(WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md §2.7).

Mirrors `test_m009a_import_services.py`'s own structure/conventions
exactly - a deterministic fake scanner (monkeypatched `get_scanner`),
`org_a`/`user_a` fixtures, `pytest.mark.django_db`.
"""
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from questionnaire import csv_import, import_services
from questionnaire.eval import m009a_ingestion_corpus as xlsx_corpus
from questionnaire.eval import m009b_csv_ingestion_corpus as corpus
from questionnaire.models import QuestionnaireImport, QuestionnaireImportQuestion
from questionnaire.scanner import STATE_CLEAN, STATE_UNAVAILABLE, ScanResult

pytestmark = pytest.mark.django_db


class _FixedScanner:
    def __init__(self, state):
        self.state = state
        self.calls = 0

    def scan_file(self, file_path):
        self.calls += 1
        return ScanResult(state=self.state, provenance={"backend": "fake", "raw_response": self.state})


def _patch_scanner(monkeypatch, scanner):
    monkeypatch.setattr(import_services, "get_scanner", lambda: scanner)


def _upload(data: bytes, name="q.csv"):
    return SimpleUploadedFile(name, data, content_type="text/csv")


# ---------------------------------------------------------------------------
# Unit tests - questionnaire.csv_import directly.
# ---------------------------------------------------------------------------
class TestValidateCsvStructure:
    @pytest.mark.parametrize(
        "builder,expected_reason",
        [
            (corpus.csv_missing_question_header, "no_question_column"),
            (corpus.csv_duplicate_question_header, "ambiguous_question_column"),
            (corpus.csv_case_ambiguous_question_header, "ambiguous_question_column"),
            (corpus.csv_invalid_encoding, "invalid_encoding"),
        ],
    )
    def test_rejects_with_specific_named_reason(self, tmp_path, builder, expected_reason):
        path = tmp_path / "f.csv"
        path.write_bytes(builder())
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is False
        assert result.structural_summary["reason"] == expected_reason

    @pytest.mark.parametrize(
        "builder",
        [
            corpus.valid_csv_with_answer_and_reference,
            corpus.valid_csv_without_answer_or_reference,
            corpus.csv_with_blank_question_rows,
            corpus.csv_with_duplicate_question_text,
            corpus.csv_bom_prefixed_utf8,
            corpus.csv_with_embedded_comma_newline_quote,
        ],
    )
    def test_accepts_legitimate_fixtures(self, tmp_path, builder):
        path = tmp_path / "f.csv"
        path.write_bytes(builder())
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is True

    def test_exceeds_max_rows_rejected(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_exceeding_row_limit(csv_import.MAX_CSV_DATA_ROWS))
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is False
        assert result.structural_summary["reason"] == "exceeds_max_rows"

    def test_never_calls_ooxml_container_gate(self, tmp_path, monkeypatch):
        """Binding global STOP condition: CSV structural validation must
        never call `security_gate.run_container_gate` (OOXML-only)."""
        from questionnaire import security_gate

        def _boom(file_path):
            raise AssertionError("run_container_gate must never be called for CSV")

        monkeypatch.setattr(security_gate, "run_container_gate", _boom)
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.valid_csv_with_answer_and_reference())
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is True


class TestExtractCandidates:
    def test_answer_column_populates_customer_provided_answer_text_verbatim(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.valid_csv_with_answer_and_reference())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        by_text = {c.raw_extracted_text: c for c in outcome.candidates}
        answered = by_text["Do you encrypt data at rest?"]
        assert answered.customer_provided_answer_text == "Yes - AES-256 everywhere."
        unanswered = by_text["Do you have an incident response plan?"]
        assert unanswered.customer_provided_answer_text is None

    def test_blank_question_row_produces_no_candidate(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_with_blank_question_rows())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        assert len(outcome.candidates) == 2
        assert outcome.summary["question_count"] == 2

    def test_duplicate_question_text_excluded(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_with_duplicate_question_text())
        outcome = csv_import.extract_candidates(str(path))
        dispositions = [c.disposition for c in outcome.candidates]
        assert dispositions == ["question", "excluded_duplicate"]

    def test_embedded_comma_newline_quote_extracted_correctly(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_with_embedded_comma_newline_quote())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        assert len(outcome.candidates) == 1
        text = outcome.candidates[0].raw_extracted_text
        assert "secret" in text
        assert "," in text
        assert "\n" in text


# ---------------------------------------------------------------------------
# Service-layer dispatch tests - questionnaire.import_services, declared_
# format routing (WO §2.2a).
# ---------------------------------------------------------------------------
class TestCsvDispatch:
    def test_valid_csv_reaches_extracted_with_linked_questions(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_csv_with_answer_and_reference()),
            original_filename="supplier-questionnaire.csv",
            declared_format=QuestionnaireImport.FILE_FORMAT_CSV,
        )
        assert import_record.file_format == QuestionnaireImport.FILE_FORMAT_CSV
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED
        assert import_record.status == QuestionnaireImport.STATUS_EXTRACTED
        assert import_record.extraction_summary["question_count"] == 2

        links = QuestionnaireImportQuestion.objects.filter(import_record=import_record)
        question_links = {
            link.raw_extracted_text: link
            for link in links.filter(disposition=QuestionnaireImportQuestion.DISPOSITION_QUESTION)
        }
        assert (
            question_links["Do you encrypt data at rest?"].customer_provided_answer_text
            == "Yes - AES-256 everywhere."
        )
        assert question_links["Do you have an incident response plan?"].customer_provided_answer_text is None
        for link in question_links.values():
            assert link.question is not None

    def test_declared_csv_but_zip_shaped_rejected_with_named_reason(self, org_a, user_a, monkeypatch):
        scanner = _FixedScanner(STATE_CLEAN)
        _patch_scanner(monkeypatch, scanner)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.declared_csv_but_actually_zip_shaped()),
            original_filename="hostile.csv",
            declared_format=QuestionnaireImport.FILE_FORMAT_CSV,
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED
        assert import_record.security_gate_result["reason"] == "declared_csv_but_zip_shaped"
        assert scanner.calls == 0  # never reached the scanner at all - never even the CSV gate

    def test_csv_extension_but_hostile_zip_bytes_rejected(self, org_a, user_a, monkeypatch):
        scanner = _FixedScanner(STATE_CLEAN)
        _patch_scanner(monkeypatch, scanner)
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.csv_extension_but_hostile_zip_bytes(), name="renamed.csv"),
            original_filename="renamed.csv",
            declared_format=QuestionnaireImport.FILE_FORMAT_CSV,
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED
        assert import_record.security_gate_result["reason"] == "declared_csv_but_zip_shaped"

    def test_csv_missing_question_header_gate_rejected(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.csv_missing_question_header()),
            original_filename="q.csv",
            declared_format=QuestionnaireImport.FILE_FORMAT_CSV,
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED
        assert import_record.security_gate_result["structural_summary"]["reason"] == "no_question_column"

    def test_scanner_retry_regression_csv(self, org_a, user_a, monkeypatch, questionnaire_storage_root):
        """C1's explicit requirement: the existing, unmodified
        `retry_security_gate` genuinely works for CSV too, not only
        XLSX."""
        _patch_scanner(monkeypatch, _FixedScanner(STATE_UNAVAILABLE))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_csv_with_answer_and_reference()),
            original_filename="q.csv",
            declared_format=QuestionnaireImport.FILE_FORMAT_CSV,
        )
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_FAILED
        path = os.path.join(
            str(questionnaire_storage_root), str(org_a.id), import_record.stored_filename
        )
        assert os.path.isfile(path)  # bytes retained privately for retry

        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        retried = import_services.retry_security_gate(import_record, actor=user_a)
        assert retried.security_gate_status == QuestionnaireImport.SECURITY_GATE_PASSED
        assert retried.status == QuestionnaireImport.STATUS_EXTRACTED

    def test_customer_provided_answer_text_excluded_from_bulk_eligibility(
        self, org_a, user_a, monkeypatch
    ):
        """WO §2.4/§2.9/§8 binding invariant: no bulk-orchestration code
        exists yet in this increment, but the exclusion must already be
        structurally provable against the real field/query shape. This
        directly proves (a) the field is byte-identical to the original
        CSV cell, and (b) the obvious `customer_provided_answer_text__
        isnull=True` eligibility filter correctly excludes the pre-
        answered row while still including the unanswered one."""
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.valid_csv_with_answer_and_reference()),
            original_filename="q.csv",
            declared_format=QuestionnaireImport.FILE_FORMAT_CSV,
        )
        all_questions = QuestionnaireImportQuestion.objects.filter(
            import_record=import_record,
            disposition=QuestionnaireImportQuestion.DISPOSITION_QUESTION,
        )
        assert all_questions.count() == 2

        eligible = all_questions.filter(customer_provided_answer_text__isnull=True)
        assert eligible.count() == 1
        assert eligible.get().raw_extracted_text == "Do you have an incident response plan?"

        pre_answered = all_questions.exclude(customer_provided_answer_text__isnull=True).get()
        assert pre_answered.raw_extracted_text == "Do you encrypt data at rest?"
        assert pre_answered.customer_provided_answer_text == "Yes - AES-256 everywhere."

    def test_xlsx_row_customer_provided_answer_text_always_null(self, org_a, user_a, monkeypatch):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(xlsx_corpus.valid_multi_sheet_workbook(), name="q.xlsx"),
            original_filename="q.xlsx",
            declared_format=QuestionnaireImport.FILE_FORMAT_XLSX,
        )
        assert import_record.file_format == QuestionnaireImport.FILE_FORMAT_XLSX
        links = QuestionnaireImportQuestion.objects.filter(import_record=import_record)
        assert links.exists()
        for link in links:
            assert link.customer_provided_answer_text is None


# ---------------------------------------------------------------------------
# Hostile-file regression (C1) - every existing M009A XLSX hostile fixture
# re-run against the dispatch-modified functions, confirming byte-identical
# rejection behaviour.
# ---------------------------------------------------------------------------
class TestXlsxPathUnchangedByDispatch:
    @pytest.mark.parametrize(
        "builder",
        [xlsx_corpus.non_xlsx_file_bytes, xlsx_corpus.macro_enabled_workbook],
    )
    def test_hostile_xlsx_fixture_rejected_identically_with_default_declared_format(
        self, org_a, user_a, monkeypatch, builder
    ):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        # No declared_format passed at all - proves the default argument
        # preserves every pre-existing caller's exact behaviour.
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(builder(), name="q.xlsx"),
            original_filename="q.xlsx",
        )
        assert import_record.file_format == QuestionnaireImport.FILE_FORMAT_XLSX
        assert import_record.security_gate_status == QuestionnaireImport.SECURITY_GATE_REJECTED

    def test_valid_xlsx_with_explicit_declared_format_reaches_extracted(
        self, org_a, user_a, monkeypatch
    ):
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(xlsx_corpus.valid_multi_sheet_workbook(), name="q.xlsx"),
            original_filename="q.xlsx",
            declared_format=QuestionnaireImport.FILE_FORMAT_XLSX,
        )
        assert import_record.status == QuestionnaireImport.STATUS_EXTRACTED
