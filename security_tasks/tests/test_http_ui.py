import uuid

import pytest
from django.urls import reverse

from entitlements.models import ProductArea
from security_tasks import services
from security_tasks.models import TaskKind


def _create(org, user, title="Org task"):
    return services.create_task(
        org, actor=user, kind=TaskKind.MANUAL_OTHER, title=title, idempotency_key=str(uuid.uuid4())
    )


@pytest.mark.django_db
class TestTasksProductAreaSeed:
    def test_tasks_product_area_exists_and_is_additive(self):
        area = ProductArea.objects.get(code="tasks")
        assert area.destination_view_name == "security_tasks:list"
        assert area.is_active is True
        assert area.show_in_navigation is True

    def test_irene_placeholder_product_area_exists_but_not_in_navigation(self):
        area = ProductArea.objects.get(code="irene")
        assert area.is_active is True
        assert area.show_in_navigation is False

    def test_existing_sixteen_product_areas_are_untouched(self):
        existing_codes = [
            "home", "foundations", "customer_assurance", "security", "security_state",
            "baseline", "assets", "risks", "evidence", "remediation", "policies",
            "company", "profile", "governance", "workplace", "activity",
        ]
        assert ProductArea.objects.filter(code__in=existing_codes).count() == 16
        home = ProductArea.objects.get(code="home")
        assert home.destination_view_name == "organisations:detail"
        assert home.min_package_tier == 0
        baseline = ProductArea.objects.get(code="baseline")
        assert baseline.parent.code == "security"


@pytest.mark.django_db
class TestTasksSidebarLink:
    def test_tasks_link_appears_in_navigation(self, client_a, org_a):
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert reverse("security_tasks:list", args=[org_a.id]).encode() in response.content


@pytest.mark.django_db
class TestTaskListPage:
    def test_list_page_renders_empty_state(self, client_a, org_a):
        response = client_a.get(reverse("security_tasks:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"No tasks match these filters." in response.content

    def test_list_page_status_filter(self, client_a, org_a, user_a):
        _create(org_a, user_a, title="Open task here")
        response = client_a.get(reverse("security_tasks:list", args=[org_a.id]), {"status": "done"})
        assert response.status_code == 200
        assert b"Open task here" not in response.content

    def test_list_page_search_filter(self, client_a, org_a, user_a):
        _create(org_a, user_a, title="Findable unique title xyz")
        _create(org_a, user_a, title="Something else entirely")
        response = client_a.get(reverse("security_tasks:list", args=[org_a.id]), {"q": "unique title xyz"})
        content = response.content.decode()
        assert "Findable unique title xyz" in content
        assert "Something else entirely" not in content

    def test_list_page_pagination(self, client_a, org_a, user_a):
        for i in range(30):
            _create(org_a, user_a, title=f"Task number {i}")
        response = client_a.get(reverse("security_tasks:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Page 1 of 2" in response.content


@pytest.mark.django_db
class TestTaskCreateFlow:
    def test_get_create_page_renders_idempotency_token(self, client_a, org_a):
        response = client_a.get(reverse("security_tasks:create", args=[org_a.id]))
        assert response.status_code == 200
        assert b'type="hidden"' in response.content

    def test_post_create_task_redirects_to_detail(self, client_a, org_a):
        get_response = client_a.get(reverse("security_tasks:create", args=[org_a.id]))
        token = get_response.context["form"]["idempotency_key"].value()
        response = client_a.post(
            reverse("security_tasks:create", args=[org_a.id]),
            {"title": "New follow-up", "summary": "", "priority": "normal", "assignee": "", "idempotency_key": token},
        )
        assert response.status_code == 302
        detail_response = client_a.get(response.url)
        assert b"New follow-up" in detail_response.content

    def test_double_submit_with_same_token_creates_one_task(self, client_a, org_a):
        from security_tasks.models import SecurityTask

        get_response = client_a.get(reverse("security_tasks:create", args=[org_a.id]))
        token = get_response.context["form"]["idempotency_key"].value()
        payload = {"title": "Double submit", "summary": "", "priority": "normal", "assignee": "", "idempotency_key": token}
        client_a.post(reverse("security_tasks:create", args=[org_a.id]), payload)
        client_a.post(reverse("security_tasks:create", args=[org_a.id]), payload)
        assert SecurityTask.objects.filter(organisation=org_a, title="Double submit").count() == 1


@pytest.mark.django_db
class TestTaskTransitionAndAssignFlow:
    def test_transition_via_post(self, client_a, org_a, user_a):
        task = _create(org_a, user_a)
        response = client_a.post(
            reverse("security_tasks:transition", args=[org_a.id, task.id]),
            {"next_status": "in_progress", "reason": "work_started", "expected_version": 1},
        )
        assert response.status_code == 302
        task.refresh_from_db()
        assert task.status == "in_progress"

    def test_assign_via_post(self, client_a, org_a, user_a, user_c, member_c):
        task = _create(org_a, user_a)
        response = client_a.post(
            reverse("security_tasks:assign", args=[org_a.id, task.id]),
            {"assignee": str(user_c.id), "expected_version": 1},
        )
        assert response.status_code == 302
        task.refresh_from_db()
        assert task.assigned_to_id == user_c.id

    def test_assign_via_post_to_non_member_shows_error_not_500(self, client_a, org_a, org_b, user_a, user_b, member_b):
        task = _create(org_a, user_a)
        response = client_a.post(
            reverse("security_tasks:assign", args=[org_a.id, task.id]),
            {"assignee": str(user_b.id), "expected_version": 1},
        )
        assert response.status_code == 302
        task.refresh_from_db()
        assert task.assigned_to_id is None

    def test_get_methods_not_allowed_for_transition(self, client_a, org_a, user_a):
        task = _create(org_a, user_a)
        response = client_a.get(reverse("security_tasks:transition", args=[org_a.id, task.id]))
        assert response.status_code == 405


@pytest.mark.django_db
class TestTaskTextEscaping:
    def test_hostile_title_is_escaped_in_list_and_detail(self, client_a, org_a, user_a):
        hostile = "<script>alert(document.cookie)</script>"
        task = _create(org_a, user_a, title=hostile)
        list_response = client_a.get(reverse("security_tasks:list", args=[org_a.id]))
        detail_response = client_a.get(reverse("security_tasks:detail", args=[org_a.id, task.id]))
        assert b"<script>alert(document.cookie)</script>" not in list_response.content
        assert b"<script>alert(document.cookie)</script>" not in detail_response.content
        assert b"&lt;script&gt;" in list_response.content
        assert b"&lt;script&gt;" in detail_response.content
