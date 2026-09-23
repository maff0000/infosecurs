"""
Approval-flow tests (PID §17-18, §26 "Policy lifecycle: direct approval /
external approval recorded / supersession correct", ADR-0002 §4.1 -
m004-2b-policy-lifecycle dispatch). Covers both `policy.services`
(`approve_policy_directly`, `record_external_policy_approval`,
`create_new_draft_from_approved`) and the HTTP views that front them.
"""
import datetime
import re

import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from policy.models import PolicyVersion
from policy.presentation import approval_summary
from policy.services import (
    PolicyLifecycleError,
    approve_policy_directly,
    create_new_draft_from_approved,
    record_external_policy_approval,
)


# --- Direct approval (PID §17.1) -------------------------------------------------


@pytest.mark.django_db
class TestApprovePolicyDirectlyService:
    def test_direct_approval_sets_fields_and_emits_event(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)
        review_date = datetime.date(2027, 1, 1)

        approved = approve_policy_directly(version, actor=user_a, next_review_date=review_date)

        assert approved.status == PolicyVersion.STATUS_APPROVED
        assert approved.policy_authoriser_id == person_a.id
        assert approved.approval_mode == PolicyVersion.APPROVAL_MODE_DIRECT
        assert approved.approved_by_id == user_a.id
        assert approved.approved_at is not None
        assert approved.next_review_date == review_date

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_APPROVED
        )
        assert events.count() == 1
        event = events.get()
        assert event.metadata == {"version_number": version.version_number, "approval_mode": "direct"}
        assert event.actor == user_a

    def test_direct_approval_refused_when_actor_is_not_the_authoriser(
        self, org_a, user_a, external_person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, external_person_a)
        version = make_draft_version(org_a)

        with pytest.raises(PolicyLifecycleError):
            approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT

    def test_direct_approval_refused_when_no_authoriser_assigned(
        self, org_a, user_a, make_draft_version
    ):
        version = make_draft_version(org_a)
        with pytest.raises(PolicyLifecycleError):
            approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

    def test_direct_approval_refused_for_non_draft_version(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a, status=PolicyVersion.STATUS_SUPERSEDED)
        with pytest.raises(PolicyLifecycleError):
            approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))


# --- External-recorded approval (PID §17.2, ADR-0002 §4.1) ----------------------


@pytest.mark.django_db
class TestRecordExternalPolicyApprovalService:
    def test_external_approval_sets_fields_and_emits_event(
        self, org_a, user_a, external_person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, external_person_a)
        version = make_draft_version(org_a)
        review_date = datetime.date(2027, 3, 1)

        approved = record_external_policy_approval(
            version, actor=user_a, next_review_date=review_date
        )

        assert approved.status == PolicyVersion.STATUS_APPROVED
        assert approved.policy_authoriser_id == external_person_a.id
        assert approved.approval_mode == PolicyVersion.APPROVAL_MODE_EXTERNAL_RECORDED
        # The Account Holder is who RECORDED it, never the named authoriser.
        assert approved.approved_by_id == user_a.id
        assert approved.next_review_date == review_date

        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_APPROVED
        )
        assert event.metadata["approval_mode"] == "external_recorded"
        assert event.actor == user_a

    def test_external_approval_refused_when_actor_is_the_authoriser(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        """PID's own instruction: never silently fall back to recording an
        external approval when a direct one was the true case."""
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)
        with pytest.raises(PolicyLifecycleError):
            record_external_policy_approval(
                version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
            )
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT

    def test_external_approval_refused_when_no_authoriser_assigned(
        self, org_a, user_a, make_draft_version
    ):
        version = make_draft_version(org_a)
        with pytest.raises(PolicyLifecycleError):
            record_external_policy_approval(
                version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
            )


# --- Approval-wording honesty (ADR-0002 §4.1) ------------------------------------


