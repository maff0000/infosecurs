"""
M009A pre-parse container security gate tests
(WO-M009A-SECURE-INGESTION-XLSX.md Correction 7, Final Corrections D/E/F) -
every hostile fixture from `questionnaire.eval.m009a_ingestion_corpus`
proven genuinely rejected, and every legitimate fixture proven accepted.
"""
import tempfile

import pytest

from questionnaire import security_gate
from questionnaire.eval import m009a_ingestion_corpus as corpus


def _run_gate(data: bytes):
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as fh:
        fh.write(data)
        fh.flush()
        return security_gate.run_container_gate(fh.name)


class TestAcceptsLegitimateWorkbooks:
    def test_valid_multi_sheet_workbook_accepted(self):
        result = _run_gate(corpus.valid_multi_sheet_workbook())
        assert result.accepted, result.reasons

    def test_workbook_with_formula_cell_accepted_at_gate_level(self):
        """The gate itself has no opinion on formulas - that is
        extraction's job (Correction 5); the container structure is
        otherwise perfectly ordinary."""
        result = _run_gate(corpus.workbook_with_formula_cell())
        assert result.accepted, result.reasons

    def test_legitimate_reupload_same_bytes_accepted_twice(self):
        data = corpus.valid_multi_sheet_workbook()
        assert _run_gate(data).accepted
        assert _run_gate(data).accepted


class TestRejectsHostileContainers:
    def test_non_xlsx_file_rejected(self):
        result = _run_gate(corpus.non_xlsx_file_bytes())
        assert not result.accepted

    def test_corrupt_truncated_zip_rejected(self):
        result = _run_gate(corpus.corrupt_truncated_zip())
        assert not result.accepted

    def test_macro_enabled_workbook_rejected(self):
        result = _run_gate(corpus.macro_enabled_workbook())
        assert not result.accepted
        assert any("macro" in r or "content type" in r for r in result.reasons)

    def test_external_link_directory_rejected(self):
        result = _run_gate(corpus.workbook_with_external_link_directory())
        assert not result.accepted
        assert any("external" in r for r in result.reasons)

    def test_external_targetmode_outside_externallinks_rejected(self):
        """Final Correction D - external relationship NOT inside
        xl/externalLinks/ at all."""
        result = _run_gate(corpus.workbook_with_external_targetmode_outside_externallinks())
        assert not result.accepted
        assert any("TargetMode" in r for r in result.reasons)

    def test_malformed_relationship_target_rejected(self):
        result = _run_gate(corpus.workbook_with_malformed_relationship_target())
        assert not result.accepted
        assert any("does not resolve" in r for r in result.reasons)

    def test_missing_relationship_target_rejected(self):
        result = _run_gate(corpus.workbook_with_missing_relationship_target())
        assert not result.accepted
        assert any("does not resolve" in r for r in result.reasons)

    def test_duplicate_member_names_rejected(self):
        result = _run_gate(corpus.workbook_with_duplicate_member_names())
        assert not result.accepted
        assert any("duplicate" in r for r in result.reasons)

    def test_traversal_member_name_rejected(self):
        result = _run_gate(corpus.workbook_with_traversal_member_name())
        assert not result.accepted
        assert any("traversal" in r for r in result.reasons)

    def test_encrypted_member_rejected(self):
        result = _run_gate(corpus.workbook_with_encrypted_member())
        assert not result.accepted
        assert any("encrypted" in r for r in result.reasons)

    def test_too_many_members_rejected(self):
        result = _run_gate(corpus.too_many_members())
        assert not result.accepted
        assert any("entries" in r for r in result.reasons)

    def test_malformed_content_types_rejected(self):
        result = _run_gate(corpus.malformed_content_types_xml())
        assert not result.accepted

    def test_missing_required_member_rejected(self):
        result = _run_gate(corpus.missing_required_member())
        assert not result.accepted
        assert any("missing required" in r for r in result.reasons)

    def test_zip_bomb_shape_rejected(self):
        result = _run_gate(corpus.zip_bomb_shape(decompressed_mib=60))
        assert not result.accepted
        assert any("ratio" in r for r in result.reasons)

    def test_crafted_metadata_understating_actual_bytes_rejected(self):
        """Final Correction F - metadata says small, real streamed bytes
        prove otherwise. This is the key proof that enforcement is
        against ACTUAL bytes, not central-directory metadata alone: a
        declared-size lie this small (100 bytes, against ~20 MiB of real
        compressed content) is invisible to the cheap metadata-ratio
        pre-filter but is still caught - here, via Python's own zipfile
        detecting the declared-size/CRC inconsistency mid-read, which
        this gate turns into an ordinary rejection rather than an
        unhandled exception."""
        result = _run_gate(corpus.crafted_metadata_understating_actual_bytes())
        assert not result.accepted
        assert any(
            "ratio" in r or "budget" in r or "integrity" in r or "CRC" in r
            for r in result.reasons
        )

    def test_billion_laughs_content_types_rejected(self):
        """Final Correction E - proves the hardened parser path is
        genuinely active against an entity-expansion attack, not merely
        that defusedxml is listed in requirements.txt."""
        result = _run_gate(corpus.billion_laughs_content_types())
        assert not result.accepted

    def test_doctype_bearing_workbook_xml_rejected(self):
        result = _run_gate(corpus.doctype_bearing_workbook_xml())
        assert not result.accepted


class TestResourceLimitEdgeCases:
    def test_zero_compressed_size_does_not_divide_by_zero(self):
        """Correction 8: 'handle zero-sized/zero-compressed edge cases
        without division errors.'"""
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("empty.txt", b"")
        # Not even a valid OOXML container, but must not raise
        # ZeroDivisionError - it must cleanly REJECT.
        result = _run_gate(buf.getvalue())
        assert not result.accepted
