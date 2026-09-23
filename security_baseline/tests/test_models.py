import pytest
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.models import ANSWER_UNKNOWN, ANSWER_YES, BaselineAnswer, BaselineAssessment


@pytest.mark.django_db
class TestBaselineAssessment:
    def test_catalogue_version_persisted(self, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        assessment.refresh_from_db()
        assert assessment.catalogue_version == CATALOGUE_VERSION

    def test_one_assessment_per_organisation(self, org_a):
        BaselineAssessment.objects.create(organisation=org_a, catalogue_version=CATALOGUE_VERSION)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BaselineAssessment.objects.create(
                    organisation=org_a, catalogue_version=CATALOGUE_VERSION
                )


@pytest.mark.django_db
class TestBaselineAnswer:
    def test_answer_defaults_to_unknown_not_blank(self, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        answer = BaselineAnswer.objects.create(assessment=assessment, question_key="mfa_user_accounts")
        answer.refresh_from_db()
        assert answer.answer == ANSWER_UNKNOWN
        assert answer.answer != ""

    def test_notes_persist(self, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        answer = BaselineAnswer.objects.create(
            assessment=assessment,
            question_key="backups",
            answer=ANSWER_YES,
            note="Backed up nightly to a second provider; last restore test was in August.",
        )
        answer.refresh_from_db()
        assert answer.note == (
            "Backed up nightly to a second provider; last restore test was in August."
        )

    def test_unsupported_answer_value_rejected_by_full_clean(self, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        answer = BaselineAnswer(
            assessment=assessment, question_key="patching", answer="definitely-yes-trust-me"
        )
        with pytest.raises(ValidationError):
            answer.full_clean()

    def test_one_answer_per_question_per_assessment(self, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(assessment=assessment, question_key="patching")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BaselineAnswer.objects.create(assessment=assessment, question_key="patching")

    def test_catalogue_has_the_pid_defined_twelve_areas_with_unique_keys(self):
        assert len(CATALOGUE) == 12
        keys = [item["key"] for item in CATALOGUE]
        assert len(keys) == len(set(keys))
