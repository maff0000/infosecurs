"""
M009A pre-parse OOXML container security gate
(WO-M009A-SECURE-INGESTION-XLSX.md "OOXML container gate - hardened"
(Correction 7), "External relationships - not only xl/externalLinks/"
(Final Correction D), "XML hardening before openpyxl" (Final Correction
E), "Enforcement against actual streamed bytes, not just metadata" (Final
Correction F)).

This module performs ONLY bounded container-level structural inspection -
never business/semantic parsing (that is `questionnaire.xlsx_extraction`'s
job, and it only ever runs AFTER this gate has already returned ACCEPT).
Nothing in this module calls `openpyxl`. Nothing in this module extracts a
ZIP member onto the filesystem merely to inspect it - every member that
needs inspecting is read straight from the open `zipfile.ZipFile` into
memory, through the SAME bounded-streaming-read helper
(`_bounded_decompressed_read`) used everywhere in this module, so a
crafted/inconsistent ZIP's own central-directory metadata can never be the
sole thing standing between an attacker and an unbounded decompression
(Final Correction F).
"""
from __future__ import annotations

import dataclasses
import zipfile
from xml.etree.ElementTree import ParseError as XmlParseError

import defusedxml.ElementTree as defused_ET
from defusedxml.common import DefusedXmlException

# ---------------------------------------------------------------------------
# WO-M009A Correction 8 - frozen resource limits for M009A-v1.
# ---------------------------------------------------------------------------
MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MiB
MAX_ARCHIVE_ENTRIES = 10_000
MAX_DECOMPRESSION_RATIO = 100  # per-entry decompressed:compressed

_READ_CHUNK_SIZE = 64 * 1024

# Permitted (non-macro) workbook content types - the ONLY content types
# this gate accepts for the package's own workbook part. Any macro-enabled
# content type (`...macroEnabled...`) is rejected outright, independent of
# whether an `xl/vbaProject.bin` member is also present (belt-and-braces -
# the actual `xl/vbaProject.bin` member check below is the primary macro
# gate; this is a second, independent signal).
PERMITTED_WORKBOOK_CONTENT_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    }
)

REQUIRED_MEMBERS = (
    "[Content_Types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
)

FORBIDDEN_EXACT_MEMBERS = ("xl/vbaProject.bin",)
FORBIDDEN_PREFIXES = ("xl/externalLinks/",)


class SecurityGateResourceLimitExceeded(Exception):
    """Raised internally the instant an actual-bytes-read counter exceeds
    a frozen budget (Correction 8/Final Correction F) - always caught at
    this module's own boundary and turned into a normal REJECT outcome,
    never allowed to propagate as an unhandled exception."""


@dataclasses.dataclass(frozen=True)
class GateResult:
    """What `questionnaire.import_services` needs to decide the next
    lifecycle transition. `accepted=True` means "safe to hand to the
    malware scanner and, if CLEAN, to `questionnaire.xlsx_extraction`" -
    it does NOT by itself mean "security_gate_status=passed" (the scanner
    result still governs that - see WO-M009A "Malware scanning")."""

    accepted: bool
    reasons: tuple[str, ...]
    structural_summary: dict


def _normalise_member_name(name: str) -> str:
    return name.replace("\\", "/")


def _is_traversal_or_absolute(name: str) -> bool:
    normalised = _normalise_member_name(name)
    if normalised.startswith("/"):
        return True
    if "\x00" in normalised:
        return True
    parts = normalised.split("/")
    return any(part == ".." for part in parts)


