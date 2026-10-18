"""
M010D - Deterministic Security Review Scheduler: emission + reconciliation
(docs/pids/M010D-REVIEW-RULES-SCHEDULER.md §2-§5, docs/architecture/
M010-DATA-WORKFLOW-CONTRACTS.md §4-§5).

This is the ONLY module in this package that writes anything. Every write
goes through `security_tasks.services.create_task`/`transition_task` -
the SAME canonical, already-tested, atomic write paths every other caller
in this app uses (M010D PID §2 "Task service upserts single occurrence
atomically"; this package's own scope note "a rule candidate upserts via
the existing atomic create_task path (never a new write path)"). Nothing
here calls `SecurityTask.objects.create()`/`.save()` directly.

Occurrence key (M010D PID §2, verbatim): "derive stable
`(organisation, rule_id, source_object, due_occurrence)` key". The
organisation is already the first argument/FK on every call this module
makes (and is part of `SecurityTask`'s own partial unique constraint), so
the STRING this module builds carries exactly the other three:

    occurrence_key = f"{rule_id}:{source_object_id}:{due_occurrence}"

`idempotency_key` is derived deterministically from that same
`occurrence_key` (`"rules_engine:" + occurrence_key`) - every repeated
scheduler run for the same occurrence presents the SAME idempotency_key,
which is exactly what "this is the same logical request, run again"
means; it is not the free, caller-chosen token a human form submission
uses, but reusing the field for a deterministic rules-engine retry token
is precisely what the data contract's own idempotency rule requires
("never generate a new occurrence key on retry").

Reconciliation policy for "source review date changed" (M010-DATA-
WORKFLOW-CONTRACTS.md §2's explicit menu of three options - this package
picks the third): if a still-OPEN `rules_engine` task already exists for
the SAME `(organisation, task_kind, source_object_id)` but a DIFFERENT
`occurrence_key` than the one just computed (the source's due date moved
since that task was created), the old task is TRANSITIONED to `cancelled`
with `closed_reason=SUPERSEDED_BY_NEW_OCCURRENCE` (never deleted, never
silently overwritten - M010D PID §7 STOP condition "deleting historical
task trace"), and a new task is created for the new occurrence.

Deliberately NOT implemented (scope decision, recorded here and in the
evidence document rather than silently added): this module does NOT
sweep-cancel an open task whose source object became otherwise
ineligible for a fresh candidate without a due-date change on that same
object (e.g. a human independently marks a `RemediationAction` `done`
while its `remediation_followup` task is still open). Auto-cancelling a
human-visible task purely because of an unrelated-field change on its
source is a product policy decision the PID/architecture doc does not
clearly authorise - the architecture doc's own reconciliation menu is
scoped to "source review date changed", not "source became inactive for
any reason". Such a task is left exactly as it is; a person closes it
through the ordinary Tasks page, same as any other task. See the evidence
document's STOP-condition self-check.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import logging

from django.db import transaction

from security_tasks import review_rules, services
from security_tasks.exceptions import ConcurrentModificationError, ForeignAssigneeError
from security_tasks.models import CLOSED_STATUSES, ClosedReason, SecurityTask, SourceOrigin, StatusReason, TaskStatus

logger = logging.getLogger("security_tasks.review_scheduler")


@dataclasses.dataclass
class OrganisationRunResult:
    organisation_id: object
    candidates_evaluated: int = 0
    created: int = 0
    unchanged: int = 0
    superseded_and_recreated: int = 0
    reconciliation_conflicts: int = 0
    candidate_errors: int = 0


def _build_occurrence_key(candidate: review_rules.ReviewCandidate) -> str:
    return f"{candidate.rule_id}:{candidate.source_object_id}:{candidate.due_occurrence}"


def _existing_open_tasks_by_source(organisation, task_kind) -> dict:
    """Current OPEN `rules_engine` tasks for this organisation+task_kind,
    keyed by `source_object_id`. One query per rule, scoped to THIS
    organisation only (M010D PID §5 "no cross-tenant aggregation into one
    query")."""
    return {
        t.source_object_id: t
        for t in SecurityTask.objects.filter(
            organisation=organisation,
            source_origin=SourceOrigin.RULES_ENGINE,
            task_kind=task_kind,
        ).exclude(status__in=CLOSED_STATUSES)
    }


def _supersede_stale_open_task(organisation, existing_task) -> bool:
    """Transitions `existing_task` (open, stale occurrence_key) to
    `cancelled`. Returns `True` on success, `False` on a genuine
    concurrent-modification conflict (another worker already moved this
    exact row - safe to skip this run, the next run reconciles again from
    whatever state won)."""
    try:
        services.transition_task(
            organisation,
            actor=None,
            task_id=existing_task.id,
            expected_version=existing_task.version,
            next_status=TaskStatus.CANCELLED,
            reason=StatusReason.LINKED_RECORD_UPDATED,
            closed_reason=ClosedReason.SUPERSEDED_BY_NEW_OCCURRENCE,
        )
        return True
    except ConcurrentModificationError:
        logger.info(
            "security_tasks.review_scheduler: reconciliation conflict superseding task "
            "%s in organisation %s - deferring to next run",
            existing_task.id,
            organisation.id,
        )
        return False


def _create_for_candidate(organisation, candidate: review_rules.ReviewCandidate, occurrence_key: str) -> SecurityTask:
    """Idempotent create for one candidate, with the architecture doc's
    own owner rule applied (M010-DATA-WORKFLOW-CONTRACTS.md §5: "Task
    owner assigned from existing source owner only if authorised member;
    otherwise unassigned queue"): attempt the candidate's own
    `owner_user_id` first, re-using `create_task`'s EXISTING live
    membership re-check rather than duplicating that query here; a
    membership that no longer holds (PID required scenario "removed-
    tenant-member-as-owner") falls back to unassigned, never raises out
    of this function."""
    idempotency_key = f"rules_engine:{occurrence_key}"
    source_version = f"{candidate.rule_id}:v{candidate.rule_version}"
    kwargs = dict(
        actor=None,
        kind=candidate.task_kind,
        title=candidate.title,
        idempotency_key=idempotency_key,
        source_origin=SourceOrigin.RULES_ENGINE,
        source_kind=candidate.source_kind,
        source_object_id=candidate.source_object_id,
        source_version=source_version,
        occurrence_key=occurrence_key,
        due_at=candidate.due_at,
    )
    try:
        return services.create_task(organisation, assignee_id=candidate.owner_user_id, **kwargs)
    except ForeignAssigneeError:
        logger.info(
            "security_tasks.review_scheduler: candidate owner is not a current member in "
            "organisation %s - creating task unassigned",
            organisation.id,
        )
        return services.create_task(organisation, assignee_id=None, **kwargs)


def _process_candidate(organisation, candidate: review_rules.ReviewCandidate, result: OrganisationRunResult) -> None:
    occurrence_key = _build_occurrence_key(candidate)
    existing_open = (
        SecurityTask.objects.filter(
            organisation=organisation,
            source_origin=SourceOrigin.RULES_ENGINE,
            task_kind=candidate.task_kind,
            source_object_id=candidate.source_object_id,
        )
        .exclude(status__in=CLOSED_STATUSES)
        .first()
    )

    if existing_open is not None and existing_open.occurrence_key == occurrence_key:
        # Already tracked for this exact occurrence - idempotent no-op,
        # including the "manually closed then reopened" case (the row is
        # open again, same occurrence_key, nothing to do) and the
        # "unchanged due date" case on every ordinary re-run.
        result.unchanged += 1
        return

    if existing_open is not None and existing_open.occurrence_key != occurrence_key:
        # Source due date changed while a task for the OLD occurrence was
        # still open - supersede it, then fall through to create the new
        # occurrence's task.
        if not _supersede_stale_open_task(organisation, existing_open):
            result.reconciliation_conflicts += 1
            return
        result.superseded_and_recreated += 1

    _create_for_candidate(organisation, candidate, occurrence_key)
    result.created += 1


def run_for_organisation(organisation, *, now: dt.datetime | None = None) -> OrganisationRunResult:
    """Evaluate every enabled rule for ONE organisation and emit/reconcile
    tasks. Each candidate is processed independently (its own
    try/except) so one candidate's unexpected failure cannot prevent the
    rest of this SAME organisation's candidates from being processed -
    the command layer additionally isolates organisation-from-organisation
    (M010D PID §3/§5)."""
    candidates = review_rules.evaluate_organisation(organisation, now=now)
    result = OrganisationRunResult(organisation_id=organisation.id, candidates_evaluated=len(candidates))

    for candidate in candidates:
        try:
            with transaction.atomic():
                _process_candidate(organisation, candidate, result)
        except Exception:  # noqa: BLE001 - deliberately broad: one bad candidate must not abort the organisation's run
            logger.exception(
                "security_tasks.review_scheduler: candidate %s/%s failed for organisation %s - "
                "skipping, no task created or mutated for it this run",
                candidate.rule_id,
                candidate.source_object_id,
                organisation.id,
            )
            result.candidate_errors += 1

    return result


__all__ = ["OrganisationRunResult", "run_for_organisation"]