@pytest.mark.django_db
class TestApprovalSummaryWording:
    def test_direct_wording_names_the_authoriser_as_approver(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))
        text = approval_summary(version)
        assert person_a.full_name in text
        assert "Policy Authoriser" in text
        assert "external" not in text.lower()

    def test_external_wording_never_implies_authoriser_logged_in(
        self, org_a, user_a, external_person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, external_person_a)
        version = make_draft_version(org_a)
        record_external_policy_approval(
            version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        text = approval_summary(version)
        # The named authoriser must be described as who the record is
        # ABOUT, and the Account Holder as who did the recording - never
        # the reverse, and never phrased as "approved by <authoriser>"
        # standing alone.
        assert "recorded by" in text
        assert external_person_a.full_name in text
        assert external_person_a.job_title in text
        assert text.index("recorded by") < text.index(external_person_a.full_name)
        assert f"approved by {external_person_a.full_name}" not in text


# --- Supersession (PID §15, §17, §26 "supersession correct") --------------------


@pytest.mark.django_db
class TestSupersessionOnApproval:
    def test_approving_a_second_version_supersedes_the_first(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        first = make_draft_version(org_a, version_number=1)
        approve_policy_directly(first, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        second = make_draft_version(org_a, version_number=2, title="Org Information Security Policy v2")
        approve_policy_directly(second, actor=user_a, next_review_date=datetime.date(2028, 1, 1))

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.status == PolicyVersion.STATUS_SUPERSEDED
        assert first.superseded_by_id == second.id
        assert second.status == PolicyVersion.STATUS_APPROVED

        assert (
            PolicyVersion.objects.filter(
                organisation=org_a, status=PolicyVersion.STATUS_APPROVED
            ).count()
            == 1
        )

        superseded_event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_SUPERSEDED
        )
        assert superseded_event.related_object_id == str(first.id)
        assert superseded_event.metadata == {"superseded_by_version_number": second.version_number}

    def test_first_approval_emits_no_superseded_event(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_SUPERSEDED
        ).exists()


# --- New draft from approved (PID §15, §26 "new draft does not mutate approved") -


@pytest.mark.django_db
class TestCreateNewDraftFromApproved:
    def test_creates_independent_copy_and_leaves_approved_row_untouched(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        approved = make_draft_version(org_a)
        approve_policy_directly(approved, actor=user_a, next_review_date=datetime.date(2027, 1, 1))
        approved.refresh_from_db()
        original_sections = [dict(s) for s in approved.sections]
        original_title = approved.title
        original_updated_at = approved.updated_at

        new_draft = create_new_draft_from_approved(approved, actor=user_a)

        assert new_draft.id != approved.id
        assert new_draft.status == PolicyVersion.STATUS_DRAFT
        assert new_draft.version_number == approved.version_number + 1
        assert new_draft.title == original_title
        assert new_draft.sections == original_sections
        assert new_draft.generation_source == PolicyVersion.GENERATION_SOURCE_MANUAL

        # A genuinely independent copy - editing the new draft must never
        # touch the approved row's own sections list object.
        new_draft.sections[0]["content"] = "mutated only on the new draft"
        new_draft.save()
        approved.refresh_from_db()
        assert approved.sections == original_sections
        assert approved.title == original_title
        assert approved.updated_at == original_updated_at

        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_NEW_DRAFT_CREATED
        )
        assert event.metadata == {
            "version_number": new_draft.version_number,
            "source_version_number": approved.version_number,
        }
        # Deliberately NOT the AI-generation event (see activity/models.py's
        # EVENT_POLICY_NEW_DRAFT_CREATED docstring for why).
        assert not ActivityEvent.objects.filter(
            organisation=org_a,
            event_type=ActivityEvent.EVENT_POLICY_DRAFT_GENERATED,
            related_object_id=str(new_draft.id),
        ).exists()

    def test_refuses_to_fork_a_draft_or_superseded_version(self, org_a, user_a, make_draft_version):
        draft = make_draft_version(org_a, version_number=1)
        with pytest.raises(PolicyLifecycleError):
            create_new_draft_from_approved(draft, actor=user_a)

        superseded = make_draft_version(
            org_a, version_number=2, status=PolicyVersion.STATUS_SUPERSEDED
        )
        with pytest.raises(PolicyLifecycleError):
            create_new_draft_from_approved(superseded, actor=user_a)


# --- HTTP views -------------------------------------------------------------------


@pytest.mark.django_db
class TestApprovalViews:
    def test_direct_approve_get_then_post_confirms(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)

        get_response = client_a.get(
            reverse("policy:version_approve_direct", args=[org_a.id, version.id])
        )
        assert get_response.status_code == 200
        # M004 post-audit repair, Finding 1: the pre-filled next_review_date
        # confirmation input must render ISO yyyy-MM-dd, never en-gb
        # locale-formatted DD/MM/YYYY (which a real HTML5 date input
        # silently refuses, rendering blank to the user).
        get_content = get_response.content.decode()
        assert 'name="next_review_date"' in get_content
        assert re.search(r'name="next_review_date"[^>]*value="\d{4}-\d{2}-\d{2}"', get_content)

        post_response = client_a.post(
            reverse("policy:version_approve_direct", args=[org_a.id, version.id]),
            data={"next_review_date": "2027-01-01"},
        )
        assert post_response.status_code == 302
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_APPROVED
        assert version.approval_mode == PolicyVersion.APPROVAL_MODE_DIRECT

    def test_direct_approve_view_refuses_a_non_authoriser(
        self, client_a, org_a, user_a, external_person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, external_person_a)
        version = make_draft_version(org_a)

        response = client_a.post(
            reverse("policy:version_approve_direct", args=[org_a.id, version.id]),
            data={"next_review_date": "2027-01-01"},
            follow=True,
        )
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT
        shown_messages = [str(m) for m in response.context["messages"]]
        assert any("not the assigned Policy Authoriser" in m for m in shown_messages)

    def test_external_approve_get_then_post_confirms(
        self, client_a, org_a, user_a, external_person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, external_person_a)
        version = make_draft_version(org_a)

        get_response = client_a.get(
            reverse("policy:version_approve_external", args=[org_a.id, version.id])
        )
        assert get_response.status_code == 200
        # The confirmation copy must name the account holder as the one
        # recording it, and never imply the authoriser logged in.
        assert b"outside Infosecurs" in get_response.content
        assert b"does not mean" in get_response.content

        post_response = client_a.post(
            reverse("policy:version_approve_external", args=[org_a.id, version.id]),
            data={"next_review_date": "2027-01-01"},
        )
        assert post_response.status_code == 302
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_APPROVED
        assert version.approval_mode == PolicyVersion.APPROVAL_MODE_EXTERNAL_RECORDED
        assert version.approved_by_id == user_a.id
        assert version.policy_authoriser_id == external_person_a.id

    def test_external_approve_view_refuses_when_actor_is_the_authoriser(
        self, client_a, org_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)

        response = client_a.post(
            reverse("policy:version_approve_external", args=[org_a.id, version.id]),
            data={"next_review_date": "2027-01-01"},
            follow=True,
        )
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT
        shown_messages = [str(m) for m in response.context["messages"]]
        assert any("use direct approval instead" in m for m in shown_messages)

    def test_approve_view_refuses_non_draft_version(
        self, client_a, org_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a, status=PolicyVersion.STATUS_SUPERSEDED)

        response = client_a.post(
            reverse("policy:version_approve_direct", args=[org_a.id, version.id]),
            data={"next_review_date": "2027-01-01"},
            follow=True,
        )
        shown_messages = [str(m) for m in response.context["messages"]]
        assert any("Only a draft policy version can be approved" in m for m in shown_messages)

    def test_new_draft_view_redirects_to_edit_the_new_version(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        response = client_a.post(
            reverse("policy:version_new_draft", args=[org_a.id, version.id])
        )
        assert response.status_code == 302

        new_draft = PolicyVersion.objects.get(
            organisation=org_a, status=PolicyVersion.STATUS_DRAFT
        )
        assert response.url == reverse(
            "policy:version_edit", args=[org_a.id, new_draft.id]
        )

    def test_new_draft_view_rejects_get(self, client_a, org_a, make_draft_version):
        version = make_draft_version(org_a, status=PolicyVersion.STATUS_APPROVED)
        response = client_a.get(
            reverse("policy:version_new_draft", args=[org_a.id, version.id])
        )
        assert response.status_code == 405

    def test_new_draft_view_refuses_a_draft_source(self, client_a, org_a, make_draft_version):
        version = make_draft_version(org_a)
        response = client_a.post(
            reverse("policy:version_new_draft", args=[org_a.id, version.id]), follow=True
        )
        shown_messages = [str(m) for m in response.context["messages"]]
        assert any("currently approved policy version" in m for m in shown_messages)
