"""
M010D emission/reconciliation tests for `security_tasks.review_scheduler`
(docs/pids/M010D-REVIEW-RULES-SCHEDULER.md §2/§3/§5/§6).
"""
from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from django.utils import timezone as django_timezone

from ai_platform.gateway import LiteLLMGateway
from evidence.models import EvidenceItem
from organisations.models import OrganisationMembership
from policy.models import PolicyDocument, PolicyVersion
from remediation.models import RemediationAction
from security_tasks import review_scheduler, services
from security_tasks.models import (
    ClosedReason,
    SecurityTask,
    SecurityTaskEvent,
    SourceOrigin,
    StatusReason,
    TaskGroup,
    TaskKind,
    TaskStatus,
)

UTC = dt.timezone.utc


def _make_policy_version(org, *, status=PolicyVersion.STATUS_APPROVED, next_review_date=None):
    document, _ = PolicyDocument.objects.get_or_create(organisation=org)
    return PolicyVersion.objects.create(
        document=document,
        organisation=org,
        version_number=document.versions.count() + 1,
        status=status,
        title="Information Security Policy",
        next_review_date=next_review_date,
        approved_at=django_timezone.now() if status != PolicyVersion.STATUS_DRAFT else None,
    )


def _make_remediation_action(org, *, status=RemediationAction.STATUS_OPEN, target_date=None, assigned_to=None):
    return RemediationAction.objects.create(
        organisation=org, title="Enable MFA on the admin console", status=status,
        target_date=target_date, assigned_to=assigned_to,
    )


def _make_evidence_item(org, *, status=EvidenceItem.STATUS_ACTIVE, valid_until=None):
    return EvidenceItem.objects.create(
        organisation=org, kind=EvidenceItem.KIND_EXTERNAL_REFERENCE, title="Cyber Essentials certificate",
        status=status, valid_until=valid_until, reference_url="https://example.invalid/certificate",
    )


@pytest.mark.django_db
class TestCreatesExactlyOneTaskPerGenuineOccurrence:
    def test_single_organisation_single_candidate(self, org_a):
        _make_policy_version(org_a, next_review_date=dt.date(2026, 11, 20))
        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert result.created == 1
        assert result.candidate_errors == 0
        tasks = SecurityTask.objects.filter(organisation=org_a)
        assert tasks.count() == 1
        task = tasks.first()
        assert task.source_origin == SourceOrigin.RULES_ENGINE
        assert task.task_kind == TaskKind.POLICY_REVIEW
        assert task.task_group == TaskGroup.POLICIES
        assert task.due_at == dt.datetime(2026, 11, 20, 0, 0, 0, tzinfo=UTC)
        assert SecurityTaskEvent.objects.filter(task=task, action="created").count() == 1

    def test_no_date_at_all_creates_no_task_no_fabrication(self, org_a):
        _make_remediation_action(org_a, target_date=None)
        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert result.created == 0
        assert SecurityTask.objects.filter(organisation=org_a).count() == 0

    def test_rerunning_with_no_change_is_idempotent(self, org_a):
        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))
        first = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        second = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert first.created == 1
        assert second.created == 0
        assert second.unchanged == 1
        assert SecurityTask.objects.filter(organisation=org_a).count() == 1
        task = SecurityTask.objects.get(organisation=org_a)
        assert SecurityTaskEvent.objects.filter(task=task, action="created").count() == 1


