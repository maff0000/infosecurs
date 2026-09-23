import pytest

from activity.models import ActivityEvent


@pytest.mark.django_db
class TestActivityEventModel:
    def test_create_minimal_event(self, org_a, user_a):
        event = ActivityEvent.objects.create(
            organisation=org_a,
            event_type=ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
            actor=user_a,
            control_key="backups",
            metadata={"previous_answer": "unknown", "new_answer": "yes", "note_changed": False},
        )
        assert event.id is not None
        assert event.organisation == org_a
        assert event.actor == user_a
        assert event.occurred_at is not None

    def test_actor_is_nullable_for_system_initiated_events(self, org_a):
        event = ActivityEvent.objects.create(
            organisation=org_a,
            event_type=ActivityEvent.EVENT_EVIDENCE_CREATED,
            actor=None,
        )
        assert event.actor is None

    def test_default_ordering_is_most_recent_first(self, org_a):
        first = ActivityEvent.objects.create(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_CREATED
        )
        second = ActivityEvent.objects.create(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_CREATED
        )
        events = list(ActivityEvent.objects.filter(organisation=org_a))
        # second was created after first, so it must sort first.
        assert events[0].pk == second.pk or events[0].occurred_at >= events[1].occurred_at

    def test_actor_deletion_sets_null_not_cascade(self, org_a, make_user):
        user = make_user("to_be_deleted")
        event = ActivityEvent.objects.create(
            organisation=org_a,
            event_type=ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
            actor=user,
        )
        user.delete()
        event.refresh_from_db()
        assert event.actor is None
        # The event itself survives - it is not cascaded away with its actor.
        assert ActivityEvent.objects.filter(pk=event.pk).exists()

    def test_organisation_deletion_cascades(self, org_a):
        event = ActivityEvent.objects.create(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_CREATED
        )
        org_a.delete()
        assert not ActivityEvent.objects.filter(pk=event.pk).exists()

    def test_human_summary_for_control_answer_changed(self, org_a):
        event = ActivityEvent.objects.create(
            organisation=org_a,
            event_type=ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
            control_key="device_encryption",
            metadata={"previous_answer": "unknown", "new_answer": "yes", "note_changed": True},
        )
        summary = event.human_summary()
        assert "device_encryption" in summary
        assert "unknown" in summary
        assert "yes" in summary
        assert "note" in summary.lower()

    def test_human_summary_falls_back_to_display_label_for_other_event_types(self, org_a):
        event = ActivityEvent.objects.create(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_CREATED
        )
        assert event.human_summary() == "Evidence created"

    # --- Learning Signal Capture Addendum event types (M003-2a) ------------

    def test_risk_suggestion_edited_and_dismissed_are_valid_choices(self):
        # Learning Signal Capture Addendum §7: PID §12's fixed list is
        # illustrative, not exhaustive - the addendum authorises these two.
        choice_keys = {choice[0] for choice in ActivityEvent.EVENT_TYPE_CHOICES}
        assert ActivityEvent.EVENT_RISK_SUGGESTION_EDITED == "risk_suggestion_edited"
        assert ActivityEvent.EVENT_RISK_SUGGESTION_DISMISSED == "risk_suggestion_dismissed"
        assert "risk_suggestion_edited" in choice_keys
        assert "risk_suggestion_dismissed" in choice_keys

    def test_human_summary_for_risk_suggestion_edited(self, org_a):
        event = ActivityEvent.objects.create(
            organisation=org_a,
            event_type=ActivityEvent.EVENT_RISK_SUGGESTION_EDITED,
            related_object_type="risk",
            related_object_id="11111111-1111-1111-1111-111111111111",
            metadata={
                "impact": {"previous": 2, "new": 4},
                "vulnerability": {"previous": "old", "new": "new"},
            },
        )
        summary = event.human_summary()
        assert "impact" in summary
        assert "vulnerability" in summary

    def test_human_summary_for_risk_suggestion_dismissed(self, org_a):
        event = ActivityEvent.objects.create(
            organisation=org_a,
            event_type=ActivityEvent.EVENT_RISK_SUGGESTION_DISMISSED,
            related_object_type="risk",
            related_object_id="11111111-1111-1111-1111-111111111111",
            metadata={"title": "Unpatched laptop OS", "impact": 4, "likelihood": 3, "risk_band": "high"},
        )
        summary = event.human_summary()
        assert "Unpatched laptop OS" in summary
        assert "dismissed" in summary.lower()
