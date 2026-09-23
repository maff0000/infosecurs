import hashlib
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from evidence import storage
from evidence.exceptions import EvidenceValidationError

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
MINIMAL_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
MINIMAL_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PLAIN_TEXT = "This is synthetic Customer-Zero-safe evidence text.\n".encode("utf-8")


def _upload(content, name="evidence.dat", content_type="application/octet-stream"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class TestDetectAndHash:
    def test_identifies_pdf_by_signature(self):
        file_type, size, digest = storage.detect_and_hash(_upload(MINIMAL_PDF, "doc.pdf", "application/pdf"))
        assert file_type == "pdf"
        assert size == len(MINIMAL_PDF)
        assert digest == hashlib.sha256(MINIMAL_PDF).hexdigest()

    def test_identifies_png_by_signature(self):
        file_type, size, digest = storage.detect_and_hash(_upload(MINIMAL_PNG, "shot.png", "image/png"))
        assert file_type == "png"
        assert digest == hashlib.sha256(MINIMAL_PNG).hexdigest()

    def test_identifies_jpeg_by_signature(self):
        file_type, size, digest = storage.detect_and_hash(_upload(MINIMAL_JPEG, "shot.jpg", "image/jpeg"))
        assert file_type == "jpeg"
        assert digest == hashlib.sha256(MINIMAL_JPEG).hexdigest()

    def test_identifies_plain_text(self):
        file_type, size, digest = storage.detect_and_hash(_upload(PLAIN_TEXT, "notes.txt", "text/plain"))
        assert file_type == "text"
        assert digest == hashlib.sha256(PLAIN_TEXT).hexdigest()

    def test_rejects_unrecognised_binary_content(self):
        garbage = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
        with pytest.raises(EvidenceValidationError):
            storage.detect_and_hash(_upload(garbage, "app.exe", "application/octet-stream"))

    def test_rejects_empty_file(self):
        with pytest.raises(EvidenceValidationError):
            storage.detect_and_hash(_upload(b"", "empty.txt", "text/plain"))

    def test_enforces_size_limit(self, monkeypatch):
        monkeypatch.setattr(storage, "MAX_UPLOAD_BYTES", 8)
        oversized = PLAIN_TEXT  # 54 bytes, well over the patched 8-byte cap
        with pytest.raises(EvidenceValidationError):
            storage.detect_and_hash(_upload(oversized, "notes.txt", "text/plain"))

    def test_content_wins_over_declared_extension_and_mime(self):
        """
        PID §9: 'Do not trust browser MIME, extension or filename.' A file
        named/declared as PNG but whose bytes are actually a PDF must be
        classified by its real content (PDF, itself an accepted type) -
        never accepted-as-PNG and never trusted-because-of-the-extension.
        """
        mismatched = _upload(MINIMAL_PDF, "screenshot.png", "image/png")
        file_type, _, _ = storage.detect_and_hash(mismatched)
        assert file_type == "pdf"

    def test_rejects_content_that_matches_no_accepted_signature_despite_plausible_name(self):
        """
        The converse mismatch: a file named/declared as an accepted type
        (application/pdf, report.pdf) whose actual bytes are neither a
        recognised signature nor valid text must still be rejected - name
        and declared type carry no weight either way.
        """
        garbage = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 24
        with pytest.raises(EvidenceValidationError):
            storage.detect_and_hash(_upload(garbage, "report.pdf", "application/pdf"))

    def test_rejects_binary_containing_null_bytes_even_if_no_other_signature_matches(self):
        with_nulls = b"some text\x00with an embedded null byte"
        with pytest.raises(EvidenceValidationError):
            storage.detect_and_hash(_upload(with_nulls, "notes.txt", "text/plain"))

    def test_utf8_text_detection_survives_multibyte_char_split_across_chunk_boundary(self, monkeypatch):
        """
        A naive per-chunk-independent UTF-8 decode would false-negative a
        genuinely valid file merely because a multi-byte character landed
        on a chunk boundary. Force a tiny chunk size to actually exercise
        that boundary, using a string whose multi-byte character (£, 2
        bytes in UTF-8) sits where a small chunk size will split it.
        """
        monkeypatch.setattr(storage, "_CHUNK_SIZE", 4)
        content = "abc£def".encode("utf-8")  # 'abc' + 2-byte £ + 'def' = 8 bytes
        file_type, size, digest = storage.detect_and_hash(_upload(content, "notes.txt", "text/plain"))
        assert file_type == "text"
        assert size == len(content)
        assert digest == hashlib.sha256(content).hexdigest()


class TestStoreUploadedFile:
    def test_stores_bytes_and_never_overwrites_existing_evidence(self, org_a, evidence_storage_root):
        f1 = _upload(MINIMAL_PDF, "a.pdf", "application/pdf")
        f2 = _upload(MINIMAL_PDF, "b.pdf", "application/pdf")

        name1 = storage.store_uploaded_file(org_a.id, f1, "pdf")
        name2 = storage.store_uploaded_file(org_a.id, f2, "pdf")

        assert name1 != name2  # opaque, unique per item - even for identical bytes
        path1 = os.path.join(str(evidence_storage_root), str(org_a.id), name1)
        path2 = os.path.join(str(evidence_storage_root), str(org_a.id), name2)
        assert os.path.isfile(path1)
        assert os.path.isfile(path2)
        with open(path1, "rb") as fh:
            assert fh.read() == MINIMAL_PDF
        with open(path2, "rb") as fh:
            assert fh.read() == MINIMAL_PDF

    def test_stored_filename_is_never_derived_from_original_filename(self, org_a):
        upload = _upload(MINIMAL_PNG, "very-sensitive-customer-name.png", "image/png")
        stored_filename = storage.store_uploaded_file(org_a.id, upload, "png")
        assert "very-sensitive-customer-name" not in stored_filename

    def test_refuses_to_overwrite_an_existing_stored_file(self, org_a, evidence_storage_root, monkeypatch):
        """
        Directly proves the O_EXCL contract: if the "random" opaque name
        were ever to collide, the second write must not silently clobber
        the first.
        """
        import uuid as uuid_module

        fixed_uuid = uuid_module.uuid4()
        monkeypatch.setattr(storage.uuid, "uuid4", lambda: fixed_uuid)

        first = storage.store_uploaded_file(org_a.id, _upload(MINIMAL_PDF, "a.pdf"), "pdf")
        with pytest.raises(EvidenceValidationError):
            storage.store_uploaded_file(org_a.id, _upload(MINIMAL_PDF, "b.pdf"), "pdf")

        path = os.path.join(str(evidence_storage_root), str(org_a.id), first)
        with open(path, "rb") as fh:
            assert fh.read() == MINIMAL_PDF


class TestEvidenceFilePath:
    def test_resolves_within_organisations_storage_directory(self, org_a, evidence_storage_root):
        upload = _upload(MINIMAL_PDF, "a.pdf")
        stored_filename = storage.store_uploaded_file(org_a.id, upload, "pdf")
        resolved = storage.evidence_file_path(org_a.id, stored_filename)
        org_dir = os.path.realpath(os.path.join(str(evidence_storage_root), str(org_a.id)))
        assert os.path.commonpath([org_dir, resolved]) == org_dir
        assert os.path.isfile(resolved)

    @pytest.mark.parametrize(
        "malicious_stored_filename",
        [
            "../../../etc/passwd",
            "..",
            ".",
            "sub/dir/file.pdf",
            "sub\\dir\\file.pdf",
            "",
        ],
    )
    def test_rejects_path_traversal_and_malformed_identifiers(self, org_a, malicious_stored_filename):
        """
        Defence in depth (PID §9 'test it anyway'): even a stored_filename
        value that should never occur through the normal write path - as
        if a DB row were corrupted or tampered with - cannot be used to
        escape the organisation's storage directory.
        """
        with pytest.raises(EvidenceValidationError):
            storage.evidence_file_path(org_a.id, malicious_stored_filename)
