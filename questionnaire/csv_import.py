"""
M009B Increment 1 - deterministic CSV V1 candidate-question extraction and
structural gate (WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md
§2.2/§2.2a/§2.3).

Mirrors `questionnaire.security_gate`/`questionnaire.xlsx_extraction`'s own
two-pass split - a bounded STRUCTURAL check (`validate_csv_structure`,
this module's own equivalent of `security_gate.run_container_gate`, never
that function itself - a CSV is never a ZIP/OOXML container, see the
binding global STOP condition against calling `run_container_gate` for
CSV) and a deterministic SEMANTIC extraction pass
(`extract_candidates`, this module's own equivalent of
`xlsx_extraction.extract_candidates`) - returning the SAME result
contracts those two functions already return (`security_gate.GateResult`/
`xlsx_extraction.ExtractionOutcome`, imported and reused directly, not
reinvented), so every line of `questionnaire.import_services` code after
the gate/extraction call needs zero change regardless of which format
produced the result (§2.2a).

Only ever called AFTER `questionnaire.import_services` has already
confirmed the declared format is genuinely CSV (the uploaded bytes are
NOT ZIP-shaped - §2.2a step 2) and, for `extract_candidates`, only after
the malware scanner has already returned CLEAN - identical ordering
discipline to `xlsx_extraction`'s own module docstring.

Question/answer header vocabulary is DELIBERATELY reused verbatim from
`questionnaire.xlsx_extraction` (`QUESTION_HEADER_VOCABULARY`/
`ANSWER_HEADER_VOCABULARY`) rather than a second, independently-maintained
copy - "what counts as a Question/Answer column" is one product concept,
not a format-specific one. `REFERENCE_HEADER_VOCABULARY` is new - CSV V1's
own optional customer-reference column (amendment's "valid CSV with and
without reference/answer columns").

CSV V1 bounded limits deliberately REUSE M009A's own frozen XLSX-v1
numerals (per the Work Order's own instruction: "reusing every bounded-
limit numeral M009A's XLSX path already established... unless this
increment's own measurement shows a CSV-specific number is required" -
no such evidence exists, so none is invented here).
"""
from __future__ import annotations

import codecs
import csv
import dataclasses
import io

from questionnaire.security_gate import GateResult
from questionnaire.xlsx_extraction import (
    ANSWER_HEADER_VOCABULARY,
    MAX_CANDIDATES_PER_IMPORT,
    MAX_CELL_TEXT_LENGTH,
    MAX_USED_COLUMNS_PER_WORKSHEET,
    MAX_USED_ROWS_PER_WORKSHEET,
    QUESTION_HEADER_VOCABULARY,
    ExtractionOutcome,
)

# CSV V1's own optional customer-reference column (not present in the
# XLSX v1 vocabulary - a CSV-specific, additive concept; amendment's
# "valid CSV (with and without reference/answer columns)").
REFERENCE_HEADER_VOCABULARY = frozenset(
    {
        "reference",
        "customer reference",
        "your reference",
        "ref",
        "id",
        "question id",
        "question ref",
    }
)

# Reused verbatim from xlsx_extraction - see module docstring. Named again
# here (rather than only imported) so this module's own bounded-limit
# intent is readable without cross-referencing the other module.
MAX_CSV_DATA_ROWS = MAX_USED_ROWS_PER_WORKSHEET
MAX_CSV_COLUMNS = MAX_USED_COLUMNS_PER_WORKSHEET
MAX_CSV_CANDIDATES_PER_IMPORT = MAX_CANDIDATES_PER_IMPORT
MAX_CSV_CELL_TEXT_LENGTH = MAX_CELL_TEXT_LENGTH

