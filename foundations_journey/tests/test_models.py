import pytest
from django.db import IntegrityError, transaction

from foundations_journey.models import JOURNEY_CODE_FOUNDATIONS, CheckpointState, JourneyCheckpoint


@pytest.mark.django_db
class TestJourneyCheckpointModel:
    def test_defaults_on_create(self, org_a, user_a, member_a):
        checkpoint = JourneyCheckpoint.objects.create(organisation=org_a, user=user_a)
        assert checkpoint.journey_code == JOURNEY_CODE_FOUNDATIONS
        assert checkpoint.checkpoint_state == CheckpointState.NEW
        assert checkpoint.version == 1
        assert checkpoint.current_question_key is None
        assert checkpoint.pending_task is None

    def test_unique_per_organisation_user_journey(self, org_a, user_a, member_a):
        JourneyCheckpoint.objects.create(organisation=org_a, user=user_a, journey_code="foundations")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                JourneyCheckpoint.objects.create(
                    organisation=org_a, user=user_a, journey_code="foundations"
                )

    def test_second_user_in_same_organisation_gets_own_row(
        self, org_a, user_a, member_a, user_c, member_c
    ):
        checkpoint_a = JourneyCheckpoint.objects.create(organisation=org_a, user=user_a)
        checkpoint_c = JourneyCheckpoint.objects.create(organisation=org_a, user=user_c)
        assert checkpoint_a.pk != checkpoint_c.pk

    def test_different_journey_code_same_org_user_is_allowed(self, org_a, user_a, member_a):
        JourneyCheckpoint.objects.create(organisation=org_a, user=user_a, journey_code="foundations")
        other = JourneyCheckpoint.objects.create(organisation=org_a, user=user_a, journey_code="other_future_journey")
        assert other.pk is not None

    def test_str_does_not_raise(self, org_a, user_a, member_a):
        checkpoint = JourneyCheckpoint.objects.create(organisation=org_a, user=user_a)
        assert "foundations" in str(checkpoint)
