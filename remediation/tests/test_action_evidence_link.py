"""
Tests for ActionEvidenceLink / remediation.services.attach_evidence_to_action
(PID §6.6, §13, §16, §17, §19 "Actions: ... evidence can attach").

Covers:
  - a successful attach creates one ActionEvidenceLink and one
    action_evidence_linked ActivityEvent with correct metadata;
  - cross-tenant attach is impossible in both directions, at both the HTTP
    view layer (tenant-scoped 404s) and the service layer directly (the
    same-organisation guard the service enforces for itself, PID §16 -
    not just relying on form validation);
  - an action can have multiple evidence links;
  - attaching evidence never changes RemediationAction.status,
    risk_register.Risk.status, or any security_baseline.BaselineAnswer -
    asserted directly against independently reloaded objects, not the
    action's own fields (same discipline as
    test_no_cascade_on_completion.py);
  - a rejected cross-tenant attach (rolled back before any DB write)
    leaves no ActivityEvent row.

This file does not test unlink/detach - no such capability exists for
ActionEvidenceLink in M003 V1 (PID §19's Actions mechanical-test list
requires only "evidence can attach"; unlink is a different, evidence-app
Engineer's parallel work item for ControlEvidenceLink, not this one).
"""
import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from evidence.models import EvidenceItem
from remediation.models import ActionEvidenceLink, RemediationAction
from remediation.services import RemediationServiceError, attach_evidence_to_action
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _action(org, user, **overrides):
    defaults = dict(organisation=org, title="Org action", created_by=user)
    defaults.update(overrides)
    return RemediationAction.objects.create(**defaults)


def _evidence(org, **overrides):
    defaults = dict(
        organisation=org,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title="Org evidence",
        reference_url="https://example.test/evidence",
    )
    defaults.update(overrides)
    return EvidenceItem.objects.create(**defaults)


def _baseline_answer(org, *, question_key="mfa_user_accounts", answer="no"):
    assessment = BaselineAssessment.objects.create(
        organisation=org, catalogue_version=CATALOGUE_VERSION
    )
    return BaselineAnswer.objects.create(
        assessment=assessment, question_key=question_key, answer=answer, note="original note"
    )


@pytest.mark.django_db
class TestAttachEvidenceToActionService:
    def test_attach_creates_link_and_event_with_correct_metadata(self, org_a, user_a):
        action = _action(org_a, user_a, control_key="mfa_user_accounts")
        evidence = _evidence(org_a, title="MFA screenshot")

        link = attach_evidence_to_action(
            organisation=org_a, action=action, evidence=evidence, linked_by=user_a
        )

        assert ActionEvidenceLink.objects.count() == 1
        reloaded_link = ActionEvidenceLink.objects.get(pk=link.pk)
        assert reloaded_link.organisation_id == org_a.id
        assert reloaded_link.action_id == action.id
        assert reloaded_link.evidence_id == evidence.id
        assert reloaded_link.linked_by_id == user_a.id

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_ACTION_EVIDENCE_LINKED
        )
        assert events.count() == 1
        event = events.get()
        assert event.actor_id == user_a.id
        assert event.control_key == "mfa_user_accounts"
        assert event.related_object_type == "remediation_action"
        assert event.related_object_id == str(action.id)
        assert event.metadata == {"evidence_id": str(evidence.id)}

    def test_action_can_have_multiple_evidence_links(self, org_a, user_a):
        action = _action(org_a, user_a)
        evidence_1 = _evidence(org_a, title="Evidence one")
        evidence_2 = _evidence(org_a, title="Evidence two")

        attach_evidence_to_action(organisation=org_a, action=action, evidence=evidence_1, linked_by=user_a)
        attach_evidence_to_action(organisation=org_a, action=action, evidence=evidence_2, linked_by=user_a)

        assert action.evidence_links.count() == 2
        linked_evidence_ids = set(action.evidence_links.values_list("evidence_id", flat=True))
        assert linked_evidence_ids == {evidence_1.id, evidence_2.id}

    # --- same-organisation guard, both directions -------------------------

    def test_service_rejects_action_from_a_different_organisation(self, org_a, org_b, user_a, user_b):
        action_b = _action(org_b, user_b)
        evidence_a = _evidence(org_a)

        with pytest.raises(RemediationServiceError):
            attach_evidence_to_action(
                organisation=org_a, action=action_b, evidence=evidence_a, linked_by=user_a
            )

        assert ActionEvidenceLink.objects.count() == 0

    def test_service_rejects_evidence_from_a_different_organisation(self, org_a, org_b, user_a):
        action_a = _action(org_a, user_a)
        evidence_b = _evidence(org_b)

        with pytest.raises(RemediationServiceError):
            attach_evidence_to_action(
                organisation=org_a, action=action_a, evidence=evidence_b, linked_by=user_a
            )

        assert ActionEvidenceLink.objects.count() == 0

    def test_rejected_cross_tenant_attach_leaves_no_activity_event(self, org_a, org_b, user_a, user_b):
        action_b = _action(org_b, user_b)
        evidence_a = _evidence(org_a)

        with pytest.raises(RemediationServiceError):
            attach_evidence_to_action(
                organisation=org_a, action=action_b, evidence=evidence_a, linked_by=user_a
            )

        assert ActivityEvent.objects.filter(
            event_type=ActivityEvent.EVENT_ACTION_EVIDENCE_LINKED
        ).count() == 0

    # --- non-cascade invariant (PID §6.6, §13) -----------------------------

    def test_attach_does_not_change_action_status_risk_status_or_baseline_answer(
        self, org_a, user_a, risk_a
    ):
        baseline_answer = _baseline_answer(org_a)
        original_risk_status = risk_a.status
        original_answer_value = baseline_answer.answer
        original_answer_updated_at = baseline_answer.updated_at

        action = _action(
            org_a, user_a, risk=risk_a, control_key=baseline_answer.question_key
        )
        evidence = _evidence(org_a, title="Completion evidence")

        attach_evidence_to_action(
            organisation=org_a, action=action, evidence=evidence, linked_by=user_a
        )

        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_OPEN

        risk_a.refresh_from_db()
        assert risk_a.status == original_risk_status

        reloaded_answer = BaselineAnswer.objects.get(pk=baseline_answer.pk)
        assert reloaded_answer.answer == original_answer_value
        assert reloaded_answer.updated_at == original_answer_updated_at
        assert reloaded_answer.note == "original note"
        assert BaselineAnswer.objects.filter(assessment__organisation=org_a).count() == 1


