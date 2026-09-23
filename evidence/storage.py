"""
File evidence storage: content-based type detection, streaming SHA-256,
opaque on-disk naming, and strict path resolution for downloads.

PID §9 (Private file evidence - Beta boundary) and §22 (security controls):
accepted types are PDF, PNG, JPEG and plain text only, detected from actual
file *content* - never from the client-supplied filename or Content-Type
header. Default max size is 10 MiB.

Dependency decision (recorded here, and in the dispatch report): this
detects all four signatures with the standard library only - no
`python-magic`/`filetype` dependency was added. PDF, PNG and JPEG each have
an unambiguous fixed magic-byte header; a hand-rolled prefix check is exactly
as reliable as a library for these three well-known signatures and avoids
the build-reproducibility doctrine's full pip-compile hash-relock/security-
scan cycle (docs/delivery/BUILD-REPRODUCIBILITY.md) for a three-line check.
Plain text is detected by streaming the whole file through an incremental
UTF-8 decoder (stdlib `codecs`) plus a NUL-byte heuristic, which is the
standard, dependency-free way to distinguish text from binary content.

`EVIDENCE_STORAGE_ROOT` (PID §9/§21) is resolved *lazily*, only by the
functions in this module that actually touch evidence bytes - see
`evidence_storage_root()`'s docstring for why, matching the existing
AI_GATEWAY_BASE_URL precedent in this codebase.
"""
import codecs
import hashlib
import os
import uuid

from config.env import require_env

from evidence.exceptions import EvidenceValidationError
from evidence.models import FILE_TYPE_JPEG, FILE_TYPE_PDF, FILE_TYPE_PNG, FILE_TYPE_TEXT

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB (PID §9 default max size)
_CHUNK_SIZE = 64 * 1024

_PDF_SIGNATURE = b"%PDF-"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"

FILE_TYPE_EXTENSIONS = {
    FILE_TYPE_PDF: "pdf",
    FILE_TYPE_PNG: "png",
    FILE_TYPE_JPEG: "jpg",
    FILE_TYPE_TEXT: "txt",
}

CONTENT_TYPES = {
    FILE_TYPE_PDF: "application/pdf",
    FILE_TYPE_PNG: "image/png",
    FILE_TYPE_JPEG: "image/jpeg",
    FILE_TYPE_TEXT: "text/plain; charset=utf-8",
}


def evidence_storage_root():
    """
    The persistent, Docker-mounted directory evidence bytes live under
    (PID §9: "a persistent Docker-mounted path external to the immutable
    application image" - e.g. `/data/evidence`).

    Resolved lazily (`require_env`, called here rather than at Django
    startup): organisation/profile/baseline/key-asset/risk pages, the
    Evidence list page, and even creating *external-reference* evidence
    never touch storage at all - only an actual file upload or file
    download does. Requiring this at import/startup time would make every
    other page in the product depend on a config value most requests never
    need, which is exactly the failure mode `AI_GATEWAY_BASE_URL` in this
    same codebase already avoids for the same reason (see .env.example).
    It still fails loudly (`require_env`, not a silent default) at the
    moment it is actually needed.
    """
    return require_env("EVIDENCE_STORAGE_ROOT")


def detect_and_hash(uploaded_file):
    """
    Stream the uploaded file exactly once: enforce the size limit as bytes
    actually arrive (never trust the browser-reported size alone), compute
    SHA-256, and detect the real file type from content. Returns
    ``(file_type, byte_size, sha256_hex)`` or raises
    ``EvidenceValidationError``.
    """
    uploaded_file.seek(0)
    hasher = hashlib.sha256()
    total = 0
    head = b""
    contains_null = False

    for chunk in uploaded_file.chunks(chunk_size=_CHUNK_SIZE):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise EvidenceValidationError(
                "This file is larger than the 10 MiB evidence upload limit."
            )
        hasher.update(chunk)
        if len(head) < 16:
            head += chunk[: 16 - len(head)]
        if not contains_null and b"\x00" in chunk:
            contains_null = True

    if total == 0:
        raise EvidenceValidationError("The uploaded file is empty.")

    if head.startswith(_PDF_SIGNATURE):
        file_type = FILE_TYPE_PDF
    elif head.startswith(_PNG_SIGNATURE):
        file_type = FILE_TYPE_PNG
    elif head.startswith(_JPEG_SIGNATURE):
        file_type = FILE_TYPE_JPEG
    elif not contains_null and _is_utf8_text(uploaded_file):
        file_type = FILE_TYPE_TEXT
    else:
        raise EvidenceValidationError(
            "This file's content is not a PDF, PNG, JPEG or plain-text file "
            "that Infosecurs recognises. Only these four evidence types are "
            "accepted, and they are checked by content, not by filename or "
            "browser-reported type."
        )

    uploaded_file.seek(0)
    return file_type, total, hasher.hexdigest()


