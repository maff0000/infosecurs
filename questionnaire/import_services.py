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
from questionnaire import csv_import, import_storage, security_gate, xlsx_extraction
from questionnaire.models import (
    QuestionnaireImport,
    QuestionnaireImportQuestion,
    QuestionnaireImportValidationError,
    QuestionnaireQuestion,
)
from questionnaire.scanner import STATE_CLEAN, STATE_INFECTED, get_scanner


class SecurityGateTransitionError(Exception):
    """Raised if a caller asks for a transition the current state does not
    permit (e.g. `retry_security_gate` on an import that is not currently
    `security_gate_failed`) - a programming-error guard, not a normal user
    -facing validation error."""


def _validate_supersedes_target(supersedes, organisation):
    """
    Fail-closed tenant guard for `ingest_questionnaire_import(supersedes=
    ...)` (Central Architecture Blocker 1 correction to PR #102, 2026-10-
    11). A `supersedes` reference that is not an already-persisted
    `QuestionnaireImport` row belonging to this EXACT SAME organisation is
    a security-relevant input and must raise
    `QuestionnaireImportValidationError` - never silently ignored, never
    silently proceeding with the new row's `supersedes` landing as `NULL`
    while the rest of the ingest otherwise succeeds, and never permitting
    a cross-tenant `supersedes` linkage to be created even transiently.

    Deliberately a single combined (pk, organisation) existence query,
    never trusting the in-memory `supersedes.organisation_id` attribute on
    its own - the same tenant-isolation discipline as
    `_get_member_import_or_404` elsewhere in this app (a foreign/invalid
    reference just fails closed, never confirming the row exists at all,
    let alone under a different tenant). This also correctly rejects an
    UNSAVED `QuestionnaireImport` instance: `QuestionnaireImport.id` is a
    `UUIDField(default=uuid.uuid4)`, so an in-memory instance already has
    a non-`None` `.pk` before `.save()` is ever called - `supersedes.pk is
    None` would NOT detect that case; only a real DB lookup does.

    This is deliberately a service-layer-only contract: Central
    Architecture's explicit ruling on this correction is that M009A adds
    NO re-upload/supersession UI - the upload surface stays exactly as
    minimal as it already is. This function exists so the Work Order's
    own required "legitimate re-upload/`supersedes` case" evaluation
    corpus item is provable against the real domain/service contract
    without any UI change.
    """
    exists = QuestionnaireImport.objects.filter(pk=supersedes.pk, organisation=organisation).exists()
    if not exists:
        # Fail the WHOLE ingest attempt closed before anything is created -
        # consistent with how every other security-gate rejection in this
        # module already behaves (never a partial/degraded success). One
        # message covers both "does not exist" and "belongs to another
        # organisation" deliberately - never confirming to the caller
        # which case applies, mirroring this app's own tenant-isolation
        # discipline of never distinguishing 404-shaped outcomes.
        raise QuestionnaireImportValidationError(
            "supersedes must reference an already-persisted QuestionnaireImport "
            "belonging to this same organisation."
        )


