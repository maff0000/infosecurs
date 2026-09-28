"""
M007-WI4 mechanical tests for entitlements.metrics (PID §26/§27).

Uses this codebase's established `org_a`/`org_b` fixture convention
(entitlements/tests/conftest.py) and real model rows throughout - never
mocks, matching organisations/tests/test_overview.py's own discipline for
the domain logic this module reuses.
"""
from __future__ import annotations

import dataclasses
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone as django_timezone

from entitlements.metrics import (
    UnresolvableFoundationRequirementError,
    get_foundational_security_posture,
    get_foundations_requirement_states,
    get_needs_attention,
    get_security_foundations_completion,
)
from entitlements.models import FOUNDATION_METRIC_VERSION, FoundationRequirement, ProductArea, RequirementKind
from evidence.models import ControlEvidenceLink, EvidenceItem
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from key_assets.models import CATEGORY_ENDPOINT, CRITICALITY_MEDIUM, KeyAsset
from organisations.models import OrganisationProfile
from policy.models import PolicyDocument, PolicyVersion
from remediation.models import RemediationAction
from risk_register.models import Risk
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
    BaselineAnswer,
    BaselineAssessment,
)
from workplace.models import Workplace

pytestmark = pytest.mark.django_db

D = Decimal


# ---------------------------------------------------------------------------
# Shared fixtures/helpers
# ---------------------------------------------------------------------------
def _set_baseline_answers(organisation, answers: dict[str, str]) -> BaselineAssessment:
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=organisation, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    for key, answer in answers.items():
        BaselineAnswer.objects.update_or_create(
            assessment=assessment, question_key=key, defaults={"answer": answer}
        )
    return assessment


def _state_by_source_key(states, source_key):
    matches = [s for s in states if s.source_key == source_key]
    assert len(matches) == 1, f"expected exactly one state with source_key={source_key!r}, got {matches!r}"
    return matches[0]


def _make_full_governance(organisation):
    person = OrganisationPerson.objects.create(
        organisation=organisation, full_name="Account Holder", is_active=True
    )
    for role, _ in GovernanceRoleAssignment.ROLE_CHOICES:
        GovernanceRoleAssignment.objects.create(organisation=organisation, role=role, person=person)


def _make_active_workplace(organisation):
    return Workplace.objects.create(
        organisation=organisation,
        name="Head office",
        type=Workplace.TYPE_DEDICATED_OFFICE,
        is_active=True,
    )


def _make_confirmed_asset(organisation):
    return KeyAsset.objects.create(
        organisation=organisation,
        name="Laptop fleet",
        category=CATEGORY_ENDPOINT,
        criticality=CRITICALITY_MEDIUM,
        status=KeyAsset.STATUS_CONFIRMED,
    )

def _make_full_profile(organisation):
    return OrganisationProfile.objects.create(
        organisation=organisation,
        legal_trading_name="Test Ltd",
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


def _make_risk(organisation, *, status, impact=1, likelihood=1):
    return Risk.objects.create(
        organisation=organisation,
        title="Test risk",
        threat="A threat",
        vulnerability="A gap",
        impact=impact,
        likelihood=likelihood,
        rationale="Because reasons.",
        proposed_treatment="Do something about it.",
        status=status,
    )


def _make_approved_policy(organisation, *, next_review_date=None):
    document = PolicyDocument.objects.create(organisation=organisation)
    return PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=1,
        status=PolicyVersion.STATUS_APPROVED,
        title="Information Security Policy",
        next_review_date=next_review_date,
        approved_at=django_timezone.now(),
    )


ALL_YES = {
    "mfa_user_accounts": ANSWER_YES,
    "mfa_privileged_accounts": ANSWER_YES,
    "endpoint_protection": ANSWER_YES,
    "patching": ANSWER_YES,
    "device_encryption": ANSWER_YES,
    "backups": ANSWER_YES,
    "joiner_mover_leaver": ANSWER_YES,
    "privileged_access_separation": ANSWER_YES,
    "security_awareness_training": ANSWER_YES,
    "incident_reporting_route": ANSWER_YES,
    "email_phishing_protection": ANSWER_YES,
    "remote_access_control": ANSWER_YES,
}

