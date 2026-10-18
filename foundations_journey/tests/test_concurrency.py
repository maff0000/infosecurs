"""
Real concurrency proof (M010 data contract §4/§7: "two users editing same
checkpoint", "two submits of same answer") - genuine separate threads/DB
connections, the same `@pytest.mark.django_db(transaction=True)` +
`threading.Barrier` precedent `security_tasks/tests/test_concurrency.py`
and `risk_register/tests/test_narrow_viewport_regression.py` already
establish for this codebase.
"""
import threading
import uuid

import pytest
from django.db import close_old_connections

from foundations_journey import services
from foundations_journey.exceptions import ConcurrentCheckpointModificationError
from foundations_journey.models import JourneyCheckpoint
from organisations.models import Organisation, OrganisationMembership
from security_baseline.models import AnswerSelectionDetail, BaselineAssessment
from security_tasks.models import SecurityTask


@pytest.mark.django_db(transaction=True)
class TestConcurrentAnswerSubmission:
    def test_two_simultaneous_submits_of_the_same_answer_leave_exactly_one_row(self, django_user_model):
        organisation = Organisation.objects.create(name="Concurrency Answer Org")
        user = django_user_model.objects.create_user(username="concurrency_user", password="x" * 12)
        OrganisationMembership.objects.create(
            organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
        )
        start_barrier = threading.Barrier(2)
        errors = [None, None]

        def _submit(index):
            try:
                start_barrier.wait(timeout=10)
                services.submit_foundations_option(
                    organisation, user, question_key="backups", option_code="BACKUPS_TESTED"
                )
            except Exception as exc:  # noqa: BLE001
                errors[index] = exc
            finally:
                close_old_connections()

        threads = [threading.Thread(target=_submit, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [None, None], f"Unexpected errors: {errors}"
        assessment = BaselineAssessment.objects.get(organisation=organisation)
        assert assessment.answers.filter(question_key="backups").count() == 1
        assert AnswerSelectionDetail.objects.filter(assessment=assessment, question_key="backups").count() == 1


@pytest.mark.django_db(transaction=True)
class TestConcurrentCheckpointPause:
    def test_two_concurrent_pause_attempts_with_the_same_expected_version_one_wins(
        self, django_user_model
    ):
        organisation = Organisation.objects.create(name="Concurrency Checkpoint Org")
        user = django_user_model.objects.create_user(username="concurrency_checkpoint_user", password="x" * 12)
        OrganisationMembership.objects.create(
            organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
        )
        baseline_checkpoint = services.get_journey_checkpoint(organisation, user)
        # Force a real persisted row at a known version before racing.
        JourneyCheckpoint.objects.get_or_create(organisation=organisation, user=user)
        persisted = JourneyCheckpoint.objects.get(organisation=organisation, user=user)

        start_barrier = threading.Barrier(2)
        results = [None, None]
        errors = [None, None]

        def _pause(index):
            try:
                start_barrier.wait(timeout=10)
                results[index] = services.update_checkpoint(
                    organisation, user, expected_version=persisted.version, transition="pause"
                )
            except Exception as exc:  # noqa: BLE001
                errors[index] = exc
            finally:
                close_old_connections()

        threads = [threading.Thread(target=_pause, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        successes = [r for r in results if r is not None]
        failures = [e for e in errors if e is not None]
        assert len(successes) == 1, f"Exactly one pause must win, got {len(successes)} (errors={errors})"
        assert len(failures) == 1
        assert isinstance(failures[0], ConcurrentCheckpointModificationError)