# M009-AMENDMENT-2026-10-13 §4.1's "Resource limits, frozen" section
# requires a bounded TOTAL text length across an entire import, in
# addition to the bounded per-field length above - no silent truncation,
# a named rejection instead. There is no existing XLSX numeral for this
# dimension to reuse (checked `xlsx_extraction.py` directly - none
# exists), so this is a genuinely new, CSV V1-owned bound, derived as
# follows:
#
# A naive "MAX_CSV_CANDIDATES_PER_IMPORT x MAX_CSV_CELL_TEXT_LENGTH"
# (5,000 x 32,767 = 163,835,000 characters) was considered and REJECTED
# - it is larger than the already-frozen 10 MiB (10,485,760-byte)
# upload-size ceiling could ever let the decoded file contain in the
# first place (every extracted character is, by construction, a literal
# substring of the decoded file text, which can never exceed the file's
# own byte count). A bound set above the upload ceiling is permanently
# unreachable - dead code, giving this check no real teeth.
#
# Instead, this bound is deliberately set BELOW the upload-byte ceiling,
# at roughly half of it (10,485,760 // 2 = 5,242,880, rounded to a clean
# 5,000,000), reserving the remaining headroom for CSV syntax overhead
# this check does not itself count (delimiters, RFC 4180 quoting, line
# endings, the header row, and any of the other non-extracted columns a
# real file may carry, up to `MAX_CSV_COLUMNS`) while still being a
# genuinely reachable, independently-enforced ceiling on the
# question+answer+reference text actually extracted/stored/forwarded
# downstream - not merely a restatement of the upload-bytes check that
# could never itself trigger.
MAX_CSV_AGGREGATE_TEXT_LENGTH = 5_000_000

SCHEMA_VERSION = 1


def _normalise_header(value) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


class _CsvStructuralError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


@dataclasses.dataclass
class Candidate:
    """Same shape as `xlsx_extraction.Candidate`, PLUS one additive field:
    `customer_provided_answer_text` - the durable provenance value for a
    CSV `answer` column cell (amendment's new contract, Work Order §2.4).
    Always `None` for an XLSX-sourced candidate (that dataclass has no
    such attribute at all) - `questionnaire.import_services._run_extraction`
    reads this via `getattr(candidate, "customer_provided_answer_text",
    None)`, so the XLSX branch's behaviour is byte-identical, never
    populating this field, regardless of this new attribute's existence
    on this sibling dataclass."""

    raw_extracted_text: str
    source_location: dict
    extraction_order: int
    extraction_status: str
    extraction_error: str
    disposition: str
    customer_provided_answer_text: str | None = None


def _decode_csv_text(raw_bytes: bytes) -> str:
    """
    Bounded, explicit decode - UTF-8 with or without a BOM (amendment's
    "BOM-prefixed UTF-8" fixture requirement) is the ONLY accepted
    encoding for CSV V1. `codecs.BOM_UTF8`-prefixed content is decoded via
    `utf-8-sig` (strips the BOM transparently); anything else is decoded
    strictly as `utf-8`. Any other byte sequence - including a genuinely
    different encoding (e.g. latin-1 bytes that are not valid UTF-8) -
    raises `_CsvStructuralError("invalid_encoding", ...)`, never silently
    replaced/ignored (`errors="strict"`, the `str.decode` default).
    """
    if raw_bytes.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"
    try:
        return raw_bytes.decode(encoding)
    except UnicodeDecodeError as exc:
        raise _CsvStructuralError(
            "invalid_encoding", f"could not decode file as {encoding}: {exc}"
        ) from exc


def _read_rows(file_path: str) -> list[list[str]]:
    """
    Reads the whole file (already bounded to <=10 MiB by `questionnaire.
    upload_handler`/`questionnaire.import_storage` before this is ever
    called) and parses it with the standard library `csv` module's
    default ("excel") dialect - comma-delimited, double-quote-quoted,
    which already correctly handles a field containing an embedded comma,
    newline, or double quote as long as it is RFC 4180-quoted (the
    amendment's "embedded comma/newline/quote in a field" fixture
    requirement - no bespoke parsing needed; this is exactly what `csv`
    is for). Returns every row (header included) as a list of strings -
    never raises for a merely-unusual-but-parseable CSV; raises
    `_CsvStructuralError` only for the specific conditions named below.
    """
    with open(file_path, "rb") as fh:
        raw_bytes = fh.read()

    text = _decode_csv_text(raw_bytes)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise _CsvStructuralError("empty_file", "the CSV file has no rows at all.")
    return rows


