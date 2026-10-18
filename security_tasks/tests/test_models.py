import uuid

import pytest
from django.db import IntegrityError, transaction

from security_tasks.models import (
    ALLOWED_TRANSITIONS,
    SecurityTask,
    SecurityTaskDependency,
    SourceOrigin,
    TaskGroup,
    TaskKind,
    TaskStatus,
    group_for_kind,
)


def _task(org, **overrides):
    defaults = dict(
        organisation=org,
        task_kind=TaskKind.MANUAL_OTHER,
        title="Synthetic task",
        idempotency_key=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    return SecurityTask.objects.create(**defaults)


@pytest.mark.django_db
class TestTaskGroupDerivation:
    def test_every_task_kind_has_a_group_mapping(self):
        for kind in TaskKind.values:
            assert group_for_kind(kind) in TaskGroup.values

    def test_unregistered_kind_raises(self):
        with pytest.raises(ValueError):
            group_for_kind("not_a_real_kind")

    def test_task_group_property_matches_group_for_kind(self, org_a):
        task = _task(org_a, task_kind=TaskKind.RISK_REVIEW)
        assert task.task_group == TaskGroup.RISKS_ACTIONS


@pytest.mark.django_db
class TestAllowedTransitions:
    def test_done_can_only_reopen_to_open(self):
        assert ALLOWED_TRANSITIONS[TaskStatus.DONE] == frozenset({TaskStatus.OPEN})

    def test_cancelled_can_only_restore_to_open(self):
        assert ALLOWED_TRANSITIONS[TaskStatus.CANCELLED] == frozenset({TaskStatus.OPEN})

    def test_open_can_reach_done_directly(self):
        assert TaskStatus.DONE in ALLOWED_TRANSITIONS[TaskStatus.OPEN]

    def test_every_status_has_a_transition_entry(self):
        for status in TaskStatus.values:
            assert status in ALLOWED_TRANSITIONS


@pytest.mark.django_db
class TestOccurrenceKeyUniqueConstraint:
    def test_duplicate_occurrence_key_within_same_scope_is_rejected(self, org_a):
        _task(
            org_a,
            task_kind=TaskKind.POLICY_REVIEW,
            source_origin=SourceOrigin.RULES_ENGINE,
            occurrence_key="policy-review-2026-q4",
            idempotency_key=str(uuid.uuid4()),
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _task(
                    org_a,
                    task_kind=TaskKind.POLICY_REVIEW,
                    source_origin=SourceOrigin.RULES_ENGINE,
                    occurrence_key="policy-review-2026-q4",
                    idempotency_key=str(uuid.uuid4()),
                )

    def test_different_organisations_may_share_the_same_occurrence_key(self, org_a, org_b):
        _task(
            org_a,
            task_kind=TaskKind.POLICY_REVIEW,
            source_origin=SourceOrigin.RULES_ENGINE,
            occurrence_key="shared-key",
        )
        # Must not raise - occurrence_key uniqueness is scoped per organisation.
        _task(
            org_b,
            task_kind=TaskKind.POLICY_REVIEW,
            source_origin=SourceOrigin.RULES_ENGINE,
            occurrence_key="shared-key",
        )

    def test_null_occurrence_key_never_collides(self, org_a):
        # Partial unique constraint only applies when occurrence_key IS NOT NULL.
        _task(org_a, occurrence_key=None, idempotency_key=str(uuid.uuid4()))
        _task(org_a, occurrence_key=None, idempotency_key=str(uuid.uuid4()))


@pytest.mark.django_db
class TestIdempotencyKeyUniqueConstraint:
    def test_duplicate_idempotency_key_within_same_organisation_is_rejected(self, org_a):
        _task(org_a, idempotency_key="same-token")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _task(org_a, idempotency_key="same-token")

    def test_different_organisations_may_share_the_same_idempotency_key(self, org_a, org_b):
        _task(org_a, idempotency_key="same-token")
        _task(org_b, idempotency_key="same-token")


@pytest.mark.django_db
class TestDependencySelfReferenceConstraint:
    def test_self_reference_rejected_at_db_level(self, org_a):
        task = _task(org_a)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SecurityTaskDependency.objects.create(
                    organisation=org_a, predecessor_task=task, successor_task=task
                )
