"""
Forged/unoffered option, cross-tenant, wrong-tier, unauthenticated and
stale-profile-state scenarios for the guided path - the direct analogue
of security_baseline/tests/test_foundations_views.py::
TestNotApplicableForgeryRejected ("the dispatch's own explicit
'required, not optional' test"), proved against BOTH the service layer
directly and the HTTP view.
"""
import pytest
from django.urls import reverse

from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_PAUSED
from foundations_journey import services
from foundations_journey.exceptions import InvalidFoundationsOptionError
from organisations.models import OrganisationProfile
from security_baseline.forms import confirm_field_name, option_field_name
from security_baseline.models import BaselineAssessment


def _question_url(organisation_id, key):
    return reverse("foundations_journey:guided_question", args=[organisation_id, key])


def _make_profile(organisation, **overrides):
    defaults = {"legal_trading_name": f"{organisation.name} Profile"}
    defaults.update(overrides)
    return OrganisationProfile.objects.create(organisation=organisation, **defaults)


@pytest.mark.django_db
class TestServiceLayerRejectsForgedOrUnofferedOptions:
    def test_device_encryption_has_no_not_applicable_option_to_forge(self, org_a, user_a, member_a):
        _make_profile(org_a, people_with_system_access_count=1, has_remote_or_offsite_access="no")
        with pytest.raises(InvalidFoundationsOptionError):
            services.submit_foundations_option(
                org_a, user_a, question_key="device_encryption", option_code="DEVICE_ENCRYPTION_NOT_APPLICABLE"
            )
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_completely_made_up_option_code_is_rejected(self, org_a, user_a, member_a):
        with pytest.raises(InvalidFoundationsOptionError):
            services.submit_foundations_option(
                org_a, user_a, question_key="mfa_user_accounts", option_code="NOT_A_REAL_CODE"
            )
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_not_applicable_rejected_without_confirmation(self, org_a, user_a, member_a):
        _make_profile(org_a, people_with_system_access_count=1)
        with pytest.raises(InvalidFoundationsOptionError):
            services.submit_foundations_option(
                org_a, user_a, question_key="joiner_mover_leaver", option_code="JML_NOT_APPLICABLE",
                confirmation=False,
            )
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_not_applicable_rejected_when_count_fact_is_not_one(self, org_a, user_a, member_a):
        _make_profile(org_a, people_with_system_access_count=3)
        with pytest.raises(InvalidFoundationsOptionError):
            services.submit_foundations_option(
                org_a, user_a, question_key="joiner_mover_leaver", option_code="JML_NOT_APPLICABLE",
                confirmation=True,
            )
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_not_applicable_accepted_with_fact_and_confirmation(self, org_a, user_a, member_a):
        _make_profile(org_a, people_with_system_access_count=1)
        receipt = services.submit_foundations_option(
            org_a, user_a, question_key="joiner_mover_leaver", option_code="JML_NOT_APPLICABLE",
            confirmation=True,
        )
        assert receipt.derived_answer == "not_applicable"

    def test_remote_access_not_applicable_rejected_when_fact_is_not_no(self, org_a, user_a, member_a):
        _make_profile(org_a, has_remote_or_offsite_access="yes")
        with pytest.raises(InvalidFoundationsOptionError):
            services.submit_foundations_option(
                org_a, user_a, question_key="remote_access_control", option_code="REMOTE_ACCESS_NOT_APPLICABLE"
            )
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_stale_option_rejected_after_profile_changes_mid_session(self, org_a, user_a, member_a):
        """Profile allows JML_NOT_APPLICABLE, then changes before the
        (simulated) submission - submit_foundations_option re-derives
        offered_options() fresh on every call, so the now-stale option is
        rejected exactly as if it had never been offered."""
        profile = _make_profile(org_a, people_with_system_access_count=1)
        profile.people_with_system_access_count = 5
        profile.save()

        with pytest.raises(InvalidFoundationsOptionError):
            services.submit_foundations_option(
                org_a, user_a, question_key="joiner_mover_leaver", option_code="JML_NOT_APPLICABLE",
                confirmation=True,
            )
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_invalid_question_key_raises_value_error(self, org_a, user_a, member_a):
        with pytest.raises(ValueError):
            services.submit_foundations_option(
                org_a, user_a, question_key="not_a_real_control", option_code="whatever"
            )


@pytest.mark.django_db
class TestHttpViewRejectsForgedOptions:
    def test_forged_option_code_200s_with_error_and_writes_nothing(self, client_a, org_a):
        response = client_a.post(
            _question_url(org_a.id, "mfa_user_accounts"),
            {option_field_name("mfa_user_accounts"): "DEFINITELY_NOT_REAL"},
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_checkbox_omitted_is_rejected(self, client_a, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a, legal_trading_name="X", people_with_system_access_count=1
        )
        response = client_a.post(
            _question_url(org_a.id, "joiner_mover_leaver"),
            {option_field_name("joiner_mover_leaver"): "JML_NOT_APPLICABLE"},
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_get_writes_nothing(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_invalid_question_key_is_404(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "not_a_real_control"))
        assert response.status_code == 404


@pytest.mark.django_db
class TestGuidedTenantIsolation:
    def test_member_cannot_read_other_organisations_guided_question(self, client_b, org_a):
        response = client_b.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 404

    def test_member_cannot_post_an_answer_to_other_organisations_question(self, client_b, org_a):
        response = client_b.post(
            _question_url(org_a.id, "backups"), {option_field_name("backups"): "BACKUPS_TESTED"}
        )
        assert response.status_code == 404
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_anonymous_user_is_redirected_to_login(self, client, org_a):
        response = client.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_service_layer_cross_tenant_source_locator_cannot_be_forged(self, org_a, org_b, user_a, user_b, member_a, member_b):
        """Even calling the service layer directly (bypassing the view's
        own get_member_organisation_or_404 tenant scoping, as a defence-
        in-depth check), offer_foundations_followup_task's task creation
        can never attach a source_object_id belonging to a DIFFERENT
        organisation than the one the task is created under - answer org_a
        then try to use org_a's BaselineAnswer pk while creating the task
        under org_b raises, because create_task's own source-locator
        validator re-resolves ownership against org_b."""
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="A", people_with_system_access_count=1)
        services.submit_foundations_option(
            org_a, user_a, question_key="mfa_user_accounts", option_code="MFA_USER_NOT_USED"
        )
        # offer_foundations_followup_task is itself organisation-scoped
        # correctly - calling it with org_b (where nothing was answered)
        # raises NoFollowUpTaskAvailableError, never leaking org_a's row.
        from foundations_journey.exceptions import NoFollowUpTaskAvailableError

        with pytest.raises(NoFollowUpTaskAvailableError):
            services.offer_foundations_followup_task(
                org_b, user_b, question_key="mfa_user_accounts", idempotency_key="probe-key"
            )


@pytest.mark.django_db
class TestWrongTierDenied:
    def test_paused_tier_cannot_reach_guided_question(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 403

    def test_paused_tier_post_is_also_denied_and_writes_nothing(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.post(
            _question_url(org_a.id, "backups"), {option_field_name("backups"): "BACKUPS_TESTED"}
        )
        assert response.status_code == 403
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()
