"""
HTTP UI tests for the M008C guided Stage 4 journey's own rendering (the
one-at-a-time question page) - the full read/write round trip, tenant
isolation, and the NOT_APPLICABLE forgery proof now live in
`test_foundations_views.py`; this file covers what a single question
screen renders.

`security_baseline:baseline` (the pre-M008C long-form page this file used
to test) now only redirects - see test_foundations_views.py's
TestLegacyBaselineEntryPointRedirects for that behaviour.
"""
import pytest
from django.urls import reverse

from security_baseline.forms import option_field_name
from security_baseline.models import BaselineAssessment
from security_baseline.stage4 import QUESTION_COPY


def _question_url(organisation_id, key):
    return reverse("security_baseline:foundations_question", args=[organisation_id, key])


@pytest.mark.django_db
class TestFoundationsQuestionRendering:
    def test_renders_approved_question_text_and_why_it_matters(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "mfa_user_accounts"))
        assert response.status_code == 200
        content = response.content.decode()
        copy = QUESTION_COPY["mfa_user_accounts"]
        assert copy["question"] in content
        assert copy["why_it_matters"] in content
        assert copy["title"] in content
        assert "csrfmiddlewaretoken" in content

    def test_renders_every_offered_option_label(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "backups"))
        content = response.content.decode()
        for label in (
            "Backed up AND a restore has been tested",
            "Backed up, but a restore has never been tested",
            "Backed up, but only some systems/data are covered",
            "Not backed up",
            "Not sure",
        ):
            assert label in content

    def test_device_encryption_never_renders_a_not_applicable_option(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "device_encryption"))
        content = response.content.decode()
        assert "not applicable" not in content.lower()

    def test_statement_not_verified_disclosure_is_present(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "backups"))
        content = response.content.decode()
        assert "not" in content.lower() and "verified" in content.lower()

    def test_valid_submission_creates_assessment_and_answer(self, client_a, org_a):
        response = client_a.post(
            _question_url(org_a.id, "mfa_user_accounts"),
            {option_field_name("mfa_user_accounts"): "MFA_USER_ALL_REQUIRED"},
        )
        assert response.status_code == 302
        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert assessment.answers.get(question_key="mfa_user_accounts").answer == "yes"

    def test_success_message_shown_after_save(self, client_a, org_a):
        url = _question_url(org_a.id, "mfa_user_accounts")
        response = client_a.post(url, {option_field_name("mfa_user_accounts"): "MFA_USER_ALL_REQUIRED"})
        follow = client_a.get(response.url)
        assert "saved" in follow.content.decode().lower()

    def test_missing_option_code_is_rejected_not_silently_defaulted(self, client_a, org_a):
        response = client_a.post(_question_url(org_a.id, "mfa_user_accounts"), {})
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()
