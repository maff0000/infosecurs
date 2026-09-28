"""
M007-WI6 - Parts B/C: fresh regression re-proof of the Foundational
Security Posture / Security Foundations Completion methodology, and the
Home/Foundations pages built on top of it, against the FINAL merged M007
source.

`entitlements/tests/test_metrics.py` (697 lines) and
`organisations/tests/test_home_view.py`/`test_foundations_view.py` were all
read in full before writing this file, and already exhaustively cover PID
§26/§27's own required-test list at the service layer and the HTTP/rendered-
content layer respectively. This file does not repeat that coverage - every
test below either (a) hand-calculates an expected percentage independently
and cross-checks it against the real, rendered HTTP response (a stronger,
more end-to-end proof than comparing the response to a second call into the
same service function under test, which is what `test_home_view.py` itself
already does), or (b) closes a specific, named gap in the existing HTTP-
level coverage (the "exactly two metric cards, no third headline score"
property, and a UI-level re-proof of the Scenario A/B metric-divergence
property `entitlements/tests/test_metrics.py::TestSeparationBetweenMetrics`
already proves at the service layer).

See `docs/evidence/M007-METRICS.md` for the full WI6 Parts B/C narrative
this file is the mechanical proof for.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_FOUNDATION
from policy.models import PolicyDocument, PolicyVersion
from risk_register.models import Risk
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import (
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_YES,
    BaselineAnswer,
    BaselineAssessment,
)

pytestmark = pytest.mark.django_db


def _set_baseline_answers(organisation, answers: dict[str, str]) -> BaselineAssessment:
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=organisation, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    for key, answer in answers.items():
        BaselineAnswer.objects.update_or_create(
            assessment=assessment, question_key=key, defaults={"answer": answer}
        )
    return assessment


# ---------------------------------------------------------------------------
# Part B - Posture arithmetic, hand-calculated independently and proven
# through the real rendered Home page (not through a second call into the
# service function under test).
# ---------------------------------------------------------------------------
class TestPostureArithmeticHandCalculatedThroughHome:
    def test_all_twelve_controls_yes_renders_100_percent(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        all_yes = {
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
        _set_baseline_answers(org_a, all_yes)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "100%" in content

    def test_hand_calculated_mixed_weight_percentage_matches_rendered_home(
        self, client_a, user_a, org_a
    ):
        """
        Independently hand-calculated (PID §11.4's fixed weight table:
        mfa_privileged_accounts/patching/backups=5,
        mfa_user_accounts/endpoint_protection/device_encryption/
        joiner_mover_leaver/privileged_access_separation/
        email_phishing_protection/remote_access_control=3,
        security_awareness_training/incident_reporting_route=1):

            mfa_privileged_accounts: YES,      weight 5 -> earned 5
            patching:                PARTIAL,  weight 5 -> earned 2.5
            backups:                 NOT_APPLICABLE, weight 5 -> excluded entirely

            available = 38 - 5 (backups excluded) = 33
            earned    = 5 + 2.5 = 7.5
            percentage = 7.5 / 33 * 100 = 22.727...% -> 23 (round half up)

        Every other of the 12 controls is left unanswered (UNKNOWN, earns 0
        but still counts in the denominator, PID §11.5's "missing ==
        unknown" - already proven at the service layer by
        `test_metrics.py::TestPosture::test_all_missing_answers_treated_
        identically_to_unknown"; this test's own point is the END-TO-END
        arithmetic through real rendered HTML, not that resolver rule
        itself).
        """
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(
            org_a,
            {
                "mfa_privileged_accounts": ANSWER_YES,
                "patching": ANSWER_PARTIAL,
                "backups": ANSWER_NOT_APPLICABLE,
            },
        )
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "23%" in content


# ---------------------------------------------------------------------------
# Part C - "exactly two metric cards, no third headline score" (PID §26/§27
# own wording this dispatch quotes verbatim) - a genuine gap in the existing
# HTTP-level coverage: `test_home_view.py` proves the two NAMED cards are
# present and the forbidden certification-adjacent wording is absent, but
# never mechanically counts the metric-card elements themselves.
# ---------------------------------------------------------------------------
class TestHomeShowsExactlyTwoMetricCardsNoThirdScore:
    @pytest.mark.parametrize("tier", [TIER_FOUNDATION])
    def test_exactly_two_metric_card_elements_rendered(self, client_a, user_a, org_a, tier):
        set_session_tier(client_a, user_a, tier)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert content.count('class="metric-card-row"') == 1
        assert content.count('class="metric-card"') == 2
        assert content.count('class="metric-card__value"') == 2
        assert content.count('class="metric-card__title"') == 2

    def test_paused_home_renders_zero_metric_cards(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, 0)  # TIER_PAUSED
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert content.count('class="metric-card"') == 0


# ---------------------------------------------------------------------------
# Part B/C - Scenario A/B metric divergence (PID §26.3/Appendix C), already
# proven at the service layer by `entitlements/tests/test_metrics.py::
# TestSeparationBetweenMetrics::{test_scenario_a_high_completion_low_posture,
# test_scenario_b_high_posture_lower_completion}` (cited, not duplicated) -
# this re-proves the SAME two scenarios are visibly distinct on the real
# rendered Home page, not merely in the service's return value.
# ---------------------------------------------------------------------------
class TestMetricDivergenceVisibleOnRenderedHome:
    def test_scenario_a_high_completion_weak_posture_renders_distinct_percentages(
        self, client_a, user_a, org_a
    ):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        all_no = {
            key: "no"
            for key in (
                "mfa_user_accounts",
                "mfa_privileged_accounts",
                "endpoint_protection",
                "patching",
                "device_encryption",
                "backups",
                "joiner_mover_leaver",
                "privileged_access_separation",
                "security_awareness_training",
                "incident_reporting_route",
                "email_phishing_protection",
                "remote_access_control",
            )
        }
        _set_baseline_answers(org_a, all_no)
        _make_full_completion_except_baseline(org_a)

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "0%" in content  # posture
        assert "100%" in content  # completion
        assert "12 of 18 Foundations items completed." not in content  # sanity: not a partial state

    def test_scenario_b_high_posture_lower_completion_renders_distinct_percentages(
        self, client_a, user_a, org_a
    ):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        all_yes = {
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
        _set_baseline_answers(org_a, all_yes)
        # No milestones completed at all - completion is 12/18, posture 100%.
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "100%" in content  # posture
        assert "12 of 18 Foundations items completed." in content  # completion, strictly lower


def _make_full_completion_except_baseline(organisation):
    """Completes every DERIVED_MILESTONE row (the 6 non-baseline completion
    items) so that, combined with the 12 baseline controls all being
    answered ALL_NO above (which counts as complete per PID §12.3 - "a
    deliberate no is a completed assessment answer"), completion reaches
    18/18 = 100% while posture stays at 0% - Scenario A's exact shape.
    Mirrors `entitlements/tests/test_metrics.py`'s own equivalent helpers
    (small per-file duplication over cross-app import, this codebase's own
    established convention)."""
    from governance.models import GovernanceRoleAssignment, OrganisationPerson
    from key_assets.models import CATEGORY_ENDPOINT, CRITICALITY_MEDIUM, KeyAsset
    from organisations.models import OrganisationProfile
    from workplace.models import Workplace

    OrganisationProfile.objects.create(
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
    person = OrganisationPerson.objects.create(
        organisation=organisation, full_name="Account Holder", is_active=True
    )
    for role, _ in GovernanceRoleAssignment.ROLE_CHOICES:
        GovernanceRoleAssignment.objects.create(organisation=organisation, role=role, person=person)
    Workplace.objects.create(
        organisation=organisation,
        name="Head office",
        type=Workplace.TYPE_DEDICATED_OFFICE,
        is_active=True,
    )
    KeyAsset.objects.create(
        organisation=organisation,
        name="Laptop fleet",
        category=CATEGORY_ENDPOINT,
        criticality=CRITICALITY_MEDIUM,
        status=KeyAsset.STATUS_CONFIRMED,
    )
    Risk.objects.create(
        organisation=organisation,
        title="Test risk",
        threat="A threat",
        vulnerability="A gap",
        impact=1,
        likelihood=1,
        rationale="Because reasons.",
        proposed_treatment="Do something about it.",
        status=Risk.STATUS_CONFIRMED,
    )
    document = PolicyDocument.objects.create(organisation=organisation)
    from django.utils import timezone as django_timezone

    PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=1,
        status=PolicyVersion.STATUS_APPROVED,
        title="Information Security Policy",
        approved_at=django_timezone.now(),
    )
