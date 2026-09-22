import pytest
from django.core.exceptions import ValidationError

from organisations.models import UNKNOWN, AuditEvent, Organisation, OrganisationProfile


@pytest.mark.django_db
class TestOrganisationProfileDomain:
    def test_create_profile_with_defaults_is_unknown_not_blank(self, org_a):
        profile = OrganisationProfile.objects.create(
            organisation=org_a, legal_trading_name="Org A Synthetic Ltd"
        )
        # Unknown/not-confirmed is a deliberate, named state - not an empty string.
        assert profile.working_model == UNKNOWN
        assert profile.handles_personal_data == UNKNOWN
        assert profile.cyber_essentials_status == UNKNOWN
        assert profile.staff_count is None  # genuinely "not confirmed", distinct from 0

    def test_update_profile_changes_persist(self, org_a):
        profile = OrganisationProfile.objects.create(
            organisation=org_a, legal_trading_name="Org A Synthetic Ltd"
        )
        profile.working_model = "hybrid"
        profile.handles_personal_data = "yes"
        profile.staff_count = 12
        profile.save()

        reloaded = OrganisationProfile.objects.get(pk=profile.pk)
        assert reloaded.working_model == "hybrid"
        assert reloaded.handles_personal_data == "yes"
        assert reloaded.staff_count == 12

    def test_negative_staff_count_is_rejected(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a, legal_trading_name="Org A Synthetic Ltd", staff_count=-1
        )
        with pytest.raises(ValidationError):
            profile.full_clean()

    def test_zero_staff_count_is_allowed_and_distinct_from_unknown(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a, legal_trading_name="Org A Synthetic Ltd", staff_count=0
        )
        profile.full_clean()  # should not raise
        profile.save()
        assert OrganisationProfile.objects.get(pk=profile.pk).staff_count == 0

    def test_enum_rejects_unsupported_value(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            working_model="on_the_moon",
        )
        with pytest.raises(ValidationError):
            profile.full_clean()

    def test_tri_state_field_rejects_unsupported_value(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            handles_personal_data="maybe",
        )
        with pytest.raises(ValidationError):
            profile.full_clean()

    def test_required_identity_cannot_be_blank(self, org_a):
        profile = OrganisationProfile(organisation=org_a, legal_trading_name="")
        with pytest.raises(ValidationError):
            profile.full_clean()


@pytest.mark.django_db
class TestAuditEvent:
    def test_audit_event_records_org_action_actor_timestamp(self, org_a, user_a):
        event = AuditEvent.objects.create(
            organisation=org_a, action=AuditEvent.ACTION_PROFILE_CREATED, actor=user_a
        )
        assert event.organisation_id == org_a.id
        assert event.action == AuditEvent.ACTION_PROFILE_CREATED
        assert event.actor_id == user_a.id
        assert event.timestamp is not None
