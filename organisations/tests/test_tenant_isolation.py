import uuid

import pytest
from django.urls import reverse

from organisations.models import Organisation, OrganisationProfile


@pytest.mark.django_db
class TestTenantIsolation:
    """
    Release-blocking (PID.md §5, §12). Uses two synthetic organisations and
    two users, each a member of exactly one, to prove:
      - a member can read/update their own organisation;
      - a member cannot read another organisation;
      - a member cannot write to another organisation;
      - manipulating the organisation id in the URL (or in POSTed form
        data) cannot cross the tenant boundary.
    """

    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_own_organisation_detail(self, client_a, org_a):
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert org_a.name.encode() in response.content

    def test_member_can_read_and_update_own_profile(self, client_a, org_a):
        response = client_a.post(
            reverse("organisations:profile", args=[org_a.id]),
            {
                "legal_trading_name": "Org A Synthetic Ltd",
                "description": "",
                "staff_count": "",
                "working_model": "hybrid",
                "endpoint_management": "unknown",
                "productivity_platform": "unknown",
                "primary_cloud_provider": "unknown",
                "develops_hosts_own_software": "unknown",
                "handles_personal_data": "yes",
                "handles_confidential_business_data": "unknown",
                "handles_payment_card_data": "unknown",
                "handles_special_category_data": "unknown",
                "receives_security_questionnaires": "unknown",
                "cyber_essentials_status": "unknown",
                "iso27001_status": "unknown",
                "commercial_security_driver": "",
            },
        )
        assert response.status_code == 302
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.working_model == "hybrid"
        assert profile.handles_personal_data == "yes"

    # --- cross-tenant read negative --------------------------------------
    def test_member_cannot_read_other_organisation_detail(self, client_b, org_a):
        response = client_b.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisation_profile(self, client_b, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a, legal_trading_name="Org A Synthetic Ltd"
        )
        response = client_b.get(reverse("organisations:profile", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_does_not_see_other_organisation_in_their_list(self, client_b, org_a, org_b):
        response = client_b.get(reverse("organisations:list"))
        assert response.status_code == 200
        assert org_a.name.encode() not in response.content
        assert org_b.name.encode() in response.content

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_create_profile_on_other_organisation(self, client_b, org_a):
        response = client_b.post(
            reverse("organisations:profile", args=[org_a.id]),
            {"legal_trading_name": "Hijacked by user_b"},
        )
        assert response.status_code == 404
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_member_cannot_update_other_organisations_existing_profile(self, client_b, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a, legal_trading_name="Original Org A Name"
        )
        response = client_b.post(
            reverse("organisations:profile", args=[org_a.id]),
            {"legal_trading_name": "Hijacked by user_b"},
        )
        assert response.status_code == 404
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.legal_trading_name == "Original Org A Name"

    # --- URL / form ID manipulation -----------------------------------------
    def test_nonexistent_organisation_id_in_url_is_404_not_error(self, client_a):
        random_id = uuid.uuid4()
        response = client_a.get(reverse("organisations:profile", args=[random_id]))
        assert response.status_code == 404

    def test_malformed_organisation_id_in_url_does_not_resolve(self, client_a):
        response = client_a.get("/organisations/not-a-uuid/profile/")
        assert response.status_code == 404

    def test_posted_organisation_field_cannot_redirect_save_to_another_org(
        self, client_a, org_a, org_b
    ):
        """
        The profile form does not expose an 'organisation' field at all
        (see OrganisationProfileForm.Meta.fields) - the tenant is bound
        entirely from the URL-scoped lookup. Prove that even if a client
        smuggles an 'organisation' value into the POST body, the saved
        profile still belongs to the URL's organisation, not org_b.
        """
        response = client_a.post(
            reverse("organisations:profile", args=[org_a.id]),
            {
                "legal_trading_name": "Org A Synthetic Ltd",
                "working_model": "unknown",
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
                "organisation": str(org_b.id),  # smuggled field; form doesn't declare it
            },
        )
        assert response.status_code == 302
        assert OrganisationProfile.objects.get().organisation_id == org_a.id
        assert not OrganisationProfile.objects.filter(organisation=org_b).exists()