def _resolve_header(header_row: list[str]):
    """
    Resolves the header row to `(question_col, answer_col, reference_col)`
    - zero-based column indexes, `answer_col`/`reference_col` possibly
    `None`. Raises `_CsvStructuralError("no_question_column", ...)` if no
    cell matches `QUESTION_HEADER_VOCABULARY`, or
    `_CsvStructuralError("ambiguous_question_column", ...)` if more than
    one does - identical discipline to `xlsx_extraction._find_header_row`,
    simplified for CSV's own single, always-row-1 header convention (no
    bounded multi-row scan is needed - a CSV file's header is,
    unambiguously, its first row).

    `answer_col`/`reference_col` get the SAME ambiguity discipline as
    `question_col` (defect B1, fixed here): two or more columns matching
    `ANSWER_HEADER_VOCABULARY` raises
    `_CsvStructuralError("ambiguous_answer_column", ...)`, and two or
    more matching `REFERENCE_HEADER_VOCABULARY` raises
    `_CsvStructuralError("ambiguous_reference_column", ...)` - never a
    silent fallback to "column absent", which would discard a genuine,
    already-supplied customer answer/reference without any named
    rejection at all. Zero matches for either remains a normal, silent
    "this optional column is absent" (`None`) - only ambiguity (more than
    one match) is an error, exactly mirroring the question column's own
    "absent is impossible, ambiguous is an error" shape, minus the
    "absent is impossible" half (these two columns are genuinely
    optional).
    """
    if len(header_row) > MAX_CSV_COLUMNS:
        raise _CsvStructuralError(
            "exceeds_max_columns",
            f"header row has {len(header_row)} columns, exceeding the frozen "
            f"{MAX_CSV_COLUMNS}-column limit.",
        )

    question_cols = []
    answer_cols = []
    reference_cols = []
    for index, raw_value in enumerate(header_row):
        header = _normalise_header(raw_value)
        if not header:
            continue
        if header in QUESTION_HEADER_VOCABULARY:
            question_cols.append(index)
        if header in ANSWER_HEADER_VOCABULARY:
            answer_cols.append(index)
        if header in REFERENCE_HEADER_VOCABULARY:
            reference_cols.append(index)

    if len(question_cols) > 1:
        raise _CsvStructuralError(
            "ambiguous_question_column",
            f"header row has {len(question_cols)} columns matching the governed "
            "question-header vocabulary - exactly one is required.",
        )
    if len(question_cols) == 0:
        raise _CsvStructuralError(
            "no_question_column",
            "no column in the header row matches the governed question-header "
            "vocabulary.",
        )

    if len(answer_cols) > 1:
        raise _CsvStructuralError(
            "ambiguous_answer_column",
            f"header row has {len(answer_cols)} columns matching the governed "
            "answer-header vocabulary - at most one is allowed.",
        )
    if len(reference_cols) > 1:
        raise _CsvStructuralError(
            "ambiguous_reference_column",
            f"header row has {len(reference_cols)} columns matching the governed "
            "reference-header vocabulary - at most one is allowed.",
        )

    answer_col = answer_cols[0] if answer_cols else None
    reference_col = reference_cols[0] if reference_cols else None
    return question_cols[0], answer_col, reference_col


def _require_data_rows(data_rows: list) -> None:
    """
    Defect B2, fixed here: a CSV with a valid header but zero data rows
    must be a deterministic, named rejection
    (`_CsvStructuralError("no_data_rows", ...)`), never a silent
    `accepted=True`/`status="extracted"` with an empty candidate list.
    Shared by both `validate_csv_structure` and `extract_candidates` (both
    call this immediately after `_resolve_header`), so neither function
    can independently drift out of sync with the other on this rule.
    """
    if not data_rows:
        raise _CsvStructuralError(
            "no_data_rows",
            "CSV has a valid header row but zero data rows - at least one "
            "data row is required.",
        )