@pytest.mark.django_db
class TestAlreadyCompletedAndSupersededSourcesAreSkipped:
    def test_done_remediation_action_yields_no_task(self, org_a):
        _make_remediation_action(org_a, status=RemediationAction.STATUS_DONE, target_date=dt.date(2026, 11, 20))
        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert result.created == 0
        assert SecurityTask.objects.filter(organisation=org_a).count() == 0

    def test_superseded_policy_version_yields_no_new_task_and_old_open_task_is_left_untouched(self, org_a):
        # First cycle: v1 approved, due date set - a task is created.
        v1 = _make_policy_version(org_a, next_review_date=dt.date(2026, 11, 20))
        first = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert first.created == 1
        task = SecurityTask.objects.get(organisation=org_a)
        assert task.status == TaskStatus.OPEN

        # v1 becomes superseded (a new approved version replaces it in
        # the real product; directly flipping status here is sufficient
        # to prove the RULE never re-offers a superseded version).
        v1.status = PolicyVersion.STATUS_SUPERSEDED
        v1.save(update_fields=["status"])

        second = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert second.created == 0, "A superseded version must never yield a fresh candidate."
        task.refresh_from_db()
        # Scope decision (see review_scheduler module docstring): the old
        # still-open task is left exactly as it was - not auto-cancelled -
        # because its source became ineligible for reasons OTHER than a
        # due-date change on the same object.
        assert task.status == TaskStatus.OPEN
        assert SecurityTask.objects.filter(organisation=org_a).count() == 1


@pytest.mark.django_db
class TestOwnerAssignmentFallsBackToUnassignedForRemovedMember:
    def test_removed_tenant_member_as_owner_falls_back_to_unassigned(self, org_a, user_c, member_c):
        action = _make_remediation_action(org_a, target_date=dt.date(2026, 11, 20), assigned_to=user_c)
        # Membership is revoked AFTER being granted, BEFORE the scheduler
        # ever runs - exactly the PID's "removed-tenant-member-as-owner"
        # scenario.
        OrganisationMembership.objects.filter(organisation=org_a, user=user_c).delete()

        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert result.created == 1
        task = SecurityTask.objects.get(organisation=org_a, source_object_id=str(action.id))
        assert task.assigned_to_id is None, "A non-member owner must fall back to the unassigned queue, never raise."


@pytest.mark.django_db
class TestManualClosureAndReopenNeverResurrectsOrDuplicates:
    def test_manually_closed_then_reopened_source_is_not_resurrected_or_duplicated(self, org_a, user_a):
        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))
        review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        task = SecurityTask.objects.get(organisation=org_a)

        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=task.version,
            next_status=TaskStatus.DONE, reason=StatusReason.ADMINISTRATIVE_WORK_COMPLETE,
        )
        task.refresh_from_db()
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=task.version,
            next_status=TaskStatus.OPEN, reason=StatusReason.REOPENED_NEW_INFORMATION,
        )
        task.refresh_from_db()
        assert task.status == TaskStatus.OPEN

        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert result.created == 0
        assert result.unchanged == 1
        assert SecurityTask.objects.filter(organisation=org_a).count() == 1
        assert SecurityTaskEvent.objects.filter(task=task, action="created").count() == 1


@pytest.mark.django_db
class TestChangedDueDateReconciliation:
    def test_open_task_is_superseded_and_a_new_occurrence_is_created(self, org_a):
        action = _make_remediation_action(org_a, target_date=dt.date(2026, 11, 20))
        review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        old_task = SecurityTask.objects.get(organisation=org_a)
        old_occurrence_key = old_task.occurrence_key

        action.target_date = dt.date(2026, 12, 15)
        action.save(update_fields=["target_date"])

        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert result.superseded_and_recreated == 1
        assert result.created == 1

        old_task.refresh_from_db()
        assert old_task.status == TaskStatus.CANCELLED
        assert old_task.closed_reason == ClosedReason.SUPERSEDED_BY_NEW_OCCURRENCE

        rows = SecurityTask.objects.filter(organisation=org_a).exclude(pk=old_task.pk)
        assert rows.count() == 1
        new_task = rows.first()
        assert new_task.status == TaskStatus.OPEN
        assert new_task.occurrence_key != old_occurrence_key
        assert new_task.due_at == dt.datetime(2026, 12, 15, 0, 0, 0, tzinfo=UTC)
        # Historical trace preserved - never deleted.
        assert SecurityTask.objects.filter(pk=old_task.pk).exists()


