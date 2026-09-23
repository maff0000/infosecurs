import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from activity.services import record_event


@pytest.mark.django_db
class TestActivityListView:
    def test_requires_login(self, client, org_a):
        response = client.get(reverse("activity:list", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_renders_empty_state_with_no_events(self, client_a, org_a):
        response = client_a.get(reverse("activity:list", args=[org_a.id]))
        assert response.status_code == 200
        assert "No activity recorded yet." in response.content.decode()

    def test_renders_a_human_readable_summary_for_a_recorded_event(self, client_a, org_a, user_a):
        record_event(
            org_a,
            ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
            actor=user_a,
            control_key="backups",
            metadata={"previous_answer": "unknown", "new_answer": "yes", "note_changed": False},
        )
        response = client_a.get(reverse("activity:list", args=[org_a.id]))
        content = response.content.decode()
        assert response.status_code == 200
        assert "backups" in content
        assert "unknown" in content
        assert "yes" in content
        assert user_a.username in content

    def test_pagination_bounds_the_page_to_page_size(self, client_a, org_a):
        for _ in range(60):
            record_event(org_a, ActivityEvent.EVENT_ACTION_CREATED)
        response = client_a.get(reverse("activity:list", args=[org_a.id]))
        assert response.status_code == 200
        assert response.context["page_obj"].paginator.count == 60
        assert len(response.context["page_obj"].object_list) == 50

        second_page = client_a.get(reverse("activity:list", args=[org_a.id]), {"page": 2})
        assert len(second_page.context["page_obj"].object_list) == 10
