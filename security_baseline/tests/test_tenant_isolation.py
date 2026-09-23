import pytest
from django.urls import reverse

from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _all_unknown_post():
    data = {}
    for item in CATALOGUE:
        data[answer_field_name(item["key"])] = "unknown"
        data[note_field_name(item["key"])] = ""
    return data


@pytest.mark.django_db
class TestSecurityBaselineTenantIsolation:
    """
    Mirrors organisations/tests/test_tenant_isolation.py's shape (PID §16):
    org A cannot read or edit org B's baseline, using two synthetic
    organisations/users each a member of exactly one.
    """

    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_and_write_own_baseline(self, client_a, org_a):
        data = _all_unknown_post()
        data[answer_field_name("backups")] = "yes"
        response = client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), data)
        assert response.status_code == 302

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert assessment.answers.get(question_key="backups").answer == "yes"

    # --- cross-tenant read negative --------------------------------------
    def test_member_cannot_read_other_organisations_baseline_page(self, client_b, org_a):
        BaselineAssessment.objects.create(organisation=org_a, catalogue_version=CATALOGUE_VERSION)
        response = client_b.get(reverse("security_baseline:baseline", args=[org_a.id]))
        assert response.status_code == 404

    def test_other_organisations_notes_never_appear_in_a_cross_tenant_response(
        self, client_b, org_a
    ):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(
            assessment=assessment,
            question_key="backups",
            answer="no",
            note="ORG-A-SECRET-NOTE-should-never-leak-to-org-b",
        )
        response = client_b.get(reverse("security_baseline:baseline", args=[org_a.id]))
        assert response.status_code == 404
        assert b"ORG-A-SECRET-NOTE-should-never-leak-to-org-b" not in response.content

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_create_baseline_on_other_organisation(self, client_b, org_a):
        response = client_b.post(
            reverse("security_baseline:baseline", args=[org_a.id]), _all_unknown_post()
        )
        assert response.status_code == 404
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_member_cannot_update_other_organisations_existing_baseline(self, client_b, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(assessment=assessment, question_key="backups", answer="no")

        data = _all_unknown_post()
        data[answer_field_name("backups")] = "yes"
        response = client_b.post(reverse("security_baseline:baseline", args=[org_a.id]), data)

        assert response.status_code == 404
        assert (
            BaselineAnswer.objects.get(assessment=assessment, question_key="backups").answer
            == "no"
        )

    # --- URL manipulation -----------------------------------------------
    def test_malformed_organisation_id_in_url_does_not_resolve(self, client_a):
        response = client_a.get("/organisations/not-a-uuid/baseline/")
        assert response.status_code == 404
