"""
Release-blocking tenant isolation tests (PID §23, §26 "Policy lifecycle" /
"Policy grounding" - m004-2a-policy-foundation + m004-2b-policy-lifecycle
dispatches). Two synthetic organisations, two users each a member of
exactly one, proving organisation A cannot view/generate/edit/approve/
download organisation B's policy draft, and that a foreign/manipulated
organisation id or version id in the URL is an ordinary 404 - never a path
to another organisation's policy.
"""
import datetime
import uuid

import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from ai_platform.models import AIInvocationRecord
from ai_platform.testing import FakePolicyGateway
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import assign_role
from policy.models import PolicyDocument, PolicyVersion
from policy.services import approve_policy_directly, generate_policy_draft


@pytest.mark.django_db
class TestPolicyTenantIsolation:
    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_own_organisations_policy_detail(self, client_a, org_a):
        response = client_a.get(reverse("policy:detail", args=[org_a.id]))
        assert response.status_code == 200

    # --- cross-tenant read negative ---------------------------------------
    def test_member_cannot_read_other_organisations_policy_detail(self, client_b, org_a, user_a):
        generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="valid"))
        response = client_b.get(reverse("policy:detail", args=[org_a.id]))
        assert response.status_code == 404

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_generate_policy_on_other_organisation(self, client_b, org_a, monkeypatch):
        monkeypatch.setattr(
            "policy.services.LiteLLMGateway", lambda: FakePolicyGateway(mode="valid")
        )
        response = client_b.post(reverse("policy:generate", args=[org_a.id]))
        assert response.status_code == 404
        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0
        assert AIInvocationRecord.objects.filter(organisation=org_a).count() == 0

    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("policy:detail", args=[uuid.uuid4()]))
        assert response.status_code == 404
        response = client_a.post(reverse("policy:generate", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_organisation_b_draft_generation_never_creates_a_row_for_organisation_a(
        self, org_a, org_b, user_b
    ):
        generate_policy_draft(org_b, actor=user_b, gateway=FakePolicyGateway(mode="valid"))
        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0


@pytest.mark.django_db
class TestPolicyLifecycleTenantIsolation:
    """m004-2b-policy-lifecycle dispatch's own PID §23/§26 negative tests:
    edit/approve/download must all be impossible across the tenant
    boundary, and a version id from organisation A used against
    organisation B's URL (or vice versa) is an ordinary 404."""

    def _org_a_version(self, org_a, sections=None):
        document, _ = PolicyDocument.objects.get_or_create(organisation=org_a)
        return PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org A ISP",
            sections=sections
            or [{"section_key": "purpose_and_scope", "content": "Org A confidential content."}],
            review_warnings=[],
        )

    def test_member_cannot_view_other_organisations_policy_version_detail(
        self, client_b, org_a
    ):
        version = self._org_a_version(org_a)
        response = client_b.get(reverse("policy:version_detail", args=[org_a.id, version.id]))
        assert response.status_code == 404

    def test_member_cannot_edit_other_organisations_draft(self, client_b, org_a):
        version = self._org_a_version(org_a)
        response = client_b.post(
            reverse("policy:version_edit", args=[org_a.id, version.id]),
            data={
                "title": "hijacked",
                "next_review_date": "",
                "section__purpose_and_scope": "hijacked content",
            },
        )
        assert response.status_code == 404
        version.refresh_from_db()
        assert version.title == "Org A ISP"
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_DRAFT_EDITED
        ).exists()

    def test_member_cannot_approve_other_organisations_draft_directly(
        self, client_b, org_a, user_a
    ):
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Org A Holder"
        )
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=person,
        )
        version = self._org_a_version(org_a)

        response = client_b.post(
            reverse("policy:version_approve_direct", args=[org_a.id, version.id]),
            data={"next_review_date": "2027-01-01"},
        )
        assert response.status_code == 404
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT

    def test_member_cannot_approve_other_organisations_draft_externally(
        self, client_b, org_a
    ):
        external_person = OrganisationPerson.objects.create(
            organisation=org_a, user=None, full_name="External Authoriser"
        )
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=external_person,
        )
        version = self._org_a_version(org_a)

        response = client_b.post(
            reverse("policy:version_approve_external", args=[org_a.id, version.id]),
            data={"next_review_date": "2027-01-01"},
        )
        assert response.status_code == 404
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT

    def test_member_cannot_download_other_organisations_approved_policy(
        self, client_b, org_a, user_a
    ):
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Org A Holder"
        )
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=person,
        )
        version = self._org_a_version(
            org_a, sections=[{"section_key": "purpose_and_scope", "content": "secret content"}]
        )
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        response = client_b.get(reverse("policy:version_download", args=[org_a.id, version.id]))
        assert response.status_code == 404

    def test_member_cannot_create_new_draft_for_other_organisations_approved_policy(
        self, client_b, org_a, user_a
    ):
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Org A Holder"
        )
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
            person=person,
        )
        version = self._org_a_version(org_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        response = client_b.post(
            reverse("policy:version_new_draft", args=[org_a.id, version.id])
        )
        assert response.status_code == 404
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 1

    def test_nonexistent_version_id_in_url_is_404(self, client_a, org_a):
        response = client_a.get(
            reverse("policy:version_detail", args=[org_a.id, uuid.uuid4()])
        )
        assert response.status_code == 404

    def test_org_b_version_id_used_against_org_a_url_is_404(
        self, client_a, org_a, org_b, user_b
    ):
        """A version that genuinely exists (for org_b), but referenced
        through org_a's URL segment - must be an ordinary 404, not a
        cross-tenant read via a mismatched organisation_id/version_id
        pairing."""
        document, _ = PolicyDocument.objects.get_or_create(organisation=org_b)
        version_b = PolicyVersion.objects.create(
            document=document,
            organisation=org_b,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org B ISP",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
            review_warnings=[],
        )
        response = client_a.get(
            reverse("policy:version_detail", args=[org_a.id, version_b.id])
        )
        assert response.status_code == 404
