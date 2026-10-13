"""
M009A deterministic XLSX candidate-question extraction
(WO-M009A-SECURE-INGESTION-XLSX.md "Formula handling - corrected"
(Correction 5), "Semantic extraction resource limits - frozen"
(Correction 9), "XLSX v1 mapping rule - frozen" (Correction 11),
"Non-question dispositions - deterministic only" (Correction 12),
"Import-level extraction summary" (Correction 13)).

Only ever called AFTER `questionnaire.security_gate.run_container_gate`
has already returned `accepted=True` AND the malware scanner has already
returned `CLEAN` (WO-M009A: "No parser/extractor of any kind may run
before the pre-parse security gate accepts the file"). This module is
pure/deterministic - it never calls any AI orchestration module, never
evaluates a formula, and never performs a second `data_only=True` read.
"""
from __future__ import annotations

import dataclasses
import zipfile

import defusedxml.ElementTree as defused_ET
import openpyxl
from openpyxl.utils.cell import range_boundaries

# ---------------------------------------------------------------------------
# WO-M009A Correction 9 - frozen for M009A-v1.
# ---------------------------------------------------------------------------
MAX_WORKSHEETS_INSPECTED = 50
MAX_USED_ROWS_PER_WORKSHEET = 20_000
MAX_USED_COLUMNS_PER_WORKSHEET = 256
MAX_NON_EMPTY_CELLS_INSPECTED = 100_000
MAX_CANDIDATES_PER_IMPORT = 5_000
MAX_CELL_TEXT_LENGTH = 32_767  # Excel's own cell maximum.

# WO-M009A Correction 11 - frozen governed header vocabulary (case-folded,
# whitespace-trimmed exact match only - never fuzzy/AI-based).
QUESTION_HEADER_VOCABULARY = frozenset(
    {
        "question",
        "security question",
        "assessment question",
        "control question",
        "requirement",
        "security requirement",
        "question / requirement",
        "control / question",
    }
)
ANSWER_HEADER_VOCABULARY = frozenset(
    {
        "answer",
        "response",
        "your answer",
        "your response",
        "supplier response",
        "vendor response",
        "company response",
    }
)

# Bounded header-scan window - the header row is searched for within the
# first N rows of a worksheet only ("Inspect a bounded header region").
_HEADER_SCAN_ROWS = 10

SCHEMA_VERSION = 1


def _normalise_header(value) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


def _column_letter(index: int) -> str:
    return openpyxl.utils.get_column_letter(index)


_SHEET_XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_MERGE_READ_CAP = 5 * 1024 * 1024  # 5 MiB - bounded, not an unbounded read.


def _merged_ranges_for_worksheet(file_path: str, ws) -> list[tuple[int, int, int, int]]:
    """
    `openpyxl`'s `read_only=True` mode exposes no `ws.merged_cells` API at
    all (`ReadOnlyWorksheet` simply does not carry it - confirmed directly
    against this pinned `openpyxl==3.1.5`). Rather than abandon
    `read_only=True` (Correction 5 is binding) or open the workbook a
    SECOND time with `openpyxl` itself (which is exactly the kind of
    second-read Correction 5 warns against for formula handling, and
    unnecessary here), this reads ONLY the one already-identified
    worksheet's own XML part (`ws._worksheet_path` - the real in-package
    path `openpyxl` itself already resolved when opening the workbook) via
    a bounded `zipfile` read, then parses it with `defusedxml` (the same
    hardened-XML discipline `questionnaire.security_gate` uses) - never a
    second semantic parse of the whole workbook. Returns a list of
    `(min_row, min_col, max_row, max_col)` tuples; empty if the sheet has
    no merged ranges or the part cannot be read.
    """
    worksheet_path = getattr(ws, "_worksheet_path", None)
    if not worksheet_path:
        return []
    try:
        with zipfile.ZipFile(file_path) as zf:
            with zf.open(worksheet_path) as fh:
                data = fh.read(_MERGE_READ_CAP + 1)
            if len(data) > _MERGE_READ_CAP:
                return []
            root = defused_ET.fromstring(data)
    except Exception:
        return []

    ranges = []
    merge_cells_el = root.find(f"{_SHEET_XML_NS}mergeCells")
    if merge_cells_el is None:
        return []
    for merge_cell_el in merge_cells_el.findall(f"{_SHEET_XML_NS}mergeCell"):
        ref = merge_cell_el.get("ref")
        if not ref:
            continue
        try:
            min_col, min_row, max_col, max_row = range_boundaries(ref)
        except ValueError:
            continue
        ranges.append((min_row, min_col, max_row, max_col))
    return ranges


@dataclasses.dataclass
class Candidate:
    raw_extracted_text: str
    source_location: dict
    extraction_order: int
    extraction_status: str
    extraction_error: str
    disposition: str


@dataclasses.dataclass
class ExtractionOutcome:
    status: str  # "extracted" | "extraction_failed"
    failure_reason: str
    summary: dict
    candidates: list


