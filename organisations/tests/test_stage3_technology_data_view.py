"""
M008C/M008B-WI2a tests for Stage 3 - Your Technology & Data
(organisations.views.organisation_stage3_technology_data, docs/design/
M008B-STAGES-1-3-CATALOGUE.md Stage 3).
"""
from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from key_assets.models import CATEGORY_ENDPOINT, KeyAsset
from organisations.models import NO, UNKNOWN, YES, AuditEvent, OrganisationProfile

pytestmark = pytest.mark.django_db


def _stage3_url(org):
    return reverse("organisations:stage3_technology_data", args=[org.id])


def _main_content(response):
    """See test_stage2_people_workplaces_view.py's identically-named
    helper's docstring: the shared shell sidebar already links to
    `key_assets:list` for every entitled organisation regardless of this
    page's own content, so an assertion about this page's OWN key-assets
    card must be scoped past the sidebar."""
    content = response.content.decode()
    return content[content.index('id="main-content"') :]


VALID_PAYLOAD = {
    "productivity_platform": "microsoft_365",
    "primary_cloud_provider": "aws",
    "endpoint_management": "company_managed",
    "develops_hosts_own_software": YES,
    "handles_personal_data": YES,
    "handles_confidential_business_data": NO,
    "handles_payment_card_data": NO,
    "handles_special_category_data": UNKNOWN,
    "cyber_essentials_status": "in_progress",
    "iso27001_status": "not_certified",
}


class TestStage3Get:
    def test_renders_with_defaults_when_no_profile_exists_yet(self, client_a, org_a):
        response = client_a.get(_stage3_url(org_a))
        assert response.status_code == 200
        assert response.context["form"].instance.pk is None
        assert "Which productivity/email platform do you mainly use?" in response.content.decode()

    def test_prefills_from_an_existing_profile(self, client_a, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Existing Ltd",
            productivity_platform="google_workspace",
            handles_payment_card_data=YES,
        )

        response = client_a.get(_stage3_url(org_a))

        form = response.context["form"]
        assert form.instance.productivity_platform == "google_workspace"
        assert form.instance.handles_payment_card_data == YES

    def test_links_to_key_assets_and_shows_the_confirmed_count(self, client_a, org_a):
        KeyAsset.objects.create(
            organisation=org_a,
            name="Finance laptop fleet",
            category=CATEGORY_ENDPOINT,
            criticality="high",
            status=KeyAsset.STATUS_CONFIRMED,
        )

        response = client_a.get(_stage3_url(org_a))

        assert response.status_code == 200
        content = _main_content(response)
        assert reverse("key_assets:list", args=[org_a.id]) in content
        assert "1 confirmed so far" in content


class TestStage3Post:
    def test_valid_submission_saves_and_redirects_to_foundations(self, client_a, org_a, user_a):
        response = client_a.post(_stage3_url(org_a), data=VALID_PAYLOAD)

        assert response.status_code == 302
        assert response.url == reverse("organisations:foundations", args=[org_a.id])

        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.productivity_platform == "microsoft_365"
        assert profile.primary_cloud_provider == "aws"
        assert profile.endpoint_management == "company_managed"
        assert profile.develops_hosts_own_software == YES
        assert profile.handles_personal_data == YES
        assert profile.handles_confidential_business_data == NO
        assert profile.handles_payment_card_data == NO
        assert profile.handles_special_category_data == UNKNOWN
        assert profile.cyber_essentials_status == "in_progress"
        assert profile.iso27001_status == "not_certified"

        audit_event = AuditEvent.objects.get(organisation=org_a)
        assert audit_event.action == AuditEvent.ACTION_PROFILE_CREATED
        assert audit_event.actor == user_a

    def test_an_out_of_choice_platform_value_is_rejected_server_side(self, client_a, org_a):
        payload = dict(VALID_PAYLOAD, productivity_platform="not_a_real_platform")

        response = client_a.post(_stage3_url(org_a), data=payload)

        assert response.status_code == 200
        assert "productivity_platform" in response.context["form"].errors
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_an_out_of_choice_data_category_value_is_rejected_server_side(self, client_a, org_a):
        payload = dict(VALID_PAYLOAD, handles_payment_card_data="not_a_real_value")

        response = client_a.post(_stage3_url(org_a), data=payload)

        assert response.status_code == 200
        assert "handles_payment_card_data" in response.context["form"].errors
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_valid_submission_against_an_existing_profile_updates_it(self, client_a, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Existing Ltd")

        response = client_a.post(_stage3_url(org_a), data=VALID_PAYLOAD)

        assert response.status_code == 302
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.legal_trading_name == "Existing Ltd"  # untouched - not a Stage 3 field
        assert profile.productivity_platform == "microsoft_365"
        audit_event = AuditEvent.objects.get(organisation=org_a)
        assert audit_event.action == AuditEvent.ACTION_PROFILE_UPDATED


class TestStage3AccessControl:
    def test_a_non_member_gets_an_ordinary_404(self, client_b, org_a):
        response = client_b.get(_stage3_url(org_a))
        assert response.status_code == 404

    def test_an_anonymous_request_is_redirected_to_login(self, org_a):
        anonymous_client = Client()
        response = anonymous_client.get(_stage3_url(org_a))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
