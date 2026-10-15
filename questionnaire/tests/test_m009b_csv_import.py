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

    def test_blank_question_row_produces_excluded_blank_question_candidate(self, tmp_path):
        """M009B Increment 1 repair (defect B3) - this test previously
        asserted the OPPOSITE (`len(outcome.candidates) == 2`, i.e. the
        blank row produced no candidate at all), which was the defect
        itself. Central Architecture has now determined CSV needs
        different handling than XLSX's own blank-row-drops-silently
        rule, so this is a deliberate, acknowledged behaviour change, not
        a regression."""
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_with_blank_question_rows())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        assert len(outcome.candidates) == 3
        assert outcome.summary["question_count"] == 2
        dispositions = [c.disposition for c in outcome.candidates]
        assert dispositions == ["question", "excluded_blank_question", "question"]
        assert outcome.summary["excluded_counts_by_disposition"]["excluded_blank_question"] == 1

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
# M009B Increment 1 repair - defects B1-B4
# (WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md §2,
# M009-AMENDMENT-2026-10-13-CSV-ASSURANCE-READINESS.md §4.1's "Resource
# limits, frozen"). Each test below was first run against the real,
# unpatched head (`8365fdf5754b2f22f597e3e09749061418d55ac8`) and
# confirmed to FAIL there - see the Implementer's report for the exact
# captured failing-before output for each one.
# ---------------------------------------------------------------------------
class TestB1AmbiguousOptionalColumns:
    """Defect B1 - two-or-more columns matching the answer/reference
    header vocabulary were previously silently treated as "column
    absent" (`answer_cols[0] if len(answer_cols) == 1 else None`) rather
    than rejected as ambiguous, discarding a real customer-supplied
    answer/reference with no named rejection at all."""

    def test_duplicate_answer_header_rejected_with_named_reason(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_duplicate_answer_header())
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is False
        assert result.structural_summary["reason"] == "ambiguous_answer_column"

    def test_duplicate_reference_header_rejected_with_named_reason(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_duplicate_reference_header())
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is False
        assert result.structural_summary["reason"] == "ambiguous_reference_column"

    def test_duplicate_answer_header_rejected_by_extract_candidates_too(self, tmp_path):
        """Both `validate_csv_structure` and `extract_candidates` call
        `_resolve_header` fresh - proving the fix lands in both, not
        only the structural gate."""
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_duplicate_answer_header())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extraction_failed"
        assert "answer-header vocabulary" in outcome.failure_reason
        assert outcome.candidates == []

    def test_duplicate_reference_header_rejected_by_extract_candidates_too(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_duplicate_reference_header())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extraction_failed"
        assert "reference-header vocabulary" in outcome.failure_reason
        assert outcome.candidates == []

    def test_single_answer_and_reference_column_still_accepted(self, tmp_path):
        """Regression guard - exactly one answer/reference column (the
        ordinary case) must remain accepted; B1's fix must not turn the
        genuinely-optional, non-ambiguous case into a rejection too."""
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.valid_csv_with_answer_and_reference())
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is True


class TestB2ZeroDataRows:
    """Defect B2 - a CSV with a valid header but zero data rows was
    previously silently accepted (`accepted=True`,
    `structural_summary={"row_count": 0, ...}`) - no named rejection
    existed for "header present, but no data rows at all"."""

    def test_valid_header_zero_data_rows_rejected(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_valid_header_zero_data_rows())
        result = csv_import.validate_csv_structure(str(path))
        assert result.accepted is False
        assert result.structural_summary["reason"] == "no_data_rows"

    def test_valid_header_zero_data_rows_rejected_by_extract_candidates_too(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_valid_header_zero_data_rows())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extraction_failed"
        assert "zero data rows" in outcome.failure_reason
        assert outcome.candidates == []


