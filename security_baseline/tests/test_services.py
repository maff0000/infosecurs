"""
security_baseline.services.save_baseline_answers is the single code path
that writes a BaselineAnswer row (PID.md M002 §0.5) - security_baseline's
own baseline_view and key_assets' asset-detail view both call this same
function. These tests exercise it directly (unit-level, no HTTP), plus the
BaselineAssessmentForm.question_keys filtering it is designed to pair with.

TestControlAnswerChangedActivityEvent below additionally covers M003 PID
§12/§17: this same function is the shared baseline save path that must
emit a `control_answer_changed` ActivityEvent on a genuine canonical
answer change, and must not do so - or leave any partial write behind -
when nothing changed or the save rolls back.
"""
from unittest import mock

import pytest

from activity.models import ActivityEvent
from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.forms import BaselineAssessmentForm, answer_field_name, note_field_name
from security_baseline.models import (
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_YES,
    AnswerSelectionDetail,
    BaselineAnswer,
    BaselineAssessment,
)
from security_baseline.services import record_structured_baseline_answer, save_baseline_answers
from security_baseline.structured_catalogue import (
    FOUNDATIONS_QUESTION_METHODOLOGY_VERSION,
    UnknownOptionCodeError,
)


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


@pytest.mark.django_db
class TestControlAnswerChangedActivityEvent:
    """
    M003 PID §12: save_baseline_answers must emit exactly one
    control_answer_changed ActivityEvent per key whose *answer* genuinely
    changes, with correct previous/new-answer and note_changed fields,
    must emit none when nothing changed, and must never persist an event
    for a save that rolled back (PID §17).
    """

    def _events(self, org_a):
        return ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED
        )

    # --- genuine change: event with correct fields --------------------

    def test_first_time_real_answer_creates_event_with_unknown_as_previous(
        self, org_a, user_a
    ):
        save_baseline_answers(
            org_a,
            {
                answer_field_name("backups"): "yes",
                note_field_name("backups"): "Tested restore.",
            },
            question_keys=["backups"],
            actor=user_a,
        )
        event = self._events(org_a).get()
        assert event.control_key == "backups"
        assert event.actor == user_a
        assert event.metadata == {
            "previous_answer": "unknown",
            "new_answer": "yes",
            "note_changed": True,
        }
        # The note's actual content is never duplicated into the event.
        assert "Tested restore." not in str(event.metadata)

    def test_subsequent_real_change_records_correct_previous_and_new_answer(
        self, org_a, user_a
    ):
        save_baseline_answers(
            org_a,
            {answer_field_name("backups"): "yes", note_field_name("backups"): "Note."},
            question_keys=["backups"],
            actor=user_a,
        )
        save_baseline_answers(
            org_a,
            {answer_field_name("backups"): "no", note_field_name("backups"): "Note."},
            question_keys=["backups"],
            actor=user_a,
        )
        events = list(self._events(org_a).order_by("occurred_at", "id"))
        assert len(events) == 2
        assert events[0].metadata["previous_answer"] == "unknown"
        assert events[0].metadata["new_answer"] == "yes"
        assert events[1].metadata["previous_answer"] == "yes"
        assert events[1].metadata["new_answer"] == "no"
        # Same note both times - note_changed must be False on the second event.
        assert events[1].metadata["note_changed"] is False

    def test_note_only_change_does_not_create_an_event(self, org_a):
        save_baseline_answers(
            org_a,
            {answer_field_name("backups"): "yes", note_field_name("backups"): "First."},
            question_keys=["backups"],
        )
        assert self._events(org_a).count() == 1  # the initial unknown -> yes change

        save_baseline_answers(
            org_a,
            {answer_field_name("backups"): "yes", note_field_name("backups"): "Second."},
            question_keys=["backups"],
        )
        # Still exactly one event: the note-only edit is not an answer change.
        assert self._events(org_a).count() == 1

    # --- no genuine change: no false event ------------------------------

    def test_first_save_at_default_unknown_creates_no_event(self, org_a):
        """
        A brand-new assessment's first full-catalogue save, where every
        question is simply being submitted at its pre-filled 'unknown'
        default, must not fire len(CATALOGUE) spurious events.
        """
        data = {}
        for item in CATALOGUE:
            data[answer_field_name(item["key"])] = "unknown"
            data[note_field_name(item["key"])] = ""
        save_baseline_answers(org_a, data)
        assert self._events(org_a).count() == 0

    def test_saving_the_exact_same_values_twice_creates_no_event_on_the_second_save(
        self, org_a
    ):
        data = {answer_field_name("backups"): "yes", note_field_name("backups"): "Note."}
        save_baseline_answers(org_a, data, question_keys=["backups"])
        assert self._events(org_a).count() == 1

        # Save the exact same values again.
        save_baseline_answers(org_a, dict(data), question_keys=["backups"])
        assert self._events(org_a).count() == 1, (
            "an unchanged re-save must not create a second control_answer_changed event"
        )

    # --- transactional coherence (PID §17) ------------------------------

    def test_rollback_leaves_no_orphaned_event_and_no_partial_answer(self, org_a):
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

        with mock.patch(
            "security_baseline.services.record_event", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError):
                save_baseline_answers(
                    org_a,
                    {
                        answer_field_name("backups"): "yes",
                        note_field_name("backups"): "Note.",
                    },
                    question_keys=["backups"],
                )

        # The whole atomic block - including the BaselineAssessment/
        # BaselineAnswer writes that happened before record_event raised -
        # must have rolled back, not just the event.
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()
        assert not BaselineAnswer.objects.filter(
            assessment__organisation=org_a, question_key="backups"
        ).exists()
        assert self._events(org_a).count() == 0

    def test_rollback_on_second_save_leaves_prior_state_untouched(self, org_a):
        """
        A rolled-back *second* save must leave the answer at its
        pre-existing value, not a half-applied new one, and must not add
        an event for the attempted change.
        """
        save_baseline_answers(
            org_a,
            {answer_field_name("backups"): "yes", note_field_name("backups"): "Original."},
            question_keys=["backups"],
        )
        assert self._events(org_a).count() == 1

        with mock.patch(
            "security_baseline.services.record_event", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError):
                save_baseline_answers(
                    org_a,
                    {
                        answer_field_name("backups"): "no",
                        note_field_name("backups"): "Attempted change.",
                    },
                    question_keys=["backups"],
                )

        answer = BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert answer.answer == "yes"
        assert answer.note == "Original."
        assert self._events(org_a).count() == 1  # only the first, genuine event


