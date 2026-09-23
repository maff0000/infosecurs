"""
Unit tests for `activity.services.record_event` - the one code path that
writes an `ActivityEvent` row.
"""
import pytest

from activity.models import ActivityEvent
from activity.services import record_event


@pytest.mark.django_db
class TestRecordEvent:
    def test_creates_and_returns_a_persisted_event(self, org_a, user_a):
        event = record_event(
            org_a,
            ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
            actor=user_a,
            control_key="backups",
            metadata={"previous_answer": "unknown", "new_answer": "yes", "note_changed": False},
        )
        assert event.pk is not None
        stored = ActivityEvent.objects.get(pk=event.pk)
        assert stored.organisation == org_a
        assert stored.actor == user_a
        assert stored.control_key == "backups"
        assert stored.metadata == {
            "previous_answer": "unknown",
            "new_answer": "yes",
            "note_changed": False,
        }

    def test_defaults_actor_to_none(self, org_a):
        event = record_event(org_a, ActivityEvent.EVENT_ACTION_CREATED)
        assert event.actor is None

    def test_defaults_metadata_to_empty_dict(self, org_a):
        event = record_event(org_a, ActivityEvent.EVENT_ACTION_CREATED)
        assert event.metadata == {}

    def test_defaults_control_key_and_related_object_fields_to_blank(self, org_a):
        event = record_event(org_a, ActivityEvent.EVENT_ACTION_CREATED)
        assert event.control_key == ""
        assert event.related_object_type == ""
        assert event.related_object_id == ""

    def test_related_object_type_and_id_are_stored(self, org_a):
        event = record_event(
            org_a,
            ActivityEvent.EVENT_EVIDENCE_CREATED,
            related_object_type="evidence_item",
            related_object_id="11111111-1111-1111-1111-111111111111",
        )
        assert event.related_object_type == "evidence_item"
        assert event.related_object_id == "11111111-1111-1111-1111-111111111111"

    def test_unknown_event_type_is_rejected(self, org_a):
        with pytest.raises(ValueError):
            record_event(org_a, "not_a_real_event_type")

    def test_every_pid_named_event_type_is_accepted(self, org_a):
        # PID §12's fixed list - every one must be constructible even
        # though only control_answer_changed has a real emitter yet.
        for event_type, _label in ActivityEvent.EVENT_TYPE_CHOICES:
            event = record_event(org_a, event_type)
            assert event.event_type == event_type
