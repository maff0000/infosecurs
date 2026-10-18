import pytest
from django.urls import reverse

from foundations_journey import services
from foundations_journey.exceptions import ConcurrentCheckpointModificationError
from foundations_journey.models import CheckpointState, JourneyCheckpoint
from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.forms import option_field_name


@pytest.mark.django_db
class TestCheckpointReadNeverWrites:
    def test_first_read_creates_a_new_row_but_advances_nothing(self, org_a, user_a, member_a):
        checkpoint = services.get_journey_checkpoint(org_a, user_a)
        assert checkpoint.current_question_key == CATALOGUE_KEYS[0]
        assert checkpoint.checkpoint_state == CheckpointState.NEW
        # The reconciled values above are in-memory only - the persisted
        # row must still show version 1 (never bumped by a mere read).
        persisted = JourneyCheckpoint.objects.get(organisation=org_a, user=user_a)
        assert persisted.version == 1

    def test_repeated_reads_never_advance_version(self, org_a, user_a, member_a):
        services.get_journey_checkpoint(org_a, user_a)
        services.get_journey_checkpoint(org_a, user_a)
        services.get_journey_checkpoint(org_a, user_a)
        persisted = JourneyCheckpoint.objects.get(organisation=org_a, user=user_a)
        assert persisted.version == 1


@pytest.mark.django_db
class TestCheckpointAdvancesOnlyAfterASuccessfulAnswer:
    def test_checkpoint_advances_to_second_control_after_first_is_answered(
        self, org_a, user_a, member_a
    ):
        services.submit_foundations_option(
            org_a, user_a, question_key=CATALOGUE_KEYS[0], option_code="MFA_USER_ALL_REQUIRED"
        )
        checkpoint = services.get_journey_checkpoint(org_a, user_a)
        assert checkpoint.current_question_key == CATALOGUE_KEYS[1]
        assert checkpoint.checkpoint_state == CheckpointState.ACTIVE

        persisted = JourneyCheckpoint.objects.get(organisation=org_a, user=user_a)
        assert persisted.version == 2  # exactly one advancing write

    def test_checkpoint_reaches_journey_complete_after_all_twelve(self, org_a, user_a, member_a):
        happy_path = {
            "mfa_user_accounts": "MFA_USER_ALL_REQUIRED",
            "mfa_privileged_accounts": "MFA_ADMIN_ALL_REQUIRED",
            "endpoint_protection": "ENDPOINT_PROTECTION_ALL",
            "patching": "PATCHING_AUTOMATIC",
            "device_encryption": "DEVICE_ENCRYPTION_ALL",
            "backups": "BACKUPS_TESTED",
            "joiner_mover_leaver": "JML_DEFINED_FOLLOWED",
            "privileged_access_separation": "PRIV_SEP_DEDICATED",
            "security_awareness_training": "AWARENESS_REGULAR",
            "incident_reporting_route": "INCIDENT_ROUTE_CLEAR",
            "email_phishing_protection": "PHISHING_PROTECTION_ACTIVE_ALL",
            "remote_access_control": "REMOTE_ACCESS_GOVERNED",
        }
        for key in CATALOGUE_KEYS:
            services.submit_foundations_option(org_a, user_a, question_key=key, option_code=happy_path[key])

        checkpoint = services.get_journey_checkpoint(org_a, user_a)
        assert checkpoint.checkpoint_state == CheckpointState.JOURNEY_COMPLETE


@pytest.mark.django_db
class TestCheckpointIndependentPerUser:
    def test_second_colleague_shares_answers_but_has_own_checkpoint(
        self, org_a, user_a, member_a, user_c, member_c
    ):
        services.submit_foundations_option(
            org_a, user_a, question_key=CATALOGUE_KEYS[0], option_code="MFA_USER_ALL_REQUIRED"
        )
        checkpoint_a = services.get_journey_checkpoint(org_a, user_a)
        checkpoint_c = services.get_journey_checkpoint(org_a, user_c)

        # Both see the SAME real reviewed state (one control reviewed,
        # so both should be pointed at the second control next) ...
        assert checkpoint_a.current_question_key == checkpoint_c.current_question_key == CATALOGUE_KEYS[1]
        # ... but they are genuinely two separate rows.
        assert JourneyCheckpoint.objects.filter(organisation=org_a).count() == 2

    def test_a_removed_members_checkpoint_is_not_reachable_via_the_view(
        self, client_c, org_a, user_c, member_c
    ):
        """Membership removal revokes further access - same ordinary
        404 every other organisation-scoped route in this codebase
        already gives a non-member, proven directly: once member_c's
        row is deleted, the same client/session can no longer reach the
        guided question for that organisation at all."""
        member_c.delete()
        response = client_c.get(
            reverse("foundations_journey:guided_question", args=[org_a.id, CATALOGUE_KEYS[0]])
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestPauseResumeCheckpointTransition:
    def test_pause_then_resume_round_trip(self, org_a, user_a, member_a):
        checkpoint = services.get_journey_checkpoint(org_a, user_a)
        persisted = JourneyCheckpoint.objects.get(pk=checkpoint.pk) if checkpoint.pk else JourneyCheckpoint.objects.get(
            organisation=org_a, user=user_a
        )

        paused = services.update_checkpoint(
            org_a, user_a, expected_version=persisted.version, transition="pause"
        )
        assert paused.checkpoint_state == CheckpointState.PAUSED

        # A mere reconciling read must NOT silently resume a paused
        # journey (M010-UX-CUSTOMER-JOURNEYS.md §4).
        still_paused = services.get_journey_checkpoint(org_a, user_a)
        assert still_paused.checkpoint_state == CheckpointState.PAUSED

        resumed = services.update_checkpoint(
            org_a, user_a, expected_version=paused.version, transition="resume"
        )
        assert resumed.checkpoint_state in (CheckpointState.NEW, CheckpointState.ACTIVE, CheckpointState.JOURNEY_COMPLETE)

    def test_stale_expected_version_raises_concurrency_error(self, org_a, user_a, member_a):
        checkpoint = services.get_journey_checkpoint(org_a, user_a)
        persisted = JourneyCheckpoint.objects.get(organisation=org_a, user=user_a)

        services.update_checkpoint(
            org_a, user_a, expected_version=persisted.version, transition="pause"
        )
        with pytest.raises(ConcurrentCheckpointModificationError):
            # Replaying the SAME (now stale) expected_version a second
            # time must fail, never silently re-apply.
            services.update_checkpoint(
                org_a, user_a, expected_version=persisted.version, transition="pause"
            )

    def test_unsupported_transition_raises_value_error(self, org_a, user_a, member_a):
        with pytest.raises(ValueError):
            services.update_checkpoint(
                org_a, user_a, expected_version=1, transition="teleport"
            )
