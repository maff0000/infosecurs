"""
Evidence creation and lifecycle operations. Views call these rather than
touching EvidenceItem.objects.create()/save() directly, so the supersede/
withdraw rules and the file-ingest sequence (detect -> store -> record) live
in exactly one place.
"""
from django.db import transaction

from evidence.exceptions import EvidenceValidationError
from evidence.models import EvidenceItem
from evidence.storage import detect_and_hash, safe_display_filename, store_uploaded_file


@transaction.atomic
def create_file_evidence(
    *,
    organisation,
    actor,
    title,
    description,
    source_label,
    observed_at,
    valid_until,
    uploaded_file,
    supersedes=None,
):
    """
    Validate and store an uploaded file (content-checked, streamed,
    hashed - see evidence.storage), then record it as a new EvidenceItem.
    If `supersedes` is given (an active EvidenceItem already verified to
    belong to this organisation), the old item is atomically marked
    superseded and pointed at the new one - it is never mutated in place
    and never deleted (PID §6.1).
    """
    file_type, byte_size, sha256_hex = detect_and_hash(uploaded_file)
    stored_filename = store_uploaded_file(organisation.id, uploaded_file, file_type)

    item = EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_FILE,
        title=title,
        description=description,
        source_label=source_label,
        observed_at=observed_at,
        valid_until=valid_until,
        original_filename=safe_display_filename(getattr(uploaded_file, "name", "")),
        stored_filename=stored_filename,
        file_type=file_type,
        byte_size=byte_size,
        sha256=sha256_hex,
        recorded_by=actor,
    )

    if supersedes is not None:
        _apply_supersession(supersedes, item)

    return item


@transaction.atomic
def create_external_reference_evidence(
    *,
    organisation,
    actor,
    title,
    description,
    source_label,
    observed_at,
    valid_until,
    reference_url,
    supersedes=None,
):
    """
    Record an external-reference EvidenceItem. PID §6.3: the URL is stored
    and validated as syntactically sane only - it is never fetched or
    crawled.
    """
    item = EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title=title,
        description=description,
        source_label=source_label,
        observed_at=observed_at,
        valid_until=valid_until,
        reference_url=reference_url,
        recorded_by=actor,
    )

    if supersedes is not None:
        _apply_supersession(supersedes, item)

    return item


def _apply_supersession(old_item, new_item):
    if old_item.organisation_id != new_item.organisation_id:
        # Defence in depth: views.py resolves `supersedes` scoped to the
        # same organisation before this is ever called, so this should be
        # unreachable in product code - but a service function must not
        # trust its caller alone for a cross-tenant write.
        raise EvidenceValidationError(
            "Cannot supersede evidence belonging to a different organisation."
        )
    if old_item.status != EvidenceItem.STATUS_ACTIVE:
        raise EvidenceValidationError("Only active evidence can be superseded.")

    old_item.status = EvidenceItem.STATUS_SUPERSEDED
    old_item.superseded_by = new_item
    old_item.save(update_fields=["status", "superseded_by", "updated_at"])


def withdraw_evidence(item):
    """Mark an active evidence item withdrawn. Never deletes it."""
    if item.status != EvidenceItem.STATUS_ACTIVE:
        raise EvidenceValidationError("Only active evidence can be withdrawn.")
    item.status = EvidenceItem.STATUS_WITHDRAWN
    item.save(update_fields=["status", "updated_at"])
