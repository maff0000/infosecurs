"""
Evidence creation and lifecycle operations. Views call these rather than
touching EvidenceItem.objects.create()/save() directly, so the supersede/
withdraw rules and the file-ingest sequence (detect -> store -> record) live
in exactly one place.
"""
from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
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
        _apply_supersession(supersedes, item, actor)

    record_event(
        organisation,
        ActivityEvent.EVENT_EVIDENCE_CREATED,
        actor=actor,
        related_object_type="evidence_item",
        related_object_id=str(item.id),
        metadata={"kind": "file", "title": item.title},
    )

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
        _apply_supersession(supersedes, item, actor)

    record_event(
        organisation,
        ActivityEvent.EVENT_EVIDENCE_CREATED,
        actor=actor,
        related_object_type="evidence_item",
        related_object_id=str(item.id),
        metadata={"kind": "external_reference", "title": item.title},
    )

    return item


def _apply_supersession(old_item, new_item, actor):
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

    # Always called from inside one of the two @transaction.atomic create_*
    # functions above, so this event write shares that same transaction
    # (PID §17) without needing its own atomic block here.
    record_event(
        old_item.organisation,
        ActivityEvent.EVENT_EVIDENCE_SUPERSEDED,
        actor=actor,
        related_object_type="evidence_item",
        related_object_id=str(old_item.id),
        metadata={"superseded_by": str(new_item.id)},
    )


@transaction.atomic
def withdraw_evidence(item, actor):
    """Mark an active evidence item withdrawn. Never deletes it."""
    if item.status != EvidenceItem.STATUS_ACTIVE:
        raise EvidenceValidationError("Only active evidence can be withdrawn.")
    item.status = EvidenceItem.STATUS_WITHDRAWN
    item.save(update_fields=["status", "updated_at"])

    record_event(
        item.organisation,
        ActivityEvent.EVENT_EVIDENCE_WITHDRAWN,
        actor=actor,
        related_object_type="evidence_item",
        related_object_id=str(item.id),
        metadata={},
    )
