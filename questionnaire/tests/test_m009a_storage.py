"""
M009A storage-layer tests (`questionnaire.import_storage`), mirroring
`evidence/tests/test_storage.py`'s own discipline for the sibling module.
"""
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from questionnaire import import_storage
from questionnaire.models import QuestionnaireImportValidationError

pytestmark = pytest.mark.django_db


def _upload(data: bytes, name="q.xlsx"):
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


class TestStoreAndHash:
    def test_stores_bytes_with_opaque_filename_and_correct_permissions(self, org_a, questionnaire_storage_root):
        data = b"PK\x03\x04" + b"hello world" * 100
        stored_filename, size, sha256_hex, is_zip = import_storage.store_and_hash_uploaded_file(
            org_a.id, _upload(data)
        )
        assert stored_filename.endswith(".xlsx")
        assert stored_filename != "q.xlsx"  # opaque, not the original name
        assert size == len(data)
        assert is_zip is True

        path = os.path.join(str(questionnaire_storage_root), str(org_a.id), stored_filename)
        assert os.path.isfile(path)
        mode = oct(os.stat(path).st_mode & 0o777)
        assert mode == "0o640"
        with open(path, "rb") as fh:
            assert fh.read() == data

    def test_non_zip_bytes_detected(self, org_a):
        _, _, _, is_zip = import_storage.store_and_hash_uploaded_file(
            org_a.id, _upload(b"not a zip at all")
        )
        assert is_zip is False

    def test_empty_upload_rejected(self, org_a):
        with pytest.raises(QuestionnaireImportValidationError):
            import_storage.store_and_hash_uploaded_file(org_a.id, _upload(b""))

    def test_abort_above_max_bytes_deletes_partial_file(self, org_a, questionnaire_storage_root, monkeypatch):
        monkeypatch.setattr(import_storage, "MAX_UPLOAD_BYTES", 10)
        with pytest.raises(QuestionnaireImportValidationError):
            import_storage.store_and_hash_uploaded_file(org_a.id, _upload(b"x" * 1000))
        org_dir = os.path.join(str(questionnaire_storage_root), str(org_a.id))
        # No partial file left behind.
        assert os.listdir(org_dir) == []


class TestPathContainment:
    def test_rejects_traversal_stored_filename(self, org_a):
        with pytest.raises(QuestionnaireImportValidationError):
            import_storage.questionnaire_file_path(org_a.id, "../../etc/passwd")

    def test_rejects_slash_in_stored_filename(self, org_a):
        with pytest.raises(QuestionnaireImportValidationError):
            import_storage.questionnaire_file_path(org_a.id, "a/b.xlsx")

    def test_resolves_within_org_directory(self, org_a, questionnaire_storage_root):
        stored_filename, *_ = import_storage.store_and_hash_uploaded_file(
            org_a.id, _upload(b"PK\x03\x04" + b"x" * 50)
        )
        path = import_storage.questionnaire_file_path(org_a.id, stored_filename)
        root = os.path.realpath(str(questionnaire_storage_root))
        assert os.path.commonpath([root, path]) == root


class TestDeletion:
    def test_delete_stored_file_is_idempotent(self, org_a, questionnaire_storage_root):
        stored_filename, *_ = import_storage.store_and_hash_uploaded_file(
            org_a.id, _upload(b"PK\x03\x04" + b"x" * 50)
        )
        assert import_storage.delete_stored_file(org_a.id, stored_filename) is True
        assert import_storage.delete_stored_file(org_a.id, stored_filename) is False

    def test_delete_organisation_directory_removes_only_that_organisation(
        self, org_a, org_b, questionnaire_storage_root
    ):
        import_storage.store_and_hash_uploaded_file(org_a.id, _upload(b"PK\x03\x04" + b"x" * 50))
        import_storage.store_and_hash_uploaded_file(org_b.id, _upload(b"PK\x03\x04" + b"y" * 50))

        removed = import_storage.delete_organisation_questionnaire_directory(org_a.id)
        assert removed is True
        assert not os.path.isdir(os.path.join(str(questionnaire_storage_root), str(org_a.id)))
        assert os.path.isdir(os.path.join(str(questionnaire_storage_root), str(org_b.id)))

    def test_delete_nonexistent_organisation_directory_is_safe_noop(self, org_a, questionnaire_storage_root):
        assert import_storage.delete_organisation_questionnaire_directory(org_a.id) is False
