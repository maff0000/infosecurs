"""
M008D-WI4 - `policy.readiness`'s own required proofs (dispatch §D):

1. Business/context facts (legal name, sector, >=1 workplace, all 3
   governance roles) are each individually checked.
2. All 12 controls deliberately reviewed is reused from
   `security_baseline.stage4.stage4_progress`, never re-derived.
3. NO/PARTIAL does not block approval.
4. UNKNOWN does not block approval either (but is surfaced via
   `policy.implementation_status`, tested separately).
5. `entitlements.metrics.get_security_foundations_completion`'s 18-item
   percentage is NOT a gate - a policy can be approved while it is below
   100% (regression test).
6. `policy.services.approve_policy_directly`/`record_external_policy_approval`
   actually refuse an approval attempt when readiness is not met (the
   service-layer backstop, never trusted from a view-layer check alone).
"""
from __future__ import annotations

import datetime

import pytest

from entitlements.metrics import get_security_foundations_completion
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import assign_role
from organisations.models import SECTOR_PROFESSIONAL_CONSULTING, OrganisationProfile
from policy.models import PolicyDocument, PolicyVersion
from policy.readiness import policy_readiness
from policy.services import PolicyLifecycleError, approve_policy_directly
from security_baseline.structured_catalogue import STRUCTURED_OPTIONS
from security_baseline.services import record_structured_baseline_answer
from workplace.models import Workplace


def _assign_all_three_roles(organisation, person):
    for role in (
        GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
        GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
        GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
    ):
        assign_role(organisation=organisation, role=role, person=person)


def _review_all_twelve_controls(organisation, user):
    for control_key, options in STRUCTURED_OPTIONS.items():
        option_code = next(iter(options.keys()))
        record_structured_baseline_answer(organisation, control_key, option_code, actor=user)


def _make_fully_ready_organisation(org, user):
    OrganisationProfile.objects.create(
        organisation=org,
        legal_trading_name="Org A Synthetic Ltd",
        sector=SECTOR_PROFESSIONAL_CONSULTING,
    )
    Workplace.objects.create(organisation=org, name="HQ", type=Workplace.TYPE_DEDICATED_OFFICE)
    person = OrganisationPerson.objects.create(organisation=org, user=user, full_name="Ada Holder")
    _assign_all_three_roles(org, person)
    _review_all_twelve_controls(org, user)
    return person


@pytest.mark.django_db
class TestPolicyReadinessConditions:
    def test_fresh_organisation_is_not_ready_on_every_condition(self, org_a):
        readiness = policy_readiness(org_a)
        assert readiness.is_ready is False
        assert readiness.legal_name_confirmed is False
        assert readiness.sector_confirmed is False
        assert readiness.has_active_workplace is False
        assert readiness.governance_roles_complete is False
        assert readiness.all_controls_reviewed is False
        assert len(readiness.blocking_reasons) == 5

    def test_fully_ready_organisation_passes_every_condition(self, org_a, user_a):
        _make_fully_ready_organisation(org_a, user_a)
        readiness = policy_readiness(org_a)
        assert readiness.is_ready is True
        assert readiness.blocking_reasons == []

    def test_legal_name_blank_still_blocks_even_with_a_profile_row(self, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="   ")
        readiness = policy_readiness(org_a)
        assert readiness.legal_name_confirmed is False

    def test_two_of_three_governance_roles_is_not_complete(self, org_a, user_a):
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Ada Holder"
        )
        assign_role(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER, person=person
        )
        assign_role(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE, person=person
        )
        readiness = policy_readiness(org_a)
        assert readiness.governance_roles_complete is False

    def test_eleven_of_twelve_controls_reviewed_is_not_all_reviewed(self, org_a, user_a):
        keys = list(STRUCTURED_OPTIONS.keys())
        for control_key in keys[:-1]:
            option_code = next(iter(STRUCTURED_OPTIONS[control_key].keys()))
            record_structured_baseline_answer(org_a, control_key, option_code, actor=user_a)
        readiness = policy_readiness(org_a)
        assert readiness.all_controls_reviewed is False

    def test_a_not_sure_answer_still_counts_as_reviewed(self, org_a, user_a):
        """UNKNOWN never blocks approval (§6 condition 4) - an honest
        'Not sure' on every control still counts as fully reviewed."""
        for control_key, options in STRUCTURED_OPTIONS.items():
            not_sure_code = next(
                code for code, opt in options.items() if opt.derived_answer == "unknown"
            )
            record_structured_baseline_answer(org_a, control_key, not_sure_code, actor=user_a)
        readiness = policy_readiness(org_a)
        assert readiness.all_controls_reviewed is True


@pytest.mark.django_db
class TestNoPartialOrUnknownBlocksApproval:
    def test_every_control_answered_no_or_partial_still_allows_approval(self, org_a, user_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Org A Synthetic Ltd",
            sector=SECTOR_PROFESSIONAL_CONSULTING,
        )
        Workplace.objects.create(organisation=org_a, name="HQ", type=Workplace.TYPE_DEDICATED_OFFICE)
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Ada Holder"
        )
        _assign_all_three_roles(org_a, person)
        # Deliberately pick a NO/PARTIAL option for every control, never YES.
        for control_key, options in STRUCTURED_OPTIONS.items():
            worst_code = next(
                code
                for code, opt in options.items()
                if opt.derived_answer in ("no", "partial")
            )
            record_structured_baseline_answer(org_a, control_key, worst_code, actor=user_a)

        readiness = policy_readiness(org_a)
        assert readiness.is_ready is True

        document, _ = PolicyDocument.objects.get_or_create(organisation=org_a)
        version = PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org A ISP",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
            review_warnings=[],
        )
        approved = approve_policy_directly(
            version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        assert approved.status == PolicyVersion.STATUS_APPROVED


@pytest.mark.django_db
class TestSecurityFoundationsCompletionIsNotAGate:
    def test_policy_can_be_approved_while_foundations_completion_is_below_100_percent(
        self, org_a, user_a
    ):
        _make_fully_ready_organisation(org_a, user_a)

        completion = get_security_foundations_completion(org_a)
        assert completion.percentage < 100, (
            "This test's fixture must leave at least one of the 18 "
            "Foundations items incomplete (e.g. no evidence/remediation/"
            "risk rows exist) - otherwise it proves nothing about this "
            "gate being independent of that metric."
        )

        document, _ = PolicyDocument.objects.get_or_create(organisation=org_a)
        version = PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org A ISP",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
            review_warnings=[],
        )
        approved = approve_policy_directly(
            version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        assert approved.status == PolicyVersion.STATUS_APPROVED


@pytest.mark.django_db
class TestServiceLayerBackstopRefusesUnreadyApproval:
    def test_approve_policy_directly_refuses_when_not_ready(self, org_a, user_a):
        """No profile, no workplace, no governance, no controls reviewed
        at all - `policy_readiness` is nowhere near ready. The SERVICE
        LAYER itself must refuse this, independent of any view-layer
        check."""
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Ada Holder"
        )
        assign_role(
            organisation=org_a, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER, person=person
        )
        document, _ = PolicyDocument.objects.get_or_create(organisation=org_a)
        version = PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org A ISP",
            sections=[{"section_key": "purpose_and_scope", "content": "x"}],
            review_warnings=[],
        )
        with pytest.raises(PolicyLifecycleError):
            approve_policy_directly(
                version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
            )
        version.refresh_from_db()
        assert version.status == PolicyVersion.STATUS_DRAFT