@pytest.mark.django_db
class TestGenuineRecurrenceSecondDueCycle:
    def test_completed_first_occurrence_does_not_block_a_later_second_occurrence(self, org_a, user_a):
        item = _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))
        review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        first_task = SecurityTask.objects.get(organisation=org_a)

        services.transition_task(
            org_a, actor=user_a, task_id=first_task.id, expected_version=first_task.version,
            next_status=TaskStatus.DONE, reason=StatusReason.ADMINISTRATIVE_WORK_COMPLETE,
        )

        # A later, genuinely new due cycle - the vendor renewed the
        # certificate to a fresh future expiry.
        item.valid_until = dt.date(2027, 11, 20)
        item.save(update_fields=["valid_until"])

        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        assert result.created == 1
        assert result.superseded_and_recreated == 0, "A CLOSED prior occurrence is never 'superseded' - just left done."

        first_task.refresh_from_db()
        assert first_task.status == TaskStatus.DONE, "The completed first occurrence must never be resurrected."

        second_task = SecurityTask.objects.filter(organisation=org_a).exclude(pk=first_task.pk).get()
        assert second_task.status == TaskStatus.OPEN
        assert second_task.occurrence_key != first_task.occurrence_key
        assert SecurityTask.objects.filter(organisation=org_a).count() == 2


@pytest.mark.django_db
class TestOrganisationScoping:
    def test_two_organisations_never_cross_contaminate(self, org_a, org_b):
        _make_policy_version(org_a, next_review_date=dt.date(2026, 11, 20))
        _make_remediation_action(org_b, target_date=dt.date(2026, 11, 21))

        result_a = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        result_b = review_scheduler.run_for_organisation(org_b, now=django_timezone.now())

        assert result_a.created == 1
        assert result_b.created == 1
        assert SecurityTask.objects.filter(organisation=org_a).count() == 1
        assert SecurityTask.objects.filter(organisation=org_b).count() == 1
        assert not SecurityTask.objects.filter(organisation=org_a, task_kind=TaskKind.REMEDIATION_FOLLOWUP).exists()
        assert not SecurityTask.objects.filter(organisation=org_b, task_kind=TaskKind.POLICY_REVIEW).exists()


@pytest.mark.django_db
class TestCompletionNeverMutatesSourceModels:
    def test_completing_a_generated_task_never_changes_its_source_row(self, org_a, user_a):
        action = _make_remediation_action(org_a, target_date=dt.date(2026, 11, 20))
        before_status, before_target = action.status, action.target_date

        review_scheduler.run_for_organisation(org_a, now=django_timezone.now())
        task = SecurityTask.objects.get(organisation=org_a)
        services.transition_task(
            org_a, actor=user_a, task_id=task.id, expected_version=task.version,
            next_status=TaskStatus.DONE, reason=StatusReason.ADMINISTRATIVE_WORK_COMPLETE,
        )

        action.refresh_from_db()
        assert action.status == before_status
        assert action.target_date == before_target


@pytest.mark.django_db
def test_run_for_organisation_makes_zero_ai_gateway_calls(org_a):
    """M010-MASTER-ARCHITECTURE.md §6 'no independent LLM scheduler
    judgement' - mirrors foundations_journey/tests/test_zero_ai_calls.py's
    exact technique: patch the one real network boundary and assert it
    is never invoked across a representative multi-rule run."""
    _make_policy_version(org_a, next_review_date=dt.date(2026, 11, 20))
    _make_remediation_action(org_a, target_date=dt.date(2026, 11, 21))
    _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 22))

    with patch.object(LiteLLMGateway, "_send") as mock_send:
        result = review_scheduler.run_for_organisation(org_a, now=django_timezone.now())

    assert result.created == 3
    mock_send.assert_not_called()