ALL_NO = {key: ANSWER_NO for key in ALL_YES}


# ---------------------------------------------------------------------------
# Posture
# ---------------------------------------------------------------------------
class TestPosture:
    def test_all_yes_is_100_percent(self, org_a):
        _set_baseline_answers(org_a, ALL_YES)
        posture = get_foundational_security_posture(org_a)
        assert posture.percentage == 100
        assert posture.earned_points == posture.available_points

    def test_all_no_is_0_percent(self, org_a):
        _set_baseline_answers(org_a, ALL_NO)
        posture = get_foundational_security_posture(org_a)
        assert posture.percentage == 0
        assert posture.earned_points == D("0")
        assert posture.available_points == D("38")  # 3x5 + 7x3 + 2x1, PID §11.4

    def test_all_unknown_is_0_percent_and_stays_lexically_unknown(self, org_a):
        _set_baseline_answers(org_a, {key: ANSWER_UNKNOWN for key in ALL_YES})
        posture = get_foundational_security_posture(org_a)
        assert posture.percentage == 0
        for state in posture.requirement_states:
            assert state.answer_state == ANSWER_UNKNOWN
            assert state.answer_state != ANSWER_NO  # UNKNOWN != NO, PID §21

    def test_all_missing_answers_treated_identically_to_unknown(self, org_a):
        """No BaselineAssessment/BaselineAnswer rows at all - PID §11.5
        "Missing rows are treated exactly as... UNKNOWN"."""
        posture = get_foundational_security_posture(org_a)
        assert posture.percentage == 0
        assert posture.available_points == D("38")
        for state in posture.requirement_states:
            assert state.answer_state == ANSWER_UNKNOWN

    def test_partial_earns_exactly_half_its_weight(self, org_a):
        answers = {key: ANSWER_NOT_APPLICABLE for key in ALL_YES}
        answers["mfa_privileged_accounts"] = ANSWER_PARTIAL  # weight 5
        _set_baseline_answers(org_a, answers)
        posture = get_foundational_security_posture(org_a)
        assert posture.available_points == D("5")
        assert posture.earned_points == D("2.5")
        assert posture.percentage == 50

    def test_not_applicable_excluded_from_denominator(self, org_a):
        _set_baseline_answers(org_a, ALL_YES)
        available_before = get_foundational_security_posture(org_a).available_points

        answers = dict(ALL_YES)
        answers["mfa_privileged_accounts"] = ANSWER_NOT_APPLICABLE  # weight 5
        _set_baseline_answers(org_a, answers)
        posture_after = get_foundational_security_posture(org_a)

        assert posture_after.available_points == available_before - D("5")
        # Still all-YES on every applicable control, so percentage is still 100.
        assert posture_after.percentage == 100
        na_state = _state_by_source_key(posture_after.requirement_states, "mfa_privileged_accounts")
        assert na_state.answer_state == ANSWER_NOT_APPLICABLE
        assert na_state.is_posture_applicable is False
        assert na_state.posture_factor is None

    def test_mixed_weights_hand_calculated(self, org_a):
        """
        earned = 5(YES) + 2.5(PARTIAL*5) + 0(NO) + 3(YES) + 0(UNKNOWN) + 3(YES)
                + 1.5(PARTIAL*3) + 0(NO) + 3(YES) + 1(YES) + 0.5(PARTIAL*1)
                = 19.5
        available = 38 - 3 (endpoint_protection excluded as N/A) = 35
        percentage = 19.5 / 35 * 100 = 55.714... -> 56 (round half up)
        """
        _set_baseline_answers(
            org_a,
            {
                "mfa_privileged_accounts": ANSWER_YES,  # 5 -> 5
                "patching": ANSWER_PARTIAL,  # 5 -> 2.5
                "backups": ANSWER_NO,  # 5 -> 0
                "mfa_user_accounts": ANSWER_YES,  # 3 -> 3
                "endpoint_protection": ANSWER_NOT_APPLICABLE,  # 3 -> excluded
                "device_encryption": ANSWER_UNKNOWN,  # 3 -> 0
                "joiner_mover_leaver": ANSWER_YES,  # 3 -> 3
                "privileged_access_separation": ANSWER_PARTIAL,  # 3 -> 1.5
                "email_phishing_protection": ANSWER_NO,  # 3 -> 0
                "remote_access_control": ANSWER_YES,  # 3 -> 3
                "incident_reporting_route": ANSWER_YES,  # 1 -> 1
                "security_awareness_training": ANSWER_PARTIAL,  # 1 -> 0.5
            },
        )
        posture = get_foundational_security_posture(org_a)
        assert posture.earned_points == D("19.5")
        assert posture.available_points == D("35")
        assert posture.percentage == 56

    def test_deterministic_round_half_up_not_bankers_rounding(self, org_a):
        """
        available=8 (weight 1 + weight 1 + weight 3 + weight 3), earned=1 ->
        exactly 12.5%. Python's builtin round(12.5) == 12 (round-half-even,
        since 12 is the even neighbour) - this module must instead produce
        13 (round-half-up), proving the rounding is deliberate, not
        float/round()-drift-dependent.
        """
        answers = {key: ANSWER_NOT_APPLICABLE for key in ALL_YES}
        answers["incident_reporting_route"] = ANSWER_YES  # weight 1 -> 1
        answers["security_awareness_training"] = ANSWER_NO  # weight 1 -> 0
        answers["endpoint_protection"] = ANSWER_NO  # weight 3 -> 0
        answers["device_encryption"] = ANSWER_NO  # weight 3 -> 0
        _set_baseline_answers(org_a, answers)

        posture = get_foundational_security_posture(org_a)
        assert posture.available_points == D("8")
        assert posture.earned_points == D("1")
        assert posture.percentage == 13
        assert round(12.5) == 12  # sanity: Python's own round() would get this wrong here

    def test_methodology_version_present_and_correct(self, org_a):
        posture = get_foundational_security_posture(org_a)
        assert posture.methodology_version == FOUNDATION_METRIC_VERSION == "2026-09-v1"


