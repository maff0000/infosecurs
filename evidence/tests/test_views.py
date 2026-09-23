import os
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evidence.models import ControlEvidenceLink, EvidenceItem
from evidence import link_services, services

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
GARBAGE = b"\x00\x01\x02\x03not a recognised evidence type"


def _upload(content=MINIMAL_PDF, name="evidence.pdf", content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.mark.django_db
class TestEvidenceUploadView:
    def test_get_renders_form(self, client_a, org_a):
        response = client_a.get(reverse("evidence:upload", args=[org_a.id]))
        assert response.status_code == 200

    def test_post_creates_file_evidence_and_redirects(self, client_a, org_a):
        response = client_a.post(
            reverse("evidence:upload", args=[org_a.id]),
            {
                "title": "MFA policy screenshot",
                "description": "Shows Conditional Access requiring MFA.",
                "source_label": "Entra admin centre",
                "observed_at": "",
                "valid_until": "",
                "file": _upload(),
            },
        )
        item = EvidenceItem.objects.get(organisation=org_a)
        assert response.status_code == 302
        assert response.url == reverse("evidence:detail", args=[org_a.id, item.id])
        assert item.title == "MFA policy screenshot"
        assert item.file_type == "pdf"

    def test_post_rejects_content_that_is_not_an_accepted_type(self, client_a, org_a):
        response = client_a.post(
            reverse("evidence:upload", args=[org_a.id]),
            {
                "title": "Bad upload",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "file": _upload(GARBAGE, "bad.pdf", "application/pdf"),
            },
        )
        assert response.status_code == 200
        assert not EvidenceItem.objects.filter(organisation=org_a).exists()
        assert b"not a PDF, PNG, JPEG or plain-text file" in response.content

    def test_post_rejects_empty_title(self, client_a, org_a):
        response = client_a.post(
            reverse("evidence:upload", args=[org_a.id]),
            {
                "title": "   ",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "file": _upload(),
            },
        )
        assert response.status_code == 200
        assert not EvidenceItem.objects.filter(organisation=org_a).exists()

    def test_supersede_via_upload_marks_old_item_superseded(self, client_a, org_a, user_a):
        old = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="Old export",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(),
        )
        response = client_a.post(
            reverse("evidence:upload", args=[org_a.id]) + f"?supersedes={old.id}",
            {
                "title": "New export",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "file": _upload(MINIMAL_PDF, "new.pdf"),
                "supersedes": str(old.id),
            },
        )
        assert response.status_code == 302
        old.refresh_from_db()
        assert old.status == EvidenceItem.STATUS_SUPERSEDED
        new = EvidenceItem.objects.get(title="New export")
        assert old.superseded_by_id == new.id

    def test_supersede_target_must_be_active(self, client_a, org_a, user_a):
        old = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="Already withdrawn",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(),
        )
        services.withdraw_evidence(old)
        response = client_a.get(reverse("evidence:upload", args=[org_a.id]) + f"?supersedes={old.id}")
        assert response.status_code == 404


@pytest.mark.django_db
class TestEvidenceAddReferenceView:
    def test_post_creates_external_reference(self, client_a, org_a):
        response = client_a.post(
            reverse("evidence:add_reference", args=[org_a.id]),
            {
                "title": "Cyber Essentials certificate",
                "description": "",
                "source_label": "IASME portal",
                "observed_at": "",
                "valid_until": "",
                "reference_url": "https://example.test/certificate",
            },
        )
        item = EvidenceItem.objects.get(organisation=org_a)
        assert response.status_code == 302
        assert item.kind == EvidenceItem.KIND_EXTERNAL_REFERENCE
        assert item.reference_url == "https://example.test/certificate"

    def test_post_rejects_an_invalid_url(self, client_a, org_a):
        response = client_a.post(
            reverse("evidence:add_reference", args=[org_a.id]),
            {
                "title": "Bad reference",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "reference_url": "not a url",
            },
        )
        assert response.status_code == 200
        assert not EvidenceItem.objects.filter(organisation=org_a).exists()

    def test_infosecurs_does_not_fetch_the_reference(self, client_a, org_a, monkeypatch):
        """
        PID §6.3: M003 does not fetch or crawl the URL. Guard against a
        regression that adds a fetch: fail the test if any outbound
        network call is attempted while adding a reference.
        """
        import urllib.request

        def _forbidden(*args, **kwargs):
            raise AssertionError("Infosecurs must never fetch/crawl an evidence reference URL")

        monkeypatch.setattr(urllib.request, "urlopen", _forbidden)

        response = client_a.post(
            reverse("evidence:add_reference", args=[org_a.id]),
            {
                "title": "Reference not fetched",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "reference_url": "https://example.test/never-fetched",
            },
        )
        assert response.status_code == 302


