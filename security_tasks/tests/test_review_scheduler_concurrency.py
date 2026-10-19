"""
M010D concurrency + crash-window proof (PID §3/§5/§6, M010-DATA-WORKFLOW-
CONTRACTS.md §4/§7 "duplicate scheduler runs"). Uses the exact same
`@pytest.mark.django_db(transaction=True)` + real-thread technique
`security_tasks/tests/test_concurrency.py` already established for this
app - see that file's own module docstring for why `transaction=True` is
required here (real commits visible across threads, not one wrapped-and-
rolled-back test transaction).
"""
from __future__ import annotations

import datetime as dt
import threading

import pytest
from django.db import close_old_connections
from django.utils import timezone as django_timezone

from evidence.models import EvidenceItem
from organisations.models import Organisation
from security_tasks import review_scheduler
from security_tasks.models import SecurityTask, SecurityTaskEvent


def _make_evidence_item(org, *, valid_until):
    return EvidenceItem.objects.create(
        organisation=org, kind=EvidenceItem.KIND_EXTERNAL_REFERENCE, title="Cyber Essentials certificate",
        status=EvidenceItem.STATUS_ACTIVE, valid_until=valid_until,
        reference_url="https://example.invalid/certificate",
    )


@pytest.mark.django_db(transaction=True)
class TestOverlappingConcurrentSchedulerWorkers:
    def test_two_overlapping_runs_for_the_same_organisation_produce_exactly_one_task_and_event(self):
        organisation = Organisation.objects.create(name="Scheduler Concurrency Org A")
        _make_evidence_item(organisation, valid_until=dt.date(2026, 11, 20))

        start_barrier = threading.Barrier(2)
        results = [None, None]
        errors = [None, None]

        def _run(index):
            start_barrier.wait(timeout=10)
            try:
                results[index] = review_scheduler.run_for_organisation(organisation, now=django_timezone.now())
            except Exception as exc:  # noqa: BLE001
                errors[index] = exc
            finally:
                close_old_connections()

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [None, None], f"Unexpected errors: {errors}"
        rows = SecurityTask.objects.filter(organisation=organisation)
        assert rows.count() == 1, "Exactly one task must exist for this occurrence, even under overlapping workers."
        task = rows.first()
        events = SecurityTaskEvent.objects.filter(task=task, action="created")
        assert events.count() == 1, "Exactly one 'created' event must exist, never two."
        # Both workers complete without error and agree on the one row
        # that exists afterwards (per-worker "who actually inserted it"
        # attribution is a racy implementation detail `create_task`'s own
        # IntegrityError-retry path already absorbs - the PID's actual
        # requirement is the row+event invariant asserted above).
        assert results[0] is not None and results[1] is not None

    def test_two_overlapping_reconciliation_runs_supersede_exactly_once(self):
        """Both workers see the SAME stale open task (due date just
        changed) at the same time - exactly one must win the supersede,
        the other must see a ConcurrentModificationError-driven conflict
        and defer, never both creating a second new-occurrence task."""
        from remediation.models import RemediationAction

        organisation = Organisation.objects.create(name="Scheduler Concurrency Org B")
        action = RemediationAction.objects.create(
            organisation=organisation, title="Patch the VPN gateway",
            status=RemediationAction.STATUS_OPEN, target_date=dt.date(2026, 11, 20),
        )
        review_scheduler.run_for_organisation(organisation, now=django_timezone.now())
        old_task = SecurityTask.objects.get(organisation=organisation)

        action.target_date = dt.date(2026, 12, 15)
        action.save(update_fields=["target_date"])

        start_barrier = threading.Barrier(2)
        results = [None, None]
        errors = [None, None]

        def _run(index):
            start_barrier.wait(timeout=10)
            try:
                results[index] = review_scheduler.run_for_organisation(organisation, now=django_timezone.now())
            except Exception as exc:  # noqa: BLE001
                errors[index] = exc
            finally:
                close_old_connections()

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [None, None], f"Unexpected errors: {errors}"
        old_task.refresh_from_db()
        assert old_task.status == "cancelled"

        new_rows = SecurityTask.objects.filter(organisation=organisation).exclude(pk=old_task.pk)
        assert new_rows.count() == 1, "Exactly one new-occurrence task must exist, never two."
        assert SecurityTaskEvent.objects.filter(task=new_rows.first(), action="created").count() == 1


@pytest.mark.django_db
class TestNoPartialStateWindowOnFailure:
    """M010D PID §7's crash-recovery requirement, proven by construction
    rather than by racing a real process kill: `security_tasks.services.
    create_task` wraps BOTH the `SecurityTask` insert and its `created`
    `SecurityTaskEvent` insert inside ONE `transaction.atomic()` block
    (see services.py lines ~339-370) - there is no instant at which the
    task row is durably committed but its event is not, or vice versa,
    because PostgreSQL commits (or rolls back) the whole block together.
    This test forces an exception to occur BETWEEN the two inserts and
    shows the result is a clean, total rollback - zero rows of either
    kind - which is exactly what "no such window exists" means in
    practice, not merely in the code's own comments."""

    def test_forced_failure_between_task_and_event_insert_leaves_zero_partial_rows(self, org_a, monkeypatch):
        import uuid

        from security_tasks import services
        from security_tasks.models import SecurityTaskEvent, TaskKind

        real_create = SecurityTaskEvent.objects.create

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated crash between the DB write and task-creation completing")

        monkeypatch.setattr(SecurityTaskEvent.objects, "create", _boom)

        with pytest.raises(RuntimeError):
            services.create_task(
                org_a, actor=None, kind=TaskKind.POLICY_REVIEW, title="Scheduled policy review",
                idempotency_key=str(uuid.uuid4()),
            )

        assert SecurityTask.objects.filter(organisation=org_a).count() == 0, (
            "The SecurityTask insert must have rolled back together with the failed event insert - "
            "never left as an orphaned, event-less row."
        )

        monkeypatch.setattr(SecurityTaskEvent.objects, "create", real_create)
