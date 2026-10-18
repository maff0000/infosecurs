import uuid

import pytest
from django.urls import reverse

from security_tasks import services
from security_tasks.exceptions import ForeignAssigneeError
from security_tasks.models import SecurityTask, TaskKind


def _create(org, user, title="Org task"):
    return services.create_task(
        org, actor=user, kind=TaskKind.MANUAL_OTHER, title=title, idempotency_key=str(uuid.uuid4())
    )


@pytest.mark.django_db
class TestTaskTenantIsolation:
    """Two synthetic organisations with OVERLAPPING task titles, proving
    organisation B cannot read, transition, assign, or dependency-link
    organisation A's tasks through any route - the same release-blocking
    convention risk_register/tests/test_tenant_isolation.py already
    establishes for this codebase."""

    def test_member_can_read_own_organisations_task_list(self, client_a, org_a, user_a):
        _create(org_a, user_a, title="Overlapping title")
        response = client_a.get(reverse("security_tasks:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Overlapping title" in response.content

    def test_member_cannot_read_other_organisations_task_list(self, client_b, org_a, user_a):
        _create(org_a, user_a, title="Org A secret task")
        response = client_b.get(reverse("security_tasks:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_task_detail(self, client_b, org_a, user_a):
        task = _create(org_a, user_a)
        response = client_b.get(reverse("security_tasks:detail", args=[org_a.id, task.id]))
        assert response.status_code == 404

    def test_task_id_from_a_different_organisation_is_404_even_for_a_member(
        self, client_a, org_a, org_b, user_b
    ):
        """user_a is a member of org_a only. A task belonging to org_b
        must not be reachable through org_a's URL prefix."""
        other_org_task = _create(org_b, user_b, title="Overlapping title")
        response = client_a.get(reverse("security_tasks:detail", args=[org_a.id, other_org_task.id]))
        assert response.status_code == 404

    def test_forged_task_id_is_404(self, client_a, org_a):
        response = client_a.get(reverse("security_tasks:detail", args=[org_a.id, uuid.uuid4()]))
        assert response.status_code == 404

    def test_member_does_not_see_other_organisations_tasks_mixed_into_their_own_list(
        self, client_a, org_a, org_b, user_a, user_b
    ):
        _create(org_a, user_a, title="Org A own task")
        _create(org_b, user_b, title="Org B test task")
        response = client_a.get(reverse("security_tasks:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Org A own task" in content
        assert "Org B test task" not in content

    def test_member_cannot_transition_other_organisations_task(self, client_b, org_a, user_a):
        task = _create(org_a, user_a)
        response = client_b.post(
            reverse("security_tasks:transition", args=[org_a.id, task.id]),
            {"next_status": "in_progress", "reason": "work_started", "expected_version": 1},
        )
        assert response.status_code == 404
        task.refresh_from_db()
        assert task.status == "open"
        assert task.version == 1

    def test_member_cannot_assign_other_organisations_task(self, client_b, org_a, user_a, user_b):
        task = _create(org_a, user_a)
        response = client_b.post(
            reverse("security_tasks:assign", args=[org_a.id, task.id]),
            {"assignee": str(user_b.id), "expected_version": 1},
        )
        assert response.status_code == 404
        task.refresh_from_db()
        assert task.assigned_to_id is None

    def test_member_cannot_link_dependency_on_other_organisations_task(self, client_b, org_a, user_a):
        task = _create(org_a, user_a)
        other_task = _create(org_a, user_a, title="Other org A task")
        response = client_b.post(
            reverse("security_tasks:link_dependency", args=[org_a.id, task.id]),
            {"predecessor": str(other_task.id)},
        )
        assert response.status_code == 404

    def test_anonymous_user_is_redirected_to_login(self, client, org_a, user_a):
        task = _create(org_a, user_a)
        response = client.get(reverse("security_tasks:detail", args=[org_a.id, task.id]))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("security_tasks:list", args=[uuid.uuid4()]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestForeignOwnerAssignmentAttempt:
    """Service-layer proof, independent of the HTTP layer above: even a
    caller that bypasses the view/form entirely cannot assign a task to a
    user who is not CURRENTLY a member of that task's organisation."""

    def test_service_rejects_cross_organisation_assignee(self, org_a, org_b, user_a, user_b, member_b):
        task = _create(org_a, user_a)
        with pytest.raises(ForeignAssigneeError):
            services.assign_task(
                org_a, actor=user_a, task_id=task.id, expected_version=1, assignee_id=user_b.id
            )
        task.refresh_from_db()
        assert task.assigned_to_id is None

    def test_revoked_membership_is_rejected_on_next_assignment(self, org_a, user_a, user_c, member_c):
        task = _create(org_a, user_a)
        # user_c starts as a genuine member...
        updated = services.assign_task(
            org_a, actor=user_a, task_id=task.id, expected_version=1, assignee_id=user_c.id
        )
        assert updated.assigned_to_id == user_c.id
        # ...membership is revoked...
        member_c.delete()
        # ...a fresh assignment re-check (not a cached grant) must reject
        # user_c now, even though the task still shows them as the
        # existing assignee from before the revocation.
        with pytest.raises(ForeignAssigneeError):
            services.assign_task(
                org_a, actor=user_a, task_id=task.id, expected_version=updated.version, assignee_id=user_c.id
            )