@pytest.mark.django_db
class TestEvidenceDetailAndListViews:
    def test_detail_shows_provenance(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a,
            actor=user_a,
            title="Cert reference",
            description="",
            source_label="IASME portal",
            observed_at=None,
            valid_until=None,
            reference_url="https://example.test/certificate",
        )
        response = client_a.get(reverse("evidence:detail", args=[org_a.id, item.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Cert reference" in content
        assert "IASME portal" in content
        assert "user_a" in content
        assert "Not yet linked to any control" in content

    def test_list_groups_items_by_status(self, client_a, org_a, user_a):
        active = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Active item", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/active",
        )
        withdrawn = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Withdrawn item", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/withdrawn",
        )
        services.withdraw_evidence(withdrawn)

        response = client_a.get(reverse("evidence:list", args=[org_a.id]))
        assert response.status_code == 200
        assert active in response.context["active_items"]
        assert withdrawn in response.context["withdrawn_items"]
        assert withdrawn not in response.context["active_items"]


@pytest.mark.django_db
class TestEvidenceDownloadView:
    def test_download_returns_correct_bytes_and_safe_headers(self, client_a, org_a, user_a):
        item = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="MFA export",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF, "MFA report.pdf", "application/pdf"),
        )
        response = client_a.get(reverse("evidence:download", args=[org_a.id, item.id]))
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == MINIMAL_PDF
        assert response["Content-Type"] == "application/pdf"
        assert response["X-Content-Type-Options"] == "nosniff"
        disposition = response["Content-Disposition"]
        assert disposition.startswith("attachment;")
        assert 'filename="MFA report.pdf"' in disposition
        assert "filename*=UTF-8''MFA%20report.pdf" in disposition

    def test_download_encodes_non_ascii_original_filename_safely(self, client_a, org_a, user_a):
        item = services.create_file_evidence(
            organisation=org_a,
            actor=user_a,
            title="Report",
            description="",
            source_label="",
            observed_at=None,
            valid_until=None,
            uploaded_file=_upload(MINIMAL_PDF, "évidence — café.pdf", "application/pdf"),
        )
        response = client_a.get(reverse("evidence:download", args=[org_a.id, item.id]))
        disposition = response["Content-Disposition"]
        assert "filename*=UTF-8''" in disposition
        # The ASCII fallback filename must not contain raw non-ASCII bytes.
        fallback = disposition.split('filename="', 1)[1].split('"', 1)[0]
        fallback.encode("ascii")  # raises if not pure ASCII

    def test_download_404s_for_an_external_reference_item(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Reference", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/x",
        )
        response = client_a.get(reverse("evidence:download", args=[org_a.id, item.id]))
        assert response.status_code == 404

    def test_download_404s_for_a_nonexistent_evidence_id(self, client_a, org_a):
        response = client_a.get(reverse("evidence:download", args=[org_a.id, uuid.uuid4()]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestEvidenceWithdrawView:
    def test_post_withdraws_active_item(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="To withdraw", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/x",
        )
        response = client_a.post(reverse("evidence:withdraw", args=[org_a.id, item.id]))
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.status == EvidenceItem.STATUS_WITHDRAWN

    def test_get_is_not_allowed(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="To withdraw", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/x",
        )
        response = client_a.get(reverse("evidence:withdraw", args=[org_a.id, item.id]))
        assert response.status_code == 405


@pytest.mark.django_db
class TestEvidenceLinkControlView:
    def test_get_renders_form(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        response = client_a.get(reverse("evidence:link_control", args=[org_a.id, item.id]))
        assert response.status_code == 200

    def test_post_creates_link_and_redirects_to_detail(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        response = client_a.post(
            reverse("evidence:link_control", args=[org_a.id, item.id]),
            {"control_key": "mfa_user_accounts", "relationship": "supports", "rationale": "Screenshot"},
        )
        assert response.status_code == 302
        assert response.url == reverse("evidence:detail", args=[org_a.id, item.id])
        link = ControlEvidenceLink.objects.get(evidence=item)
        assert link.control_key == "mfa_user_accounts"
        assert link.relationship == "supports"
        assert link.rationale == "Screenshot"
        assert link.linked_by_id == user_a.id

    def test_post_duplicate_link_shows_friendly_error(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        link_services.link_evidence_to_control(
            org_a, item, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        response = client_a.post(
            reverse("evidence:link_control", args=[org_a.id, item.id]),
            {"control_key": "mfa_user_accounts", "relationship": "supports", "rationale": ""},
        )
        assert response.status_code == 200
        assert ControlEvidenceLink.objects.filter(evidence=item).count() == 1

    def test_detail_page_shows_linked_controls(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        link_services.link_evidence_to_control(
            org_a, item, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "My rationale", user_a
        )
        response = client_a.get(reverse("evidence:detail", args=[org_a.id, item.id]))
        content = response.content.decode()
        assert "Multi-factor authentication (staff)" in content
        assert "My rationale" in content
        assert "Supports" in content


@pytest.mark.django_db
class TestEvidenceUnlinkControlView:
    def test_post_deletes_the_link(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        link = link_services.link_evidence_to_control(
            org_a, item, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        response = client_a.post(reverse("evidence:unlink_control", args=[org_a.id, item.id, link.id]))
        assert response.status_code == 302
        assert not ControlEvidenceLink.objects.filter(pk=link.pk).exists()
        # Unlink does not delete the underlying evidence item (PID §19).
        assert EvidenceItem.objects.filter(pk=item.pk).exists()

    def test_get_is_not_allowed(self, client_a, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        link = link_services.link_evidence_to_control(
            org_a, item, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        response = client_a.get(reverse("evidence:unlink_control", args=[org_a.id, item.id, link.id]))
        assert response.status_code == 405
