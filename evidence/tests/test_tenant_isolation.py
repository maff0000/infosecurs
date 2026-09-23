import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from evidence import services
from evidence.models import EvidenceItem

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _upload(content=MINIMAL_PDF, name="evidence.pdf", content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.mark.django_db
class TestEvidenceTenantIsolation:
    """
    Release-blocking (M003 PID §16, §19 'tenant isolation'). Two synthetic
    organisations, two users each a member of exactly one, proving
    organisation B can never list, view, download, supersede or withdraw
    organisation A's evidence, and that a manipulated evidence id in
    org A's own URL prefix cannot reach org B's evidence either.
    """

    # --- list ---------------------------------------------------------
    def test_member_cannot_list_other_organisations_evidence(self, client_b, org_a, user_a):
        services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Org A secret evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        response = client_b.get(reverse("evidence:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_does_not_see_other_organisations_evidence_mixed_into_their_own_list(
        self, client_a, org_a, org_b, user_a, user_b
    ):
        services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Org A own evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        services.create_external_reference_evidence(
            organisation=org_b, actor=user_b, title="Org B evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/b",
        )
        response = client_a.get(reverse("evidence:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Org A own evidence" in content
        assert "Org B evidence" not in content

    # --- metadata / detail ----------------------------------------------
    def test_member_cannot_view_other_organisations_evidence_detail(self, client_b, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Org A evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        response = client_b.get(reverse("evidence:detail", args=[org_a.id, item.id]))
        assert response.status_code == 404

    def test_evidence_id_from_a_different_organisation_is_404_even_via_a_members_own_org_url(
        self, client_a, org_a, org_b, user_b
    ):
        """
        user_a is a member of org_a. An evidence item belonging to org_b
        must not be reachable through org_a's URL prefix, even though
        user_a is authenticated and a genuine member of *some*
        organisation.
        """
        other_org_item = services.create_external_reference_evidence(
            organisation=org_b, actor=user_b, title="Org B evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/b",
        )
        response = client_a.get(reverse("evidence:detail", args=[org_a.id, other_org_item.id]))
        assert response.status_code == 404

    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("evidence:list", args=[uuid.uuid4()]))
        assert response.status_code == 404

    # --- file download ---------------------------------------------------
    def test_member_cannot_download_other_organisations_evidence_file(self, client_b, org_a, user_a):
        item = services.create_file_evidence(
            organisation=org_a, actor=user_a, title="Org A file", description="",
            source_label="", observed_at=None, valid_until=None,
            uploaded_file=_upload(),
        )
        response = client_b.get(reverse("evidence:download", args=[org_a.id, item.id]))
        assert response.status_code == 404

    def test_cross_tenant_file_id_via_own_org_url_prefix_is_404(self, client_a, org_a, org_b, user_b):
        other_org_item = services.create_file_evidence(
            organisation=org_b, actor=user_b, title="Org B file", description="",
            source_label="", observed_at=None, valid_until=None,
            uploaded_file=_upload(),
        )
        response = client_a.get(reverse("evidence:download", args=[org_a.id, other_org_item.id]))
        assert response.status_code == 404

    # --- lifecycle mutation (withdraw / supersede) ------------------------
    def test_member_cannot_withdraw_other_organisations_evidence(self, client_b, org_a, user_a):
        item = services.create_external_reference_evidence(
            organisation=org_a, actor=user_a, title="Org A evidence", description="",
            source_label="", observed_at=None, valid_until=None,
            reference_url="https://example.test/a",
        )
        response = client_b.post(reverse("evidence:withdraw", args=[org_a.id, item.id]))
        assert response.status_code == 404
        item.refresh_from_db()
        assert item.status == EvidenceItem.STATUS_ACTIVE

    def test_member_cannot_supersede_another_organisations_evidence_via_upload(
        self, client_b, org_a, user_a
    ):
        target = services.create_file_evidence(
            organisation=org_a, actor=user_a, title="Org A file", description="",
            source_label="", observed_at=None, valid_until=None,
            uploaded_file=_upload(),
        )
        response = client_b.post(
            reverse("evidence:upload", args=[org_a.id]) + f"?supersedes={target.id}",
            {
                "title": "Hijacked replacement",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "file": _upload(MINIMAL_PDF, "new.pdf"),
                "supersedes": str(target.id),
            },
        )
        # user_b is not even a member of org_a, so the organisation lookup
        # itself 404s before the supersedes target is ever considered.
        assert response.status_code == 404
        target.refresh_from_db()
        assert target.status == EvidenceItem.STATUS_ACTIVE

    def test_member_cannot_use_own_org_evidence_id_to_supersede_another_organisations_evidence(
        self, client_a, org_a, org_b, user_b
    ):
        """
        user_a IS a member of org_a (the URL organisation is legitimate),
        but the `supersedes` id points at org_b's evidence. The
        organisation-scoped supersedes lookup itself must 404, not the
        wider org_a membership check.
        """
        other_org_item = services.create_file_evidence(
            organisation=org_b, actor=user_b, title="Org B file", description="",
            source_label="", observed_at=None, valid_until=None,
            uploaded_file=_upload(),
        )
        response = client_a.get(
            reverse("evidence:upload", args=[org_a.id]) + f"?supersedes={other_org_item.id}"
        )
        assert response.status_code == 404
        other_org_item.refresh_from_db()
        assert other_org_item.status == EvidenceItem.STATUS_ACTIVE

    def test_member_cannot_create_evidence_on_another_organisation(self, client_b, org_a):
        response = client_b.post(
            reverse("evidence:add_reference", args=[org_a.id]),
            {
                "title": "Hijacked evidence",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "reference_url": "https://example.test/hijacked",
            },
        )
        assert response.status_code == 404
        assert not EvidenceItem.objects.filter(organisation=org_a).exists()

    # --- hash/dedup must never leak cross-tenant information --------------
    def test_identical_file_bytes_across_two_organisations_never_leak_a_cross_tenant_hint(
        self, org_a, org_b, user_a, user_b, member_a, member_b
    ):
        """
        M003 PID §10/§16: 'Never reveal cross-tenant duplicate/hash
        information.' This dispatch implements no dedup/duplicate-warning
        behaviour at all (see the dispatch report) - the strongest way to
        satisfy the negative requirement is simply not to have a code path
        that compares hashes across organisations. This test proves that
        directly: uploading byte-identical content to two different
        organisations succeeds independently for both, with no error,
        warning, or behavioural difference between the first and second
        upload that could let one organisation infer the other's evidence
        exists.

        Uses two independently-instantiated django.test.Client objects
        rather than the shared client_a/client_b fixtures: those fixtures
        both resolve to the *same* underlying pytest-django `client`
        fixture instance (function-scoped, cached per test), so
        force_login(user_b) on client_b silently logs user_a back out of
        client_a when both are requested in one test - discovered while
        writing this test (see this dispatch's report to the PL). Every
        other test in this dispatch only needs one of the two clients per
        test, where that sharing is invisible.
        """
        client_a = Client()
        client_a.force_login(user_a)
        client_b = Client()
        client_b.force_login(user_b)

        response_a = client_a.post(
            reverse("evidence:upload", args=[org_a.id]),
            {
                "title": "Shared content, org A",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "file": _upload(MINIMAL_PDF, "shared.pdf"),
            },
        )
        response_b = client_b.post(
            reverse("evidence:upload", args=[org_b.id]),
            {
                "title": "Shared content, org B",
                "description": "",
                "source_label": "",
                "observed_at": "",
                "valid_until": "",
                "file": _upload(MINIMAL_PDF, "shared.pdf"),
            },
        )
        assert response_a.status_code == 302
        assert response_b.status_code == 302

        item_a = EvidenceItem.objects.get(organisation=org_a)
        item_b = EvidenceItem.objects.get(organisation=org_b)
        assert item_a.sha256 == item_b.sha256  # same bytes, as expected
        assert item_a.stored_filename != item_b.stored_filename  # independent, opaque storage

        # Org B's evidence list/detail must show no trace of org A's item.
        list_response = client_b.get(reverse("evidence:list", args=[org_b.id]))
        assert "Shared content, org A" not in list_response.content.decode()
        assert client_b.get(reverse("evidence:detail", args=[org_a.id, item_a.id])).status_code == 404
