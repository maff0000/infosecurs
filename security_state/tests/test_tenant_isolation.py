"""
PID §16/§19: organisation A's security-state view must never include
organisation B's evidence/links/actions, and B must not be able to reach
A's security-state pages at all.
"""
import pytest
from django.urls import reverse

from evidence import link_services
from evidence.models import ControlEvidenceLink, EvidenceItem
from remediation.models import RemediationAction
from security_baseline.models import ANSWER_YES, BaselineAnswer, BaselineAssessment

CONTROL_KEY = "mfa_user_accounts"


def _set_answer(org, key, answer):
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": "test-v1"}
    )
    return BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=key, defaults={"answer": answer}
    )[0]


@pytest.mark.django_db
class TestSecurityStateTenantIsolation:
    def test_member_cannot_view_another_organisations_security_state_list(self, client_b, org_a):
        response = client_b.get(reverse("security_state:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_view_another_organisations_security_state_detail(self, client_b, org_a):
        response = client_b.get(reverse("security_state:detail", args=[org_a.id, CONTROL_KEY]))
        assert response.status_code == 404

    def test_nonexistent_organisation_id_is_404(self, client_a):
        import uuid

        response = client_a.get(reverse("security_state:list", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_org_as_list_never_shows_org_bs_evidence_title(self, client_a, org_a, org_b, user_a, user_b):
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        _set_answer(org_b, CONTROL_KEY, ANSWER_YES)
        evidence_b = EvidenceItem.objects.create(
            organisation=org_b,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Org B secret evidence title",
            reference_url="https://example.test/b",
            recorded_by=user_b,
        )
        link_services.link_evidence_to_control(
            org_b, evidence_b, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_b
        )
        response = client_a.get(reverse("security_state:detail", args=[org_a.id, CONTROL_KEY]))
        assert "Org B secret evidence title" not in response.content.decode()

    def test_org_as_detail_never_shows_org_bs_remediation_action(self, client_a, org_a, org_b, user_b):
        RemediationAction.objects.create(
            organisation=org_b, title="Org B secret action title", control_key=CONTROL_KEY,
            status=RemediationAction.STATUS_OPEN, created_by=user_b,
        )
        response = client_a.get(reverse("security_state:detail", args=[org_a.id, CONTROL_KEY]))
        assert "Org B secret action title" not in response.content.decode()
