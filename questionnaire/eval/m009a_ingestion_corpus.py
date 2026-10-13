"""
M009A hostile/legitimate fixture builders
(WO-M009A-SECURE-INGESTION-XLSX.md "Evaluation corpus", Correction 20).

Every function below returns raw `bytes` for one fixture - never a
committed binary file in the repository (these are built on the fly, so
the corpus is reviewable as Python, not opaque binaries). Consumed by
`questionnaire/tests/test_m009a_*.py` - this module itself contains no
assertions, only fixture construction, mirroring `questionnaire.eval.
golden_corpus`'s own "corpus is data, tests are assertions" separation.

Legitimate fixtures use `openpyxl` directly (the same library the product
itself parses with). Hostile fixtures that need to violate OOXML/ZIP
structure in ways `openpyxl`/`zipfile`'s own high-level API cannot express
honestly use raw `zipfile`/`struct` byte manipulation - commented at each
one explaining exactly what is being violated and why.
"""
from __future__ import annotations

import io
import struct
import zipfile

import openpyxl

CONTENT_TYPES_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/xl/workbook.xml" '
    b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    b"</Types>"
)

MACRO_CONTENT_TYPES_XML = CONTENT_TYPES_XML.replace(
    b"spreadsheetml.sheet.main+xml", b"spreadsheetml.sheet.macroEnabled.main+xml"
)


def _xlsx_bytes(build_fn) -> bytes:
    """Build a real workbook via openpyxl and return its bytes."""
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    build_fn(wb)
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Legitimate fixtures
# ---------------------------------------------------------------------------
def valid_multi_sheet_workbook() -> bytes:
    """Two visible sheets, each with Question/Answer headers and several
    questions - proves "process every unambiguous sheet", not just the
    first one."""

    def build(wb):
        ws1 = wb.active
        ws1.title = "Security"
        ws1.append(["Question", "Answer"])
        ws1.append(["Do you encrypt data at rest?", ""])
        ws1.append(["Do you have an incident response plan?", ""])

        ws2 = wb.create_sheet("Privacy")
        ws2.append(["Security Requirement", "Response"])
        ws2.append(["Is a DPO appointed?", ""])

    return _xlsx_bytes(build)


def workbook_with_formula_cell() -> bytes:
    def build(wb):
        ws = wb.active
        ws.append(["Question", "Answer"])
        ws.append(["=1+1", ""])
        ws.append(["A genuine literal question?", ""])

    return _xlsx_bytes(build)


def workbook_with_merged_heading_row() -> bytes:
    def build(wb):
        ws = wb.active
        ws.append(["Question", "Answer"])
        ws.append(["Section A - Access Control", ""])
        ws.merge_cells("A2:B2")
        ws.append(["Do you enforce MFA?", ""])

    return _xlsx_bytes(build)


def workbook_with_duplicate_question_text() -> bytes:
    def build(wb):
        ws = wb.active
        ws.append(["Question", "Answer"])
        ws.append(["Do you encrypt backups?", ""])
        ws.append(["Do you encrypt backups?", ""])

    return _xlsx_bytes(build)


def workbook_with_ambiguous_question_columns() -> bytes:
    def build(wb):
        ws = wb.active
        ws.append(["Question", "Security Question", "Answer"])
        ws.append(["Do you patch servers?", "irrelevant", ""])

    return _xlsx_bytes(build)


def workbook_with_no_question_column() -> bytes:
    def build(wb):
        ws = wb.active
        ws.append(["Notes", "Comments"])
        ws.append(["just some free text", "more text"])

    return _xlsx_bytes(build)


def workbook_exceeding_row_limit(max_used_rows: int) -> bytes:
    """A sheet whose declared dimension exceeds the frozen per-worksheet
    row limit (Correction 9) - cheap to build: one header row plus one
    cell written far below the limit, which alone makes `ws.max_row`
    exceed it."""

    def build(wb):
        ws = wb.active
        ws.append(["Question", "Answer"])
        ws.cell(row=max_used_rows + 10, column=1, value="too far down")

    return _xlsx_bytes(build)


def workbook_exceeding_worksheet_count(count: int) -> bytes:
    def build(wb):
        wb.active.title = "Sheet0"
        wb.active.append(["Question"])
        for i in range(1, count):
            wb.create_sheet(f"Sheet{i}")

    return _xlsx_bytes(build)


