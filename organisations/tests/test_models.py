import pytest
from django.core.exceptions import ValidationError

from organisations.models import (
    DRIVER_CUSTOMER_SUPPLIER,
    DRIVER_NOT_SURE,
    NO,
    SECTOR_NOT_SURE,
    SECTOR_TECHNOLOGY_SOFTWARE,
    UNKNOWN,
    YES,
    AuditEvent,
    Organisation,
    OrganisationProfile,
)


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
        # M008B new/corrected fields - same UNKNOWN/not-confirmed discipline.
        assert profile.sector == SECTOR_NOT_SURE
        assert profile.has_remote_or_offsite_access == UNKNOWN
        assert profile.people_with_system_access_count is None
        assert profile.commercial_security_driver == DRIVER_NOT_SURE

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
class TestM008BOrganisationProfileFieldChanges:
    """
    M008B (docs/design/M008B-STAGES-1-3-CATALOGUE.md): the three new
    additive OrganisationProfile fields (sector,
    has_remote_or_offsite_access, people_with_system_access_count) and
    the one corrected field (commercial_security_driver, TextField ->
    choice-constrained CharField).
    """

    # --- sector ----------------------------------------------------------

    def test_sector_accepts_a_real_choice(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            sector=SECTOR_TECHNOLOGY_SOFTWARE,
        )
        profile.full_clean()  # should not raise
        profile.save()
        assert OrganisationProfile.objects.get(pk=profile.pk).sector == SECTOR_TECHNOLOGY_SOFTWARE

    def test_sector_rejects_an_arbitrary_value(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            sector="a_sector_that_was_never_defined",
        )
        with pytest.raises(ValidationError):
            profile.full_clean()

    # --- has_remote_or_offsite_access ------------------------------------

    def test_has_remote_or_offsite_access_accepts_each_tri_state_value(self, org_a):
        for value in (UNKNOWN, YES, NO):
            profile = OrganisationProfile(
                organisation=org_a,
                legal_trading_name="Org A Synthetic Ltd",
                has_remote_or_offsite_access=value,
            )
            profile.full_clean()  # should not raise

    def test_has_remote_or_offsite_access_rejects_an_arbitrary_value(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            has_remote_or_offsite_access="sometimes_i_guess",
        )
        with pytest.raises(ValidationError):
            profile.full_clean()

    # --- people_with_system_access_count ---------------------------------

    def test_people_with_system_access_count_accepts_a_non_negative_integer(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            people_with_system_access_count=1,
        )
        profile.full_clean()  # should not raise
        profile.save()
        assert (
            OrganisationProfile.objects.get(pk=profile.pk).people_with_system_access_count == 1
        )

    def test_people_with_system_access_count_accepts_null(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            people_with_system_access_count=None,
        )
        profile.full_clean()  # should not raise

    def test_people_with_system_access_count_rejects_negative(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            people_with_system_access_count=-1,
        )
        with pytest.raises(ValidationError):
            profile.full_clean()

    # --- commercial_security_driver (corrected: TextField -> choices) ----

    def test_commercial_security_driver_accepts_a_real_choice(self, org_a):
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            commercial_security_driver=DRIVER_CUSTOMER_SUPPLIER,
        )
        profile.full_clean()  # should not raise
        profile.save()
        assert (
            OrganisationProfile.objects.get(pk=profile.pk).commercial_security_driver
            == DRIVER_CUSTOMER_SUPPLIER
        )

    def test_commercial_security_driver_rejects_previously_valid_free_text(self, org_a):
        """
        Before M008B this field was an open TextField - arbitrary free
        text was valid. After the correction, full_clean/choices
        validation must reject it: only the 5 DRIVER_* codes are valid.
        """
        profile = OrganisationProfile(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            commercial_security_driver="A customer asked nicely, so here we are.",
        )
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