@pytest.mark.django_db
class TestActionAttachEvidenceView:
    def test_member_can_attach_own_organisations_evidence_to_own_action(self, client_a, org_a, user_a):
        action = _action(org_a, user_a)
        evidence = _evidence(org_a, title="Uploaded evidence")

        response = client_a.post(
            reverse("remediation:attach_evidence", args=[org_a.id, action.id]),
            {"evidence": str(evidence.id)},
        )

        assert response.status_code == 302
        assert ActionEvidenceLink.objects.filter(action=action, evidence=evidence).exists()

    def test_evidence_link_appears_on_action_detail_page(self, client_a, org_a, user_a):
        action = _action(org_a, user_a)
        evidence = _evidence(org_a, title="Visible evidence title")
        attach_evidence_to_action(organisation=org_a, action=action, evidence=evidence, linked_by=user_a)

        response = client_a.get(reverse("remediation:detail", args=[org_a.id, action.id]))
        assert response.status_code == 200
        assert b"Visible evidence title" in response.content

    def test_member_cannot_attach_evidence_to_other_organisations_action(
        self, client_a, org_a, org_b, user_a, user_b
    ):
        """
        user_a (member of org_a only) cannot reach org_b's action at all -
        the tenant-scoped _get_member_action_or_404 pattern makes this an
        ordinary 404, mirroring every other remediation view.
        """
        action_b = _action(org_b, user_b)
        evidence_a = _evidence(org_a)

        response = client_a.post(
            reverse("remediation:attach_evidence", args=[org_b.id, action_b.id]),
            {"evidence": str(evidence_a.id)},
        )

        assert response.status_code == 404
        assert ActionEvidenceLink.objects.count() == 0

    def test_member_cannot_attach_other_organisations_evidence_via_form(
        self, client_a, org_a, org_b, user_a
    ):
        """
        Even against A's own action (reachable and valid), org B's
        evidence must not be an acceptable choice: the attach form's
        queryset is scoped to the organisation, so a foreign evidence id
        fails form validation rather than silently linking cross-tenant
        evidence.
        """
        action_a = _action(org_a, user_a)
        evidence_b = _evidence(org_b, title="Org B secret evidence")

        response = client_a.post(
            reverse("remediation:attach_evidence", args=[org_a.id, action_a.id]),
            {"evidence": str(evidence_b.id)},
        )

        assert response.status_code == 302
        assert ActionEvidenceLink.objects.count() == 0
