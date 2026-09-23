"""
HTTP-level tests for the section-based draft editor
(`policy.views.policy_edit`, PID §16, §26 "Policy lifecycle: edit" -
m004-2b-policy-lifecycle dispatch).
"""
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from activity.models import ActivityEvent
from policy.models import ImmutablePolicyVersionError, PolicyVersion


@pytest.mark.django_db
class TestPolicyEditView:
    def test_get_renders_form_with_current_content(self, client_a, org_a, make_draft_version):
        version = make_draft_version(org_a)
        response = client_a.get(reverse("policy:version_edit", args=[org_a.id, version.id]))
        assert response.status_code == 200
        assert b"Purpose text." in response.content
        assert b"Access text." in response.content

    def test_get_renders_next_review_date_input_in_iso_format(
        self, client_a, org_a, make_draft_version
    ):
        # M004 post-audit repair, Finding 1 (PRODUCT RED): LANGUAGE_CODE
        # "en-gb" must never leak DD/MM/YYYY into the rendered <input
        # type="date"> value attribute - an HTML5 date input only accepts
        # ISO yyyy-MM-dd, or the picker renders blank in a real browser.
        version = make_draft_version(
            org_a, next_review_date=datetime.date(2027, 9, 23)
        )
        response = client_a.get(reverse("policy:version_edit", args=[org_a.id, version.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="next_review_date"' in content
        assert 'value="2027-09-23"' in content
        assert "23/09/2027" not in content

    def test_edit_persists_and_emits_exactly_one_event_with_correct_delta(
        self, client_a, org_a, user_a, make_draft_version
    ):
        version = make_draft_version(org_a, next_review_date=None)
        response = client_a.post(
            reverse("policy:version_edit", args=[org_a.id, version.id]),
            data={
                "title": "Updated Title",
                "next_review_date": "2027-06-15",
                "section__purpose_and_scope": "Updated purpose text.",
                "section__access_and_authentication": "Access text.",  # unchanged
            },
        )
        assert response.status_code == 302

        version.refresh_from_db()
        assert version.title == "Updated Title"
        assert str(version.next_review_date) == "2027-06-15"
        contents = {s["section_key"]: s["content"] for s in version.sections}
        assert contents["purpose_and_scope"] == "Updated purpose text."
        assert contents["access_and_authentication"] == "Access text."

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_DRAFT_EDITED
        )
        assert events.count() == 1
        event = events.get()
        assert event.related_object_type == "policy_version"
        assert event.related_object_id == str(version.id)
        assert event.metadata == {
            "changed_sections": ["purpose_and_scope"],
            "title_changed": True,
            "next_review_date_changed": True,
        }
        assert event.actor == user_a
        # PID §16: activity events need not duplicate large policy text -
        # confirm the actual edited content is NOT sitting in metadata.
        assert "Updated purpose text." not in str(event.metadata)

    def test_edit_with_no_actual_change_emits_no_event(self, client_a, org_a, make_draft_version):
        version = make_draft_version(org_a, next_review_date=None)
        response = client_a.post(
            reverse("policy:version_edit", args=[org_a.id, version.id]),
            data={
                "title": version.title,
                "next_review_date": "",
                "section__purpose_and_scope": "Purpose text.",
                "section__access_and_authentication": "Access text.",
            },
        )
        assert response.status_code == 302
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_DRAFT_EDITED
        ).exists()

    def test_only_changed_section_is_reported_when_two_sections_exist_and_one_changes(
        self, client_a, org_a, make_draft_version
    ):
        version = make_draft_version(org_a, next_review_date=None)
        client_a.post(
            reverse("policy:version_edit", args=[org_a.id, version.id]),
            data={
                "title": version.title,
                "next_review_date": "",
                "section__purpose_and_scope": "Purpose text.",  # unchanged
                "section__access_and_authentication": "New access text.",  # changed
            },
        )
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_DRAFT_EDITED
        )
        assert event.metadata["changed_sections"] == ["access_and_authentication"]
        assert event.metadata["title_changed"] is False
        assert event.metadata["next_review_date_changed"] is False

    def test_editing_non_draft_version_blocked_at_view_layer_with_clear_error(
        self, client_a, org_a, make_draft_version
    ):
        version = make_draft_version(
            org_a, status=PolicyVersion.STATUS_APPROVED, approved_at=timezone.now()
        )
        original_title = version.title

        response = client_a.post(
            reverse("policy:version_edit", args=[org_a.id, version.id]),
            data={
                "title": "sneaky new title",
                "next_review_date": "",
                "section__purpose_and_scope": "sneaky content",
                "section__access_and_authentication": "sneaky content",
            },
            follow=True,
        )
        version.refresh_from_db()
        assert version.title == original_title
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_DRAFT_EDITED
        ).exists()
        shown_messages = [str(m) for m in response.context["messages"]]
        assert any("Only a draft policy version can be edited" in m for m in shown_messages)

    def test_get_on_non_draft_version_also_redirects_with_error(
        self, client_a, org_a, make_draft_version
    ):
        version = make_draft_version(
            org_a, status=PolicyVersion.STATUS_SUPERSEDED
        )
        response = client_a.get(
            reverse("policy:version_edit", args=[org_a.id, version.id]), follow=True
        )
        shown_messages = [str(m) for m in response.context["messages"]]
        assert any("Only a draft policy version can be edited" in m for m in shown_messages)

    def test_model_layer_immutability_backstop_still_fires_if_view_layer_is_bypassed(
        self, org_a, make_draft_version
    ):
        """Defence in depth (PID §16): even if a caller bypassed the view's
        own draft-only gate entirely and mutated an approved PolicyVersion
        object directly, `PolicyVersion.save()`'s own guard still refuses
        the write - re-confirmed here at the same layer the dispatch
        instructions ask for, not merely re-relying on
        policy/tests/test_models.py's existing coverage of this guard."""
        version = make_draft_version(
            org_a, status=PolicyVersion.STATUS_APPROVED, approved_at=timezone.now()
        )
        version.title = "bypassed the view layer"
        with pytest.raises(ImmutablePolicyVersionError):
            version.save()

    def test_edit_requires_login(self, client, org_a, make_draft_version):
        version = make_draft_version(org_a)
        response = client.get(reverse("policy:version_edit", args=[org_a.id, version.id]))
        assert response.status_code in (302, 403)