class TestPostureNonInflation:
    """PID §21/§26.1 - evidence, policy approval, remediation completion and
    raw AI output must never move the posture percentage for a FIXED set of
    BaselineAnswer rows."""

    def test_surrounding_domain_records_do_not_change_posture(self, org_a, make_user):
        _set_baseline_answers(
            org_a,
            {
                "mfa_privileged_accounts": ANSWER_YES,
                "patching": ANSWER_PARTIAL,
                "backups": ANSWER_NO,
                **{k: ANSWER_UNKNOWN for k in ALL_YES if k not in ("mfa_privileged_accounts", "patching", "backups")},
            },
        )
        before = get_foundational_security_posture(org_a)

        user = make_user("evidence_recorder")

        # Evidence attached to a control.
        evidence = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="MFA admin console screenshot",
            reference_url="https://example.test/evidence",
            recorded_by=user,
        )
        ControlEvidenceLink.objects.create(
            organisation=org_a,
            evidence=evidence,
            control_key="mfa_privileged_accounts",
            relationship=ControlEvidenceLink.RELATIONSHIP_SUPPORTS,
            linked_by=user,
        )

        # An approved policy.
        _make_approved_policy(org_a)

        # A completed remediation action.
        RemediationAction.objects.create(
            organisation=org_a,
            title="Roll out MFA everywhere",
            status=RemediationAction.STATUS_DONE,
        )

        # Raw AI output - an AI-suggested draft risk, never confirmed.
        _make_risk(org_a, status=Risk.STATUS_DRAFT_AI_SUGGESTED)

        after = get_foundational_security_posture(org_a)
        assert after.percentage == before.percentage
        assert after.earned_points == before.earned_points
        assert after.available_points == before.available_points


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------
class TestCompletion:
    def test_fresh_organisation_is_fully_incomplete(self, org_a):
        completion = get_security_foundations_completion(org_a)
        assert completion.total_count == 18
        assert completion.completed_count == 0
        assert completion.percentage == 0

    def test_each_answered_baseline_control_increments_completion_by_one(self, org_a):
        _set_baseline_answers(org_a, {"mfa_privileged_accounts": ANSWER_YES})
        completion = get_security_foundations_completion(org_a)
        assert completion.completed_count == 1

        _set_baseline_answers(org_a, {"patching": ANSWER_NO})
        completion = get_security_foundations_completion(org_a)
        assert completion.completed_count == 2

    def test_unknown_and_missing_do_not_count_complete(self, org_a):
        _set_baseline_answers(org_a, {"mfa_privileged_accounts": ANSWER_UNKNOWN})
        completion = get_security_foundations_completion(org_a)
        assert completion.completed_count == 0  # explicit UNKNOWN, and 11 missing rows

    @pytest.mark.parametrize("answer", [ANSWER_YES, ANSWER_PARTIAL, ANSWER_NO, ANSWER_NOT_APPLICABLE])
    def test_yes_partial_no_not_applicable_all_count_complete(self, org_a, answer):
        _set_baseline_answers(org_a, {"mfa_privileged_accounts": answer})
        completion = get_security_foundations_completion(org_a)
        state = _state_by_source_key(completion.requirement_states, "mfa_privileged_accounts")
        assert state.is_completion_complete is True
        assert state.answer_state == answer

    # --- Milestone resolvers: one positive + one negative case each -------

    def test_organisation_profile_resolver(self, org_a):
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "organisation_profile").is_completion_complete is False

        _make_full_profile(org_a)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "organisation_profile").is_completion_complete is True

    def test_governance_resolver(self, org_a):
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "governance_roles").is_completion_complete is False

        _make_full_governance(org_a)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "governance_roles").is_completion_complete is True

    def test_governance_resolver_false_when_assignee_inactive(self, org_a):
        person = OrganisationPerson.objects.create(
            organisation=org_a, full_name="Leaver", is_active=False
        )
        for role, _ in GovernanceRoleAssignment.ROLE_CHOICES:
            GovernanceRoleAssignment.objects.create(organisation=org_a, role=role, person=person)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "governance_roles").is_completion_complete is False

    def test_workplace_resolver(self, org_a):
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "workplace").is_completion_complete is False

        _make_active_workplace(org_a)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "workplace").is_completion_complete is True

    def test_assets_review_resolver(self, org_a):
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "assets_review").is_completion_complete is False

        _make_confirmed_asset(org_a)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "assets_review").is_completion_complete is True

    def test_assets_review_resolver_incomplete_while_suggestion_pending(self, org_a):
        KeyAsset.objects.create(
            organisation=org_a,
            name="Suggested asset",
            category=CATEGORY_ENDPOINT,
            criticality=CRITICALITY_MEDIUM,
            status=KeyAsset.STATUS_SUGGESTED,
        )
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "assets_review").is_completion_complete is False

    def test_risks_review_resolver_not_started_and_in_progress_are_incomplete(self, org_a):
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "risks_review").is_completion_complete is False  # no risks at all

        _make_risk(org_a, status=Risk.STATUS_DRAFT_AI_SUGGESTED)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "risks_review").is_completion_complete is False  # draft pending

    def test_risks_review_resolver_ready_is_complete(self, org_a):
        _make_risk(org_a, status=Risk.STATUS_CONFIRMED, impact=1, likelihood=1)  # low band
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "risks_review").is_completion_complete is True

    def test_risks_review_resolver_needs_attention_still_counts_complete(self, org_a):
        """
        Flagged judgement call: an unaddressed confirmed CRITICAL risk with
        no remediation action puts `_risks_area` in STATE_NEEDS_ATTENTION,
        but PID §12.3's own milestone wording ("no AI-suggested draft risk
        remains awaiting customer review... Do not require all risk
        remediated") does not require remediation - only that the review
        step (clearing drafts) is done. This proves that reading.
        """
        _make_risk(org_a, status=Risk.STATUS_CONFIRMED, impact=5, likelihood=5)  # critical band
        assert not RemediationAction.objects.filter(organisation=org_a).exists()
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "risks_review").is_completion_complete is True

    def test_policy_approved_resolver(self, org_a):
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "policy_approved").is_completion_complete is False

        _make_approved_policy(org_a)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "policy_approved").is_completion_complete is True

    def test_policy_approved_resolver_stays_complete_even_when_overdue(self, org_a):
        """PID §12.3: "A later overdue review may generate Needs Attention,
        but must not rewrite the fact that the Foundation policy milestone
        was completed"."""
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        _make_approved_policy(org_a, next_review_date=yesterday)
        states = get_foundations_requirement_states(org_a)
        assert _state_by_source_key(states, "policy_approved").is_completion_complete is True

    def test_full_eighteen_item_total_no_double_counting(self, org_a):
        _set_baseline_answers(org_a, ALL_YES)
        _make_full_profile(org_a)
        _make_full_governance(org_a)
        _make_active_workplace(org_a)
        _make_confirmed_asset(org_a)
        _make_risk(org_a, status=Risk.STATUS_CONFIRMED, impact=1, likelihood=1)
        _make_approved_policy(org_a)

        completion = get_security_foundations_completion(org_a)
        assert completion.total_count == 18
        assert completion.completed_count == 18
        assert completion.percentage == 100
        assert len({s.code for s in completion.requirement_states}) == 18  # no duplicates

    def test_requirement_state_is_immutable_no_editable_completion_flag(self, org_a):
        """`RequirementState` is a frozen dataclass - there is no code path
        anywhere that can set an editable `completed` flag on it, or on the
        FoundationRequirement model itself (see entitlements/models.py -
        no such field exists there either)."""
        states = get_foundations_requirement_states(org_a)
        with pytest.raises(dataclasses.FrozenInstanceError):
            states[0].is_completion_complete = True
        assert not hasattr(FoundationRequirement, "completed")
        assert not hasattr(FoundationRequirement, "posture_percentage")
        assert not hasattr(FoundationRequirement, "completion_percentage")