class _ExtractionAborted(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _find_header_row(ws, *, max_row_scan: int):
    """
    Bounded header-region scan (Correction 11 step 1-5). Returns
    `(header_row_index, question_col_index, answer_col_index)` or `None`
    if no row in the scanned window has exactly one deterministic
    question-header match, or raises `_ExtractionAborted("ambiguous")` if
    a row has MORE than one plausible question-header match.
    """
    max_row = min(ws.max_row or 0, max_row_scan)
    max_col = min(ws.max_column or 0, MAX_USED_COLUMNS_PER_WORKSHEET)
    if max_row == 0 or max_col == 0:
        return None

    for row in ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col):
        question_cols = []
        answer_cols = []
        for cell in row:
            header = _normalise_header(cell.value)
            if not header:
                continue
            if header in QUESTION_HEADER_VOCABULARY:
                question_cols.append(cell.column)
            if header in ANSWER_HEADER_VOCABULARY:
                answer_cols.append(cell.column)

        if len(question_cols) > 1:
            raise _ExtractionAborted("ambiguous_question_column")
        if len(question_cols) == 1:
            answer_col = answer_cols[0] if len(answer_cols) == 1 else None
            return row[0].row, question_cols[0], answer_col

    return None


def extract_candidates(file_path: str) -> ExtractionOutcome:
    """
    The whole deterministic extraction pass. Never raises for an ordinary
    extraction-rule outcome (ambiguous sheet, no question column anywhere,
    a resource-limit breach) - those become `status="extraction_failed"`
    with a clear `failure_reason`. An unexpected/unknown exception (e.g. a
    genuinely corrupt file that somehow passed the container gate) is
    allowed to propagate - the caller treats that as an infrastructure
    failure, never a silent partial success.
    """
    # Correction 5 - binding load mode. openpyxl never evaluates formulas
    # either way; `data_only=False` keeps formula cells visibly
    # formula-shaped (`cell.data_type == "f"`, `cell.value` is the literal
    # formula text) rather than substituting a cached result. NEVER a
    # second `data_only=True` read anywhere in this module.
    workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=False)

    try:
        sheet_names = workbook.sheetnames
        summary = {
            "sheets_discovered": len(sheet_names),
            "sheets_processed": [],
            "sheets_skipped": [],
            "question_count": 0,
            "excluded_counts_by_disposition": {},
            "failed_count": 0,
            "answer_destination_found": False,
        }

        if len(sheet_names) > MAX_WORKSHEETS_INSPECTED:
            return ExtractionOutcome(
                status="extraction_failed",
                failure_reason=(
                    f"workbook has {len(sheet_names)} worksheets, exceeding the frozen "
                    f"{MAX_WORKSHEETS_INSPECTED}-worksheet inspection limit."
                ),
                summary=summary,
                candidates=[],
            )

        candidates: list[Candidate] = []
        seen_normalised_question_text: set[str] = set()
        non_empty_cells_inspected = 0
        extraction_order = 0
        any_sheet_processed = False
        question_candidate_count = 0

        for sheet_index, sheet_name in enumerate(sheet_names):
            ws = workbook[sheet_name]
            if getattr(ws, "sheet_state", "visible") != "visible":
                summary["sheets_skipped"].append({"sheet": sheet_name, "reason": "not_visible"})
                continue

            if (ws.max_row or 0) > MAX_USED_ROWS_PER_WORKSHEET or (
                ws.max_column or 0
            ) > MAX_USED_COLUMNS_PER_WORKSHEET:
                summary["sheets_skipped"].append(
                    {"sheet": sheet_name, "reason": "sheet_exceeds_row_or_column_limit"}
                )
                continue

            try:
                header = _find_header_row(ws, max_row_scan=_HEADER_SCAN_ROWS)
            except _ExtractionAborted as exc:
                summary["sheets_skipped"].append({"sheet": sheet_name, "reason": exc.reason})
                continue

            if header is None:
                summary["sheets_skipped"].append(
                    {"sheet": sheet_name, "reason": "no_question_column"}
                )
                continue

            header_row, question_col, answer_col = header
            any_sheet_processed = True
            summary["sheets_processed"].append(sheet_name)

            merged_ranges = _merged_ranges_for_worksheet(file_path, ws)

            data_max_row = min(ws.max_row, MAX_USED_ROWS_PER_WORKSHEET)
            for row_cells in ws.iter_rows(
                min_row=header_row + 1, max_row=data_max_row, max_col=ws.max_column
            ):
                question_cell = row_cells[question_col - 1]
                row_index = question_cell.row

                # Count every non-empty cell actually visited in the
                # question column (Correction 9 - workbook-wide cumulative
                # limit, checked on every iteration so a crafted wide/tall
                # sheet aborts promptly rather than after a full pass).
                if question_cell.value is not None:
                    non_empty_cells_inspected += 1
                    if non_empty_cells_inspected > MAX_NON_EMPTY_CELLS_INSPECTED:
                        return ExtractionOutcome(
                            status="extraction_failed",
                            failure_reason=(
                                "exceeded the frozen 100,000 non-empty-cell workbook "
                                "inspection limit."
                            ),
                            summary=summary,
                            candidates=[],
                        )

                if question_cell.value is None or (
                    isinstance(question_cell.value, str) and question_cell.value.strip() == ""
                ):
                    # Blank row - no QuestionnaireImportQuestion row needed
                    # (Correction 11 point 11).
                    continue

                question_coord = f"{_column_letter(question_col)}{row_index}"
                answer_coord = None
                if answer_col is not None:
                    # Built from the column letter + row number directly,
                    # never `.coordinate` - a cell beyond the row's own
                    # populated extent (e.g. the answer column on a row
                    # that only has a question cell) comes back as an
                    # `openpyxl.cell.read_only.EmptyCell` placeholder in
                    # read_only mode, which has no `.coordinate` attribute
                    # at all (confirmed directly against this pinned
                    # `openpyxl==3.1.5`).
                    answer_coord = f"{_column_letter(answer_col)}{row_index}"

                source_location = {
                    "schema_version": SCHEMA_VERSION,
                    "format": "xlsx",
                    "sheet_name": sheet_name,
                    "sheet_index": sheet_index,
                    "question_cell": question_coord,
                    "row": row_index,
                    "question_column": _column_letter(question_col),
                    "answer_cell": answer_coord,
                }

                is_formula = getattr(question_cell, "data_type", None) == "f"
                raw_text = question_cell.value
                raw_text = "" if raw_text is None else str(raw_text)
                truncated_for_storage = raw_text[:MAX_CELL_TEXT_LENGTH]

                if is_formula:
                    disposition = "excluded_other"
                    extraction_status = "extracted"
                    extraction_error = "formula_cell_excluded_never_evaluated"
                elif len(raw_text) > MAX_CELL_TEXT_LENGTH:
                    disposition = "excluded_other"
                    extraction_status = "failed"
                    extraction_error = "cell_text_exceeds_excel_max_length"
                elif _is_heading_row(question_cell, merged_ranges):
                    disposition = "heading"
                    extraction_status = "extracted"
                    extraction_error = ""
                else:
                    normalised = truncated_for_storage.strip().casefold()
                    if normalised in seen_normalised_question_text:
                        disposition = "excluded_duplicate"
                        extraction_status = "extracted"
                        extraction_error = ""
                    else:
                        seen_normalised_question_text.add(normalised)
                        disposition = "question"
                        extraction_status = "extracted"
                        extraction_error = ""
                        question_candidate_count += 1
                        if answer_coord is not None:
                            summary["answer_destination_found"] = True

                extraction_order += 1
                candidates.append(
                    Candidate(
                        raw_extracted_text=truncated_for_storage,
                        source_location=source_location,
                        extraction_order=extraction_order,
                        extraction_status=extraction_status,
                        extraction_error=extraction_error,
                        disposition=disposition,
                    )
                )

                if question_candidate_count > MAX_CANDIDATES_PER_IMPORT:
                    return ExtractionOutcome(
                        status="extraction_failed",
                        failure_reason=(
                            "exceeded the frozen 5,000 normalised-question-candidate "
                            "per-import limit."
                        ),
                        summary=summary,
                        candidates=[],
                    )

        if not any_sheet_processed:
            return ExtractionOutcome(
                status="extraction_failed",
                failure_reason="no sheet had a deterministically identifiable question column.",
                summary=summary,
                candidates=[],
            )

        for candidate in candidates:
            if candidate.disposition == "question":
                summary["question_count"] += 1
            elif candidate.extraction_status == "failed":
                summary["failed_count"] += 1
            else:
                summary["excluded_counts_by_disposition"][candidate.disposition] = (
                    summary["excluded_counts_by_disposition"].get(candidate.disposition, 0) + 1
                )

        return ExtractionOutcome(
            status="extracted", failure_reason="", summary=summary, candidates=candidates
        )
    finally:
        workbook.close()


def _is_heading_row(cell, merged_ranges) -> bool:
    """
    The ONE deterministic *structural* non-question rule implemented for
    M009A-v1 (Correction 12 forbids inventing NLP "looks instructional"
    heuristics): a candidate cell that is the top-left anchor of a
    horizontally-merged range (spanning more than one column) is
    structurally a section heading, not a question. `merged_ranges` is the
    list of `(min_row, min_col, max_row, max_col)` tuples from
    `_merged_ranges_for_worksheet`, read directly from the worksheet's own
    XML - never guessed from text content.
    """
    for min_row, min_col, max_row, max_col in merged_ranges:
        if cell.row != min_row or cell.column != min_col:
            continue
        if max_col > min_col:
            return True
    return False
