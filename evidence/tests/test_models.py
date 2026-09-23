import pytest

from evidence.models import EvidenceImmutableFieldError, EvidenceItem


@pytest.mark.django_db
class TestEvidenceItemModel:
    def test_create_file_evidence_item(self, org_a, user_a):
        item = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_FILE,
            title="MFA policy screenshot",
            original_filename="mfa.png",
            stored_filename="abc123.png",
            file_type="png",
            byte_size=1024,
            sha256="a" * 64,
            recorded_by=user_a,
        )
        assert item.status == EvidenceItem.STATUS_ACTIVE
        assert item.kind == "file"
        assert item.organisation_id == org_a.id

    def test_create_external_reference_evidence_item(self, org_a, user_a):
        item = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Cyber Essentials certificate",
            reference_url="https://example.test/certificate",
            recorded_by=user_a,
        )
        assert item.status == EvidenceItem.STATUS_ACTIVE
        assert item.reference_url == "https://example.test/certificate"

    def test_immutable_file_fields_cannot_be_mutated_via_orm(self, org_a, user_a):
        """
        PID §6.2/§10: bytes and SHA-256 (and the other content-identifying
        fields) are immutable after creation. Proven directly against the
        model/ORM layer, not merely by the absence of an edit view.
        """
        item = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_FILE,
            title="Device encryption export",
            original_filename="export.pdf",
            stored_filename="deadbeef.pdf",
            file_type="pdf",
            byte_size=2048,
            sha256="b" * 64,
            recorded_by=user_a,
        )

        item.sha256 = "c" * 64
        with pytest.raises(EvidenceImmutableFieldError):
            item.save()

        item.refresh_from_db()
        assert item.sha256 == "b" * 64

    def test_each_immutable_field_individually_rejected(self, org_a, user_a):
        base_kwargs = dict(
            organisation=org_a,
            kind=EvidenceItem.KIND_FILE,
            title="Endpoint protection export",
            original_filename="export.txt",
            stored_filename="feedface.txt",
            file_type="text",
            byte_size=10,
            sha256="d" * 64,
            recorded_by=user_a,
        )
        mutations = {
            "original_filename": "renamed.txt",
            "stored_filename": "different.txt",
            "file_type": "pdf",
            "byte_size": 999,
            "sha256": "e" * 64,
        }
        for field_name, new_value in mutations.items():
            item = EvidenceItem.objects.create(**base_kwargs)
            setattr(item, field_name, new_value)
            with pytest.raises(EvidenceImmutableFieldError):
                item.save()

    def test_mutable_fields_can_still_be_updated(self, org_a, user_a):
        """The immutability guard must not block ordinary lifecycle writes."""
        item = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Original title",
            reference_url="https://example.test/a",
            recorded_by=user_a,
        )
        item.title = "Updated title"
        item.status = EvidenceItem.STATUS_WITHDRAWN
        item.save()
        item.refresh_from_db()
        assert item.title == "Updated title"
        assert item.status == EvidenceItem.STATUS_WITHDRAWN

    def test_superseded_by_self_relationship(self, org_a, user_a):
        old = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Old reference",
            reference_url="https://example.test/old",
            recorded_by=user_a,
        )
        new = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="New reference",
            reference_url="https://example.test/new",
            recorded_by=user_a,
        )
        old.status = EvidenceItem.STATUS_SUPERSEDED
        old.superseded_by = new
        old.save()

        old.refresh_from_db()
        assert old.superseded_by_id == new.id
        assert list(new.superseded_items.all()) == [old]

    def test_withdrawn_and_superseded_items_are_never_deleted(self, org_a, user_a):
        item = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Reference to withdraw",
            reference_url="https://example.test/withdraw-me",
            recorded_by=user_a,
        )
        item.status = EvidenceItem.STATUS_WITHDRAWN
        item.save()
        assert EvidenceItem.objects.filter(pk=item.pk).exists()
