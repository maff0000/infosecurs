"""
Questionnaire artifact (original uploaded workbook) storage - M009A
(WO-M009A-SECURE-INGESTION-XLSX.md "Questionnaire storage - persistent and
recoverable", Correction 4).

Mirrors `evidence.storage`'s already-proven pattern exactly: a persistent,
Docker-mounted directory external to the application image; a private,
tenant-scoped (per-organisation) directory; opaque, server-generated
filenames (`uuid4().hex`); explicit `0640` file / `0750` directory
permissions; strict path containment on every read/delete; no static/media
public serving path, ever. Deliberately a SEPARATE storage root
(`QUESTIONNAIRE_STORAGE_ROOT`, never `EVIDENCE_STORAGE_ROOT`) - the WO's
own "conceptual artifact domain remains distinct from EvidenceItem"
(Correction 1) applies to the bytes on disk too, not only the DB model.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid

from config.env import require_env

from questionnaire.models import QuestionnaireImportValidationError

_CHUNK_SIZE = 64 * 1024

# Kept identical to questionnaire.upload_handler.MAX_UPLOAD_BYTES - this
# module's own streaming persist pass re-checks the same bound as a
# defence-in-depth backstop (WO-M009A Final Correction G: "never load the
# whole upload into memory first... once the counter exceeds 10 MiB: stop
# processing"), independent of whatever upload_handlers happened to be
# installed on the request that produced `uploaded_file`.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def questionnaire_storage_root():
    """
    Resolved LAZILY (same `require_env` discipline as
    `evidence.storage.evidence_storage_root()` - see that function's own
    docstring for the full reasoning: most requests never touch
    questionnaire storage at all, so this must not be a hard dependency at
    Django-startup time for every other page in the product).
    """
    return require_env("QUESTIONNAIRE_STORAGE_ROOT")


def safe_display_filename(name):
    """Identical discipline to `evidence.storage.safe_display_filename` -
    display metadata only, never used to build the on-disk storage path."""
    name = (name or "").strip().replace("\\", "/")
    name = name.rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable())
    return name[:255] or "questionnaire-file"


def store_and_hash_uploaded_file(organisation_id, uploaded_file):
    """
    ONE bounded streaming pass: persist `uploaded_file`'s bytes to a fresh,
    opaque filename inside this organisation's questionnaire storage
    directory, while computing SHA-256 and the running byte count, and
    while sniffing whether the stream is ZIP-shaped (the OOXML/ZIP local
    file header signature) - all in the same pass, mirroring
    `questionnaire.upload_handler`'s own single-pass discipline at the
    WSGI layer (Final Correction G). Aborts (deletes the partial file,
    raises `QuestionnaireImportValidationError`) the instant the running
    total exceeds `MAX_UPLOAD_BYTES` - this is a defence-in-depth re-check,
    independent of whether `request.upload_handlers` already aborted the
    stream earlier; it never trusts `uploaded_file.size` alone.

    Returns `(stored_filename, size_bytes, sha256_hex, is_zip_shaped)`.
    """
    root = questionnaire_storage_root()
    org_dir = os.path.join(root, str(organisation_id))
    os.makedirs(org_dir, mode=0o750, exist_ok=True)

    uploaded_file.seek(0)

    last_error = None
    for _ in range(5):
        stored_filename = f"{uuid.uuid4().hex}.xlsx"
        path = os.path.join(org_dir, stored_filename)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError as exc:
            last_error = exc
            continue

        hasher = hashlib.sha256()
        total = 0
        head = b""
        try:
            with os.fdopen(fd, "wb") as fh:
                for chunk in uploaded_file.chunks(chunk_size=_CHUNK_SIZE):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise QuestionnaireImportValidationError(
                            "Upload exceeds the 10 MiB questionnaire artifact limit."
                        )
                    hasher.update(chunk)
                    if len(head) < 4:
                        head += chunk[: 4 - len(head)]
                    fh.write(chunk)
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            raise

        if total == 0:
            try:
                os.remove(path)
            except OSError:
                pass
            raise QuestionnaireImportValidationError("The uploaded file is empty.")

        is_zip_shaped = head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
        return stored_filename, total, hasher.hexdigest(), is_zip_shaped

    raise QuestionnaireImportValidationError(
        "Could not allocate a unique questionnaire storage identifier."
    ) from last_error


def questionnaire_file_path(organisation_id, stored_filename):
    """
    Resolve a `QuestionnaireImport`'s own opaque `stored_filename` to a
    filesystem path strictly within that organisation's storage directory
    - identical containment discipline to
    `evidence.storage.evidence_file_path` (see that function's own
    docstring). The only inputs trusted are the organisation id (already
    tenant-checked by the caller) and the model's own DB column.
    """
    if (
        not stored_filename
        or "/" in stored_filename
        or "\\" in stored_filename
        or stored_filename in (".", "..")
    ):
        raise QuestionnaireImportValidationError("Invalid stored questionnaire filename.")

    root = questionnaire_storage_root()
    org_dir = os.path.realpath(os.path.join(root, str(organisation_id)))
    candidate = os.path.realpath(os.path.join(org_dir, stored_filename))

    if os.path.commonpath([org_dir, candidate]) != org_dir:
        raise QuestionnaireImportValidationError(
            "Resolved questionnaire path escaped the organisation's storage directory."
        )
    return candidate


def delete_stored_file(organisation_id, stored_filename):
    """
    Remove exactly one stored artifact's bytes (used when the security
    gate deterministically REJECTS or when an INFECTED scan result is
    confirmed - WO-M009A "Original-artifact retention", Final Correction
    H: hostile/invalid bytes "may be deleted... immediately" once rejected
    - never for `security_gate_failed`, which retains bytes for retry).
    Idempotent: a missing file is a safe no-op.
    """
    path = questionnaire_file_path(organisation_id, stored_filename)
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False


def delete_organisation_questionnaire_directory(organisation_id):
    """
    Remove the WHOLE questionnaire storage directory for one organisation
    (Customer Zero reset filesystem cleanup - WO-M009A "Customer Zero
    reset reconciliation"). Identical containment + idempotency discipline
    to `evidence.storage.delete_organisation_evidence_directory` - see
    that function's own docstring for the full reasoning. Never touches
    the database; called only after the DB transaction that deletes this
    organisation's `QuestionnaireImport` rows has already committed.
    """
    root = os.path.realpath(questionnaire_storage_root())
    org_dir = os.path.realpath(os.path.join(root, str(organisation_id)))

    if org_dir == root or os.path.commonpath([root, org_dir]) != root:
        raise QuestionnaireImportValidationError(
            "Resolved questionnaire directory escaped the storage root; refusing to delete."
        )

    if not os.path.isdir(org_dir):
        return False

    shutil.rmtree(org_dir)
    return True