def non_xlsx_file_bytes() -> bytes:
    """A plain JPEG-signature-bearing file - proves content-sniffing (not
    extension) rejects a non-ZIP file even if a caller names it `.xlsx`."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 128


def corrupt_truncated_zip() -> bytes:
    good = valid_multi_sheet_workbook()
    return good[: len(good) // 3]


def oversized_payload(byte_count: int) -> bytes:
    return b"PK\x03\x04" + (b"\x00" * (byte_count - 4))


# ---------------------------------------------------------------------------
# Hostile fixtures requiring raw zip/struct manipulation
# ---------------------------------------------------------------------------
def _minimal_rels() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        b'Target="xl/workbook.xml"/>'
        b"</Relationships>"
    )


def _minimal_workbook_xml() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        b"<sheets/></workbook>"
    )


def _minimal_workbook_rels() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b"</Relationships>"
    )


def macro_enabled_workbook() -> bytes:
    """A real vbaProject.bin member + the macro-enabled content type -
    openpyxl's own API has no "add a macro" affordance, so this is built
    directly with zipfile, derived from a genuine valid workbook's other
    parts (so everything else about it is structurally normal)."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            data = base.read(name)
            if name == "[Content_Types].xml":
                data = MACRO_CONTENT_TYPES_XML
            out.writestr(name, data)
        out.writestr("xl/vbaProject.bin", b"\x00" * 64)
    return buf.getvalue()


def workbook_with_external_link_directory() -> bytes:
    """A real `xl/externalLinks/` package member (the original, narrower
    Correction 7 fixture)."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        out.writestr("xl/externalLinks/externalLink1.xml", b"<externalLink/>")
    return buf.getvalue()


def workbook_with_external_targetmode_outside_externallinks() -> bytes:
    """Final Correction D - an external relationship OUTSIDE
    `xl/externalLinks/` entirely: a worksheet relationship document
    declaring `TargetMode="External"` for an ordinary hyperlink."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    hostile_rels = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId99" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        b'Target="https://attacker.example/" TargetMode="External"/>'
        b"</Relationships>"
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        out.writestr("xl/worksheets/_rels/sheet1.xml.rels", hostile_rels)
    return buf.getvalue()


def workbook_with_malformed_relationship_target() -> bytes:
    """Final Correction D - a relationship target that traverses above
    the package root via `..` segments."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    hostile_rels = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        b'Target="../../../etc/passwd"/>'
        b"</Relationships>"
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            if name == "_rels/.rels":
                out.writestr(name, hostile_rels)
            else:
                out.writestr(name, base.read(name))
    return buf.getvalue()


def workbook_with_missing_relationship_target() -> bytes:
    """Final Correction D - a relationship pointing at a member that does
    not exist anywhere in the package."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    hostile_rels = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        b'Target="xl/does_not_exist.xml"/>'
        b"</Relationships>"
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            if name == "_rels/.rels":
                out.writestr(name, hostile_rels)
            else:
                out.writestr(name, base.read(name))
    return buf.getvalue()


def workbook_with_duplicate_member_names() -> bytes:
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        # A genuine second entry with the IDENTICAL normalised name.
        out.writestr("xl/workbook.xml", _minimal_workbook_xml())
    return buf.getvalue()


def workbook_with_traversal_member_name() -> bytes:
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        out.writestr("../../../tmp/evil.txt", b"hostile")
    return buf.getvalue()


def _find_central_directory_record_offset(raw: bytes, member_name: str) -> int:
    """
    Parses the ZIP End-Of-Central-Directory record to find the central
    directory's own start offset, then walks central-directory records
    SEQUENTIALLY from there (each record's fixed 46-byte part plus its own
    declared name/extra/comment lengths determines exactly where the next
    one starts) until `member_name` is found - returns that record's start
    offset. This never searches for the name as a raw substring anywhere
    in the file (which would false-positive on the same string appearing
    inside unrelated XML content, e.g. a relationship Target) - it walks
    the archive's own structural records exactly as `zipfile` itself
    would.
    """
    eocd_sig = raw.rfind(b"PK\x05\x06")
    if eocd_sig == -1:
        raise AssertionError("no End-Of-Central-Directory record found")
    cd_offset = struct.unpack_from("<L", raw, eocd_sig + 16)[0]

    offset = cd_offset
    while True:
        if raw[offset : offset + 4] != b"PK\x01\x02":
            raise AssertionError(f"central directory record not found for {member_name!r}")
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", raw, offset + 28)
        name = raw[offset + 46 : offset + 46 + name_len].decode("utf-8")
        if name == member_name:
            return offset
        offset += 46 + name_len + extra_len + comment_len


