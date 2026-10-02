"""
HTTP-level tests for the remediation product UI (PID §6.5, §13, §18, §19).
"""
import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from remediation.models import RemediationAction
from risk_register.methodology import CATALOGUE_BY_ID


@pytest.mark.django_db
class TestActionCreate:
    def test_get_renders_empty_create_form(self, client_a, org_a):
        response = client_a.get(reverse("remediation:create", args=[org_a.id]))
        assert response.status_code == 200
        assert b"New remediation action" in response.content

    def test_post_creates_open_action_owned_by_requesting_user(self, client_a, org_a, user_a):
        response = client_a.post(
            reverse("remediation:create", args=[org_a.id]),
            {
                "title": "Enable MFA everywhere",
                "description": "Roll out MFA to all staff accounts.",
                "priority": "high",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 302
        action = RemediationAction.objects.get(organisation=org_a)
        assert action.title == "Enable MFA everywhere"
        assert action.status == RemediationAction.STATUS_OPEN
        assert action.priority == "high"
        assert action.created_by_id == user_a.id
        assert action.risk_id is None

    def test_post_emits_action_created_event(self, client_a, org_a, user_a):
        client_a.post(
            reverse("remediation:create", args=[org_a.id]),
            {
                "title": "Enable MFA everywhere",
                "description": "Roll out MFA to all staff accounts.",
                "priority": "high",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        action = RemediationAction.objects.get(organisation=org_a)
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_CREATED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "remediation_action"
        assert event.related_object_id == str(action.id)
        assert event.metadata == {
            "title": "Enable MFA everywhere",
            "created_from_risk": False,
        }

    def test_visiting_the_create_page_never_creates_an_action_by_itself(self, client_a, org_a):
        """Creation is explicit (PID §13) - a bare GET must never create a row."""
        client_a.get(reverse("remediation:create", args=[org_a.id]))
        assert RemediationAction.objects.filter(organisation=org_a).count() == 0

    def test_blank_title_is_rejected(self, client_a, org_a):
        response = client_a.post(
            reverse("remediation:create", args=[org_a.id]),
            {
                "title": "   ",
                "description": "",
                "priority": "medium",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 200
        assert RemediationAction.objects.filter(organisation=org_a).count() == 0


@pytest.mark.django_db
class TestActionCreateFromRisk:
    def test_get_prefills_title_and_shows_scenario_description_from_risk(
        self, client_a, org_a, risk_a
    ):
        response = client_a.get(
            reverse("remediation:create_from_risk", args=[org_a.id, risk_a.id])
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert risk_a.title in content
        scenario_treatment = CATALOGUE_BY_ID[risk_a.scenario_id].suggested_treatment
        assert scenario_treatment in content

    def test_get_never_creates_an_action_automatically(self, client_a, org_a, risk_a):
        """PID §13: 'Creation is explicit... do not automatically create actions for every risk.'"""
        client_a.get(reverse("remediation:create_from_risk", args=[org_a.id, risk_a.id]))
        assert RemediationAction.objects.filter(organisation=org_a).count() == 0

    def test_post_creates_action_linked_to_the_risk_with_scenario_description(
        self, client_a, org_a, risk_a, user_a
    ):
        response = client_a.post(
            reverse("remediation:create_from_risk", args=[org_a.id, risk_a.id]),
            {
                "title": risk_a.title,
                "priority": "medium",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 302
        action = RemediationAction.objects.get(organisation=org_a)
        assert action.risk_id == risk_a.id
        assert action.status == RemediationAction.STATUS_OPEN
        assert action.created_by_id == user_a.id
        assert action.description == CATALOGUE_BY_ID[risk_a.scenario_id].suggested_treatment

    def test_post_emits_action_created_event_with_risk_id(self, client_a, org_a, risk_a, user_a):
        client_a.post(
            reverse("remediation:create_from_risk", args=[org_a.id, risk_a.id]),
            {
                "title": risk_a.title,
                "priority": "medium",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        action = RemediationAction.objects.get(organisation=org_a)
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_CREATED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_id == str(action.id)
        assert event.metadata == {
            "title": risk_a.title,
            "created_from_risk": True,
            "risk_id": str(risk_a.id),
        }

    def test_user_can_edit_title_but_a_forged_description_override_is_ignored(
        self, client_a, org_a, risk_a
    ):
        """
        PID §13: 'user reviews/edits' - the title is genuinely editable.
        M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 10: description is NOT
        - there is no form field for it any more, so even a forged POST
        "description" key is silently ignored (ordinary Django behaviour
        for a POST key with no matching field), never persisted in place
        of the scenario's own verbatim text.
        """
        response = client_a.post(
            reverse("remediation:create_from_risk", args=[org_a.id, risk_a.id]),
            {
                "title": "A rewritten, more specific action title",
                "description": "A rewritten description the user actually wrote.",
                "priority": "critical",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 302
        action = RemediationAction.objects.get(organisation=org_a)
        assert action.title == "A rewritten, more specific action title"
        assert action.priority == "critical"
        assert action.description == CATALOGUE_BY_ID[risk_a.scenario_id].suggested_treatment
        assert "A rewritten description the user actually wrote." not in action.description

    def test_nonexistent_risk_id_is_404(self, client_a, org_a):
        import uuid

        response = client_a.get(
            reverse("remediation:create_from_risk", args=[org_a.id, uuid.uuid4()])
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestActionList:
    def test_lists_actions_grouped_by_status(self, client_a, org_a, user_a):
        RemediationAction.objects.create(
            organisation=org_a, title="Open one", created_by=user_a, status=RemediationAction.STATUS_OPEN
        )
        RemediationAction.objects.create(
            organisation=org_a, title="Done one", created_by=user_a, status=RemediationAction.STATUS_DONE
        )
        response = client_a.get(reverse("remediation:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Open one" in response.content
        assert b"Done one" in response.content

    def test_status_filter_narrows_to_one_group(self, client_a, org_a, user_a):
        RemediationAction.objects.create(
            organisation=org_a, title="Open one", created_by=user_a, status=RemediationAction.STATUS_OPEN
        )
        RemediationAction.objects.create(
            organisation=org_a, title="Done one", created_by=user_a, status=RemediationAction.STATUS_DONE
        )
        response = client_a.get(reverse("remediation:list", args=[org_a.id]) + "?status=open")
        content = response.content.decode()
        assert "Open one" in content
        assert "Done one" not in content


@pytest.mark.django_db
class TestActionEdit:
    def test_edit_updates_fields_without_touching_status(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="Original title", created_by=user_a,
            description="Original, programmatically-set description.",
        )
        response = client_a.post(
            reverse("remediation:edit", args=[org_a.id, action.id]),
            {
                "title": "Updated title",
                "description": "Updated description",
                "priority": "critical",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 302
        action.refresh_from_db()
        assert action.title == "Updated title"
        assert action.priority == "critical"
        assert action.status == RemediationAction.STATUS_OPEN
        # M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 10: description is not
        # a form field on `remediation:edit` either - a forged POST
        # "description" value must be silently ignored, never persisted.
        assert action.description == "Original, programmatically-set description."


@pytest.mark.django_db
class TestActionLifecycleTransitions:
    def test_get_is_not_allowed_on_transition_endpoints(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a
        )
        for name in ("start", "complete", "accept"):
            response = client_a.get(reverse(f"remediation:{name}", args=[org_a.id, action.id]))
            assert response.status_code == 405

    def test_start_moves_open_to_in_progress(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a
        )
        response = client_a.post(reverse("remediation:start", args=[org_a.id, action.id]))
        assert response.status_code == 302
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_IN_PROGRESS

    def test_start_emits_action_status_changed_event(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a
        )
        client_a.post(reverse("remediation:start", args=[org_a.id, action.id]))
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_STATUS_CHANGED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "remediation_action"
        assert event.related_object_id == str(action.id)
        assert event.metadata == {
            "previous_status": RemediationAction.STATUS_OPEN,
            "new_status": RemediationAction.STATUS_IN_PROGRESS,
        }

    def test_start_rejected_when_not_open(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a, status=RemediationAction.STATUS_DONE
        )
        response = client_a.post(reverse("remediation:start", args=[org_a.id, action.id]), follow=True)
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_DONE

    def test_complete_from_open_sets_done_and_completed_fields(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a
        )
        response = client_a.post(reverse("remediation:complete", args=[org_a.id, action.id]))
        assert response.status_code == 302
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_DONE
        assert action.completed_by_id == user_a.id
        assert action.completed_at is not None

    def test_complete_from_in_progress_sets_done(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a,
            title="A",
            created_by=user_a,
            status=RemediationAction.STATUS_IN_PROGRESS,
        )
        client_a.post(reverse("remediation:complete", args=[org_a.id, action.id]))
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_DONE

    def test_complete_emits_action_status_changed_event(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a,
            title="A",
            created_by=user_a,
            status=RemediationAction.STATUS_IN_PROGRESS,
        )
        client_a.post(reverse("remediation:complete", args=[org_a.id, action.id]))
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_STATUS_CHANGED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "remediation_action"
        assert event.related_object_id == str(action.id)
        assert event.metadata == {
            "previous_status": RemediationAction.STATUS_IN_PROGRESS,
            "new_status": RemediationAction.STATUS_DONE,
        }

    def test_complete_rejected_when_already_closed(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a, status=RemediationAction.STATUS_ACCEPTED
        )
        client_a.post(reverse("remediation:complete", args=[org_a.id, action.id]))
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_ACCEPTED  # unchanged

    def test_accept_from_open_sets_accepted_and_completed_fields(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a
        )
        response = client_a.post(reverse("remediation:accept", args=[org_a.id, action.id]))
        assert response.status_code == 302
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_ACCEPTED
        assert action.completed_by_id == user_a.id
        assert action.completed_at is not None

    def test_accept_emits_action_status_changed_event(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a
        )
        client_a.post(reverse("remediation:accept", args=[org_a.id, action.id]))
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_STATUS_CHANGED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "remediation_action"
        assert event.related_object_id == str(action.id)
        assert event.metadata == {
            "previous_status": RemediationAction.STATUS_OPEN,
            "new_status": RemediationAction.STATUS_ACCEPTED,
        }

    def test_accept_rejected_when_already_closed(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a, status=RemediationAction.STATUS_DONE
        )
        client_a.post(reverse("remediation:accept", args=[org_a.id, action.id]))
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_DONE  # unchanged

    def test_detail_page_shows_accepted_not_resolved_wording(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="A", created_by=user_a, status=RemediationAction.STATUS_ACCEPTED
        )
        response = client_a.get(reverse("remediation:detail", args=[org_a.id, action.id]))
        content = response.content.decode()
        assert "not mean the underlying control requirement is met" in content
