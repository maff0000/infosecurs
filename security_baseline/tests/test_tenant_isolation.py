import uuid

import pytest
from django.urls import reverse

from security_baseline.forms import option_field_name
from security_baseline.models import BaselineAnswer, BaselineAssessment
from security_baseline.catalogue import CATALOGUE_VERSION


def _question_url(organisation_id, key):
    return reverse("security_baseline:foundations_question", args=[organisation_id, key])


@pytest.mark.django_db
class TestSecurityBaselineTenantIsolation:
    """
    Mirrors organisations/tests/test_tenant_isolation.py's shape (PID §16):
    org A cannot read or edit org B's baseline, using two synthetic
    organisations/users each a member of exactly one. Exercises the
    M008C guided journey's own routes - see test_foundations_views.py for
    the fuller round-trip/forgery coverage; this file stays focused on
    the tenant-isolation dimension, matching every other app's own test
    file naming/shape in this codebase.
    """

    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_and_write_own_baseline(self, client_a, org_a):
        url = _question_url(org_a.id, "backups")
        response = client_a.post(url, {option_field_name("backups"): "BACKUPS_TESTED"})
        assert response.status_code == 302

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert assessment.answers.get(question_key="backups").answer == "yes"

    # --- cross-tenant read negative --------------------------------------
    def test_member_cannot_read_other_organisations_question_page(self, client_b, org_a):
        BaselineAssessment.objects.create(organisation=org_a, catalogue_version=CATALOGUE_VERSION)
        response = client_b.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 404

    def test_other_organisations_answers_never_appear_in_a_cross_tenant_response(
        self, client_b, org_a
    ):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(
            assessment=assessment,
            question_key="backups",
            answer="no",
        )
        response = client_b.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 404

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_create_baseline_on_other_organisation(self, client_b, org_a):
        response = client_b.post(
            _question_url(org_a.id, "backups"), {option_field_name("backups"): "BACKUPS_TESTED"}
        )
        assert response.status_code == 404
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_member_cannot_update_other_organisations_existing_baseline(self, client_b, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(assessment=assessment, question_key="backups", answer="no")

        response = client_b.post(
            _question_url(org_a.id, "backups"), {option_field_name("backups"): "BACKUPS_TESTED"}
        )

        assert response.status_code == 404
        assert (
            BaselineAnswer.objects.get(assessment=assessment, question_key="backups").answer
            == "no"
        )

    # --- URL manipulation -----------------------------------------------
    def test_malformed_organisation_id_in_url_does_not_resolve(self, client_a):
        response = client_a.get("/organisations/not-a-uuid/baseline/")
        assert response.status_code == 404

    def test_nonexistent_organisation_id_is_404(self, client_a):
        response = client_a.get(_question_url(uuid.uuid4(), "backups"))
        assert response.status_code == 404