@pytest.mark.django_db
class TestRecordStructuredBaselineAnswer:
    """
    security_baseline.services.record_structured_baseline_answer (M008B,
    docs/design/M008B-QUESTION-CATALOGUE.md) - the sole write path for a
    structured Stage 4 answer.
    """

    def test_creates_assessment_on_first_call_with_current_catalogue_version(self, org_a):
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

        recorded = record_structured_baseline_answer(
            org_a, "mfa_user_accounts", "MFA_USER_ALL_REQUIRED"
        )

        assert recorded.assessment.catalogue_version == CATALOGUE_VERSION
        assert BaselineAssessment.objects.filter(organisation=org_a).count() == 1

    def test_second_call_reuses_the_same_assessment_without_changing_its_catalogue_version(
        self, org_a
    ):
        record_structured_baseline_answer(org_a, "mfa_user_accounts", "MFA_USER_ALL_REQUIRED")
        assessment = BaselineAssessment.objects.get(organisation=org_a)
        # Simulate an assessment stamped under an older catalogue version -
        # this function must never silently overwrite it.
        assessment.catalogue_version = "some-older-version"
        assessment.save(update_fields=["catalogue_version"])

        recorded = record_structured_baseline_answer(
            org_a, "patching", "PATCHING_AUTOMATIC"
        )

        assert recorded.assessment.pk == assessment.pk
        assert BaselineAssessment.objects.filter(organisation=org_a).count() == 1
        recorded.assessment.refresh_from_db()
        assert recorded.assessment.catalogue_version == "some-older-version"

    def test_creates_the_correct_derived_baseline_answer(self, org_a):
        recorded = record_structured_baseline_answer(
            org_a, "backups", "BACKUPS_RESTORE_UNTESTED"
        )

        assert recorded.answer.question_key == "backups"
        assert recorded.answer.answer == ANSWER_PARTIAL
        answer = BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert answer.answer == ANSWER_PARTIAL

    def test_creates_exactly_one_answer_selection_detail_row(self, org_a):
        recorded = record_structured_baseline_answer(
            org_a, "backups", "BACKUPS_RESTORE_UNTESTED"
        )

        detail = AnswerSelectionDetail.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert detail.pk == recorded.selection_detail.pk
        assert detail.option_code == "BACKUPS_RESTORE_UNTESTED"
        assert detail.methodology_version == FOUNDATIONS_QUESTION_METHODOLOGY_VERSION

    def test_reanswering_the_same_control_updates_rather_than_duplicates(self, org_a):
        record_structured_baseline_answer(org_a, "backups", "BACKUPS_RESTORE_UNTESTED")
        first_answer_pk = BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        ).pk
        first_detail_pk = AnswerSelectionDetail.objects.get(
            assessment__organisation=org_a, question_key="backups"
        ).pk

        record_structured_baseline_answer(org_a, "backups", "BACKUPS_TESTED")

        answers = BaselineAnswer.objects.filter(
            assessment__organisation=org_a, question_key="backups"
        )
        details = AnswerSelectionDetail.objects.filter(
            assessment__organisation=org_a, question_key="backups"
        )
        assert answers.count() == 1
        assert details.count() == 1
        assert answers.get().pk == first_answer_pk
        assert answers.get().answer == ANSWER_YES
        assert details.get().pk == first_detail_pk
        assert details.get().option_code == "BACKUPS_TESTED"

    def test_two_option_codes_sharing_a_canonical_answer_are_still_distinguishable(self, org_a):
        """
        BACKUPS_RESTORE_UNTESTED and BACKUPS_COVERAGE_PARTIAL both derive
        the same canonical PARTIAL BaselineAnswer, but calling this
        function with each in turn must leave two provably different
        AnswerSelectionDetail.option_code values behind (sequentially, on
        the same control - re-answering the same question).
        """
        record_structured_baseline_answer(org_a, "backups", "BACKUPS_RESTORE_UNTESTED")
        first_detail = AnswerSelectionDetail.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert first_detail.option_code == "BACKUPS_RESTORE_UNTESTED"
        first_answer = BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert first_answer.answer == ANSWER_PARTIAL

        record_structured_baseline_answer(org_a, "backups", "BACKUPS_COVERAGE_PARTIAL")
        second_detail = AnswerSelectionDetail.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert second_detail.option_code == "BACKUPS_COVERAGE_PARTIAL"
        second_answer = BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert second_answer.answer == ANSWER_PARTIAL
        # Same canonical BaselineAnswer.answer both times...
        assert first_answer.answer == second_answer.answer
        # ...but two provably different option_code values were recorded.
        assert first_detail.option_code != second_detail.option_code

    def test_not_applicable_option_derives_not_applicable_answer(self, org_a):
        recorded = record_structured_baseline_answer(
            org_a, "remote_access_control", "REMOTE_ACCESS_NOT_APPLICABLE"
        )
        assert recorded.answer.answer == ANSWER_NOT_APPLICABLE

    def test_invalid_control_key_raises_and_writes_nothing(self, org_a):
        with pytest.raises(ValueError):
            record_structured_baseline_answer(org_a, "not_a_real_control", "ANYTHING")

        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()
        assert not BaselineAnswer.objects.filter(assessment__organisation=org_a).exists()
        assert not AnswerSelectionDetail.objects.filter(assessment__organisation=org_a).exists()

    def test_invalid_option_code_raises_and_writes_nothing(self, org_a):
        with pytest.raises(UnknownOptionCodeError):
            record_structured_baseline_answer(
                org_a, "mfa_user_accounts", "NOT_A_REAL_OPTION_CODE"
            )

        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()
        assert not BaselineAnswer.objects.filter(assessment__organisation=org_a).exists()
        assert not AnswerSelectionDetail.objects.filter(assessment__organisation=org_a).exists()

    def test_invalid_option_code_on_an_existing_assessment_leaves_prior_state_untouched(
        self, org_a
    ):
        record_structured_baseline_answer(org_a, "backups", "BACKUPS_TESTED")

        with pytest.raises(UnknownOptionCodeError):
            record_structured_baseline_answer(
                org_a, "patching", "NOT_A_REAL_OPTION_CODE"
            )

        # The earlier, valid "backups" answer is untouched; nothing for
        # "patching" was written.
        assert BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        ).answer == ANSWER_YES
        assert not BaselineAnswer.objects.filter(
            assessment__organisation=org_a, question_key="patching"
        ).exists()
        assert not AnswerSelectionDetail.objects.filter(
            assessment__organisation=org_a, question_key="patching"
        ).exists()

    def test_does_not_touch_an_existing_note_on_the_baseline_answer(self, org_a):
        """
        The structured Stage 4 journey has no free-text note concept -
        this function must never clear/overwrite an existing note left by
        the general baseline page's own save path.
        """
        save_baseline_answers(
            org_a,
            {answer_field_name("backups"): "no", note_field_name("backups"): "Left by the general page."},
            question_keys=["backups"],
        )

        record_structured_baseline_answer(org_a, "backups", "BACKUPS_TESTED")

        answer = BaselineAnswer.objects.get(
            assessment__organisation=org_a, question_key="backups"
        )
        assert answer.answer == ANSWER_YES
        assert answer.note == "Left by the general page."