def ingest_questionnaire_import(
    *,
    organisation,
    actor,
    uploaded_file,
    original_filename,
    supersedes=None,
    declared_format=QuestionnaireImport.FILE_FORMAT_XLSX,
):
    """
    Step 1 of the pipeline: stream, hash and store the uploaded bytes
    (`questionnaire.import_storage` - ONE bounded pass, Final Correction
    G), create the `QuestionnaireImport` row, and immediately run the full
    security gate + scanner synchronously (Correction 16 - no async
    infrastructure). Returns the final `QuestionnaireImport` (whatever
    state the pipeline above ended at).

    `declared_format` (M009B Increment 1, WO-M009B-FOUNDATIONS-READINESS-
    CSV-BULK-ORCHESTRATION.md §2.2a) is the caller's (the view's) own
    declaration of which upload action the customer used - `FILE_FORMAT_
    XLSX` (the default, preserving every existing caller's byte-identical
    behaviour) or `FILE_FORMAT_CSV`. This is NEVER trusted blindly against
    the real bytes - see the `is_zip_shaped` cross-check below, §2.2a step
    2's binding requirement.

    If `supersedes` is supplied, it is validated FIRST - before any bytes
    are streamed/stored and before any new `QuestionnaireImport` row is
    created - via `_validate_supersedes_target` above (Central Architecture
    Blocker 1 correction, 2026-10-11): it must be a persisted
    `QuestionnaireImport` belonging to this exact same `organisation`. A
    foreign-organisation (or otherwise invalid) reference raises
    `QuestionnaireImportValidationError` and the whole ingest attempt fails
    closed for those specific input bytes - no row is created, nothing is
    stored, and no cross-tenant relationship is ever created. On a
    legitimate same-organisation `supersedes`, the prior import and all of
    its questions are never touched - only the NEW row's own `supersedes`
    FK is set.

    The early, cheapest-possible deterministic rejection is now format-
    conditional (§2.2a step 2), never merely removed - the row is still
    created either way (so the rejection itself is durably auditable), but
    is created ALREADY `security_gate_rejected` and the bytes are deleted
    immediately, and the heavier gate below never runs:

      - `declared_format == FILE_FORMAT_XLSX` and the bytes are NOT
        ZIP-shaped - rejected exactly as today, byte-for-byte unchanged
        (reason `"not_a_zip_or_ooxml_container"` - WO-M009A evaluation
        corpus: "a non-XLSX file renamed with a .xlsx extension").
      - `declared_format == FILE_FORMAT_CSV` and the bytes ARE ZIP-shaped
        - a declared-format mismatch is itself hostile/malformed input and
        fails closed too (reason `"declared_csv_but_zip_shaped"`) - never
        silently reinterpreted as an XLSX upload.

    Every other combination (XLSX+zip-shaped, the existing case; CSV+not-
    zip-shaped, the new, normal CSV case) proceeds to the structural gate.
    """
    if supersedes is not None:
        _validate_supersedes_target(supersedes, organisation)

    stored_filename, size_bytes, sha256_hex, is_zip_shaped = (
        import_storage.store_and_hash_uploaded_file(organisation.id, uploaded_file)
    )
    safe_name = import_storage.safe_display_filename(original_filename)

    is_declared_xlsx = declared_format == QuestionnaireImport.FILE_FORMAT_XLSX
    is_declared_csv = declared_format == QuestionnaireImport.FILE_FORMAT_CSV

    if is_zip_shaped:
        detected_content_type = "application/zip"
    elif is_declared_csv:
        detected_content_type = "text/csv"
    else:
        detected_content_type = "application/octet-stream"

    format_mismatch_reason = None
    if is_declared_xlsx and not is_zip_shaped:
        format_mismatch_reason = "not_a_zip_or_ooxml_container"
    elif is_declared_csv and is_zip_shaped:
        format_mismatch_reason = "declared_csv_but_zip_shaped"

    with transaction.atomic():
        import_record = QuestionnaireImport.objects.create(
            organisation=organisation,
            uploaded_by=actor,
            original_filename=safe_name,
            stored_filename=stored_filename,
            detected_content_type=detected_content_type,
            file_format=declared_format,
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

        if format_mismatch_reason is not None:
            import_record.security_gate_result = {
                "reason": format_mismatch_reason,
                "detail": (
                    "The uploaded bytes do not begin with a ZIP/OOXML signature."
                    if format_mismatch_reason == "not_a_zip_or_ooxml_container"
                    else "The upload was declared as CSV, but the bytes are ZIP-shaped - "
                    "a declared-format mismatch is treated as hostile/malformed input."
                ),
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
                metadata={"reason": format_mismatch_reason},
            )

    if format_mismatch_reason is not None:
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

    # M009B Increment 1 (§2.2a step 3) - dispatches on the already-
    # persisted `file_format`, never re-derived from the bytes. XLSX
    # calls `security_gate.run_container_gate` exactly as today (never
    # touched for CSV - binding global STOP condition: CSV must never
    # reach the OOXML/ZIP-only container gate). CSV calls the new,
    # separate `csv_import.validate_csv_structure`, returning the
    # identically-shaped `GateResult` - every line of code below this
    # call needs zero change regardless of which one ran.
    try:
        if import_record.file_format == QuestionnaireImport.FILE_FORMAT_CSV:
            gate_result = csv_import.validate_csv_structure(file_path)
        else:
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

    # M009B Increment 1 (§2.2a step 5) - same dispatch discipline as the
    # gate call above. CSV's `extract_candidates` returns the identically
    # -shaped `ExtractionOutcome` (reused directly from `xlsx_extraction`
    # - see `questionnaire.csv_import`'s own module docstring).
    try:
        if import_record.file_format == QuestionnaireImport.FILE_FORMAT_CSV:
            outcome = csv_import.extract_candidates(file_path)
        else:
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
                    if import_record.file_format == QuestionnaireImport.FILE_FORMAT_CSV:
                        # CSV source_location has no sheet_name/question_cell
                        # keys (questionnaire.csv_import's own, separate
                        # schema - see that module's extract_candidates) -
                        # build a CSV-shaped label rather than reusing the
                        # XLSX-only .get(..., "") keys below unmodified.
                        source_label = (
                            f"{import_record.original_filename} - "
                            f"row {candidate.source_location.get('row', '')}"
                        )[:255]
                    else:
                        source_label = (
                            f"{import_record.original_filename} - "
                            f"{candidate.source_location.get('sheet_name', '')} "
                            f"{candidate.source_location.get('question_cell', '')}"
                        )[:255]
                    linked_question = QuestionnaireQuestion.objects.create(
                        organisation=organisation,
                        question_text=candidate.raw_extracted_text,
                        source_label=source_label,
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
                    # M009B Increment 1 (§2.4) - always None/NULL for an
                    # XLSX candidate (that dataclass has no such
                    # attribute at all), so this is byte-identical to the
                    # XLSX path's pre-existing behaviour.
                    customer_provided_answer_text=getattr(
                        candidate, "customer_provided_answer_text", None
                    ),
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