def _bounded_decompressed_read(zf: zipfile.ZipFile, info: zipfile.ZipInfo, *, budget: list) -> bytes:
    """
    Reads ONE archive member fully into memory, in bounded chunks, never
    via a single unbounded `.read()` call (Final Correction F). `budget`
    is a one-element list `[remaining_global_bytes]`, shared and mutated
    across every call made during one gate run, so the running GLOBAL
    total of actual decompressed bytes consumed during this gate's
    inspection stays bounded across every member, not just the member
    currently being read (WO-M009A: "The total actual decompressed bytes
    consumed during gate inspection must remain bounded").

    Also enforces the frozen per-entry compression-ratio limit against the
    ACTUAL bytes read so far (not the member's advertised metadata) - a
    crafted entry whose central-directory metadata understates its real
    decompressed size is caught here, mid-read, the moment actual bytes
    exceed `compress_size * MAX_DECOMPRESSION_RATIO`, regardless of what
    `info.file_size` claims.
    """
    compressed_size = max(info.compress_size, 1)  # never divide by zero
    per_entry_cap = compressed_size * MAX_DECOMPRESSION_RATIO

    out = bytearray()
    total = 0
    try:
        with zf.open(info) as fh:
            while True:
                chunk = fh.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                budget[0] -= len(chunk)
                if total > per_entry_cap:
                    raise SecurityGateResourceLimitExceeded(
                        f"member {info.filename!r} exceeded the {MAX_DECOMPRESSION_RATIO}:1 "
                        "decompression ratio against ACTUAL streamed bytes."
                    )
                if budget[0] < 0:
                    raise SecurityGateResourceLimitExceeded(
                        "total actual decompressed bytes exceeded the 200 MiB gate budget."
                    )
                out.extend(chunk)
    except zipfile.BadZipFile as exc:
        # Python's own `zipfile` detects a CRC/declared-size inconsistency
        # at the point it believes it has delivered the member's declared
        # `file_size` bytes (Final Correction F: a member whose advertised
        # metadata understates its real decompressed content hits exactly
        # this - the declared size is too small for the real compressed
        # stream to produce a CRC-matching result). Treated as a
        # deterministic rejection, never an unhandled exception.
        raise SecurityGateResourceLimitExceeded(
            f"member {info.filename!r} failed ZIP integrity validation during bounded "
            f"read (declared size/CRC inconsistent with actual decompressed content): {exc}"
        ) from exc
    return bytes(out)


def _parse_xml_hardened(data: bytes, *, member_name: str):
    """
    `defusedxml` parse of one already-bounded-read XML part (Final
    Correction E). Any DOCTYPE/ENTITY/billion-laughs-shaped construct -
    or any other `defusedxml`-detected hostility - raises a
    `DefusedXmlException` subclass here, which this gate turns into an
    ordinary REJECT, never forwarding the hostile bytes to any other
    parser (and never to `openpyxl`, which this module never imports).
    """
    try:
        return defused_ET.fromstring(data)
    except (DefusedXmlException, XmlParseError) as exc:
        raise SecurityGateResourceLimitExceeded(  # reused as "reject with reason" signal
            f"{member_name}: rejected by XML hardening or malformed XML ({exc})."
        ) from exc


_CT_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
_RELS_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _workbook_content_type(content_types_xml: bytes) -> str | None:
    root = _parse_xml_hardened(content_types_xml, member_name="[Content_Types].xml")
    override_type = None
    default_type = None
    for child in root:
        if child.tag == f"{_CT_NS}Override" and child.get("PartName") == "/xl/workbook.xml":
            override_type = child.get("ContentType")
        if child.tag == f"{_CT_NS}Default" and child.get("Extension") == "xml":
            default_type = child.get("ContentType")
    return override_type or default_type


