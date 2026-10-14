"""
M009B Increment 1 hostile/legitimate CSV fixture builders
(WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md §2.7), mirroring
`questionnaire.eval.m009a_ingestion_corpus`'s own shape 1:1: every function
below returns raw `bytes` for one fixture - never a committed binary file
- consumed by `questionnaire/tests/test_m009b_csv_import.py`. This module
itself contains no assertions, only fixture construction.
"""
from __future__ import annotations

import io
import zipfile


def valid_csv_with_answer_and_reference() -> bytes:
    """Question/Answer/Reference columns, two genuine questions, one with
    a non-blank customer-supplied answer - proves `answer`-column
    provenance capture."""
    return (
        "Question,Answer,Reference\r\n"
        "Do you encrypt data at rest?,Yes - AES-256 everywhere.,REF-001\r\n"
        "Do you have an incident response plan?,,REF-002\r\n"
    ).encode("utf-8")


def valid_csv_without_answer_or_reference() -> bytes:
    """Question column only - proves the optional columns are genuinely
    optional."""
    return ("Question\r\n" "Is a DPO appointed?\r\n" "Do you patch servers?\r\n").encode("utf-8")


def csv_missing_question_header() -> bytes:
    return ("Notes,Comments\r\n" "just some free text,more text\r\n").encode("utf-8")


def csv_duplicate_question_header() -> bytes:
    """Two columns both literally named 'Question' - ambiguous, same
    class as `workbook_with_ambiguous_question_columns` in the XLSX
    corpus."""
    return ("Question,Question,Answer\r\n" "Do you patch servers?,irrelevant,\r\n").encode("utf-8")


def csv_case_ambiguous_question_header() -> bytes:
    """Two columns matching the governed vocabulary only once each
    column is case-folded ('Question' and 'SECURITY QUESTION') - proves
    case-insensitive matching still correctly detects ambiguity, not just
    exact-case duplicates."""
    return ("Question,Security Question,Answer\r\n" "Do you patch servers?,irrelevant,\r\n").encode(
        "utf-8"
    )


def csv_with_blank_question_rows() -> bytes:
    """A genuine question, a blank question cell (skipped, no candidate
    row at all - identical to xlsx_extraction's own blank-row rule), and
    a second genuine question."""
    return (
        "Question,Answer\r\n"
        "Do you encrypt backups?,\r\n"
        ",\r\n"
        "Do you enforce MFA?,\r\n"
    ).encode("utf-8")


def csv_with_duplicate_question_text() -> bytes:
    return (
        "Question,Answer\r\n"
        "Do you encrypt backups?,\r\n"
        "Do you encrypt backups?,\r\n"
    ).encode("utf-8")


def csv_exceeding_row_limit(max_data_rows: int) -> bytes:
    lines = ["Question,Answer"]
    for i in range(max_data_rows + 10):
        lines.append(f"Question number {i}?,")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def csv_invalid_encoding() -> bytes:
    """Genuine non-UTF-8 bytes (Latin-1 encoded accented characters that
    are NOT valid UTF-8 byte sequences on their own) - proves the
    structural gate rejects undecodeable content rather than silently
    replacing/ignoring bad bytes."""
    return "Question,Answer\r\nDo you encrypt r\xe9sum\xe9s?,\r\n".encode("latin-1")


def csv_bom_prefixed_utf8() -> bytes:
    """A genuine UTF-8 BOM (`EF BB BF`) prefix - proves `utf-8-sig`
    decoding strips it transparently rather than treating it as part of
    the first header cell's text (which would otherwise make the
    'Question' header fail to match the governed vocabulary)."""
    return b"\xef\xbb\xbf" + "Question,Answer\r\nDo you rotate credentials?,\r\n".encode("utf-8")


def csv_with_embedded_comma_newline_quote() -> bytes:
    """A properly RFC 4180-quoted field containing an embedded comma, an
    embedded newline, and an embedded double quote (escaped as `""`) -
    proves the standard `csv` module's own quoting handles this
    correctly, with no bespoke parsing needed."""
    return (
        'Question,Answer\r\n'
        '"Do you encrypt, at rest, data containing a ""secret""\n'
        'and multiple lines?",Yes\r\n'
    ).encode("utf-8")


def declared_csv_but_actually_zip_shaped() -> bytes:
    """Genuine ZIP-shaped bytes (not even a real XLSX workbook - just a
    minimal valid ZIP local-file-header signature is enough to trigger
    the declared-format mismatch check) - proves
    `ingest_questionnaire_import`'s own `"declared_csv_but_zip_shaped"`
    named rejection fires when a caller declares CSV but the real bytes
    are ZIP-shaped."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("not_a_real_workbook.txt", "hostile payload, irrelevant content")
    return buf.getvalue()


def csv_extension_but_hostile_zip_bytes() -> bytes:
    """Same hostile shape as `declared_csv_but_zip_shaped` above, named
    separately per the Work Order's own corpus item ("a CSV renamed with
    a .csv extension but containing hostile ZIP bytes") - the upload
    filename is the test's own concern (`original_filename="q.csv"`), not
    this fixture's; this function exists for the corpus's completeness
    even though its bytes are identical in shape to the fixture above."""
    return declared_csv_but_actually_zip_shaped()