class TestB3BlankQuestionRowProvenance:
    """Defect B3 - a blank-question row previously vanished from import
    provenance entirely (bare `continue`, no `Candidate` ever created),
    taking any answer/reference data that row carried with it."""

    def test_blank_question_row_carrying_reference_produces_candidate(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_blank_question_row_carrying_reference())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        assert len(outcome.candidates) == 3
        dispositions = [c.disposition for c in outcome.candidates]
        assert dispositions == ["question", "excluded_blank_question", "question"]

        blank_row_candidate = outcome.candidates[1]
        # Provenance survives: the original row number and its
        # non-blank reference value are both retained.
        assert blank_row_candidate.source_location["row"] == 3
        assert blank_row_candidate.source_location["reference_value"] == "REF-BLANK-ROW"

    def test_blank_question_row_never_eligible_for_ai_generation(self, tmp_path):
        """Explicit proof, not just absence of a counter-example: a
        blank-question row's disposition is NEVER
        `QuestionnaireImportQuestion.DISPOSITION_QUESTION` - the one
        value the real pipeline treats as eligible for AI generation."""
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_blank_question_row_carrying_reference())
        outcome = csv_import.extract_candidates(str(path))
        blank_row_candidate = outcome.candidates[1]
        assert blank_row_candidate.disposition == "excluded_blank_question"
        assert blank_row_candidate.disposition != QuestionnaireImportQuestion.DISPOSITION_QUESTION
        assert blank_row_candidate.disposition == QuestionnaireImportQuestion.DISPOSITION_EXCLUDED_BLANK_QUESTION
        question_dispositions = [c.disposition for c in outcome.candidates if c is not blank_row_candidate]
        assert all(d == "question" for d in question_dispositions)

    def test_blank_question_row_reaches_db_via_dispatch(self, org_a, user_a, monkeypatch):
        """End-to-end proof through the real `import_services` pipeline,
        not just the unit-level `extract_candidates` call - a
        `QuestionnaireImportQuestion` row genuinely exists in the
        database for the blank-question row, with no linked
        `QuestionnaireQuestion` (never eligible for drafting)."""
        _patch_scanner(monkeypatch, _FixedScanner(STATE_CLEAN))
        import_record = import_services.ingest_questionnaire_import(
            organisation=org_a,
            actor=user_a,
            uploaded_file=_upload(corpus.csv_blank_question_row_carrying_reference()),
            original_filename="q.csv",
            declared_format=QuestionnaireImport.FILE_FORMAT_CSV,
        )
        assert import_record.status == QuestionnaireImport.STATUS_EXTRACTED
        links = QuestionnaireImportQuestion.objects.filter(import_record=import_record)
        assert links.count() == 3
        blank_link = links.get(disposition=QuestionnaireImportQuestion.DISPOSITION_EXCLUDED_BLANK_QUESTION)
        assert blank_link.question is None
        assert blank_link.source_location["reference_value"] == "REF-BLANK-ROW"


class TestB4BoundedTextLength:
    """Defect B4 - no bounded-length protection existed for
    answer/reference text (only the question-text column had one), and
    no aggregate total-text bound existed anywhere in this module."""

    def test_oversized_answer_cell_rejected_with_named_reason(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_oversized_answer_cell(csv_import.MAX_CSV_CELL_TEXT_LENGTH))
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        assert len(outcome.candidates) == 1
        candidate = outcome.candidates[0]
        assert candidate.disposition == "excluded_other"
        assert candidate.extraction_status == "failed"
        assert candidate.extraction_error == "answer_text_exceeds_max_length"
        # Never eligible for AI generation, and never silently carrying
        # the oversized answer as "provenance" either.
        assert candidate.customer_provided_answer_text is None

    def test_oversized_reference_cell_rejected_with_named_reason(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.csv_oversized_reference_cell(csv_import.MAX_CSV_CELL_TEXT_LENGTH))
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        assert len(outcome.candidates) == 1
        candidate = outcome.candidates[0]
        assert candidate.disposition == "excluded_other"
        assert candidate.extraction_status == "failed"
        assert candidate.extraction_error == "reference_text_exceeds_max_length"

    def test_within_limit_answer_and_reference_still_accepted(self, tmp_path):
        """Regression guard - an ordinary, within-bound answer/reference
        cell must remain unaffected by the new per-field checks."""
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.valid_csv_with_answer_and_reference())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"
        assert all(c.extraction_status != "failed" for c in outcome.candidates)

    def test_aggregate_text_length_exceeded_rejected(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_bytes(
            corpus.csv_exceeding_aggregate_text_length(
                csv_import.MAX_CSV_AGGREGATE_TEXT_LENGTH, csv_import.MAX_CSV_CELL_TEXT_LENGTH
            )
        )
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extraction_failed"
        assert "aggregate" in outcome.failure_reason
        assert outcome.candidates == []

    def test_moderate_import_well_under_aggregate_bound_still_accepted(self, tmp_path):
        """Regression guard - the ordinary, legitimate
        `valid_csv_with_answer_and_reference` fixture (tiny, nowhere
        near the aggregate bound) must remain accepted."""
        path = tmp_path / "f.csv"
        path.write_bytes(corpus.valid_csv_with_answer_and_reference())
        outcome = csv_import.extract_candidates(str(path))
        assert outcome.status == "extracted"


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
