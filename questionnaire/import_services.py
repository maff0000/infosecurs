"""
M009A governed import lifecycle services
(WO-M009A-SECURE-INGESTION-XLSX.md "Service-owned state transitions"
(Correction 14)).

Views NEVER mutate `security_gate_status`, `status`, `extraction_summary`,
or any artifact-identity field directly - every lifecycle transition goes
through exactly one of the functions below. Each function performs its
own DB write(s) inside `transaction.atomic()` and returns the refreshed
`QuestionnaireImport`.

Pipeline, matching WO-M009A's own lifecycle diagram exactly:

    ingest_questionnaire_import()      uploaded -> security_gate_pending
        -> run_security_gate()        -> security_gate_rejected (terminal)
                                       -> security_gate_failed (retryable)
                                       -> extracting -> _run_extraction()
                                                           -> extracted
                                                           -> extraction_failed
    retry_security_gate()              security_gate_failed -> (same as above)
"""
from __future__ import annotations

from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
from questionnaire import import_storage, security_gate, xlsx_extraction
from questionnaire.models import (
    QuestionnaireImport,
    QuestionnaireImportQuestion,
    QuestionnaireQuestion,
)
from questionnaire.scanner import STATE_CLEAN, STATE_INFECTED, get_scanner


class SecurityGateTransitionError(Exception):
    """Raised if a caller asks for a transition the current state does not
    permit (e.g. `retry_security_gate` on an import that is not currently
    `security_gate_failed`) - a programming-error guard, not a normal user
    -facing validation error."""


def ingest_questionnaire_import(
    *, organisation, actor, uploaded_file, original_filename, supersedes=None
):
    """
    Step 1 of the pipeline: stream, hash and store the uploaded bytes
    (`questionnaire.import_storage` - ONE bounded pass, Final Correction
    G), create the `QuestionnaireImport` row, and immediately run the full
    security gate + scanner synchronously (Correction 16 - no async
    infrastructure). Returns the final `QuestionnaireImport` (whatever
    state the pipeline above ended at).

    If the uploaded bytes are not even ZIP-shaped (the cheapest possible
    deterministic rejection - WO-M009A evaluation corpus: "a non-XLSX file
    renamed with a .xlsx extension"), the row is still created (so the
    rejection itself is durably auditable) but is created ALREADY
    `security_gate_rejected` and the bytes are deleted immediately - the
    heavier container gate below never runs against content that could
    not possibly be a ZIP/OOXML container in the first place.
    """
    stored_filename, size_bytes, sha256_hex, is_zip_shaped = (
        import_storage.store_and_hash_uploaded_file(organisation.id, uploaded_file)
    )
    safe_name = import_storage.safe_display_filename(original_filename)

    with transaction.atomic():
        import_record = QuestionnaireImport.objects.create(
            organisation=organisation,
            uploaded_by=actor,
            original_filename=safe_name,
            stored_filename=stored_filename,
            detected_content_type="application/zip" if is_zip_shaped else "application/octet-stream",
            file_format=QuestionnaireImport.FILE_FORMAT_XLSX,
            sha256_hash=sha256_hex,
            size_bytes=size_bytes,
            security_gate_status=QuestionnaireImport.SECURITY_GATE_PENDING,
            security_gate_result={},
            status=QuestionnaireImport.STATUS_UPLOADED,
            supersedes=supersedes,
        )
        record_event(
            organisation,
            ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_UPLOADED,
            actor=actor,
            related_object_type="questionnaire_import",
            related_object_id=str(import_record.id),
            metadata={"original_filename": safe_name, "size_bytes": size_bytes},
        )

        if not is_zip_shaped:
            import_record.security_gate_result = {
                "reason": "not_a_zip_or_ooxml_container",
                "detail": "The uploaded bytes do not begin with a ZIP/OOXML signature.",
            }
            import_record.security_gate_status = QuestionnaireImport.SECURITY_GATE_REJECTED
            import_record.status = QuestionnaireImport.STATUS_SECURITY_GATE_REJECTED
            import_record.save(
                update_fields=["security_gate_result", "security_gate_status", "status", "updated_at"]
            )
            record_event(
                organisation,
                ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_GATE_REJECTED,
                actor=actor,
                related_object_type="questionnaire_import",
                related_object_id=str(import_record.id),
                metadata={"reason": "not_a_zip_or_ooxml_container"},
            )

    if not is_zip_shaped:
        import_storage.delete_stored_file(organisation.id, stored_filename)
        return import_record

    import_record.status = QuestionnaireImport.STATUS_SECURITY_GATE_PENDING
    import_record.save(update_fields=["status", "updated_at"])

    return _run_gate_and_scanner(import_record, actor=actor)


