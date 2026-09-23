import uuid

import pytest
from django.urls import reverse

from evidence import link_services
from evidence.models import ControlEvidenceLink, EvidenceItem
from remediation.models import RemediationAction
from security_baseline.models import ANSWER_YES, BaselineAnswer, BaselineAssessment


def _set_answer(org, key, answer):
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": "test-v1"}
    )
    return BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=key, defaults={"answer": answer}
    )[0]


@pytest.mark.django_db
class TestSecurityStateListView:
    def test_get_renders_one_row_per_catalogue_control(self, client_a, org_a):
        response = client_a.get(reverse("security_state:list", args=[org_a.id]))
        assert response.status_code == 200
        from security_baseline.catalogue import CATALOGUE

        assert len(response.context["rows"]) == len(CATALOGUE)

    def test_shows_not_confirmed_for_an_unanswered_control(self, client_a, org_a):
        response = client_a.get(reverse("security_state:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Not confirmed" in content
        assert "Verified" not in content
        assert "Certified" not in content
        assert "Compliant" not in content
        assert "Audited" not in content


@pytest.mark.django_db
class TestSecurityStateDetailView:
    def test_get_shows_canonical_answer_and_evidence(self, client_a, org_a, user_a):
        _set_answer(org_a, "mfa_user_accounts", ANSWER_YES)
        evidence = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="MFA policy export",
            reference_url="https://example.test/mfa",
            recorded_by=user_a,
        )
        link_services.link_evidence_to_control(
            org_a, evidence, "mfa_user_accounts", ControlEvidenceLink.RELATIONSHIP_SUPPORTS, "", user_a
        )
        response = client_a.get(
            reverse("security_state:detail", args=[org_a.id, "mfa_user_accounts"])
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Supporting evidence attached" in content
        assert "MFA policy export" in content

    def test_get_shows_remediation_actions_for_this_control(self, client_a, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="Fix MFA gap", control_key="mfa_user_accounts",
            status=RemediationAction.STATUS_OPEN, created_by=user_a,
        )
        response = client_a.get(
            reverse("security_state:detail", args=[org_a.id, "mfa_user_accounts"])
        )
        assert action.title in response.content.decode()

    def test_get_links_to_the_canonical_baseline_edit_page(self, client_a, org_a):
        response = client_a.get(
            reverse("security_state:detail", args=[org_a.id, "mfa_user_accounts"])
        )
        assert reverse("security_baseline:baseline", args=[org_a.id]) in response.content.decode()

    def test_unknown_control_key_is_404(self, client_a, org_a):
        response = client_a.get(
            reverse("security_state:detail", args=[org_a.id, "not_a_real_control_key"])
        )
        assert response.status_code == 404
