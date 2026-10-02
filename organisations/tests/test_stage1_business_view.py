"""
M008C/M008B-WI2a tests for Stage 1 - Your Business
(organisations.views.organisation_stage1_business, docs/design/
M008B-STAGES-1-3-CATALOGUE.md Stage 1).

Follows this package's own established fixture convention
(organisations/tests/conftest.py: org_a/org_b/user_a/user_b/member_a/
member_b/client_a/client_b).
"""
from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from organisations.models import (
    DRIVER_GENERAL_RISK,
    DRIVER_NOT_SURE,
    SECTOR_NOT_SURE,
    SECTOR_RETAIL_ECOMMERCE,
    YES,
    AuditEvent,
    OrganisationProfile,
)

pytestmark = pytest.mark.django_db


def _stage1_url(org):
    return reverse("organisations:stage1_business", args=[org.id])


VALID_PAYLOAD = {
    "legal_trading_name": "Acme Bookkeeping Ltd",
    "sector": SECTOR_RETAIL_ECOMMERCE,
    "staff_count": "12",
    "commercial_security_driver": DRIVER_GENERAL_RISK,
    "receives_security_questionnaires": YES,
}


class TestStage1Get:
    def test_renders_with_defaults_when_no_profile_exists_yet(self, client_a, org_a):
        response = client_a.get(_stage1_url(org_a))
        assert response.status_code == 200
        assert response.context["form"].instance.pk is None
        assert response.context["form"].instance.sector == SECTOR_NOT_SURE
        # HTML-escaped apostrophe (Django's own template auto-escaping -
        # not a bug in the view/form, just how `'` renders in `<label>`
        # text), so this asserts against the escaped form.
        assert "What is your business" in response.content.decode()
        assert "legal or trading name?" in response.content.decode()

    def test_prefills_from_an_existing_profile(self, client_a, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Existing Trading Name Ltd",
            sector=SECTOR_RETAIL_ECOMMERCE,
            staff_count=7,
            commercial_security_driver=DRIVER_GENERAL_RISK,
            receives_security_questionnaires=YES,
        )

        response = client_a.get(_stage1_url(org_a))

        assert response.status_code == 200
        form = response.context["form"]
        assert form.instance.legal_trading_name == "Existing Trading Name Ltd"
        assert form.instance.sector == SECTOR_RETAIL_ECOMMERCE
        assert form.instance.staff_count == 7
        content = response.content.decode()
        assert "Existing Trading Name Ltd" in content


class TestStage1Post:
    def test_valid_submission_creates_the_profile_and_redirects_to_stage2(
        self, client_a, org_a, user_a
    ):
        response = client_a.post(_stage1_url(org_a), data=VALID_PAYLOAD)

        assert response.status_code == 302
        assert response.url == reverse(
            "organisations:stage2_people_workplaces", args=[org_a.id]
        )

        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.legal_trading_name == "Acme Bookkeeping Ltd"
        assert profile.sector == SECTOR_RETAIL_ECOMMERCE
        assert profile.staff_count == 12
        assert profile.commercial_security_driver == DRIVER_GENERAL_RISK
        assert profile.receives_security_questionnaires == YES

        audit_event = AuditEvent.objects.get(organisation=org_a)
        assert audit_event.action == AuditEvent.ACTION_PROFILE_CREATED
        assert audit_event.actor == user_a

    def test_valid_submission_against_an_existing_profile_updates_it(self, client_a, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Old Name Ltd")

        response = client_a.post(_stage1_url(org_a), data=VALID_PAYLOAD)

        assert response.status_code == 302
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.legal_trading_name == "Acme Bookkeeping Ltd"
        audit_event = AuditEvent.objects.get(organisation=org_a)
        assert audit_event.action == AuditEvent.ACTION_PROFILE_UPDATED

    def test_an_out_of_choice_sector_value_is_rejected_server_side(self, client_a, org_a):
        payload = dict(VALID_PAYLOAD, sector="not_a_real_sector_code")

        response = client_a.post(_stage1_url(org_a), data=payload)

        assert response.status_code == 200
        assert response.context["form"].is_valid() is False
        assert "sector" in response.context["form"].errors
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_an_out_of_choice_driver_value_is_rejected_server_side(self, client_a, org_a):
        payload = dict(VALID_PAYLOAD, commercial_security_driver="not_a_real_driver_code")

        response = client_a.post(_stage1_url(org_a), data=payload)

        assert response.status_code == 200
        assert "commercial_security_driver" in response.context["form"].errors
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_a_blank_legal_trading_name_is_rejected_server_side(self, client_a, org_a):
        payload = dict(VALID_PAYLOAD, legal_trading_name="   ")

        response = client_a.post(_stage1_url(org_a), data=payload)

        assert response.status_code == 200
        assert "legal_trading_name" in response.context["form"].errors
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()


class TestStage1AccessControl:
    def test_a_non_member_gets_an_ordinary_404(self, client_b, org_a):
        response = client_b.get(_stage1_url(org_a))
        assert response.status_code == 404

    def test_an_anonymous_request_is_redirected_to_login(self, org_a):
        anonymous_client = Client()
        response = anonymous_client.get(_stage1_url(org_a))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_driver_not_sure_is_itself_a_valid_choice(self, client_a, org_a):
        """Sanity check that the catalogue's own 'Not sure yet' option is
        not accidentally excluded by the form-level choice reorder
        (`organisations.forms._choices_in_order`)."""
        payload = dict(VALID_PAYLOAD, commercial_security_driver=DRIVER_NOT_SURE)

        response = client_a.post(_stage1_url(org_a), data=payload)

        assert response.status_code == 302
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.commercial_security_driver == DRIVER_NOT_SURE