def retry_security_gate(import_record, *, actor):
    """
    Explicit, distinct retry operation for an import currently
    `security_gate_failed` (WO-M009A "Import lifecycle": "An explicit
    service operation for retrying the security gate is required... a
    scanner result of UNAVAILABLE or ERROR must... retain the uploaded
    bytes privately so the gate can be retried without forcing
    re-upload."). Never usable from any other state.
    """
    if import_record.security_gate_status != QuestionnaireImport.SECURITY_GATE_FAILED:
        raise SecurityGateTransitionError(
            f"QuestionnaireImport {import_record.id} is not security_gate_failed - cannot retry."
        )
    return _run_gate_and_scanner(import_record, actor=actor)


def _run_gate_and_scanner(import_record, *, actor):
    organisation = import_record.organisation
    file_path = import_storage.questionnaire_file_path(
        organisation.id, import_record.stored_filename
    )

    try:
        gate_result = security_gate.run_container_gate(file_path)
    except Exception as exc:
        # An unexpected exception from the container gate is treated as an
        # infrastructure failure, never a silent pass and never a false
        # "deterministic rejection" of the customer's own bytes (WO-M009A:
        # "Do not treat infrastructure failure as evidence that a
        # customer's workbook itself was malicious").
        return _transition_to_gate_failed(
            import_record,
            actor=actor,
            result={"reason": "container_gate_infrastructure_error", "detail": str(exc)},
        )

    if not gate_result.accepted:
        return _transition_to_gate_rejected(
            import_record,
            actor=actor,
            result={
                "reason": "container_gate_rejected",
                "findings": list(gate_result.reasons),
                "structural_summary": gate_result.structural_summary,
            },
        )

    scanner = get_scanner()
    scan_result = scanner.scan_file(file_path)

    if scan_result.state == STATE_CLEAN:
        with transaction.atomic():
            import_record.security_gate_result = {
                "reason": "clean",
                "structural_summary": gate_result.structural_summary,
                "scanner": scan_result.provenance,
            }
            import_record.security_gate_status = QuestionnaireImport.SECURITY_GATE_PASSED
            import_record.status = QuestionnaireImport.STATUS_EXTRACTING
            import_record.save(
                update_fields=["security_gate_result", "security_gate_status", "status", "updated_at"]
            )
            record_event(
                organisation,
                ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_GATE_PASSED,
                actor=actor,
                related_object_type="questionnaire_import",
                related_object_id=str(import_record.id),
                metadata={"scanner_backend": scan_result.provenance.get("backend")},
            )
        return _run_extraction(import_record, actor=actor)

    if scan_result.state == STATE_INFECTED:
        return _transition_to_gate_rejected(
            import_record,
            actor=actor,
            result={
                "reason": "malware_detected",
                "structural_summary": gate_result.structural_summary,
                "scanner": scan_result.provenance,
                "signature": scan_result.infected_signature,
            },
        )

    # UNAVAILABLE or ERROR - fail closed, retryable, bytes retained.
    return _transition_to_gate_failed(
        import_record,
        actor=actor,
        result={
            "reason": f"scanner_{scan_result.state.lower()}",
            "structural_summary": gate_result.structural_summary,
            "scanner": scan_result.provenance,
        },
    )


