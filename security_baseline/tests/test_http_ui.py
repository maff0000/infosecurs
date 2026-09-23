import pytest
from django.urls import reverse

from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.models import ANSWER_UNKNOWN, ANSWER_YES, BaselineAnswer, BaselineAssessment


def _all_unknown_post():
    """A minimal valid POST: every question explicitly answered 'unknown'."""
    data = {}
    for item in CATALOGUE:
        data[answer_field_name(item["key"])] = ANSWER_UNKNOWN
        data[note_field_name(item["key"])] = ""
    return data


@pytest.mark.django_db
class TestSecurityBaselineHttpUi:
    def test_form_renders_with_expected_fields_and_explanatory_copy(self, client_a, org_a):
        response = client_a.get(reverse("security_baseline:baseline", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        for item in CATALOGUE:
            assert f'name="{answer_field_name(item["key"])}"' in content
            assert item["question"] in content
        # PID §6.2: the UI must explain these are customer-confirmed
        # statements, not system-verified controls.
        assert "not" in content.lower() and "verified" in content.lower()
        assert "csrfmiddlewaretoken" in content

    def test_valid_submission_creates_assessment_and_answers(self, client_a, org_a):
        data = _all_unknown_post()
        data[answer_field_name("mfa_user_accounts")] = "yes"
        data[note_field_name("mfa_user_accounts")] = "Enforced via conditional access."
        data[answer_field_name("backups")] = "partial"
        data[answer_field_name("device_encryption")] = "not_applicable"

        response = client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), data)
        assert response.status_code == 302

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert assessment.catalogue_version == CATALOGUE_VERSION
        assert assessment.answers.count() == len(CATALOGUE)

        mfa_answer = assessment.answers.get(question_key="mfa_user_accounts")
        assert mfa_answer.answer == "yes"
        assert mfa_answer.note == "Enforced via conditional access."
        assert assessment.answers.get(question_key="backups").answer == "partial"
        assert assessment.answers.get(question_key="device_encryption").answer == "not_applicable"

    def test_success_message_shown_after_save(self, client_a, org_a):
        response = client_a.post(
            reverse("security_baseline:baseline", args=[org_a.id]), _all_unknown_post()
        )
        follow = client_a.get(response.url)
        assert "saved" in follow.content.decode().lower()

    def test_reload_after_save_shows_persisted_answers_and_notes(self, client_a, org_a):
        data = _all_unknown_post()
        data[answer_field_name("backups")] = "yes"
        data[note_field_name("backups")] = "Tested restore in September."
        client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), data)

        response = client_a.get(reverse("security_baseline:baseline", args=[org_a.id]))
        content = response.content.decode()
        assert "Tested restore in September." in content
        assert f'name="{answer_field_name("backups")}"' in content

    def test_second_save_updates_existing_answers_rather_than_duplicating(self, client_a, org_a):
        client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), _all_unknown_post())
        data = _all_unknown_post()
        data[answer_field_name("patching")] = "yes"
        client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), data)

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert assessment.answers.count() == len(CATALOGUE)
        assert assessment.answers.get(question_key="patching").answer == "yes"

    def test_unsupported_answer_value_rejected_and_not_saved(self, client_a, org_a):
        data = _all_unknown_post()
        data[answer_field_name("mfa_user_accounts")] = "definitely-yes-trust-me"

        response = client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), data)
        assert response.status_code == 200  # re-renders the form, no redirect
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_missing_answer_field_is_rejected_not_silently_treated_as_unknown(
        self, client_a, org_a
    ):
        """
        A missing/blank answer must be a validation error, not silently
        saved as 'unknown' - unknown is only valid when explicitly chosen
        (PID §6.2, §21 "unknown distinct from a blank/missing answer").
        """
        data = _all_unknown_post()
        del data[answer_field_name("mfa_user_accounts")]

        response = client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), data)
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()
        assert "required" in response.content.decode().lower()

    def test_notes_are_optional(self, client_a, org_a):
        data = _all_unknown_post()  # every note field already blank
        response = client_a.post(reverse("security_baseline:baseline", args=[org_a.id]), data)
        assert response.status_code == 302
