import uuid

import pytest
from django.urls import reverse

from workplace.models import Workplace


@pytest.mark.django_db
class TestWorkplaceTenantIsolation:
    """
    Release-blocking (PID §23, §26 "Workplace" -> tenant isolation). Two
    synthetic organisations, two users each a member of exactly one,
    proving organisation A cannot view, edit, deactivate or reactivate
    organisation B's workplaces, and that org B cannot create a workplace
    under org A's URL prefix - both at the HTTP level and, separately, by
    calling the service layer directly with mismatched organisation
    scope.
    """

    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_own_organisations_workplace_list(self, client_a, org_a):
        Workplace.objects.create(
            organisation=org_a, name="Org A workplace", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_a.get(reverse("workplace:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Org A workplace" in response.content

    # --- cross-tenant read negative ---------------------------------------
    def test_member_cannot_read_other_organisations_workplace_list(self, client_b, org_a):
        Workplace.objects.create(
            organisation=org_a, name="Org A secret workplace", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_b.get(reverse("workplace:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_workplace_edit_form(self, client_b, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a, name="Org A workplace", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_b.get(reverse("workplace:edit", args=[org_a.id, workplace.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_onboarding_pages(self, client_b, org_a):
        for url_name in (
            "workplace:onboarding_start",
            "workplace:onboarding_all_remote",
            "workplace:onboarding_one_office",
            "workplace:onboarding_shared_coworking",
            "workplace:onboarding_office_and_home",
        ):
            response = client_b.get(reverse(url_name, args=[org_a.id]))
            assert response.status_code == 404, url_name

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_create_workplace_on_other_organisation(self, client_b, org_a):
        response = client_b.post(
            reverse("workplace:create", args=[org_a.id]),
            {"name": "Hijacked workplace", "type": Workplace.TYPE_DEDICATED_OFFICE},
        )
        assert response.status_code == 404
        assert not Workplace.objects.filter(organisation=org_a).exists()

    def test_member_cannot_run_onboarding_for_other_organisation(self, client_b, org_a):
        response = client_b.post(
            reverse("workplace:onboarding_all_remote", args=[org_a.id]),
            {"approx_people_count": "4"},
        )
        assert response.status_code == 404
        assert not Workplace.objects.filter(organisation=org_a).exists()

    def test_member_cannot_edit_other_organisations_workplace(self, client_b, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a,
            name="Original name",
            type=Workplace.TYPE_DEDICATED_OFFICE,
        )
        response = client_b.post(
            reverse("workplace:edit", args=[org_a.id, workplace.id]),
            {"name": "Hijacked by user_b", "type": Workplace.TYPE_DEDICATED_OFFICE},
        )
        assert response.status_code == 404
        workplace.refresh_from_db()
        assert workplace.name == "Original name"

    def test_member_cannot_deactivate_other_organisations_workplace(self, client_b, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a, name="Org A workplace", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_b.post(reverse("workplace:deactivate", args=[org_a.id, workplace.id]))
        assert response.status_code == 404
        workplace.refresh_from_db()
        assert workplace.is_active is True

    def test_member_cannot_reactivate_other_organisations_workplace(self, client_b, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a,
            name="Org A workplace",
            type=Workplace.TYPE_DEDICATED_OFFICE,
            is_active=False,
        )
        response = client_b.post(reverse("workplace:activate", args=[org_a.id, workplace.id]))
        assert response.status_code == 404
        workplace.refresh_from_db()
        assert workplace.is_active is False

    # --- URL / cross-organisation workplace-id manipulation -----------------
    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("workplace:list", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_workplace_id_from_a_different_organisation_is_404_even_for_a_member(
        self, client_a, org_a, org_b
    ):
        """
        user_a is a member of org_a. A workplace that belongs to org_b
        must not be reachable through org_a's URL prefix, even though
        user_a is authenticated and a genuine member of *some*
        organisation.
        """
        other_org_workplace = Workplace.objects.create(
            organisation=org_b, name="Org B workplace", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_a.get(reverse("workplace:edit", args=[org_a.id, other_org_workplace.id]))
        assert response.status_code == 404

    def test_member_does_not_see_other_organisations_workplaces_mixed_into_their_own_list(
        self, client_a, org_a, org_b
    ):
        Workplace.objects.create(
            organisation=org_a, name="Org A own workplace", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        Workplace.objects.create(
            organisation=org_b, name="Org B workplace", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        response = client_a.get(reverse("workplace:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Org A own workplace" in content
        assert "Org B workplace" not in content


@pytest.mark.django_db
class TestSyncWorkingModelTenantIsolation:
    """
    Service-layer negative test: computing/syncing organisation A's
    derived working model must never be influenced by organisation B's
    Workplace rows, even though both exist in the same table.
    """

    def test_compute_working_model_is_scoped_to_the_given_organisation(
        self, org_a, org_b, user_b
    ):
        from organisations.models import UNKNOWN

        from workplace.services import compute_working_model, create_workplace

        create_workplace(
            organisation=org_b,
            name="Org B office",
            type=Workplace.TYPE_DEDICATED_OFFICE,
            actor=user_b,
        )
        # org_a has no workplaces of its own - org_b's office row must not
        # leak into org_a's derivation.
        assert compute_working_model(org_a) == UNKNOWN