def _transition_to_gate_rejected(import_record, *, actor, result):
    organisation = import_record.organisation
    with transaction.atomic():
        import_record.security_gate_result = result
        import_record.security_gate_status = QuestionnaireImport.SECURITY_GATE_REJECTED
        import_record.status = QuestionnaireImport.STATUS_SECURITY_GATE_REJECTED
        import_record.save(
            update_fields=["security_gate_result", "security_gate_status", "status", "updated_at"]
        )
        record_event(
            organisation,
            ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_GATE_REJECTED,
            actor=actor,
            related_object_type="questionnaire_import",
            related_object_id=str(import_record.id),
            metadata={"reason": result.get("reason")},
        )
    # Deterministic rejection - hostile/invalid bytes removed immediately
    # (WO-M009A Final Correction H's documented, implementation's-choice
    # cleanup timing). Audit metadata above is permanent regardless.
    import_storage.delete_stored_file(organisation.id, import_record.stored_filename)
    return import_record


def _transition_to_gate_failed(import_record, *, actor, result):
    organisation = import_record.organisation
    with transaction.atomic():
        import_record.security_gate_result = result
        import_record.security_gate_status = QuestionnaireImport.SECURITY_GATE_FAILED
        import_record.status = QuestionnaireImport.STATUS_SECURITY_GATE_FAILED
        import_record.save(
            update_fields=["security_gate_result", "security_gate_status", "status", "updated_at"]
        )
        record_event(
            organisation,
            ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_GATE_FAILED,
            actor=actor,
            related_object_type="questionnaire_import",
            related_object_id=str(import_record.id),
            metadata={"reason": result.get("reason")},
        )
    # NEVER deleted - security_gate_failed retains bytes privately so the
    # gate can be retried without forcing re-upload (WO-M009A).
    return import_record


def _run_extraction(import_record, *, actor):
    organisation = import_record.organisation
    file_path = import_storage.questionnaire_file_path(
        organisation.id, import_record.stored_filename
    )

    try:
        outcome = xlsx_extraction.extract_candidates(file_path)
    except Exception as exc:
        outcome = xlsx_extraction.ExtractionOutcome(
            status="extraction_failed",
            failure_reason=f"unexpected_extraction_error: {exc}",
            summary={},
            candidates=[],
        )

    with transaction.atomic():
        if outcome.status == "extracted":
            for candidate in outcome.candidates:
                linked_question = None
                if candidate.disposition == QuestionnaireImportQuestion.DISPOSITION_QUESTION:
                    linked_question = QuestionnaireQuestion.objects.create(
                        organisation=organisation,
                        question_text=candidate.raw_extracted_text,
                        source_label=(
                            f"{import_record.original_filename} - "
                            f"{candidate.source_location.get('sheet_name', '')} "
                            f"{candidate.source_location.get('question_cell', '')}"
                        )[:255],
                        created_by=actor,
                    )
                QuestionnaireImportQuestion.objects.create(
                    import_record=import_record,
                    question=linked_question,
                    raw_extracted_text=candidate.raw_extracted_text,
                    source_location=candidate.source_location,
                    extraction_order=candidate.extraction_order,
                    extraction_status=candidate.extraction_status,
                    extraction_error=candidate.extraction_error,
                    disposition=candidate.disposition,
                )
            import_record.extraction_summary = outcome.summary
            import_record.status = QuestionnaireImport.STATUS_EXTRACTED
            import_record.save(update_fields=["extraction_summary", "status", "updated_at"])
            record_event(
                organisation,
                ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_EXTRACTED,
                actor=actor,
                related_object_type="questionnaire_import",
                related_object_id=str(import_record.id),
                metadata={"question_count": outcome.summary.get("question_count", 0)},
            )
        else:
            summary = dict(outcome.summary)
            summary["failure_reason"] = outcome.failure_reason
            import_record.extraction_summary = summary
            import_record.status = QuestionnaireImport.STATUS_EXTRACTION_FAILED
            import_record.save(update_fields=["extraction_summary", "status", "updated_at"])
            record_event(
                organisation,
                ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_EXTRACTION_FAILED,
                actor=actor,
                related_object_type="questionnaire_import",
                related_object_id=str(import_record.id),
                metadata={"reason": outcome.failure_reason},
            )

    return import_record


__all__ = [
    "SecurityGateTransitionError",
    "ingest_questionnaire_import",
    "retry_security_gate",
]