def _resolve_relationship_target(rels_member_name: str, target: str) -> str:
    """
    OOXML convention: a `.rels` file's own relationship targets are
    resolved relative to the directory that CONTAINS the `.rels` file's
    parent (e.g. `xl/_rels/workbook.xml.rels` resolves relative to `xl/`,
    `_rels/.rels` resolves relative to the package root). Normalises `..`
    segments by hand (never trusting `os.path` for archive-member-name
    semantics, which are POSIX-style regardless of host OS) and returns
    the resolved, normalised member-name-shaped string - WITHOUT checking
    it exists; the caller does that.
    """
    # `xl/_rels/workbook.xml.rels` -> base dir is `xl`.
    rels_dir = rels_member_name.rsplit("/_rels/", 1)[0] if "/_rels/" in rels_member_name else ""
    if rels_member_name.startswith("_rels/"):
        rels_dir = ""

    if target.startswith("/"):
        # Package-absolute target, per the spec - strip the leading slash.
        combined_parts = target.lstrip("/").split("/")
    else:
        base_parts = [p for p in rels_dir.split("/") if p]
        combined_parts = base_parts + target.split("/")

    resolved: list[str] = []
    for part in combined_parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not resolved:
                # Escapes above the package root entirely - caller treats
                # an empty/invalid resolution as "does not resolve inside
                # the package namespace".
                return ""
            resolved.pop()
        else:
            resolved.append(part)
    return "/".join(resolved)


def _inspect_relationship_documents_from_bytes(needed_member_bytes, rels_members, member_names, reasons):
    for rels_name in rels_members:
        data = needed_member_bytes[rels_name]
        try:
            root = _parse_xml_hardened(data, member_name=rels_name)
        except SecurityGateResourceLimitExceeded as exc:
            reasons.append(str(exc))
            continue

        for rel in root:
            if rel.tag != f"{_RELS_NS}Relationship":
                continue
            target_mode = rel.get("TargetMode")
            target = rel.get("Target")
            if target_mode == "External":
                reasons.append(
                    f"{rels_name}: relationship {rel.get('Id')!r} declares "
                    "TargetMode=\"External\" - external relationships are never "
                    "permitted (WO-M009A Final Correction D)."
                )
                continue
            if not target:
                reasons.append(f"{rels_name}: relationship {rel.get('Id')!r} has no Target.")
                continue
            resolved = _resolve_relationship_target(rels_name, target)
            if not resolved or resolved not in member_names:
                reasons.append(
                    f"{rels_name}: relationship {rel.get('Id')!r} target {target!r} "
                    "does not resolve to a real, in-package member (malformed or "
                    "traversal-shaped relationship target)."
                )


