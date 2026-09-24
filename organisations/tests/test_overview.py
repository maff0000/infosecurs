"""
Mechanical tests for `organisations.overview.build_overview` (M006 PID §6,
§22 "Overview derived state/no independent state").

Focuses on the two worked-example areas the dispatch instructions asked to
be reasoned through in full first - Organisation setup and Policy - across
their Not started / In progress / Ready (/ Needs attention, for Policy)
transitions, using real model rows via this codebase's established
`org_a`/`org_b` fixture convention (organisations/tests/conftest.py), never
mocks. A final smoke test proves every one of the ten PID §6 areas is
present and well-formed for a completely fresh organisation.
"""
import datetime

import pytest
from django.utils import timezone

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from organisations.models import OrganisationProfile
from organisations.overview import (
    STATE_IN_PROGRESS,
    STATE_NEEDS_ATTENTION,
    STATE_NOT_STARTED,
    STATE_READY,
    build_overview,
)
from policy.models import PolicyDocument, PolicyVersion


def _area(org, key):
    areas = build_overview(org)
    matches = [a for a in areas if a["key"] == key]
    assert len(matches) == 1, f"expected exactly one area with key={key!r}, got {matches!r}"
    return matches[0]


# --- Worked example 1: Organisation setup ---------------------------------------


@pytest.mark.django_db
class TestOrganisationSetupArea:
    def test_not_started_with_no_profile(self, org_a):
        area = _area(org_a, "organisation_setup")
        assert area["state"] == STATE_NOT_STARTED

    def test_in_progress_with_load_bearing_facts_still_unconfirmed(self, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            staff_count=12,
            # every other tri-state/enum field is left at its "unknown" default
        )
        area = _area(org_a, "organisation_setup")
        assert area["state"] == STATE_IN_PROGRESS
        assert area["count"] > 0

    def test_ready_when_every_load_bearing_fact_is_confirmed(self, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            staff_count=12,
            endpoint_management="company_managed",
            productivity_platform="microsoft_365",
            primary_cloud_provider="none",
            develops_hosts_own_software="no",
            handles_personal_data="yes",
            handles_confidential_business_data="yes",
            handles_payment_card_data="no",
            handles_special_category_data="no",
            receives_security_questionnaires="yes",
        )
        area = _area(org_a, "organisation_setup")
        assert area["state"] == STATE_READY

    def test_staff_count_alone_being_unset_blocks_ready(self, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            staff_count=None,
            endpoint_management="company_managed",
            productivity_platform="microsoft_365",
            primary_cloud_provider="none",
            develops_hosts_own_software="no",
            handles_personal_data="yes",
            handles_confidential_business_data="yes",
            handles_payment_card_data="no",
            handles_special_category_data="no",
            receives_security_questionnaires="yes",
        )
        area = _area(org_a, "organisation_setup")
        assert area["state"] == STATE_IN_PROGRESS

    def test_optional_assurance_fields_never_block_ready(self, org_a):
        """cyber_essentials_status/iso27001_status are genuinely optional
        (organisations/overview.py's own documented judgment call) - left
        at "unknown" here and Ready must still be reached."""
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            staff_count=12,
            endpoint_management="company_managed",
            productivity_platform="microsoft_365",
            primary_cloud_provider="none",
            develops_hosts_own_software="no",
            handles_personal_data="yes",
            handles_confidential_business_data="yes",
            handles_payment_card_data="no",
            handles_special_category_data="no",
            receives_security_questionnaires="yes",
            cyber_essentials_status="unknown",
            iso27001_status="unknown",
        )
        area = _area(org_a, "organisation_setup")
        assert area["state"] == STATE_READY

    def test_never_reaches_needs_attention(self, org_a):
        """Documented judgment call: profile completeness has no
        failure/warning condition of its own."""
        area = _area(org_a, "organisation_setup")
        assert area["state"] != STATE_NEEDS_ATTENTION