def workbook_with_encrypted_member() -> bytes:
    """Sets the ZIP general-purpose flag bit 0 (encrypted) on one member's
    CENTRAL DIRECTORY record (not merely its local header) - the security
    gate's own encrypted-member check reads exactly this bit from
    `zipfile.ZipFile.infolist()`, which parses the central directory, so
    this proves that check without needing genuine ZipCrypto/AES
    encryption. `zipfile.ZipFile._open_to_write` unconditionally resets
    `zinfo.flag_bits = 0x00` at write time (confirmed directly against
    this pinned Python's own `zipfile` source) - there is no supported
    API to make `writestr` emit a custom flag bit, so this patches the
    already-written central directory record directly, located precisely
    via `_find_central_directory_record_offset` (never a raw substring
    search for the member's name, which would false-positive against the
    same string appearing inside unrelated XML content elsewhere in the
    archive)."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    member_name = "xl/media/m009a_encrypted_fixture.bin"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        out.writestr(member_name, b"irrelevant payload")

    raw = bytearray(buf.getvalue())
    record_offset = _find_central_directory_record_offset(bytes(raw), member_name)
    flag_offset = record_offset + 8
    current = struct.unpack_from("<H", raw, flag_offset)[0]
    struct.pack_into("<H", raw, flag_offset, current | 0x1)
    return bytes(raw)


def zip_bomb_shape(decompressed_mib: int = 60) -> bytes:
    """A real high-expansion-ratio member: a highly repetitive buffer
    compresses far beyond the frozen 100:1 ratio - a genuine zip-bomb
    SHAPE (not a metadata lie), proving the ratio/size enforcement itself
    (Correction 8), independent of the separate crafted-metadata fixture
    below (Final Correction F)."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    payload = b"0" * (decompressed_mib * 1024 * 1024)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        out.writestr("xl/media/bomb.bin", payload, zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def too_many_members(count: int = 10_050) -> bytes:
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        for i in range(count):
            out.writestr(f"xl/worksheets/junk/{i}.xml", b"x")
    return buf.getvalue()


def malformed_content_types_xml() -> bytes:
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            if name == "[Content_Types].xml":
                out.writestr(name, b"<Types><Override not even well formed")
            else:
                out.writestr(name, base.read(name))
    return buf.getvalue()


def missing_required_member() -> bytes:
    """`xl/workbook.xml` itself absent - a required OOXML part missing."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            if name == "xl/workbook.xml":
                continue
            out.writestr(name, base.read(name))
    return buf.getvalue()


_BILLION_LAUGHS_PAYLOAD = (
    b'<?xml version="1.0"?>'
    b"<!DOCTYPE lolz [similar"
    b' <!ENTITY lol "lol">'
    b' <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
    b' <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
    b"]>"
    b"<lolz>&lol3;</lolz>"
)


def billion_laughs_content_types() -> bytes:
    """Final Correction E - an ENTITY/billion-laughs-style
    `[Content_Types].xml`. `defusedxml` must reject this before it ever
    reaches a real parse."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            if name == "[Content_Types].xml":
                out.writestr(name, _BILLION_LAUGHS_PAYLOAD)
            else:
                out.writestr(name, base.read(name))
    return buf.getvalue()


def doctype_bearing_workbook_xml() -> bytes:
    """Final Correction E - a plain DOCTYPE (no entity expansion) on
    `xl/workbook.xml` itself."""
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    hostile = (
        b'<?xml version="1.0"?><!DOCTYPE workbook SYSTEM "file:///etc/passwd">'
        + _minimal_workbook_xml()
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            if name == "xl/workbook.xml":
                out.writestr(name, hostile)
            else:
                out.writestr(name, base.read(name))
    return buf.getvalue()


def crafted_metadata_understating_actual_bytes() -> bytes:
    """
    Final Correction F - a ZIP whose CENTRAL DIRECTORY metadata for one
    member claims a small uncompressed size, while the member's real
    compressed data stream decompresses to far more. Built by patching
    the 4-byte uncompressed-size field (offset 22 within the fixed part of
    a central-directory file header, immediately before the variable-
    length name/extra/comment fields) for one entry, in BOTH its local
    file header and its central-directory record, to a small lie - the
    compressed byte stream itself is left completely untouched, so a gate
    that trusts only the metadata would wrongly conclude this entry is
    small and safe, while bounded actual-byte-streaming reveals the truth
    mid-read.
    """
    base = zipfile.ZipFile(io.BytesIO(valid_multi_sheet_workbook()))
    buf = io.BytesIO()
    real_payload = b"A" * (20 * 1024 * 1024)  # 20 MiB of real content
    # A deliberately distinctive member name, unlikely to appear anywhere
    # else in the archive's own XML text content (e.g. a relationship
    # Target string) - `raw.find()` below must locate the member's OWN
    # local/central-directory header, never a false-positive substring
    # match inside unrelated XML content.
    member_name = "xl/media/m009a_oversized_payload_fixture.bin"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in base.namelist():
            out.writestr(name, base.read(name))
        out.writestr(member_name, real_payload)

    raw = bytearray(buf.getvalue())
    lie = 100  # claim only 100 bytes uncompressed.

    # Only the CENTRAL DIRECTORY record's uncompressed-size field matters
    # here: `zipfile.ZipFile.open()`/`.infolist()` both read size/CRC from
    # the central directory's own `ZipInfo`, never re-deriving it from the
    # local header at read time - confirmed directly against this pinned
    # Python's own `zipfile` source. Located precisely via
    # `_find_central_directory_record_offset` (never a raw substring
    # search for the member's name). Uncompressed size is the 4-byte
    # field at offset 24 from the record's own "PK\x01\x02" signature
    # (its compressed-size field sits immediately before, at offset 20).
    record_offset = _find_central_directory_record_offset(bytes(raw), member_name)
    struct.pack_into("<L", raw, record_offset + 24, lie)

    return bytes(raw)


__all__ = [name for name in dir() if not name.startswith("_")]
