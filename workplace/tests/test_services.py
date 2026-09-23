"""
Mechanical tests for workplace.services (PID docs/pids/M004-POLICY-
FOUNDATION.md §26 "Workplace", ADR-0002 §5.2).
"""
import pytest

from activity.models import ActivityEvent
from organisations.models import UNKNOWN, OrganisationProfile

from workplace.models import Workplace
from workplace.services import (
    activate_workplace,
    compute_working_model,
    create_workplace,
    deactivate_workplace,
    sync_working_model,
    update_workplace,
)


@pytest.mark.django_db
class TestWorkingModelDerivation:
    def test_no_active_workplace_is_unknown(self, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        assert compute_working_model(org_a) == UNKNOWN

    def test_home_only_is_remote(self, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        create_workplace(
            organisation=org_a,
            name="Home / remote working",
            type=Workplace.TYPE_DISTRIBUTED_HOME,
            approx_people_count=4,
            actor=user_a,
        )
        assert compute_working_model(org_a) == "remote"
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "remote"

    def test_office_only_is_office(self, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        create_workplace(
            organisation=org_a,
            name="Woking shared office",
            type=Workplace.TYPE_SHARED_OFFICE,
            location_label="Woking, Surrey",
            approx_people_count=6,
            actor=user_a,
        )
        assert compute_working_model(org_a) == "office"
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "office"

    def test_home_and_non_home_mix_is_hybrid(self, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        create_workplace(
            organisation=org_a,
            name="London Head Office",
            type=Workplace.TYPE_DEDICATED_OFFICE,
            location_label="London",
            approx_people_count=15,
            actor=user_a,
        )
        create_workplace(
            organisation=org_a,
            name="Home / remote working",
            type=Workplace.TYPE_DISTRIBUTED_HOME,
            approx_people_count=5,
            actor=user_a,
        )
        assert compute_working_model(org_a) == "hybrid"
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "hybrid"

    def test_multiple_locations_supported(self, org_a, user_a):
        """PID §9.1's twenty-person example: two active Workplace rows for
        one organisation."""
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        create_workplace(
            organisation=org_a, name="London Head Office", type=Workplace.TYPE_DEDICATED_OFFICE,
            location_label="London", approx_people_count=15, actor=user_a,
        )
        create_workplace(
            organisation=org_a, name="Home / remote working", type=Workplace.TYPE_DISTRIBUTED_HOME,
            approx_people_count=5, actor=user_a,
        )
        assert Workplace.objects.filter(organisation=org_a, is_active=True).count() == 2

    def test_deactivating_the_only_active_workplace_drops_back_to_unknown(self, org_a, user_a):
        """
        Easy edge case to get wrong: deactivating the sole active
        Workplace must not leave working_model stale at its previous
        derived value.
        """
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        workplace = create_workplace(
            organisation=org_a,
            name="Home / remote working",
            type=Workplace.TYPE_DISTRIBUTED_HOME,
            approx_people_count=4,
            actor=user_a,
        )
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "remote"

        deactivate_workplace(workplace, actor=user_a)

        profile.refresh_from_db()
        assert profile.working_model == UNKNOWN

    def test_only_active_rows_count_towards_derivation(self, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        office = create_workplace(
            organisation=org_a, name="Office", type=Workplace.TYPE_DEDICATED_OFFICE, actor=user_a,
        )
        create_workplace(
            organisation=org_a, name="Old home setup", type=Workplace.TYPE_DISTRIBUTED_HOME,
            is_active=False, actor=user_a,
        )
        # The inactive home row must not turn this into "hybrid".
        assert compute_working_model(org_a) == "office"

        deactivate_workplace(office, actor=user_a)
        assert compute_working_model(org_a) == UNKNOWN

    def test_reactivating_a_workplace_resyncs_the_summary(self, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        workplace = create_workplace(
            organisation=org_a, name="Office", type=Workplace.TYPE_DEDICATED_OFFICE, actor=user_a,
        )
        deactivate_workplace(workplace, actor=user_a)
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == UNKNOWN

        activate_workplace(workplace, actor=user_a)
        profile.refresh_from_db()
        assert profile.working_model == "office"

    def test_update_workplace_type_resyncs_the_summary(self, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        workplace = create_workplace(
            organisation=org_a, name="Setup", type=Workplace.TYPE_DISTRIBUTED_HOME, actor=user_a,
        )
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "remote"

        update_workplace(workplace, actor=user_a, type=Workplace.TYPE_DEDICATED_OFFICE)
        profile.refresh_from_db()
        assert profile.working_model == "office"


@pytest.mark.django_db
class TestSyncWorkingModelMissingProfile:
    def test_sync_is_a_silent_no_op_when_no_profile_exists_yet(self, org_a, user_a):
        """
        M001's OrganisationProfile is optional/created separately. A
        Workplace write for an organisation with no profile yet must not
        error, and must not fabricate a profile row.
        """
        create_workplace(
            organisation=org_a,
            name="Home / remote working",
            type=Workplace.TYPE_DISTRIBUTED_HOME,
            actor=user_a,
        )
        assert sync_working_model(org_a) is None
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_profile_created_later_picks_up_correct_summary_once_synced(self, org_a, user_a):
        create_workplace(
            organisation=org_a,
            name="Home / remote working",
            type=Workplace.TYPE_DISTRIBUTED_HOME,
            actor=user_a,
        )
        profile = OrganisationProfile.objects.create(
            organisation=org_a, legal_trading_name=org_a.name
        )
        assert profile.working_model == UNKNOWN  # model default, not yet synced

        sync_working_model(org_a)
        profile.refresh_from_db()
        assert profile.working_model == "remote"


@pytest.mark.django_db
class TestWorkplaceActivityEvents:
    """
    M004-1d-closeout, PID §22: `workplace_created`/`workplace_updated`
    ActivityEvents emitted by create_workplace/update_workplace (and, via
    update_workplace, deactivate_workplace/activate_workplace).
    """

    def test_create_workplace_emits_exactly_one_workplace_created_event(self, org_a, user_a):
        workplace = create_workplace(
            organisation=org_a,
            name="Woking shared office",
            type=Workplace.TYPE_SHARED_OFFICE,
            location_label="Woking, Surrey",
            approx_people_count=6,
            actor=user_a,
        )

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_WORKPLACE_CREATED
        )
        assert events.count() == 1
        event = events.get()
        assert event.actor_id == user_a.id
        assert event.related_object_type == "workplace"
        assert event.related_object_id == str(workplace.id)
        assert event.metadata == {"name": "Woking shared office", "type": Workplace.TYPE_SHARED_OFFICE}

    def test_update_workplace_emits_workplace_updated_event_with_actor(self, org_a, user_a):
        workplace = create_workplace(
            organisation=org_a, name="Setup", type=Workplace.TYPE_DISTRIBUTED_HOME, actor=user_a,
        )
        ActivityEvent.objects.filter(organisation=org_a).delete()  # isolate the update

        update_workplace(workplace, actor=user_a, type=Workplace.TYPE_DEDICATED_OFFICE)

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_WORKPLACE_UPDATED
        )
        assert events.count() == 1
        event = events.get()
        assert event.actor_id == user_a.id
        assert event.related_object_type == "workplace"
        assert event.related_object_id == str(workplace.id)
        assert event.metadata["changed_fields"] == ["type"]
        assert event.metadata["is_active"] is True

    def test_deactivate_workplace_emits_workplace_updated_event_with_actor(self, org_a, user_a):
        workplace = create_workplace(
            organisation=org_a, name="Office", type=Workplace.TYPE_DEDICATED_OFFICE, actor=user_a,
        )
        ActivityEvent.objects.filter(organisation=org_a).delete()

        deactivate_workplace(workplace, actor=user_a)

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_WORKPLACE_UPDATED
        )
        assert events.count() == 1
        event = events.get()
        assert event.actor_id == user_a.id
        assert event.metadata["changed_fields"] == ["is_active"]
        assert event.metadata["is_active"] is False

    def test_activate_workplace_emits_workplace_updated_event_with_actor(self, org_a, user_a):
        workplace = create_workplace(
            organisation=org_a, name="Office", type=Workplace.TYPE_DEDICATED_OFFICE, actor=user_a,
        )
        deactivate_workplace(workplace, actor=user_a)
        ActivityEvent.objects.filter(organisation=org_a).delete()

        activate_workplace(workplace, actor=user_a)

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_WORKPLACE_UPDATED
        )
        assert events.count() == 1
        event = events.get()
        assert event.actor_id == user_a.id
        assert event.metadata["changed_fields"] == ["is_active"]
        assert event.metadata["is_active"] is True

    def test_update_workplace_with_no_actual_change_emits_no_event(self, org_a, user_a):
        workplace = create_workplace(
            organisation=org_a, name="Office", type=Workplace.TYPE_DEDICATED_OFFICE, actor=user_a,
        )
        ActivityEvent.objects.filter(organisation=org_a).delete()

        update_workplace(workplace, actor=user_a, type=Workplace.TYPE_DEDICATED_OFFICE)

        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_WORKPLACE_UPDATED
        ).exists()
