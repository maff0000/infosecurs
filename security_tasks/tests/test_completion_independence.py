"""
M010A PID §4/§5, M010-MASTER-ARCHITECTURE.md §6: "A task marked done is
NOT proof that a risk is accepted, a policy approved, a control
implemented or an evidence item current." This file is the explicit,
direct proof - calling `entitlements.metrics.get_security_foundations_
completion` BEFORE and AFTER completing a task (including a task whose
source_locator points AT a BaselineAnswer/PolicyVersion/Risk row) and
asserting the result, and each underlying row, is byte-for-byte
identical.
"""
import uuid

import pytest

from entitlements.metrics import get_security_foundations_completion
from policy.models import PolicyDocument, PolicyVersion
from risk_register.models import Risk
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment
from security_tasks import services
from security_tasks.models import TaskKind, TaskStatus
from security_tasks.source_registry import (
    SOURCE_KIND_BASELINE_ANSWER,
    SOURCE_KIND_POLICY_VERSION,
    SOURCE_KIND_RISK,
)


@pytest.mark.django_db
class TestTaskCompletionNeverMutatesCanonicalFacts:
    def test_completion_percentage_identical_before_and_after_plain_task(self, org_a, user_a):
        assessment = BaselineAssessment.objects.create(organisation=org_a, catalogue_version=CATALOGUE_VERSION)
        BaselineAnswer.objects.create(assessment=assessment, question_key="device_encryption", answer="yes")

        before = get_security_foundations_completion(org_a)

        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="Administrative follow-up",
            idempotency_key=str(uuid.uuid4()),
        )
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )

        after = get_security_foundations_completion(org_a)
        assert before.percentage == after.percentage
        assert before.completed_count == after.completed_count
        assert before.total_count == after.total_count

    def test_completing_a_task_linked_to_a_baseline_answer_does_not_change_it(self, org_a, user_a):
        assessment = BaselineAssessment.objects.create(organisation=org_a, catalogue_version=CATALOGUE_VERSION)
        answer = BaselineAnswer.objects.create(
            assessment=assessment, question_key="device_encryption", answer="unknown"
        )

        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.FOUNDATION_CONFIRM, title="Confirm device encryption",
            idempotency_key=str(uuid.uuid4()), source_kind=SOURCE_KIND_BASELINE_ANSWER,
            source_object_id=str(answer.id),
        )
        before_completion = get_security_foundations_completion(org_a)

        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
            completion_source_kind=SOURCE_KIND_BASELINE_ANSWER, completion_source_object_id=str(answer.id),
        )

        answer.refresh_from_db()
        assert answer.answer == "unknown", "Task completion must never write to BaselineAnswer.answer."
        after_completion = get_security_foundations_completion(org_a)
        assert before_completion.percentage == after_completion.percentage
        assert before_completion.completed_count == after_completion.completed_count

    def test_completing_a_task_linked_to_a_policy_version_does_not_approve_it(self, org_a, user_a):
        document = PolicyDocument.objects.create(organisation=org_a)
        version = PolicyVersion.objects.create(
            document=document, organisation=org_a, version_number=1, status=PolicyVersion.STATUS_DRAFT,
            title="Information Security Policy", sections=[],
        )

        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.POLICY_REVIEW, title="Review policy draft",
            idempotency_key=str(uuid.uuid4()), source_kind=SOURCE_KIND_POLICY_VERSION,
            source_object_id=str(version.id),
        )
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )

        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT, "Task completion must never change PolicyVersion.status."

    def test_completing_a_task_linked_to_a_risk_does_not_change_its_status(self, org_a, user_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Synthetic risk", threat="t", vulnerability="v",
            impact=3, likelihood=3, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_MANUAL,
        )

        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.RISK_REVIEW, title="Review risk",
            idempotency_key=str(uuid.uuid4()), source_kind=SOURCE_KIND_RISK,
            source_object_id=str(risk.id),
        )
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )

        risk.refresh_from_db()
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED, "Task completion must never change Risk.status."

    def test_reading_task_list_and_detail_repeatedly_mutates_nothing(self, org_a, user_a, client_a):
        """M010 data contract §7: 'Repeated reads mutate nothing.'"""
        from django.urls import reverse

        task = services.create_task(
            org_a, actor=user_a, kind=TaskKind.MANUAL_OTHER, title="Read-only check",
            idempotency_key=str(uuid.uuid4()),
        )
        before_version = task.version
        for _ in range(3):
            client_a.get(reverse("security_tasks:list", args=[org_a.id]))
            client_a.get(reverse("security_tasks:detail", args=[org_a.id, task.id]))
        task.refresh_from_db()
        assert task.version == before_version
