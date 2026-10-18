import uuid

import pytest

from key_assets.models import KeyAsset
from security_tasks import services
from security_tasks.exceptions import (
    ConcurrentModificationError,
    ForeignAssigneeError,
    InvalidSourceLocatorError,
    InvalidTaskKindError,
    InvalidTransitionError,
)
from security_tasks.models import (
    SecurityTask,
    SecurityTaskEvent,
    SourceOrigin,
    TaskKind,
    TaskStatus,
)
from security_tasks.source_registry import SOURCE_KIND_KEY_ASSET, UnregisteredSourceKindError


@pytest.mark.django_db
class TestCreateTask:
    def test_creates_task_and_one_created_event(self, org_a, user_a):
        task = services.create_task(
            org_a,
            actor=user_a,
            kind=TaskKind.MANUAL_OTHER,
            title="Follow up with IT",
            idempotency_key=str(uuid.uuid4()),
        )
        assert task.organisation_id == org_a.id
        assert task.status == TaskStatus.OPEN
        assert task.version == 1
        events = SecurityTaskEvent.objects.filter(task=task)
        assert events.count() == 1
        assert events.first().action == "created"

    def test_rejects_unregistered_kind(self, org_a, user_a):
        with pytest.raises(InvalidTaskKindError):
            services.create_task(
                org_a, actor=user_a, kind="not_a_real_kind", title="x", idempotency_key=str(uuid.uuid4())
            )

    def test_rejects_empty_title(self, org_a, user_a):
        with pytest.raises(ValueError):
            services.create_task(
                org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="   ", idempotency_key=str(uuid.uuid4())
            )

    def test_rejects_idempotency_key_missing(self, org_a, user_a):
        with pytest.raises(ValueError):
            services.create_task(org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="x", idempotency_key="")

    def test_repeated_idempotency_key_returns_original_row(self, org_a, user_a):
        key = str(uuid.uuid4())
        first = services.create_task(
            org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="Original title", idempotency_key=key
        )
        second = services.create_task(
            org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="Different title", idempotency_key=key
        )
        assert first.id == second.id
        assert second.title == "Original title"
        assert SecurityTask.objects.filter(organisation=org_a).count() == 1
        assert SecurityTaskEvent.objects.filter(task=first).count() == 1

    def test_rejects_foreign_assignee(self, org_a, org_b, user_a, user_b, member_b):
        with pytest.raises(ForeignAssigneeError):
            services.create_task(
                org_a,
                actor=user_a,
                kind=TaskKind.MANUAL_OTHER,
                title="x",
                idempotency_key=str(uuid.uuid4()),
                assignee_id=user_b.id,
            )

    def test_accepts_genuine_member_assignee(self, org_a, user_a, user_c, member_c):
        task = services.create_task(
            org_a,
            actor=user_a,
            kind=TaskKind.MANUAL_OTHER,
            title="x",
            idempotency_key=str(uuid.uuid4()),
            assignee_id=user_c.id,
        )
        assert task.assigned_to_id == user_c.id

    def test_rejects_unregistered_source_kind(self, org_a, user_a):
        with pytest.raises(UnregisteredSourceKindError):
            services.create_task(
                org_a,
                actor=user_a,
                kind=TaskKind.MANUAL_OTHER,
                title="x",
                idempotency_key=str(uuid.uuid4()),
                source_kind="some_app.somemodel",
                source_object_id="1",
            )

    def test_rejects_cross_organisation_source(self, org_a, org_b, user_a):
        other_org_asset = KeyAsset.objects.create(
            organisation=org_b, name="Org B asset", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        with pytest.raises(InvalidSourceLocatorError):
            services.create_task(
                org_a,
                actor=user_a,
                kind=TaskKind.MANUAL_OTHER,
                title="x",
                idempotency_key=str(uuid.uuid4()),
                source_kind=SOURCE_KIND_KEY_ASSET,
                source_object_id=str(other_org_asset.id),
            )

    def test_accepts_same_organisation_source(self, org_a, user_a):
        asset = KeyAsset.objects.create(
            organisation=org_a, name="Org A asset", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        task = services.create_task(
            org_a,
            actor=user_a,
            kind=TaskKind.MANUAL_OTHER,
            title="x",
            idempotency_key=str(uuid.uuid4()),
            source_kind=SOURCE_KIND_KEY_ASSET,
            source_object_id=str(asset.id),
        )
        assert task.source_object_id == str(asset.id)


@pytest.mark.django_db
class TestTransitionTask:
    def _create(self, org, user, **overrides):
        return services.create_task(
            org, actor=user, kind=TaskKind.MANUAL_OTHER, title="x", idempotency_key=str(uuid.uuid4()), **overrides
        )

    def test_valid_transition_bumps_version_and_records_event(self, org_a, user_a):
        task = self._create(org_a, user_a)
        updated = services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.IN_PROGRESS, reason="work_started",
        )
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.version == 2
        events = SecurityTaskEvent.objects.filter(task=task).order_by("event_time")
        assert events.count() == 2
        assert events.last().previous_status == TaskStatus.OPEN
        assert events.last().new_status == TaskStatus.IN_PROGRESS

    def test_invalid_transition_rejected(self, org_a, user_a):
        task = self._create(org_a, user_a)
        with pytest.raises(InvalidTransitionError):
            services.transition_task(
                org_a, actor=user_a, task_id=task.id, expected_version=1,
                next_status="not_a_real_status", reason="x",
            )

    def test_blocked_transition_rejected_by_table(self, org_a, user_a):
        task = self._create(org_a, user_a)
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )
        task.refresh_from_db()
        assert task.version == 2
        # done -> in_progress is not in the allowed table.
        with pytest.raises(InvalidTransitionError):
            services.transition_task(
                org_a, actor=user_a, task_id=task.id, expected_version=2,
                next_status=TaskStatus.IN_PROGRESS, reason="x",
            )

    def test_done_can_reopen_to_open_with_reason(self, org_a, user_a):
        task = self._create(org_a, user_a)
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )
        task.refresh_from_db()
        reopened = services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=task.version,
            next_status=TaskStatus.OPEN, reason="reopened_new_information",
        )
        assert reopened.status == TaskStatus.OPEN
        assert reopened.completed_at is None

    def test_stale_version_raises_conflict(self, org_a, user_a):
        task = self._create(org_a, user_a)
        with pytest.raises(ConcurrentModificationError):
            services.transition_task(
                org_a, actor=user_a, task_id=task.id, expected_version=999,
                next_status=TaskStatus.IN_PROGRESS, reason="x",
            )

    def test_repeated_idempotency_key_does_not_duplicate_event(self, org_a, user_a):
        task = self._create(org_a, user_a)
        key = str(uuid.uuid4())
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.IN_PROGRESS, reason="work_started", idempotency_key=key,
        )
        result = services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.IN_PROGRESS, reason="work_started", idempotency_key=key,
        )
        assert result.version == 2
        assert SecurityTaskEvent.objects.filter(task=task).count() == 2  # created + one transition, not two


@pytest.mark.django_db
class TestAssignTask:
    def test_assign_to_member_succeeds(self, org_a, user_a, user_c, member_c):
        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="x", idempotency_key=str(uuid.uuid4())
        )
        updated = services.assign_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1, assignee_id=user_c.id
        )
        assert updated.assigned_to_id == user_c.id
        assert updated.version == 2

    def test_assign_to_non_member_rejected(self, org_a, org_b, user_a, user_b, member_b):
        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="x", idempotency_key=str(uuid.uuid4())
        )
        with pytest.raises(ForeignAssigneeError):
            services.assign_task(
                org_a, actor=user_a, task_id=task.id, expected_version=1, assignee_id=user_b.id
            )

    def test_stale_version_raises_conflict(self, org_a, user_a, user_c, member_c):
        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="x", idempotency_key=str(uuid.uuid4())
        )
        with pytest.raises(ConcurrentModificationError):
            services.assign_task(
                org_a, actor=user_a, task_id=task.id, expected_version=999, assignee_id=user_c.id
            )
