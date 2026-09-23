"""
Approved-artefact PDF download tests (PID §19, §26 "Policy lifecycle:
download exact approved version" - m004-2b-policy-lifecycle dispatch).
"""
import datetime

import pytest
from django.urls import reverse

from organisations.models import OrganisationProfile
from policy.models import PolicyVersion
from policy.services import approve_policy_directly


@pytest.mark.django_db
class TestPolicyDownloadView:
    def test_draft_version_cannot_be_downloaded(self, client_a, org_a, make_draft_version):
        version = make_draft_version(org_a)
        response = client_a.get(reverse("policy:version_download", args=[org_a.id, version.id]))
        assert response.status_code == 404

    def test_approved_version_downloads_as_pdf_with_safe_headers(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(org_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        response = client_a.get(reverse("policy:version_download", args=[org_a.id, version.id]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert "attachment" in response["Content-Disposition"]
        assert "filename=" in response["Content-Disposition"]
        assert "filename*=UTF-8''" in response["Content-Disposition"]
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response.content[:5] == b"%PDF-"

    def test_superseded_version_remains_downloadable(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        first = make_draft_version(org_a, version_number=1)
        approve_policy_directly(first, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        second = make_draft_version(org_a, version_number=2, title="Second version")
        approve_policy_directly(second, actor=user_a, next_review_date=datetime.date(2028, 1, 1))

        first.refresh_from_db()
        assert first.status == PolicyVersion.STATUS_SUPERSEDED
        response = client_a.get(reverse("policy:version_download", args=[org_a.id, first.id]))
        assert response.status_code == 200
        assert response.content[:5] == b"%PDF-"

    def test_download_reflects_the_frozen_version_not_current_live_state(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        """PID §19: 'no hidden mutable live-state lookup when downloading an
        old approved version'. Construct a case where organisation state
        that is NOT part of the immutable `PolicyVersion` row (its
        `OrganisationProfile.description`, and a security-baseline-shaped
        marker string) changes AFTER approval, and prove the downloaded
        PDF's rendered TEXT still shows only the version's own frozen
        section content - never the post-approval marker text - by
        asserting directly on the (uncompressed - see policy/pdf.py)
        rendered PDF bytes, not merely on the Python object graph."""
        assign_policy_authoriser(org_a, person_a)
        frozen_marker = "FROZEN-AT-APPROVAL-6f2a1c"
        live_marker = "CHANGED-AFTER-APPROVAL-9d84be"
        version = make_draft_version(
            org_a,
            title="Original Frozen Title",
            sections=[{"section_key": "purpose_and_scope", "content": frozen_marker}],
        )
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        # Mutate organisation-level state that a careless implementation
        # might be tempted to re-query at download time - the render must
        # never pick this up.
        OrganisationProfile.objects.update_or_create(
            organisation=org_a, defaults={"description": live_marker}
        )

        response = client_a.get(reverse("policy:version_download", args=[org_a.id, version.id]))
        assert response.status_code == 200
        assert frozen_marker.encode() in response.content
        assert b"Original Frozen Title" in response.content
        assert live_marker.encode() not in response.content

    def test_download_requires_login(self, client, org_a, make_draft_version):
        version = make_draft_version(org_a, status=PolicyVersion.STATUS_APPROVED)
        response = client.get(reverse("policy:version_download", args=[org_a.id, version.id]))
        assert response.status_code in (302, 403)