def _column_label(header_row: list[str], index: int | None) -> str | None:
    if index is None or index >= len(header_row):
        return None
    return header_row[index]


def validate_csv_structure(file_path: str) -> GateResult:
    """
    CSV V1's own structural gate - this module's equivalent of
    `security_gate.run_container_gate`, never that function itself (a CSV
    is never a ZIP/OOXML container - binding global STOP condition).
    Returns a `GateResult` (reused directly from `questionnaire.
    security_gate` - identical `.accepted`/`.reasons`/`.structural_summary`
    contract, so `questionnaire.import_services._run_gate_and_scanner`'s
    existing code after the gate call needs zero change).

    Never raises for an ordinary hostile/malformed CSV - every expected
    failure mode (bad encoding, empty file, missing/ambiguous question
    column, too many rows/columns) is caught and turned into
    `accepted=False` with a specific, named reason. An unexpected/unknown
    exception is allowed to propagate - the caller
    (`questionnaire.import_services`) treats that as an infrastructure
    failure (`security_gate_failed`), identical to `run_container_gate`'s
    own documented contract.
    """
    try:
        rows = _read_rows(file_path)
    except _CsvStructuralError as exc:
        return GateResult(accepted=False, reasons=(exc.detail,), structural_summary={"reason": exc.reason})

    header_row, data_rows = rows[0], rows[1:]

    try:
        question_col, answer_col, reference_col = _resolve_header(header_row)
        _require_data_rows(data_rows)
    except _CsvStructuralError as exc:
        return GateResult(
            accepted=False,
            reasons=(exc.detail,),
            structural_summary={"reason": exc.reason, "header": header_row},
        )

    if len(data_rows) > MAX_CSV_DATA_ROWS:
        return GateResult(
            accepted=False,
            reasons=(
                f"CSV has {len(data_rows)} data rows, exceeding the frozen "
                f"{MAX_CSV_DATA_ROWS}-row limit (reused from M009A's own XLSX "
                "per-worksheet row limit).",
            ),
            structural_summary={"reason": "exceeds_max_rows", "row_count": len(data_rows)},
        )

    summary = {
        "row_count": len(data_rows),
        "column_count": len(header_row),
        "question_column": _column_label(header_row, question_col),
        "answer_column": _column_label(header_row, answer_col),
        "reference_column": _column_label(header_row, reference_col),
    }
    return GateResult(accepted=True, reasons=(), structural_summary=summary)


