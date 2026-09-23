"""
security_baseline.services.save_baseline_answers is the single code path
that writes a BaselineAnswer row (PID.md M002 §0.5) - security_baseline's
own baseline_view and key_assets' asset-detail view both call this same
function. These tests exercise it directly (unit-level, no HTTP), plus the
BaselineAssessmentForm.question_keys filtering it is designed to pair with.
"""
import pytest

from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.forms import BaselineAssessmentForm, answer_field_name, note_field_name
from security_baseline.models import BaselineAnswer, BaselineAssessment
from security_baseline.services import save_baseline_answers


@pytest.mark.django_db
class TestSaveBaselineAnswers:
    def test_default_question_keys_saves_every_catalogue_question(self, org_a):
        cleaned_data = {}
        for item in CATALOGUE:
            cleaned_data[answer_field_name(item["key"])] = "unknown"
            cleaned_data[note_field_name(item["key"])] = ""

        assessment = save_baseline_answers(org_a, cleaned_data)

        assert assessment.organisation == org_a
        assert assessment.catalogue_version == CATALOGUE_VERSION
        assert assessment.answers.count() == len(CATALOGUE)

    def test_restricted_question_keys_saves_only_that_subset(self, org_a):
        cleaned_data = {
            answer_field_name("device_encryption"): "no",
            note_field_name("device_encryption"): "Not encrypted.",
            answer_field_name("patching"): "yes",
            note_field_name("patching"): "",
        }

        assessment = save_baseline_answers(
            org_a, cleaned_data, question_keys=["device_encryption", "patching"]
        )

        assert assessment.answers.count() == 2
        assert assessment.answers.get(question_key="device_encryption").answer == "no"
        assert assessment.answers.get(question_key="patching").answer == "yes"

    def test_restricted_save_does_not_touch_answers_outside_its_subset(self, org_a):
        # First establish a full baseline (mimics the general baseline page).
        full_data = {}
        for item in CATALOGUE:
            full_data[answer_field_name(item["key"])] = "unknown"
            full_data[note_field_name(item["key"])] = ""
        full_data[answer_field_name("mfa_user_accounts")] = "yes"
        full_data[note_field_name("mfa_user_accounts")] = "Untouched by the restricted save below."
        save_baseline_answers(org_a, full_data)

        # A restricted save (mimics the asset-detail page) for an unrelated
        # question subset must not alter mfa_user_accounts at all.
        restricted_data = {
            answer_field_name("device_encryption"): "no",
            note_field_name("device_encryption"): "",
        }
        save_baseline_answers(org_a, restricted_data, question_keys=["device_encryption"])

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        mfa_answer = assessment.answers.get(question_key="mfa_user_accounts")
        assert mfa_answer.answer == "yes"
        assert mfa_answer.note == "Untouched by the restricted save below."

    def test_second_call_updates_the_same_row_rather_than_duplicating(self, org_a):
        data = {
            answer_field_name("backups"): "no",
            note_field_name("backups"): "First save.",
        }
        save_baseline_answers(org_a, data, question_keys=["backups"])
        first_pk = BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        ).pk

        data = {
            answer_field_name("backups"): "yes",
            note_field_name("backups"): "Second save.",
        }
        save_baseline_answers(org_a, data, question_keys=["backups"])

        answers = BaselineAnswer.objects.filter(
            assessment__organisation=org_a, question_key="backups"
        )
        assert answers.count() == 1
        answer = answers.get()
        assert answer.pk == first_pk
        assert answer.answer == "yes"
        assert answer.note == "Second save."

    def test_stamps_current_catalogue_version_even_on_a_restricted_save(self, org_a):
        data = {
            answer_field_name("backups"): "unknown",
            note_field_name("backups"): "",
        }
        assessment = save_baseline_answers(org_a, data, question_keys=["backups"])
        assert assessment.catalogue_version == CATALOGUE_VERSION


@pytest.mark.django_db
class TestBaselineAssessmentFormQuestionKeysFiltering:
    def test_default_builds_a_field_per_catalogue_question(self):
        form = BaselineAssessmentForm()
        for item in CATALOGUE:
            assert answer_field_name(item["key"]) in form.fields
            assert note_field_name(item["key"]) in form.fields

    def test_question_keys_restricts_fields_to_that_subset(self):
        form = BaselineAssessmentForm(question_keys=["device_encryption", "patching"])
        assert answer_field_name("device_encryption") in form.fields
        assert answer_field_name("patching") in form.fields
        assert answer_field_name("mfa_user_accounts") not in form.fields
        assert len(form.fields) == 4  # 2 questions x (answer + note)

    def test_restricted_form_validates_with_only_its_subset_submitted(self):
        form = BaselineAssessmentForm(
            data={
                answer_field_name("device_encryption"): "no",
                note_field_name("device_encryption"): "",
            },
            question_keys=["device_encryption"],
        )
        assert form.is_valid(), form.errors
