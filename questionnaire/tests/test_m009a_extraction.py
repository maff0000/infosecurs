"""
M009A deterministic XLSX extraction tests (`questionnaire.xlsx_extraction`)
(WO-M009A-SECURE-INGESTION-XLSX.md Corrections 5/9/11/12/13).
"""
import tempfile

from questionnaire import xlsx_extraction as extraction
from questionnaire.eval import m009a_ingestion_corpus as corpus


def _extract(data: bytes):
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as fh:
        fh.write(data)
        fh.flush()
        return extraction.extract_candidates(fh.name)


class TestMultiSheetProcessing:
    def test_processes_every_unambiguous_sheet_not_just_the_first(self):
        outcome = _extract(corpus.valid_multi_sheet_workbook())
        assert outcome.status == "extracted"
        assert outcome.summary["sheets_processed"] == ["Security", "Privacy"]
        assert outcome.summary["question_count"] == 3
        questions = [c for c in outcome.candidates if c.disposition == "question"]
        assert {c.source_location["sheet_name"] for c in questions} == {"Security", "Privacy"}


class TestFormulaHandling:
    def test_formula_cell_never_becomes_a_question(self):
        outcome = _extract(corpus.workbook_with_formula_cell())
        assert outcome.status == "extracted"
        formula_candidates = [c for c in outcome.candidates if c.raw_extracted_text == "=1+1"]
        assert len(formula_candidates) == 1
        assert formula_candidates[0].disposition == "excluded_other"
        assert formula_candidates[0].extraction_error == "formula_cell_excluded_never_evaluated"
        # The genuine literal question on the next row is still extracted.
        assert outcome.summary["question_count"] == 1


class TestStructuralHeading:
    def test_merged_row_classified_as_heading(self):
        outcome = _extract(corpus.workbook_with_merged_heading_row())
        assert outcome.status == "extracted"
        heading = [c for c in outcome.candidates if c.disposition == "heading"]
        assert len(heading) == 1
        assert "Section A" in heading[0].raw_extracted_text
        assert outcome.summary["question_count"] == 1


class TestDuplicates:
    def test_exact_normalised_duplicate_excluded_but_raw_preserved(self):
        outcome = _extract(corpus.workbook_with_duplicate_question_text())
        dispositions = [c.disposition for c in outcome.candidates]
        assert dispositions == ["question", "excluded_duplicate"]
        assert outcome.candidates[1].raw_extracted_text == "Do you encrypt backups?"


class TestAmbiguousAndMissingHeaders:
    def test_ambiguous_question_columns_sheet_skipped(self):
        outcome = _extract(corpus.workbook_with_ambiguous_question_columns())
        assert outcome.status == "extraction_failed"
        assert outcome.summary["sheets_skipped"][0]["reason"] == "ambiguous_question_column"

    def test_no_identifiable_question_column_fails_closed(self):
        outcome = _extract(corpus.workbook_with_no_question_column())
        assert outcome.status == "extraction_failed"
        assert outcome.summary["sheets_skipped"][0]["reason"] == "no_question_column"


class TestResourceLimits:
    def test_sheet_exceeding_row_limit_is_skipped_not_whole_import_failed(self):
        outcome = _extract(
            corpus.workbook_exceeding_row_limit(extraction.MAX_USED_ROWS_PER_WORKSHEET)
        )
        assert outcome.status == "extraction_failed"  # only sheet in workbook, so nothing processed
        assert outcome.summary["sheets_skipped"][0]["reason"] == "sheet_exceeds_row_or_column_limit"

    def test_workbook_exceeding_worksheet_count_fails_closed(self):
        outcome = _extract(
            corpus.workbook_exceeding_worksheet_count(extraction.MAX_WORKSHEETS_INSPECTED + 5)
        )
        assert outcome.status == "extraction_failed"
        assert "worksheet" in outcome.failure_reason


class TestSourceLocationContract:
    def test_source_location_matches_schema_v1(self):
        outcome = _extract(corpus.valid_multi_sheet_workbook())
        question = next(c for c in outcome.candidates if c.disposition == "question")
        loc = question.source_location
        assert loc["schema_version"] == 1
        assert loc["format"] == "xlsx"
        assert loc["question_cell"].startswith("A")
        assert loc["answer_cell"] is None or loc["answer_cell"].startswith("B")