def extract_candidates(file_path: str) -> ExtractionOutcome:
    """
    CSV V1's own deterministic extraction pass - this module's equivalent
    of `xlsx_extraction.extract_candidates`. Returns an `ExtractionOutcome`
    (reused directly from `questionnaire.xlsx_extraction`) whose
    `candidates` list is built from this module's own `Candidate`
    dataclass above (same shape as `xlsx_extraction.Candidate`, plus the
    additive `customer_provided_answer_text` field).

    Only ever called after `validate_csv_structure` has already returned
    `accepted=True` AND the malware scanner has already returned CLEAN
    (identical ordering discipline to `xlsx_extraction`'s own module
    docstring) - but this function still re-derives the header resolution
    itself, from a fresh read, rather than trusting a cached result from
    the earlier gate call: a prior CLEAN structural result is never cached
    across a retry (mirroring the existing XLSX behaviour exactly, WO
    §2.2a step 6).

    Deterministic-only disposition rules (amendment Correction 12, same
    discipline `xlsx_extraction` already follows): every non-blank
    question cell is disposition "question" on first occurrence,
    "excluded_duplicate" on a later occurrence of the same normalised
    text - CSV has no structural signal equivalent to XLSX's merged-cell
    heading rule, so no "heading" disposition is ever produced here (never
    an invented NLP "looks instructional" heuristic). A BLANK question
    cell is its own disposition, "excluded_blank_question" - a deliberate
    CSV-specific divergence from XLSX's own silent-drop blank-row rule,
    because a CSV row can carry independent customer-answer/reference
    data that must never be lost along with a blank question cell.
    """
    try:
        rows = _read_rows(file_path)
    except _CsvStructuralError as exc:
        return ExtractionOutcome(
            status="extraction_failed", failure_reason=exc.detail, summary={}, candidates=[]
        )

    header_row, data_rows = rows[0], rows[1:]

    try:
        question_col, answer_col, reference_col = _resolve_header(header_row)
        _require_data_rows(data_rows)
    except _CsvStructuralError as exc:
        return ExtractionOutcome(
            status="extraction_failed", failure_reason=exc.detail, summary={}, candidates=[]
        )

    question_label = _column_label(header_row, question_col)
    answer_label = _column_label(header_row, answer_col)
    reference_label = _column_label(header_row, reference_col)

    summary = {
        "rows_discovered": len(data_rows),
        "question_count": 0,
        "excluded_counts_by_disposition": {},
        "failed_count": 0,
        "answer_destination_found": answer_col is not None,
    }

    candidates: list[Candidate] = []
    seen_normalised_question_text: set[str] = set()
    extraction_order = 0
    question_candidate_count = 0
    aggregate_text_length = 0

    for offset, data_row in enumerate(data_rows):
        row_number = offset + 2  # 1-based, header is row 1.

        question_value = data_row[question_col] if question_col < len(data_row) else ""
        raw_question_text = "" if question_value is None else str(question_value)
        is_blank_question = raw_question_text.strip() == ""

        answer_value = None
        if answer_col is not None and answer_col < len(data_row):
            answer_value = data_row[answer_col]
        raw_answer_text = "" if answer_value is None else str(answer_value)

        reference_value = None
        if reference_col is not None and reference_col < len(data_row):
            reference_value = data_row[reference_col]
        raw_reference_text = "" if reference_value is None else str(reference_value)

        # Bounded, defense-in-depth storage copy of every text field,
        # computed regardless of disposition - a row already flagged
        # "failed" for exceeding a per-field limit below must never
        # persist an unbounded string to `source_location`/`Candidate`
        # storage either. This is NOT the "no silent truncation" rule
        # being violated: the row's own `extraction_error` already names
        # the specific rejection reason, so nothing about the rejection
        # itself is silent - only the stored copy of an already-rejected
        # field is capped.
        question_text_for_storage = raw_question_text[:MAX_CSV_CELL_TEXT_LENGTH]
        answer_text_for_storage = raw_answer_text[:MAX_CSV_CELL_TEXT_LENGTH]
        reference_text_for_storage = raw_reference_text[:MAX_CSV_CELL_TEXT_LENGTH]

        source_location = {
            "schema_version": SCHEMA_VERSION,
            "format": "csv",
            "row": row_number,
            "question_column": question_label,
            "answer_column": answer_label,
            "reference_column": reference_label,
            "reference_value": reference_text_for_storage or None,
        }

        # Deterministic disposition/rejection rules, in priority order.
        # Per-field oversized checks (B4.1) take priority over
        # blank-question/duplicate/question determination below,
        # mirroring the pre-existing oversized-question-text check's own
        # priority (already checked ahead of duplicate detection, never
        # after it).
        if len(raw_answer_text) > MAX_CSV_CELL_TEXT_LENGTH:
            disposition = "excluded_other"
            extraction_status = "failed"
            extraction_error = "answer_text_exceeds_max_length"
        elif len(raw_reference_text) > MAX_CSV_CELL_TEXT_LENGTH:
            disposition = "excluded_other"
            extraction_status = "failed"
            extraction_error = "reference_text_exceeds_max_length"
        elif len(raw_question_text) > MAX_CSV_CELL_TEXT_LENGTH:
            disposition = "excluded_other"
            extraction_status = "failed"
            extraction_error = "cell_text_exceeds_max_length"
        elif is_blank_question:
            # Defect B3, fixed here: a blank-question row still produces
            # a Candidate (row identification/provenance survives, row
            # count reconciles against `rows_discovered`), with its own,
            # specifically-named disposition - never "question" (so this
            # row can never become eligible for later AI generation,
            # which requires disposition == "question" elsewhere in the
            # pipeline - this falls out naturally simply by never setting
            # that value here), and distinct from "excluded_duplicate"/
            # "excluded_other" so an operator/export can tell the three
            # apart. Central Architecture determined CSV needs different
            # handling here than XLSX's own blank-row-drops-silently rule
            # (XLSX rows cannot carry independent per-row customer-
            # answer/reference data the way a CSV row can).
            disposition = "excluded_blank_question"
            extraction_status = "extracted"
            extraction_error = ""
        else:
            normalised = question_text_for_storage.strip().casefold()
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

        extraction_order += 1
        customer_provided_answer_text = None
        if (
            disposition in ("question", "excluded_blank_question")
            and answer_value is not None
            and raw_answer_text.strip() != ""
        ):
            # Verbatim, byte-for-byte - the durable provenance field (WO
            # §2.4). Never truncated/normalised - this is the customer's
            # own already-supplied answer, not extracted/derived text.
            # An OVERSIZED answer never reaches this branch at all - it
            # is forced to disposition "excluded_other" above, before
            # this check ever runs - so this verbatim-provenance promise
            # and the B4.1 per-field bound never conflict. Included for
            # "excluded_blank_question" too (B3's own requirement to
            # retain any non-blank answer/reference a blank-question row
            # carries), not only "question".
            customer_provided_answer_text = answer_value

        candidates.append(
            Candidate(
                raw_extracted_text=question_text_for_storage,
                source_location=source_location,
                extraction_order=extraction_order,
                extraction_status=extraction_status,
                extraction_error=extraction_error,
                disposition=disposition,
                customer_provided_answer_text=customer_provided_answer_text,
            )
        )

        # Defect B4.2, fixed here: bounded TOTAL extracted text across
        # the whole import. Counted from the same bounded-for-storage
        # copies above, so an already-rejected oversized single field's
        # contribution here is itself already capped by the per-field
        # check above - this check exists purely for the OTHER failure
        # mode a per-field/per-row bound cannot catch: many individually
        # -fine cells that cumulatively balloon. Checked after every row
        # (never only at the end), mirroring the existing
        # MAX_CSV_CANDIDATES_PER_IMPORT check's own fail-fast-mid-loop
        # placement immediately below - never a silent truncation, a
        # named rejection instead.
        aggregate_text_length += (
            len(question_text_for_storage)
            + len(answer_text_for_storage)
            + len(reference_text_for_storage)
        )
        if aggregate_text_length > MAX_CSV_AGGREGATE_TEXT_LENGTH:
            return ExtractionOutcome(
                status="extraction_failed",
                failure_reason=(
                    f"exceeded the frozen {MAX_CSV_AGGREGATE_TEXT_LENGTH:,} "
                    "character aggregate extracted-text-length limit (question "
                    "+ answer + reference text combined, across the whole "
                    "import)."
                ),
                summary=summary,
                candidates=[],
            )

        if question_candidate_count > MAX_CSV_CANDIDATES_PER_IMPORT:
            return ExtractionOutcome(
                status="extraction_failed",
                failure_reason=(
                    f"exceeded the frozen {MAX_CSV_CANDIDATES_PER_IMPORT:,} "
                    "normalised-question-candidate per-import limit (reused from "
                    "M009A's own XLSX limit)."
                ),
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

    return ExtractionOutcome(status="extracted", failure_reason="", summary=summary, candidates=candidates)


__all__ = [
    "REFERENCE_HEADER_VOCABULARY",
    "MAX_CSV_DATA_ROWS",
    "MAX_CSV_COLUMNS",
    "MAX_CSV_CANDIDATES_PER_IMPORT",
    "MAX_CSV_CELL_TEXT_LENGTH",
    "MAX_CSV_AGGREGATE_TEXT_LENGTH",
    "Candidate",
    "validate_csv_structure",
    "extract_candidates",
]
