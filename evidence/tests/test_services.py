import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from activity.models import ActivityEvent
from evidence import services
from evidence.exceptions import EvidenceValidationError
from evidence.models import EvidenceItem

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
GARBAGE = b"\x00\x01\x02\x03not a recognised evidence type"


def _upload(content, name="evidence.pdf", content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.mark.django_db
class TestCreateFileEvidence:
    def test_persists_item_and_writes_bytes_to_storage(self, org_a, user_a, evidence_storage_root):
        item = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="MFA policy export",
            description="",
            source_label="Microsoft 365 admin centre",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF),
        )
        assert item.kind == EvidenceItem.KIND_FILE
        assert item.file_type == "pdf"
        assert item.byte_size == len(MINIMAL_PDF)
        assert item.status == EvidenceItem.STATUS_ACTIVE
        assert item.recorded_by_id == user_a.id

        stored_path = os.path.join(str(evidence_storage_root), str(org_a.id), item.stored_filename)
        assert os.path.isfile(stored_path)

    def test_emits_evidence_created_event(self, org_a, user_a, evidence_storage_root):
        item = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="MFA policy export",
            description="",
            source_label="Microsoft 365 admin centre",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF),
        )
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_CREATED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "evidence_item"
        assert event.related_object_id == str(item.id)
        assert event.metadata == {"kind": "file", "title": "MFA policy export"}

    def test_rejects_invalid_content_and_persists_nothing(self, org_a, user_a, evidence_storage_root):
        before = EvidenceItem.objects.count()
        with pytest.raises(EvidenceValidationError):
            services.create_file_evidence(
                organisation=org_a,
                actor=user_a,
                title="Bad upload",
                description="",
                source_label="",
                observed_at=None,
                valid_until=None,
                uploaded_file=_upload(GARBAGE, "bad.pdf", "application/pdf"),
            )
        assert EvidenceItem.objects.count() == before
        org_dir = os.path.join(str(evidence_storage_root), str(org_a.id))
        assert not os.path.isdir(org_dir) or os.listdir(org_dir) == []
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_CREATED
        ).exists()

    def test_supersede_marks_old_item_superseded_and_links_replacement(self, org_a, user_a):
        old = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="Old MFA export",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF),
        )
        new = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="New MFA export",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF, "new.pdf"),
            supersedes=old,
        )
        old.refresh_from_db()
        assert old.status == EvidenceItem.STATUS_SUPERSEDED
        assert old.superseded_by_id == new.id
        assert new.status == EvidenceItem.STATUS_ACTIVE

    def test_supersede_emits_evidence_superseded_event_on_the_old_item(self, org_a, user_a):
        old = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="Old MFA export",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF),
        )
        new = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="New MFA export",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF, "new.pdf"),
            supersedes=old,
        )
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_SUPERSEDED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "evidence_item"
        assert event.related_object_id == str(old.id)
        assert event.metadata == {"superseded_by": str(new.id)}

    def test_supersede_refuses_an_already_inactive_target(self, org_a, user_a):
        old = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="Already withdrawn",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF),
        )
        services.withdraw_evidence(old, user_a)
        events_before = ActivityEvent.objects.filter(organisation=org_a).count()
        items_before = EvidenceItem.objects.filter(organisation=org_a).count()
        with pytest.raises(EvidenceValidationError):
            services.create_file_evidence(
                organisation=org_a,
                actor=user_a,
                title="Replacement",
                description="",
                source_label="",
                observed_at=None,
                valid_until=None,
                uploaded_file=_upload(MINIMAL_PDF, "new.pdf"),
                supersedes=old,
            )
        # PID §17 rollback safety, exercised with a real trigger: the new
        # EvidenceItem is created *inside* the same @transaction.atomic
        # block as the (failing) supersession attempt, so the whole
        # create_file_evidence call - including any activity event - must
        # roll back together, not leave an orphaned item or event behind.
        assert EvidenceItem.objects.filter(organisation=org_a).count() == items_before
        assert ActivityEvent.objects.filter(organisation=org_a).count() == events_before
        assert not ActivityEvent.objects.filter(
            organisation=org_a, metadata__title="Replacement"
        ).exists()

    def test_apply_supersession_refuses_cross_organisation_items(self, org_a, org_b, user_a, user_b):
        """
        Defence in depth: _apply_supersession itself must refuse a
        cross-tenant pairing even if a caller somehow bypassed the view's
        own same-organisation lookup.
        """
        item_a = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Org A evidence",
            reference_url="https://example.test/a",
            recorded_by=user_a,
        )
        item_b = EvidenceItem.objects.create(
            organisation=org_b,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Org B evidence",
            reference_url="https://example.test/b",
            recorded_by=user_b,
        )
        with pytest.raises(EvidenceValidationError):
            services._apply_supersession(item_a, item_b, user_a)


@pytest.mark.django_db
class TestCreateExternalReferenceEvidence:
    def test_persists_item(self, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="Cyber Essentials certificate",
            description="",
            source_label="IASME portal",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/certificate",
        )
        assert item.kind == EvidenceItem.KIND_EXTERNAL_REFERENCE
        assert item.reference_url == "https://example.test/certificate"
        assert item.status == EvidenceItem.STATUS_ACTIVE

    def test_emits_evidence_created_event(self, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="Cyber Essentials certificate",
            description="",
            source_label="IASME portal",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/certificate",
        )
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_CREATED
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "evidence_item"
        assert event.related_object_id == str(item.id)
        assert event.metadata == {
            "kind": "external_reference",
            "title": "Cyber Essentials certificate",
        }

    def test_supersede_reference_with_reference(self, org_a, user_a):
        old = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="Old cert",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/old",
        )
        new = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="New cert",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/new",
            supersedes=old,
        )
        old.refresh_from_db()
        assert old.status == EvidenceItem.STATUS_SUPERSEDED
        assert old.superseded_by_id == new.id


@pytest.mark.django_db
class TestWithdrawEvidence:
    def test_withdraws_active_item(self, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="To withdraw",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/x",
        )
        services.withdraw_evidence(item, user_a)
        item.refresh_from_db()
        assert item.status == EvidenceItem.STATUS_WITHDRAWN

    def test_emits_evidence_withdrawn_event(self, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="To withdraw",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/x",
        )
        services.withdraw_evidence(item, user_a)
        event = ActivityEvent.objects.get(
            organisation=org_a, event_type=ActivityEvent.EVENT_EVIDENCE_WITHDRAWN
        )
        assert event.actor_id == user_a.id
        assert event.related_object_type == "evidence_item"
        assert event.related_object_id == str(item.id)
        assert event.metadata == {}

    def test_refuses_to_withdraw_a_non_active_item(self, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="Already withdrawn",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/x",
        )
        services.withdraw_evidence(item, user_a)
        with pytest.raises(EvidenceValidationError):
            services.withdraw_evidence(item, user_a)
