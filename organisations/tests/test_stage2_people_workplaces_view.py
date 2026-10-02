"""
M008C/M008B-WI2a tests for Stage 2 - Your People & Workplaces
(organisations.views.organisation_stage2_people_workplaces, docs/design/
M008B-STAGES-1-3-CATALOGUE.md Stage 2).
"""
from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from governance import services as governance_services
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from organisations.models import NO, UNKNOWN, YES, AuditEvent, OrganisationProfile
from workplace import services as workplace_services
from workplace.models import Workplace

pytestmark = pytest.mark.django_db


def _stage2_url(org):
    return reverse("organisations:stage2_people_workplaces", args=[org.id])


def _main_content(response):
    """
    Isolates this page's own `{% block content %}` from the shared
    `application_shell.html` sidebar - the sidebar's own nav already links
    to `workplace:list`/`governance:roles` for every entitled organisation
    regardless of this page's own conditional link-out logic, so an
    assertion about THIS page's own choice of link must not accidentally
    pass (or fail) because of the sidebar's unrelated, always-present
    link. Mirrors organisations/tests/test_foundations_view.py's own
    `main_start = content.index('id="main-content"')` pattern.
    """
    content = response.content.decode()
    return content[content.index('id="main-content"') :]


VALID_PAYLOAD = {
    "people_with_system_access_count": "5",
    "has_remote_or_offsite_access": YES,
}


class TestStage2Get:
    def test_links_to_workplace_onboarding_when_no_workplace_exists(self, client_a, org_a):
        response = client_a.get(_stage2_url(org_a))

        assert response.status_code == 200
        content = _main_content(response)
        onboarding_url = reverse("workplace:onboarding_start", args=[org_a.id])
        list_url = reverse("workplace:list", args=[org_a.id])
        # `workplace:list`'s own URL ("/.../workplace/") is a literal
        # string PREFIX of `workplace:onboarding_start`'s URL
        # ("/.../workplace/onboarding/") - a bare substring check would
        # false-pass "list not in content" as soon as the onboarding link
        # is merely present. Asserting the exact `href="..."` token (the
        # closing quote defeats the prefix overlap) proves this page
        # links to onboarding and NOT, separately, to the plain list.
        assert f'href="{onboarding_url}"' in content
        assert f'href="{list_url}"' not in content

    def test_links_to_workplace_list_once_an_active_workplace_exists(
        self, client_a, org_a, user_a
    ):
        workplace_services.create_workplace(
            organisation=org_a,
            name="Head office",
            type=Workplace.TYPE_DEDICATED_OFFICE,
            location_label="London",
            approx_people_count=10,
            is_primary=True,
            actor=user_a,
        )

        response = client_a.get(_stage2_url(org_a))

        assert response.status_code == 200
        content = _main_content(response)
        list_url = reverse("workplace:list", args=[org_a.id])
        assert f'href="{list_url}"' in content

    def test_links_to_governance_roles_and_shows_the_assigned_count(self, client_a, org_a, user_a):
        person = OrganisationPerson.objects.create(organisation=org_a, full_name="Jo Example")
        governance_services.assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
            person=person,
            assigned_by=user_a,
        )

        response = client_a.get(_stage2_url(org_a))

        assert response.status_code == 200
        content = _main_content(response)
        assert reverse("governance:roles", args=[org_a.id]) in content
        assert "1 of 3" in content

    def test_prefills_from_an_existing_profile(self, client_a, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Existing Ltd",
            people_with_system_access_count=3,
            has_remote_or_offsite_access=NO,
        )

        response = client_a.get(_stage2_url(org_a))

        form = response.context["form"]
        assert form.instance.people_with_system_access_count == 3
        assert form.instance.has_remote_or_offsite_access == NO


class TestStage2Post:
    def test_valid_submission_saves_and_redirects_to_stage3(self, client_a, org_a, user_a):
        response = client_a.post(_stage2_url(org_a), data=VALID_PAYLOAD)

        assert response.status_code == 302
        assert response.url == reverse("organisations:stage3_technology_data", args=[org_a.id])

        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.people_with_system_access_count == 5
        assert profile.has_remote_or_offsite_access == YES

        audit_event = AuditEvent.objects.get(organisation=org_a)
        assert audit_event.action == AuditEvent.ACTION_PROFILE_CREATED
        assert audit_event.actor == user_a

    def test_an_out_of_choice_offsite_access_value_is_rejected_server_side(self, client_a, org_a):
        payload = dict(VALID_PAYLOAD, has_remote_or_offsite_access="not_a_real_choice")

        response = client_a.post(_stage2_url(org_a), data=payload)

        assert response.status_code == 200
        assert "has_remote_or_offsite_access" in response.context["form"].errors
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_not_sure_remains_a_valid_choice_for_offsite_access(self, client_a, org_a):
        payload = dict(VALID_PAYLOAD, has_remote_or_offsite_access=UNKNOWN)

        response = client_a.post(_stage2_url(org_a), data=payload)

        assert response.status_code == 302
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.has_remote_or_offsite_access == UNKNOWN


class TestStage2AccessControl:
    def test_a_non_member_gets_an_ordinary_404(self, client_b, org_a):
        response = client_b.get(_stage2_url(org_a))
        assert response.status_code == 404

    def test_an_anonymous_request_is_redirected_to_login(self, org_a):
        anonymous_client = Client()
        response = anonymous_client.get(_stage2_url(org_a))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
