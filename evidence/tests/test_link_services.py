"""
Unit tests for `evidence.link_services` - the one code path that creates
and deletes `ControlEvidenceLink` rows (PID §6.4, §19 "Links").
"""
import pytest

from activity.models import ActivityEvent
from evidence import link_services
from evidence.exceptions import EvidenceValidationError
from evidence.models import ControlEvidenceLink, EvidenceItem


def _reference_evidence(org, actor, title="Evidence"):
    return EvidenceItem.objects.create(
        organisation=org,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title=title,
        reference_url="https://example.test/evidence",
        recorded_by=actor,
    )


@pytest.mark.django_db
class TestLinkEvidenceToControl:
    def test_supports_relationship_creates_a_link(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link = link_services.link_evidence_to_control(
            org_a, evidence, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        assert link.pk is not None
        assert link.relationship == ControlEvidenceLink.RELATIONSHIP_SUPPORTS
        assert link.control_key == "mfa_user_accounts"
        assert link.organisation_id == org_a.id
        assert link.evidence_id == evidence.id
        assert link.linked_by_id == user_a.id

    def test_contradicts_relationship_creates_a_link(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link = link_services.link_evidence_to_control(
            org_a, evidence, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_CONTRADICTS, "", user_a
        )
        assert link.relationship == ControlEvidenceLink.RELATIONSHIP_CONTRADICTS

    def test_context_relationship_creates_a_link(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link = link_services.link_evidence_to_control(
            org_a, evidence, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_CONTEXT, "", user_a
        )
        assert link.relationship == ControlEvidenceLink.RELATIONSHIP_CONTEXT

    def test_emits_evidence_linked_activity_event(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link_services.link_evidence_to_control(
            org_a, evidence, "backups", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "Backup export attached", user_a
        )
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_LINKED
        )
        assert event.control_key == "backups"
        assert event.actor_id == user_a.id
        assert event.related_object_type == "evidence_item"
        assert event.related_object_id == str(evidence.id)
        assert event.metadata == {"relationship": "supports", "rationale_provided": True}

    def test_rationale_provided_is_false_when_rationale_blank(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link_services.link_evidence_to_control(
            org_a, evidence, "backups", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_LINKED
        )
        assert event.metadata["rationale_provided"] is False

    def test_cross_tenant_linking_is_impossible(self, org_a, org_b, user_a):
        """
        PID §6.4/§19: the link operation must verify all referenced objects
        belong to the same organisation. org_b's evidence cannot be linked
        under org_a's organisation argument, even if a caller bypasses the
        view/form layer entirely and calls the service directly.
        """
        evidence_b = _reference_evidence(org_b, user_a, title="Org B evidence")
        with pytest.raises(EvidenceValidationError):
            link_services.link_evidence_to_control(
                org_a, evidence_b, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
            )
        assert not ControlEvidenceLink.objects.filter(evidence=evidence_b, organisation=org_a).exists()

    def test_duplicate_link_same_triple_is_rejected_deterministically(self, org_a, user_a):
        """
        PID §19 'duplicate-link behaviour deterministic'. Chosen behaviour
        (documented on ControlEvidenceLink): an exact duplicate
        (evidence, control_key, relationship) triple is rejected with a
        friendly EvidenceValidationError, both on first attempt and on a
        repeated resubmission - never silently ignored, never a 500.
        """
        evidence = _reference_evidence(org_a, user_a)
        link_services.link_evidence_to_control(
            org_a, evidence, "patching", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        with pytest.raises(EvidenceValidationError):
            link_services.link_evidence_to_control(
                org_a, evidence, "patching", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
            )
        assert ControlEvidenceLink.objects.filter(
            evidence=evidence, control_key="patching", relationship=ControlEvidenceLink.RELATIONSHIP_SUPPORTS
        ).count() == 1

    def test_same_evidence_and_control_with_a_different_relationship_is_allowed(self, org_a, user_a):
        """
        Only the exact (evidence, control_key, relationship) triple is a
        duplicate - the same evidence linked to the same control under a
        *different* relationship is a distinct, independent link.
        """
        evidence = _reference_evidence(org_a, user_a)
        link_services.link_evidence_to_control(
            org_a, evidence, "patching", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        second = link_services.link_evidence_to_control(
            org_a, evidence, "patching", ControlEvidenceLink.RELATIONSHIP_CONTEXT, "", user_a
        )
        assert second.pk is not None
        assert ControlEvidenceLink.objects.filter(evidence=evidence, control_key="patching").count() == 2

    def test_one_evidence_item_can_support_multiple_controls(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link_services.link_evidence_to_control(
            org_a, evidence, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        link_services.link_evidence_to_control(
            org_a, evidence, "mfa_privileged_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        assert ControlEvidenceLink.objects.filter(evidence=evidence).count() == 2
        assert set(
            ControlEvidenceLink.objects.filter(evidence=evidence).values_list("control_key", flat=True)
        ) == {"mfa_user_accounts", "mfa_privileged_accounts"}


@pytest.mark.django_db
class TestUnlinkEvidenceFromControl:
    def test_deletes_the_link_row(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link = link_services.link_evidence_to_control(
            org_a, evidence, "backups", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        link_services.unlink_evidence_from_control(link, user_a)
        assert not ControlEvidenceLink.objects.filter(pk=link.pk).exists()

    def test_does_not_delete_the_underlying_evidence_item(self, org_a, user_a):
        """PID §19 'unlink does not delete evidence'."""
        evidence = _reference_evidence(org_a, user_a)
        link = link_services.link_evidence_to_control(
            org_a, evidence, "backups", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        link_services.unlink_evidence_from_control(link, user_a)
        assert EvidenceItem.objects.filter(pk=evidence.pk).exists()
        evidence.refresh_from_db()
        assert evidence.status == EvidenceItem.STATUS_ACTIVE

    def test_emits_evidence_unlinked_activity_event(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a)
        link = link_services.link_evidence_to_control(
            org_a, evidence, "backups", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "A rationale", user_a
        )
        link_services.unlink_evidence_from_control(link, user_a)
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_UNLINKED
        )
        assert event.control_key == "backups"
        assert event.related_object_type == "evidence_item"
        assert event.related_object_id == str(evidence.id)
        assert event.metadata == {"relationship": "supports", "rationale_provided": True}

    def test_unlinking_then_relinking_the_same_triple_succeeds(self, org_a, user_a):
        """Deleting a link frees up its (evidence, control_key,
        relationship) triple for a fresh link - unlink is a real delete,
        not a soft/tombstone state that would keep tripping the
        duplicate-link guard."""
        evidence = _reference_evidence(org_a, user_a)
        link = link_services.link_evidence_to_control(
            org_a, evidence, "backups", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        link_services.unlink_evidence_from_control(link, user_a)
        new_link = link_services.link_evidence_to_control(
            org_a, evidence, "backups", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        assert new_link.pk is not None
        assert new_link.pk != link.pk
