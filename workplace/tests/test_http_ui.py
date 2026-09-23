import pytest
from django.urls import reverse

from organisations.models import OrganisationProfile

from workplace.models import Workplace


@pytest.mark.django_db
class TestOnboardingStartView:
    def test_renders(self, client_a, org_a):
        response = client_a.get(reverse("workplace:onboarding_start", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Where do people normally work" in content
        assert 'value="all_remote"' in content
        assert 'value="several_locations"' in content

    def test_requires_login(self, client, org_a):
        response = client.get(reverse("workplace:onboarding_start", args=[org_a.id]))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_all_remote_choice_redirects_to_headcount_step(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_start", args=[org_a.id]), {"pattern": "all_remote"}
        )
        assert response.status_code == 302
        assert response.url == reverse("workplace:onboarding_all_remote", args=[org_a.id])

    def test_several_locations_choice_redirects_straight_to_list(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_start", args=[org_a.id]),
            {"pattern": "several_locations"},
        )
        assert response.status_code == 302
        assert response.url == reverse("workplace:list", args=[org_a.id])


@pytest.mark.django_db
class TestAllRemoteOnboarding:
    def test_creates_one_distributed_home_workplace(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_all_remote", args=[org_a.id]),
            {"approx_people_count": "4"},
        )
        assert response.status_code == 302
        workplace = Workplace.objects.get(organisation=org_a)
        assert workplace.type == Workplace.TYPE_DISTRIBUTED_HOME
        assert workplace.name == "Home / remote working"
        assert workplace.location_label == ""
        assert workplace.approx_people_count == 4
        assert workplace.is_primary is True

    def test_headcount_is_optional(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_all_remote", args=[org_a.id]), {}
        )
        assert response.status_code == 302
        workplace = Workplace.objects.get(organisation=org_a)
        assert workplace.approx_people_count is None


@pytest.mark.django_db
class TestOneOfficeOnboarding:
    def test_creates_one_dedicated_office_workplace(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_one_office", args=[org_a.id]),
            {"name": "Woking Office", "location_label": "Woking, Surrey", "approx_people_count": "6"},
        )
        assert response.status_code == 302
        workplace = Workplace.objects.get(organisation=org_a)
        assert workplace.type == Workplace.TYPE_DEDICATED_OFFICE
        assert workplace.name == "Woking Office"
        assert workplace.location_label == "Woking, Surrey"
        assert workplace.approx_people_count == 6

    def test_blank_name_is_rejected(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_one_office", args=[org_a.id]),
            {"name": "", "location_label": "", "approx_people_count": ""},
        )
        assert response.status_code == 200
        assert not Workplace.objects.filter(organisation=org_a).exists()


@pytest.mark.django_db
class TestSharedCoworkingOnboarding:
    def test_creates_shared_office_by_default_subtype(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_shared_coworking", args=[org_a.id]),
            {
                "subtype": Workplace.TYPE_SHARED_OFFICE,
                "name": "Woking shared office",
                "location_label": "Woking, Surrey",
                "approx_people_count": "6",
            },
        )
        assert response.status_code == 302
        workplace = Workplace.objects.get(organisation=org_a)
        assert workplace.type == Workplace.TYPE_SHARED_OFFICE

    def test_can_choose_coworking_space_subtype(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_shared_coworking", args=[org_a.id]),
            {
                "subtype": Workplace.TYPE_COWORKING_SPACE,
                "name": "WeWork Manchester",
                "location_label": "Manchester",
                "approx_people_count": "3",
            },
        )
        assert response.status_code == 302
        workplace = Workplace.objects.get(organisation=org_a)
        assert workplace.type == Workplace.TYPE_COWORKING_SPACE


@pytest.mark.django_db
class TestOfficeAndHomeOnboarding:
    def test_creates_two_workplace_rows(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:onboarding_office_and_home", args=[org_a.id]),
            {
                "office_name": "London Head Office",
                "office_location_label": "London",
                "office_approx_people_count": "15",
                "home_approx_people_count": "5",
            },
        )
        assert response.status_code == 302
        workplaces = Workplace.objects.filter(organisation=org_a).order_by("type")
        assert workplaces.count() == 2

        office = workplaces.get(type=Workplace.TYPE_DEDICATED_OFFICE)
        assert office.name == "London Head Office"
        assert office.location_label == "London"
        assert office.approx_people_count == 15

        home = workplaces.get(type=Workplace.TYPE_DISTRIBUTED_HOME)
        assert home.name == "Home / remote working"
        assert home.approx_people_count == 5

    def test_derived_working_model_is_hybrid_after_office_and_home(self, client_a, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        client_a.post(
            reverse("workplace:onboarding_office_and_home", args=[org_a.id]),
            {
                "office_name": "London Head Office",
                "office_location_label": "London",
                "office_approx_people_count": "15",
                "home_approx_people_count": "5",
            },
        )
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "hybrid"


@pytest.mark.django_db
class TestWorkplaceListCreateEditViews:
    def test_list_renders_without_any_workplace(self, client_a, org_a):
        response = client_a.get(reverse("workplace:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Workplace" in response.content

    def test_create_via_general_form(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:create", args=[org_a.id]),
            {
                "name": "Manchester office",
                "type": Workplace.TYPE_DEDICATED_OFFICE,
                "location_label": "Manchester",
                "approx_people_count": "8",
            },
        )
        assert response.status_code == 302
        workplace = Workplace.objects.get(organisation=org_a)
        assert workplace.name == "Manchester office"

    def test_list_shows_created_workplace(self, client_a, org_a):
        Workplace.objects.create(
            organisation=org_a, name="Manchester office", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_a.get(reverse("workplace:list", args=[org_a.id]))
        assert b"Manchester office" in response.content

    def test_edit_updates_fields(self, client_a, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a, name="Old name", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_a.post(
            reverse("workplace:edit", args=[org_a.id, workplace.id]),
            {
                "name": "New name",
                "type": Workplace.TYPE_DEDICATED_OFFICE,
                "location_label": "",
                "approx_people_count": "",
            },
        )
        assert response.status_code == 302
        workplace.refresh_from_db()
        assert workplace.name == "New name"

    def test_deactivate_then_reactivate(self, client_a, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a, name="Office", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_a.post(reverse("workplace:deactivate", args=[org_a.id, workplace.id]))
        assert response.status_code == 302
        workplace.refresh_from_db()
        assert workplace.is_active is False

        response = client_a.post(reverse("workplace:activate", args=[org_a.id, workplace.id]))
        assert response.status_code == 302
        workplace.refresh_from_db()
        assert workplace.is_active is True

    def test_deactivate_rejects_get(self, client_a, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a, name="Office", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_a.get(reverse("workplace:deactivate", args=[org_a.id, workplace.id]))
        assert response.status_code == 405
        workplace.refresh_from_db()
        assert workplace.is_active is True


@pytest.mark.django_db
class TestWorkingModelCannotBeIndependentlyEdited:
    """
    PID §26 "Workplace" mechanical test: "the normal product UI cannot
    independently contradict the derived working model" - an HTTP-level
    test posting a working_model value through the organisations profile
    -save endpoint must have no effect on the stored value; only the
    workplace sync path (workplace.services.sync_working_model) can
    change it.
    """

    def test_posting_working_model_through_profile_form_has_no_effect(self, client_a, org_a):
        valid_post = {
            "legal_trading_name": org_a.name,
            "description": "",
            "staff_count": "",
            "working_model": "office",  # attempted independent edit
            "endpoint_management": "unknown",
            "productivity_platform": "unknown",
            "primary_cloud_provider": "unknown",
            "develops_hosts_own_software": "unknown",
            "handles_personal_data": "unknown",
            "handles_confidential_business_data": "unknown",
            "handles_payment_card_data": "unknown",
            "handles_special_category_data": "unknown",
            "receives_security_questionnaires": "unknown",
            "cyber_essentials_status": "unknown",
            "iso27001_status": "unknown",
            "commercial_security_driver": "",
        }
        response = client_a.post(reverse("organisations:profile", args=[org_a.id]), valid_post)
        assert response.status_code == 302  # the rest of the profile still saves fine

        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "unknown"  # untouched by the submitted "office"

    def test_only_the_workplace_sync_path_changes_it(self, client_a, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name=org_a.name)
        client_a.post(
            reverse("workplace:onboarding_all_remote", args=[org_a.id]),
            {"approx_people_count": "4"},
        )
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "remote"

        # Attempting to independently override it back through the profile
        # form must not succeed.
        client_a.post(
            reverse("organisations:profile", args=[org_a.id]),
            {
                "legal_trading_name": org_a.name,
                "working_model": "office",
                "endpoint_management": "unknown",
                "productivity_platform": "unknown",
                "primary_cloud_provider": "unknown",
                "develops_hosts_own_software": "unknown",
                "handles_personal_data": "unknown",
                "handles_confidential_business_data": "unknown",
                "handles_payment_card_data": "unknown",
                "handles_special_category_data": "unknown",
                "receives_security_questionnaires": "unknown",
                "cyber_essentials_status": "unknown",
                "iso27001_status": "unknown",
            },
        )
        profile.refresh_from_db()
        assert profile.working_model == "remote"

    def test_working_model_field_still_renders_on_profile_page(self, client_a, org_a):
        """
        The field itself is not removed from the page (it still shows the
        derived value) - only independent submission is defeated. See
        organisations.forms.OrganisationProfileForm's docstring.
        """
        response = client_a.get(reverse("organisations:profile", args=[org_a.id]))
        assert response.status_code == 200
        assert 'name="working_model"' in response.content.decode()