# --- Worked example 2: Policy ----------------------------------------------------


@pytest.mark.django_db
class TestPolicyArea:
    def test_not_started_with_no_version(self, org_a):
        area = _area(org_a, "policy")
        assert area["state"] == STATE_NOT_STARTED

    def test_in_progress_with_only_a_draft(self, org_a):
        document = PolicyDocument.objects.create(organisation=org_a)
        PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org A ISP",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
        )
        area = _area(org_a, "policy")
        assert area["state"] == STATE_IN_PROGRESS

    def test_ready_when_an_approved_version_exists(self, org_a):
        document = PolicyDocument.objects.create(organisation=org_a)
        PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_APPROVED,
            title="Org A ISP",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
            approved_at=timezone.now(),
            next_review_date=timezone.now().date() + datetime.timedelta(days=180),
        )
        area = _area(org_a, "policy")
        assert area["state"] == STATE_READY

    def test_ready_holds_even_with_a_newer_unreviewed_draft_alongside_it(self, org_a):
        """M004's 'create a new draft from an approved version' flow (PID
        §15) - a genuinely approved version is still current regardless of
        a newer draft sitting next to it (this dispatch's documented
        judgment call)."""
        document = PolicyDocument.objects.create(organisation=org_a)
        PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_APPROVED,
            title="Org A ISP v1",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
            approved_at=timezone.now(),
            next_review_date=timezone.now().date() + datetime.timedelta(days=180),
        )
        PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=2,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org A ISP v2 draft",
            sections=[{"section_key": "purpose_and_scope", "content": "y"}],
        )
        area = _area(org_a, "policy")
        assert area["state"] == STATE_READY

    def test_needs_attention_when_approved_versions_review_date_has_passed(self, org_a):
        document = PolicyDocument.objects.create(organisation=org_a)
        PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_APPROVED,
            title="Org A ISP",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
            approved_at=timezone.now(),
            next_review_date=timezone.now().date() - datetime.timedelta(days=1),
        )
        area = _area(org_a, "policy")
        assert area["state"] == STATE_NEEDS_ATTENTION


# --- Smoke test: every PID §6 area is present and well-formed -------------------


@pytest.mark.django_db
def test_build_overview_returns_all_ten_areas_for_a_fresh_organisation(org_a):
    areas = build_overview(org_a)
    keys = [a["key"] for a in areas]
    assert keys == [
        "organisation_setup",
        "security_baseline",
        "assets",
        "risks",
        "evidence",
        "remediation",
        "security_state",
        "governance_workplace",
        "policy",
        "questionnaire",
    ]
    for area in areas:
        assert area["state"] in (
            STATE_NOT_STARTED,
            STATE_NEEDS_ATTENTION,
            STATE_IN_PROGRESS,
            STATE_READY,
        )
        assert area["next_action_url"].startswith("/")
        assert area["next_action_label"]


@pytest.mark.django_db
def test_governance_workplace_not_started_for_org_created_outside_the_normal_flow(org_a):
    """`org_a` is created directly by the fixture (Organisation.objects.
    create), bypassing `organisations.views.organisation_create`'s
    atomic governance-role-defaulting - so, unlike an organisation created
    through the real product flow, it genuinely has zero
    GovernanceRoleAssignment rows and zero workplaces yet."""
    assert not GovernanceRoleAssignment.objects.filter(organisation=org_a).exists()
    area = _area(org_a, "governance_workplace")
    assert area["state"] == STATE_NOT_STARTED


@pytest.mark.django_db
def test_governance_workplace_needs_attention_when_an_assignee_is_inactive(org_a):
    person = OrganisationPerson.objects.create(
        organisation=org_a, full_name="Jane Doe", is_active=False
    )
    GovernanceRoleAssignment.objects.create(
        organisation=org_a,
        role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
        person=person,
    )
    area = _area(org_a, "governance_workplace")
    assert area["state"] == STATE_NEEDS_ATTENTION
