"""
Release-blocking (M003 PID §16, matching organisations/tests/
test_tenant_isolation.py's shape): a member of one organisation must not
be able to see another organisation's activity timeline, by manipulating
the organisation id in the URL.
"""
import uuid

import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from activity.services import record_event


@pytest.mark.django_db
class TestActivityTenantIsolation:
    def test_member_can_read_own_organisation_activity(self, client_a, org_a):
        record_event(org_a, ActivityEvent.EVENT_ACTION_CREATED)
        response = client_a.get(reverse("activity:list", args=[org_a.id]))
        assert response.status_code == 200

    def test_member_cannot_read_other_organisations_activity_list(self, client_b, org_a):
        response = client_b.get(reverse("activity:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_other_organisations_events_never_appear_in_the_list(self, client_a, org_a, org_b):
        record_event(
            org_a,
            ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
            control_key="mfa_user_accounts",
            metadata={"previous_answer": "unknown", "new_answer": "yes", "note_changed": False},
        )
        record_event(
            org_b,
            ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
            control_key="patching",
            metadata={"previous_answer": "unknown", "new_answer": "no", "note_changed": False},
        )
        response = client_a.get(reverse("activity:list", args=[org_a.id]))
        content = response.content.decode()
        assert "mfa_user_accounts" in content
        assert "patching" not in content

    def test_nonexistent_organisation_id_in_url_is_404_not_error(self, client_a):
        response = client_a.get(reverse("activity:list", args=[uuid.uuid4()]))
        assert response.status_code == 404