# ---------------------------------------------------------------------------
# Separation between the two metrics (PID §26.3, Appendix C)
# ---------------------------------------------------------------------------
class TestSeparationBetweenMetrics:
    def test_scenario_a_high_completion_low_posture(self, org_a):
        _set_baseline_answers(org_a, ALL_NO)
        _make_full_profile(org_a)
        _make_full_governance(org_a)
        _make_active_workplace(org_a)
        _make_confirmed_asset(org_a)
        _make_risk(org_a, status=Risk.STATUS_CONFIRMED, impact=1, likelihood=1)
        _make_approved_policy(org_a)

        posture = get_foundational_security_posture(org_a)
        completion = get_security_foundations_completion(org_a)
        assert completion.percentage == 100
        assert posture.percentage == 0
        assert completion.percentage > posture.percentage

    def test_scenario_b_high_posture_lower_completion(self, org_a):
        _set_baseline_answers(org_a, ALL_YES)
        # No milestones completed at all.
        posture = get_foundational_security_posture(org_a)
        completion = get_security_foundations_completion(org_a)
        assert posture.percentage == 100
        assert completion.completed_count == 12
        assert completion.total_count == 18
        assert completion.percentage < 100
        assert posture.percentage > completion.percentage


# ---------------------------------------------------------------------------
# Needs Attention (PID §14/§27)
# ---------------------------------------------------------------------------
class TestNeedsAttention:
    def test_important_controls_count_excludes_low_weight_and_unknown_and_na(self, org_a):
        # Every one of the 12 keys is given an explicit answer here (starting
        # from ALL_YES and overriding) - an unanswered key defaults to
        # UNKNOWN (PID §11.5's "missing == unknown"), which would otherwise
        # silently inflate the not_sure count below with keys this test
        # never intended to touch.
        answers = dict(ALL_YES)
        answers.update(
            {
                "mfa_privileged_accounts": ANSWER_NO,  # weight 5, important, counts
                "patching": ANSWER_PARTIAL,  # weight 5, important, counts
                "backups": ANSWER_YES,  # weight 5, important, does NOT count (yes)
                "security_awareness_training": ANSWER_NO,  # weight 1, NOT important
                "incident_reporting_route": ANSWER_UNKNOWN,  # weight 1, NOT important + unknown
                "device_encryption": ANSWER_UNKNOWN,  # weight 3, important but unknown -> not_sure only
                "endpoint_protection": ANSWER_NOT_APPLICABLE,  # weight 3, important but N/A -> never flagged
            }
        )
        _set_baseline_answers(org_a, answers)
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.important_controls.count == 2  # mfa_privileged_accounts, patching
        assert needs_attention.not_sure_controls.count == 2  # incident_reporting_route, device_encryption

    def test_not_sure_never_double_counted_into_important(self, org_a):
        answers = dict(ALL_YES)
        answers["mfa_privileged_accounts"] = ANSWER_UNKNOWN  # weight 5
        _set_baseline_answers(org_a, answers)
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.important_controls.count == 0
        assert needs_attention.not_sure_controls.count == 1

    def test_not_applicable_never_flagged_anywhere(self, org_a):
        _set_baseline_answers(org_a, {key: ANSWER_NOT_APPLICABLE for key in ALL_YES})
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.important_controls.count == 0
        assert needs_attention.not_sure_controls.count == 0

    def test_foundations_incomplete_count_matches_completion_resolver_exactly(self, org_a):
        _make_full_profile(org_a)
        _make_active_workplace(org_a)
        completion = get_security_foundations_completion(org_a)
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.foundations_incomplete.count == (
            completion.total_count - completion.completed_count
        )

    def test_policy_review_overdue_signal(self, org_a):
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.policy_review_overdue.count == 0  # no policy at all

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        _make_approved_policy(org_a, next_review_date=tomorrow)
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.policy_review_overdue.count == 0  # approved, not yet due

    def test_policy_review_overdue_signal_when_actually_overdue(self, org_b):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        _make_approved_policy(org_b, next_review_date=yesterday)
        needs_attention = get_needs_attention(org_b)
        assert needs_attention.policy_review_overdue.count == 1

    def test_destination_metadata_present_no_html_and_zero_count_lines_still_returned(self, org_a):
        needs_attention = get_needs_attention(org_a)
        for signal in (
            needs_attention.important_controls,
            needs_attention.foundations_incomplete,
            needs_attention.not_sure_controls,
            needs_attention.policy_review_overdue,
        ):
            assert signal.destination_product_area_code
            assert "<" not in signal.destination_product_area_code
            assert ProductArea.objects.filter(code=signal.destination_product_area_code).exists()
        # A fresh organisation has zero policy-overdue/important-control
        # signals but this module still returns the (count=0) signal - it
        # is WI5's template job to omit the zero-count line, not ours.
        assert needs_attention.policy_review_overdue.count == 0