def _is_utf8_text(uploaded_file):
    """
    Whole-file incremental UTF-8 decode (not per-chunk independent decodes,
    which would false-negative on a multi-byte character split across a
    chunk boundary).
    """
    uploaded_file.seek(0)
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        for chunk in uploaded_file.chunks(chunk_size=_CHUNK_SIZE):
            decoder.decode(chunk)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True


def safe_display_filename(name):
    """
    A safe, storable display filename for the *original* upload name -
    strips any path component and non-printable characters, bounded to the
    field length. This is display metadata only; it is never used to build
    the on-disk storage path (see store_uploaded_file/stored_filename).
    """
    name = (name or "").strip().replace("\\", "/")
    name = name.rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable())
    return name[:255] or "evidence-file"


def store_uploaded_file(organisation_id, uploaded_file, file_type):
    """
    Persist the uploaded bytes under an opaque, server-generated filename
    inside a per-organisation directory of the externally-mounted evidence
    root. Never derived from the original filename (PID §9/§10). Never
    overwrites an existing file in place: `O_EXCL` makes a name collision
    fail loudly and retry with a fresh identifier, rather than silently
    clobbering existing evidence bytes.

    Returns the opaque stored filename (bare name, no directory component)
    to be recorded on the EvidenceItem.
    """
    root = evidence_storage_root()
    org_dir = os.path.join(root, str(organisation_id))
    os.makedirs(org_dir, mode=0o750, exist_ok=True)

    extension = FILE_TYPE_EXTENSIONS[file_type]
    uploaded_file.seek(0)

    last_error = None
    for _ in range(5):
        stored_filename = f"{uuid.uuid4().hex}.{extension}"
        path = os.path.join(org_dir, stored_filename)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError as exc:
            last_error = exc
            continue
        try:
            with os.fdopen(fd, "wb") as fh:
                for chunk in uploaded_file.chunks(chunk_size=_CHUNK_SIZE):
                    fh.write(chunk)
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            raise
        return stored_filename

    raise EvidenceValidationError(
        "Could not allocate a unique evidence storage identifier."
    ) from last_error


def evidence_file_path(organisation_id, stored_filename):
    """
    Resolve an EvidenceItem's own opaque `stored_filename` to a filesystem
    path strictly within that organisation's storage directory.

    The only inputs this function trusts are the organisation id (already
    tenant-checked by the caller via `get_member_organisation_or_404`) and
    the EvidenceItem's own DB column - never a path fragment from the URL
    or query string (PID §9). Defence in depth even so (PID §9 "test it
    anyway"): a bare-filename check plus a resolved-path containment check,
    so even a `stored_filename` value that should never occur (e.g. a
    corrupted/tampered DB row) cannot escape the organisation's directory.
    """
    if (
        not stored_filename
        or "/" in stored_filename
        or "\\" in stored_filename
        or stored_filename in (".", "..")
    ):
        raise EvidenceValidationError("Invalid stored evidence filename.")

    root = evidence_storage_root()
    org_dir = os.path.realpath(os.path.join(root, str(organisation_id)))
    candidate = os.path.realpath(os.path.join(org_dir, stored_filename))

    if os.path.commonpath([org_dir, candidate]) != org_dir:
        raise EvidenceValidationError(
            "Resolved evidence path escaped the organisation's storage directory."
        )
    return candidate
