import uuid

import pytest

from security_tasks import services
from security_tasks.exceptions import (
    DependencyBlockedError,
    DependencyCrossOrganisationError,
    DependencyCycleError,
    DependencySelfReferenceError,
    DuplicateDependencyError,
)
from security_tasks.models import SecurityTaskDependency, TaskKind, TaskStatus


def _create(org, user, title="x"):
    return services.create_task(
        org, actor=user, kind=TaskKind.MANUAL_OTHER, title=title, idempotency_key=str(uuid.uuid4())
    )


@pytest.mark.django_db
class TestLinkTaskDependency:
    def test_creates_edge(self, org_a, user_a):
        a = _create(org_a, user_a, "A")
        b = _create(org_a, user_a, "B")
        dep = services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=b.id)
        assert dep.predecessor_task_id == a.id
        assert dep.successor_task_id == b.id

    def test_self_reference_rejected(self, org_a, user_a):
        a = _create(org_a, user_a, "A")
        with pytest.raises(DependencySelfReferenceError):
            services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=a.id)

    def test_cross_organisation_rejected(self, org_a, org_b, user_a, user_b):
        a = _create(org_a, user_a, "A")
        b = _create(org_b, user_b, "B")
        with pytest.raises(DependencyCrossOrganisationError):
            services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=b.id)
        with pytest.raises(DependencyCrossOrganisationError):
            services.link_task_dependency(org_a, actor=user_a, predecessor_id=b.id, successor_id=a.id)
        assert SecurityTaskDependency.objects.count() == 0

    def test_duplicate_edge_rejected(self, org_a, user_a):
        a = _create(org_a, user_a, "A")
        b = _create(org_a, user_a, "B")
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=b.id)
        with pytest.raises(DuplicateDependencyError):
            services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=b.id)

    def test_direct_cycle_rejected(self, org_a, user_a):
        a = _create(org_a, user_a, "A")
        b = _create(org_a, user_a, "B")
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=b.id)
        with pytest.raises(DependencyCycleError):
            services.link_task_dependency(org_a, actor=user_a, predecessor_id=b.id, successor_id=a.id)

    def test_transitive_cycle_rejected(self, org_a, user_a):
        a = _create(org_a, user_a, "A")
        b = _create(org_a, user_a, "B")
        c = _create(org_a, user_a, "C")
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=b.id)
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=b.id, successor_id=c.id)
        # c -> a would close A -> B -> C -> A.
        with pytest.raises(DependencyCycleError):
            services.link_task_dependency(org_a, actor=user_a, predecessor_id=c.id, successor_id=a.id)

    def test_diamond_shape_is_not_a_cycle(self, org_a, user_a):
        """A -> B, A -> C, B -> D, C -> D is a valid DAG, not a cycle -
        proves the reachability check does not over-reject a shared
        descendant."""
        a = _create(org_a, user_a, "A")
        b = _create(org_a, user_a, "B")
        c = _create(org_a, user_a, "C")
        d = _create(org_a, user_a, "D")
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=b.id)
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=a.id, successor_id=c.id)
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=b.id, successor_id=d.id)
        services.link_task_dependency(org_a, actor=user_a, predecessor_id=c.id, successor_id=d.id)
        assert SecurityTaskDependency.objects.filter(organisation=org_a).count() == 4


@pytest.mark.django_db
class TestCompletionBlockedByDependency:
    def test_cannot_complete_successor_while_predecessor_open(self, org_a, user_a):
        predecessor = _create(org_a, user_a, "Predecessor")
        successor = _create(org_a, user_a, "Successor")
        services.link_task_dependency(
            org_a, actor=user_a, predecessor_id=predecessor.id, successor_id=successor.id
        )
        with pytest.raises(DependencyBlockedError):
            services.transition_task(
                org_a, actor=user_a, task_id=successor.id, expected_version=1,
                next_status=TaskStatus.DONE, reason="administrative_work_complete",
            )

    def test_can_complete_successor_once_predecessor_done(self, org_a, user_a):
        predecessor = _create(org_a, user_a, "Predecessor")
        successor = _create(org_a, user_a, "Successor")
        services.link_task_dependency(
            org_a, actor=user_a, predecessor_id=predecessor.id, successor_id=successor.id
        )
        services.transition_task(
            org_a, actor=user_a, task_id=predecessor.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )
        updated = services.transition_task(
            org_a, actor=user_a, task_id=successor.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )
        assert updated.status == TaskStatus.DONE

    def test_override_blocked_allows_completion_with_reason(self, org_a, user_a):
        predecessor = _create(org_a, user_a, "Predecessor")
        successor = _create(org_a, user_a, "Successor")
        services.link_task_dependency(
            org_a, actor=user_a, predecessor_id=predecessor.id, successor_id=successor.id
        )
        updated = services.transition_task(
            org_a, actor=user_a, task_id=successor.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
            override_blocked=True,
        )
        assert updated.status == TaskStatus.DONE