# ---------------------------------------------------------------------------
# Fail-loud unmapped resolver (PID §10.2)
# ---------------------------------------------------------------------------
class TestUnresolvableFoundationRequirement:
    def test_unmapped_active_requirement_raises_not_silently_skipped(self, org_a):
        baseline_area = ProductArea.objects.get(code="baseline")
        FoundationRequirement.objects.create(
            code="test_unmapped_requirement",
            title="Deliberately unmapped test requirement",
            product_area=baseline_area,
            requirement_kind=RequirementKind.BASELINE_CONTROL,
            source_key="not_a_real_registered_source_key",
            min_package_tier=1,
            counts_toward_posture=True,
            counts_toward_completion=True,
            security_weight=1,
            is_active=True,
        )
        with pytest.raises(UnresolvableFoundationRequirementError):
            get_foundations_requirement_states(org_a)
        with pytest.raises(UnresolvableFoundationRequirementError):
            get_foundational_security_posture(org_a)


# ---------------------------------------------------------------------------
# Methodology version isolation (PID §10.3, Central Architecture correction
# to WI4) - an active `FoundationRequirement` row belonging to a DIFFERENT
# `methodology_version` must never be consumed by a calculation that itself
# reports `methodology_version=FOUNDATION_METRIC_VERSION` for its result,
# even though that row is `is_active=True` too.
# ---------------------------------------------------------------------------
class TestMethodologyVersionIsolation:
    def test_foreign_version_active_row_never_affects_any_of_the_four_functions(self, org_a):
        # A realistic, non-trivial baseline that engages both
        # BASELINE_CONTROL and DERIVED_MILESTONE resolvers, so all four
        # functions below have meaningful, non-zero/non-empty state to
        # compare before and after - not just "doesn't crash".
        _set_baseline_answers(
            org_a,
            {
                "mfa_user_accounts": ANSWER_YES,
                "mfa_privileged_accounts": ANSWER_NO,
                "endpoint_protection": ANSWER_PARTIAL,
                "patching": ANSWER_UNKNOWN,
                "device_encryption": ANSWER_YES,
                "backups": ANSWER_NOT_APPLICABLE,
            },
        )
        _make_full_governance(org_a)
        _make_active_workplace(org_a)
        _make_approved_policy(org_a)

        states_before = get_foundations_requirement_states(org_a)
        posture_before = get_foundational_security_posture(org_a)
        completion_before = get_security_foundations_completion(org_a)
        needs_attention_before = get_needs_attention(org_a)
        assert len(states_before) == 18  # the seeded v1 row count (PID §10.2/§22)

        baseline_area = ProductArea.objects.get(code="baseline")
        FoundationRequirement.objects.create(
            code="test_future_version_requirement",
            title="Deliberately future-methodology test requirement",
            product_area=baseline_area,
            methodology_version="2099-01-v2",  # deliberately NOT FOUNDATION_METRIC_VERSION
            requirement_kind=RequirementKind.BASELINE_CONTROL,
            # Deliberately a REAL, registered, resolvable source_key - the
            # same "mfa_user_accounts" key already answered ANSWER_YES above
            # for org_a's baseline - not an unregistered one. If version
            # filtering ever regressed and let this row through, it would
            # NOT raise UnresolvableFoundationRequirementError; it would be
            # silently, successfully resolved (to ANSWER_YES, weight 5,
            # counting toward both posture and completion) and quietly
            # change every one of the four functions' results below. That
            # is the actual failure mode this test must catch, so this row
            # must be excluded solely because
            # methodology_version != FOUNDATION_METRIC_VERSION - not
            # because it fails to resolve at all.
            source_key="mfa_user_accounts",
            min_package_tier=1,
            counts_toward_posture=True,
            counts_toward_completion=True,
            security_weight=5,
            is_active=True,
        )

        states_after = get_foundations_requirement_states(org_a)
        posture_after = get_foundational_security_posture(org_a)
        completion_after = get_security_foundations_completion(org_a)
        needs_attention_after = get_needs_attention(org_a)

        # The foreign-version row must not appear in the returned list at all.
        assert len(states_after) == 18
        assert "test_future_version_requirement" not in {state.code for state in states_after}

        # And none of the four functions' results changed in any way.
        assert states_after == states_before
        assert posture_after == posture_before
        assert completion_after == completion_before
        assert needs_attention_after == needs_attention_before