def run_container_gate(file_path: str) -> GateResult:
    """
    The whole bounded container gate. Returns a `GateResult`; never
    raises for an ordinary hostile/malformed input - every expected
    failure mode (bad zip, encrypted member, traversal, macro, external
    relationship, resource-limit breach, hostile XML, ...) is caught and
    turned into `accepted=False` with a human-readable reason. An
    unexpected/unknown exception is allowed to propagate - the caller
    (`questionnaire.import_services`) treats that as an infrastructure
    failure (`security_gate_failed`), never a silent pass.
    """
    reasons: list[str] = []
    summary: dict = {}

    try:
        zf = zipfile.ZipFile(file_path)
    except zipfile.BadZipFile as exc:
        return GateResult(
            accepted=False,
            reasons=(f"not a valid ZIP/OOXML container: {exc}",),
            structural_summary={},
        )

    with zf:
        try:
            infolist = zf.infolist()
        except Exception as exc:  # corrupt central directory, etc.
            return GateResult(
                accepted=False,
                reasons=(f"could not read ZIP central directory: {exc}",),
                structural_summary={},
            )

        summary["entry_count"] = len(infolist)
        if len(infolist) > MAX_ARCHIVE_ENTRIES:
            reasons.append(
                f"archive has {len(infolist)} entries, exceeding the frozen "
                f"{MAX_ARCHIVE_ENTRIES} entry limit."
            )
            # Too many entries is itself disqualifying - return early
            # rather than also trying to decompress all of them.
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        member_names = set()
        for info in infolist:
            name = _normalise_member_name(info.filename)
            if name in member_names:
                reasons.append(f"duplicate archive member name: {name!r}.")
            member_names.add(name)

            if _is_traversal_or_absolute(info.filename):
                reasons.append(f"traversal/absolute archive member name: {info.filename!r}.")

            if info.flag_bits & 0x1:
                reasons.append(f"encrypted archive member: {info.filename!r}.")

            # Cheap metadata-level ratio pre-filter (Correction 8) - the
            # REAL enforcement against actual bytes happens in
            # `_bounded_decompressed_read` below (Final Correction F); this
            # is just an early, cheap rejection for the common case where
            # the metadata itself already violates the ratio.
            compressed = max(info.compress_size, 1)
            if info.file_size / compressed > MAX_DECOMPRESSION_RATIO:
                reasons.append(
                    f"archive member {info.filename!r} advertises a "
                    f"{info.file_size / compressed:.0f}:1 compression ratio, exceeding "
                    f"the frozen {MAX_DECOMPRESSION_RATIO}:1 limit."
                )

        if reasons:
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        for required in REQUIRED_MEMBERS:
            if required not in member_names:
                reasons.append(f"missing required OOXML package member: {required!r}.")
        for forbidden in FORBIDDEN_EXACT_MEMBERS:
            if forbidden in member_names:
                reasons.append(f"forbidden (macro) package member present: {forbidden!r}.")
        for name in member_names:
            if any(name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                reasons.append(f"forbidden external-link package member present: {name!r}.")

        if reasons:
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        # Bounded streaming budget shared across every member read for the
        # remainder of this gate run (Final Correction F).
        budget = [MAX_TOTAL_UNCOMPRESSED_BYTES]

        # Real-bytes pass over EVERY archive member - not only the few
        # parts this gate semantically inspects below (Final Correction
        # F: "Do not rely exclusively on ZIP central-directory metadata
        # for bomb defence"). A crafted entry whose metadata understates
        # its real decompressed size, OR a genuine high-ratio zip-bomb
        # entry hidden in a part this gate never otherwise opens (e.g. an
        # extra worksheet XML part), is caught HERE, against actual
        # streamed bytes, regardless of whether anything later in this
        # function would have opened that specific member for its own
        # semantic purpose. Bytes for the few parts this gate DOES need
        # semantically (content types / every .rels / the workbook part)
        # are captured in `needed_member_bytes` in this same pass so they
        # are never read from the archive twice.
        rels_members = sorted(name for name in member_names if name.endswith(".rels"))
        semantically_needed = {"[Content_Types].xml", "xl/workbook.xml", *rels_members}
        needed_member_bytes: dict[str, bytes] = {}

        try:
            for info in infolist:
                name = _normalise_member_name(info.filename)
                data = _bounded_decompressed_read(zf, info, budget=budget)
                if name in semantically_needed:
                    needed_member_bytes[name] = data
        except SecurityGateResourceLimitExceeded as exc:
            reasons.append(str(exc))
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        summary["relationship_documents_inspected"] = len(rels_members)

        try:
            workbook_content_type = _workbook_content_type(
                needed_member_bytes["[Content_Types].xml"]
            )
        except SecurityGateResourceLimitExceeded as exc:
            reasons.append(str(exc))
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        summary["workbook_content_type"] = workbook_content_type
        if workbook_content_type not in PERMITTED_WORKBOOK_CONTENT_TYPES:
            reasons.append(
                f"workbook content type {workbook_content_type!r} is not a permitted "
                "non-macro XLSX content type."
            )
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        try:
            _inspect_relationship_documents_from_bytes(
                needed_member_bytes, rels_members, member_names, reasons
            )
        except SecurityGateResourceLimitExceeded as exc:
            reasons.append(str(exc))

        if reasons:
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        # Finally: confirm the workbook part is well-formed, hardened XML
        # too (not just present) - `xl/workbook.xml` itself.
        try:
            _parse_xml_hardened(needed_member_bytes["xl/workbook.xml"], member_name="xl/workbook.xml")
        except SecurityGateResourceLimitExceeded as exc:
            reasons.append(str(exc))
            return GateResult(accepted=False, reasons=tuple(reasons), structural_summary=summary)

        summary["bytes_consumed_during_gate"] = MAX_TOTAL_UNCOMPRESSED_BYTES - budget[0]

    return GateResult(accepted=True, reasons=tuple(reasons), structural_summary=summary)
