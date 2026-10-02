"""
Learning Signal Capture Addendum tests (M003-2a dispatch).

`docs/pids/M003-LEARNING-SIGNAL-CAPTURE-ADDENDUM.md` §3/§7: M002's
risk-domain corrections - an AI-suggested risk later edited, or dismissed,
by a customer - must be recorded as structured `ActivityEvent` rows, using
the same `activity.services.record_event()` mechanism the rest of M003
uses (not a second, parallel logging system). These tests prove
`risk_register.views.risk_edit`/`risk_dismiss` do that, with the right
delta/metadata shape, only when something actually changed, transactionally
coherent with the underlying save (PID §17), and tenant-scoped.

M008C-WI3 update: `threat`/`vulnerability` are no longer editable via
`risk_register:edit` at all (M008-FREE-TEXT-REPLACEMENT-REGISTER.md rows
6-7) - removed from `_edit_payload`/`_RISK_EDIT_DELTA_FIELDS` coverage
below. `rationale`/`proposed_treatment` are now closed-form codes (rows
8-9, `risk_register.risk_choices`) rather than free text.
"""
import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from risk_register.models import Risk
from risk_register.risk_choices import TREATMENT_MITIGATE_SUGGESTED


def _draft_risk(org, **overrides):
    defaults = dict(
        organisation=org,
        title="Original title",
        threat="Original threat",
        vulnerability="Original vulnerability",
        impact=2,
        likelihood=2,
        rationale="impact_2_limited_scope",
        proposed_treatment=TREATMENT_MITIGATE_SUGGESTED,
        status=Risk.STATUS_DRAFT_AI_SUGGESTED,
        source=Risk.SOURCE_AI,
    )
    defaults.update(overrides)
    return Risk.objects.create(**defaults)


def _edit_payload(**overrides):
    payload = {
        "title": "Original title",
        "impact": "2",
        "likelihood": "2",
        "rationale": "impact_2_limited_scope",
        "proposed_treatment": TREATMENT_MITIGATE_SUGGESTED,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestRiskEditActivityCapture:
    def test_edit_creates_exactly_one_event_with_only_changed_fields_in_delta(
        self, client_a, org_a, user_a
    ):
        risk = _draft_risk(org_a)

        response = client_a.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            _edit_payload(impact="4"),
        )
        assert response.status_code == 302

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_RISK_SUGGESTION_EDITED
        )
        assert events.count() == 1
        event = events.first()
        assert event.actor == user_a
        assert event.related_object_type == "risk"
        assert event.related_object_id == str(risk.id)
        assert event.metadata == {
            "impact": {"previous": 2, "new": 4},
        }
        # Unchanged fields must not appear in the delta at all.
        for untouched in ("title", "likelihood", "rationale", "proposed_treatment"):
            assert untouched not in event.metadata

    def test_edit_with_no_actual_changes_creates_no_event(self, client_a, org_a):
        risk = _draft_risk(org_a)

        response = client_a.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            _edit_payload(),  # identical to the risk's current values
        )
        assert response.status_code == 302
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_RISK_SUGGESTION_EDITED
        ).exists()

    def test_edit_events_are_scoped_to_the_correct_organisation(self, client_a, org_a, org_b):
        risk = _draft_risk(org_a)
        client_a.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            _edit_payload(title="Retitled"),
        )
        assert ActivityEvent.objects.filter(organisation=org_a).count() == 1
        assert ActivityEvent.objects.filter(organisation=org_b).count() == 0

    def test_edit_rollback_leaves_no_event_and_no_saved_change(
        self, client_a, org_a, monkeypatch
    ):
        """
        Forces a contrived failure inside the risk_edit view's
        transaction.atomic() block (record_event raising) to prove the
        save and the event are transactionally coherent (PID §17): a
        rolled-back save must never leave an orphaned event, and - just as
        importantly here - a failure recording the event must roll back
        the save too, since both now live in the same atomic block.
        """
        risk = _draft_risk(org_a)

        def _boom(*args, **kwargs):
            raise RuntimeError("forced failure to prove atomicity")

        monkeypatch.setattr("risk_register.views.record_event", _boom)

        with pytest.raises(RuntimeError):
            client_a.post(
                reverse("risk_register:edit", args=[org_a.id, risk.id]),
                _edit_payload(title="Should not persist", impact="5"),
            )

        risk.refresh_from_db()
        assert risk.title == "Original title"
        assert risk.impact == 2
        assert not ActivityEvent.objects.filter(organisation=org_a).exists()


@pytest.mark.django_db
class TestRiskDismissActivityCapture:
    def test_dismiss_creates_exactly_one_event_with_suggested_values(
        self, client_a, org_a, user_a
    ):
        risk = _draft_risk(org_a, title="Suggested risk", impact=4, likelihood=3)

        response = client_a.post(reverse("risk_register:dismiss", args=[org_a.id, risk.id]))
        assert response.status_code == 302

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_RISK_SUGGESTION_DISMISSED
        )
        assert events.count() == 1
        event = events.first()
        assert event.actor == user_a
        assert event.related_object_type == "risk"
        assert event.related_object_id == str(risk.id)
        assert event.metadata == {
            "title": "Suggested risk",
            "impact": 4,
            "likelihood": 3,
            "risk_band": "high",  # score = 4*3 = 12 -> high band
        }

    def test_dismiss_events_are_scoped_to_the_correct_organisation(self, client_a, org_a, org_b):
        risk = _draft_risk(org_a)
        client_a.post(reverse("risk_register:dismiss", args=[org_a.id, risk.id]))
        assert ActivityEvent.objects.filter(organisation=org_a).count() == 1
        assert ActivityEvent.objects.filter(organisation=org_b).count() == 0

    def test_dismiss_rollback_leaves_no_event_and_no_status_change(
        self, client_a, org_a, monkeypatch
    ):
        """See TestRiskEditActivityCapture.test_edit_rollback_... - same
        rationale, applied to risk_dismiss's own transaction.atomic()
        block."""
        risk = _draft_risk(org_a)

        def _boom(*args, **kwargs):
            raise RuntimeError("forced failure to prove atomicity")

        monkeypatch.setattr("risk_register.views.record_event", _boom)

        with pytest.raises(RuntimeError):
            client_a.post(reverse("risk_register:dismiss", args=[org_a.id, risk.id]))

        risk.refresh_from_db()
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED
        assert risk.dismissed_by_id is None
        assert risk.dismissed_at is None
        assert not ActivityEvent.objects.filter(organisation=org_a).exists()
