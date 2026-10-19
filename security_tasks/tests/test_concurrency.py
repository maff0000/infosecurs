"""
Real concurrency proof (M010A PID §4, M010 data contract §4/§7) - genuine
separate threads/DB connections racing the same service call, not merely
two sequential calls that happen to exercise the same code path. Uses
`@pytest.mark.django_db(transaction=True)` (this codebase's own existing
precedent for anything requiring real commits visible across threads -
see risk_register/tests/test_narrow_viewport_regression.py's identical
marker) so each thread's Django-managed, thread-local DB connection
genuinely commits, rather than sharing one wrapped-and-rolled-back test
transaction.
"""
import threading
import uuid

import pytest
from django.db import close_old_connections

from organisations.models import Organisation
from security_tasks import services
from security_tasks.exceptions import ConcurrentModificationError
from security_tasks.models import SecurityTask, SecurityTaskEvent, SourceOrigin, TaskKind, TaskStatus


@pytest.mark.django_db(transaction=True)
class TestConcurrentCreate:
    def test_two_simultaneous_creators_of_the_same_occurrence_produce_exactly_one_row(self):
        organisation = Organisation.objects.create(name="Concurrency Org A")
        start_barrier = threading.Barrier(2)
        occurrence_key = "concurrent-occurrence-key"

        def _create():
            start_barrier.wait(timeout=10)
            return services.create_task(
                organisation,
                actor=None,
                kind=TaskKind.POLICY_REVIEW,
                title="Scheduled policy review",
                idempotency_key=str(uuid.uuid4()),
                source_origin=SourceOrigin.RULES_ENGINE,
                occurrence_key=occurrence_key,
            )

        results = [None, None]
        errors = [None, None]

        def _target(index):
            try:
                results[index] = _create()
            except Exception as exc:  # noqa: BLE001
                errors[index] = exc
            finally:
                close_old_connections()

        threads = [threading.Thread(target=_target, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [None, None], f"Unexpected errors: {errors}"
        assert results[0] is not None and results[1] is not None
        assert results[0].id == results[1].id, "Both callers must resolve to the SAME row."

        rows = SecurityTask.objects.filter(organisation=organisation, occurrence_key=occurrence_key)
        assert rows.count() == 1, "Exactly one row must exist for this occurrence key."
        events = SecurityTaskEvent.objects.filter(task=rows.first(), action="created")
        assert events.count() == 1, "Exactly one 'created' event must exist, never two."


@pytest.mark.django_db(transaction=True)
class TestConcurrentTransition:
    def test_two_concurrent_writers_with_stale_version_one_wins_one_conflicts(self):
        organisation = Organisation.objects.create(name="Concurrency Org B")
        task = services.create_task(
            organisation,
            actor=None,
            kind=TaskKind.MANUAL_OTHER,
            title="Contested task",
            idempotency_key=str(uuid.uuid4()),
        )
        start_barrier = threading.Barrier(2)
        outcomes = [None, None]

        def _transition(index):
            start_barrier.wait(timeout=10)
            try:
                outcomes[index] = (
                    "ok",
                    services.transition_task(
                        organisation,
                        actor=None,
                        task_id=task.id,
                        expected_version=1,
                        next_status=TaskStatus.IN_PROGRESS,
                        reason="work_started",
                    ),
                )
            except ConcurrentModificationError as exc:
                outcomes[index] = ("conflict", exc)
            except Exception as exc:  # noqa: BLE001
                outcomes[index] = ("error", exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=_transition, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        kinds = sorted(outcome[0] for outcome in outcomes)
        assert kinds == ["conflict", "ok"], f"Expected exactly one winner and one conflict, got: {outcomes}"

        task.refresh_from_db()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.version == 2, "Exactly one transition must have been applied - never double-applied."
        assert SecurityTaskEvent.objects.filter(task=task, action="status_changed").count() == 1


@pytest.mark.django_db
class TestIdempotentCreateRetrySimulation:
    """A non-threaded, deterministic proof of the same IntegrityError ->
    re-fetch path the threaded test above also exercises under real
    concurrency - kept as its own fast, always-reliable test so this
    specific code path (security_tasks.services._find_existing_for_retry)
    has a test that does not depend on thread scheduling to pass."""

    def test_repeated_occurrence_key_create_returns_existing_row(self, org_a):
        first = services.create_task(
            org_a, actor=None, kind=TaskKind.POLICY_REVIEW, title="First title",
            idempotency_key=str(uuid.uuid4()), source_origin=SourceOrigin.RULES_ENGINE,
            occurrence_key="deterministic-retry-key",
        )
        second = services.create_task(
            org_a, actor=None, kind=TaskKind.POLICY_REVIEW, title="Second title",
            idempotency_key=str(uuid.uuid4()), source_origin=SourceOrigin.RULES_ENGINE,
            occurrence_key="deterministic-retry-key",
        )
        assert first.id == second.id
        assert second.title == "First title"
        assert SecurityTask.objects.filter(organisation=org_a, occurrence_key="deterministic-retry-key").count() == 1
