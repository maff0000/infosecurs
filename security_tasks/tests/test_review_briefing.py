"""
M010D zero-AI briefing-counts tests (PID §4, M010-MASTER-ARCHITECTURE.md
§6 "Do not make the Task List depend on a model call") for
`security_tasks.services.get_review_briefing_counts`.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.utils import timezone

from ai_platform.gateway import LiteLLMGateway
from security_tasks import services
from security_tasks.models import TaskKind, TaskStatus


def _task_due_in(org, *, days, kind=TaskKind.MANUAL_OTHER, title="A task"):
    return services.create_task(
        org, actor=None, kind=kind, title=title, idempotency_key=str(uuid.uuid4()),
        due_at=timezone.now() + timezone.timedelta(days=days),
    )


@pytest.mark.django_db
class TestGetReviewBriefingCounts:
    def test_counts_overdue_due_soon_and_due_within_thirty_days_separately(self, org_a):
        _task_due_in(org_a, days=-2)  # overdue
        _task_due_in(org_a, days=3)  # within 7 days (and within 30)
        _task_due_in(org_a, days=20)  # within 30 days only
        _task_due_in(org_a, days=60)  # beyond everything

        counts = services.get_review_briefing_counts(org_a)
        assert counts["overdue"] == 1
        assert counts["due_within_7_days"] == 1
        # due_within_30_days includes everything due within 30 days,
        # i.e. both the 3-day and the 20-day task (never the overdue one,
        # and never the 60-day one).
        assert counts["due_within_30_days"] == 2

    def test_a_task_with_no_due_date_is_counted_nowhere(self, org_a):
        services.create_task(
            org_a, actor=None, kind=TaskKind.MANUAL_OTHER, title="No due date",
            idempotency_key=str(uuid.uuid4()),
        )
        counts = services.get_review_briefing_counts(org_a)
        assert counts == {"overdue": 0, "due_within_7_days": 0, "due_within_30_days": 0}

    def test_a_closed_task_is_never_counted_as_overdue_or_due_soon(self, org_a):
        task = _task_due_in(org_a, days=-5)
        services.transition_task(
            org_a, actor=None, task_id=task.id, expected_version=task.version,
            next_status=TaskStatus.DONE, reason="administrative_work_complete",
        )
        counts = services.get_review_briefing_counts(org_a)
        assert counts == {"overdue": 0, "due_within_7_days": 0, "due_within_30_days": 0}

    def test_organisation_scoping_never_counts_another_organisations_tasks(self, org_a, org_b):
        _task_due_in(org_a, days=-1)
        _task_due_in(org_b, days=-1)
        _task_due_in(org_b, days=-1)

        counts_a = services.get_review_briefing_counts(org_a)
        counts_b = services.get_review_briefing_counts(org_b)
        assert counts_a["overdue"] == 1
        assert counts_b["overdue"] == 2

    def test_makes_no_ai_gateway_call(self, org_a):
        _task_due_in(org_a, days=-1)
        with patch.object(LiteLLMGateway, "_send") as mock_send:
            services.get_review_briefing_counts(org_a)
        mock_send.assert_not_called()
