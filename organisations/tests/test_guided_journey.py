"""
M008-WI5 tests for `organisations.guided_journey.current_guided_stage` -
the resolver behind Home's new "Continue Security Foundations" CTA
(docs/design/M008C-UX-FLOW-DESIGN.md §5).

Every stage transition below is driven through REAL write paths - the
same ones a real customer's data would go through - never a
hand-constructed shortcut:

- Stage 1/2/3: the Django test client POSTing to the real
  `organisations:stage1_business`/`stage2_people_workplaces`/
  `stage3_technology_data` views (the exact `OrganisationProfileStage*Form`
  instances those views already use).
- Stage 2's workplace/governance facts: real `workplace.Workplace` rows
  and `governance.services.assign_role` calls (the same service the real
  governance UI uses).
- Stage 4: `security_baseline.services.record_structured_baseline_answer`
  - the sole real write path for a structured Stage 4 answer.
- Stage 6: the real `policy.services.generate_policy_draft_deterministic`
  + `policy.services.approve_policy_directly` service calls.
"""
from __future__ import annotations

import datetime
import inspect

import pytest
from django.urls import reverse

from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import assign_role
from organisations import guided_journey
from organisations.guided_journey import current_guided_stage
from organisations.models import (
    DRIVER_CUSTOMER_SUPPLIER,
    NO,
    SECTOR_TECHNOLOGY_SOFTWARE,
    YES,
)
from policy.services import approve_policy_directly, generate_policy_draft_deterministic
from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.services import record_structured_baseline_answer
from security_baseline.structured_catalogue import STRUCTURED_OPTIONS
from workplace.models import Workplace

pytestmark = pytest.mark.django_db

# Any valid, real option_code per control - "reviewed" counts ANY
# deliberate selection, so the specific strength of the answer doesn't
# matter here, only that all 12 have been reviewed (mirrors
# security_baseline.stage4's own EXPLAINER_TEXT keys - these are real,
# defined option codes, not invented strings).
_ALL_CONTROL_OPTION_CODES = {
    "mfa_user_accounts": "MFA_USER_ALL_REQUIRED",
    "mfa_privileged_accounts": "MFA_ADMIN_ALL_REQUIRED",
    "endpoint_protection": "ENDPOINT_PROTECTION_ALL",
    "patching": "PATCHING_AUTOMATIC",
    "device_encryption": "DEVICE_ENCRYPTION_ALL",
    "backups": "BACKUPS_TESTED",
    "joiner_mover_leaver": "JML_DEFINED_FOLLOWED",
    "privileged_access_separation": "PRIV_SEP_DEDICATED",
    "security_awareness_training": "AWARENESS_REGULAR",
    "incident_reporting_route": "INCIDENT_ROUTE_CLEAR",
    "email_phishing_protection": "PHISHING_PROTECTION_ACTIVE_ALL",
    "remote_access_control": "REMOTE_ACCESS_GOVERNED",
}
assert set(_ALL_CONTROL_OPTION_CODES) == set(CATALOGUE_KEYS)


def _complete_stage1(client, org):
    response = client.post(
        reverse("organisations:stage1_business", args=[org.id]),
        {
            "legal_trading_name": "Org A Synthetic Ltd",
            "sector": SECTOR_TECHNOLOGY_SOFTWARE,
            "staff_count": "12",
            "commercial_security_driver": DRIVER_CUSTOMER_SUPPLIER,
            "receives_security_questionnaires": YES,
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]


def _complete_stage2(client, org, user):
    # §2.1/§2.2 (work pattern/workplaces) - a real active Workplace row.
    Workplace.objects.create(
        organisation=org,
        name="Home / remote working",
        type=Workplace.TYPE_DISTRIBUTED_HOME,
        is_active=True,
    )
    # §2.5 (governance roles) - a real governance person, all three roles
    # assigned via the real service function.
    person = OrganisationPerson.objects.create(
        organisation=org, full_name="Account Holder", user=user
    )
    for role, _label in GovernanceRoleAssignment.ROLE_CHOICES:
        assign_role(organisation=org, role=role, person=person, assigned_by=user)
    # §2.3/§2.4 - the two Stage-2-owned dedicated facts, via the real form/view.
    response = client.post(
        reverse("organisations:stage2_people_workplaces", args=[org.id]),
        {"people_with_system_access_count": "5", "has_remote_or_offsite_access": YES},
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    return person


def _complete_stage3(client, org):
    response = client.post(
        reverse("organisations:stage3_technology_data", args=[org.id]),
        {
            "productivity_platform": "microsoft_365",
            "primary_cloud_provider": "azure",
            "endpoint_management": "company_managed",
            "develops_hosts_own_software": NO,
            "handles_personal_data": YES,
            "handles_confidential_business_data": YES,
            "handles_payment_card_data": NO,
            "handles_special_category_data": NO,
            "cyber_essentials_status": "not_certified",
            "iso27001_status": "not_certified",
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]


def _complete_stage4(org, actor):
    for control_key, option_code in _ALL_CONTROL_OPTION_CODES.items():
        record_structured_baseline_answer(org, control_key, option_code, actor=actor)


# ---------------------------------------------------------------------------
# Zero AI/LLM calls (same import-statement-level technique as
# organisations/tests/test_stage_forms_no_free_text_and_zero_ai.py).
# ---------------------------------------------------------------------------
class TestGuidedJourneyMakesZeroAICalls:
    def test_module_has_no_ai_platform_or_interpretation_service_import(self):
        """Import-statement-level only (not a blunt whole-source substring
        search) - same technique, and same reason, as organisations/tests/
        test_stage_forms_no_free_text_and_zero_ai.py's own identically-named
        test: a blunt substring check would false-positive on this very
        module's own docstring, which explains in prose why it makes zero
        AI calls and therefore necessarily names `ai_platform`/
        `risk_register.interpretation_service` in that explanation."""
        source = inspect.getsource(guided_journey)
        for line in source.splitlines():
            stripped = line.strip()
            assert not stripped.startswith("import ai_platform")
            assert not stripped.startswith("from ai_platform")
            assert not stripped.startswith("import risk_register.interpretation_service")
            assert not stripped.startswith("from risk_register.interpretation_service")
            assert not stripped.startswith("import risk_register ")

    def test_module_object_has_no_ai_platform_attribute_bound(self):
        assert not any(
            name == "ai_platform" or name.startswith("ai_platform_")
            for name in vars(guided_journey)
        )


# ---------------------------------------------------------------------------
# Stage-by-stage resolution.
# ---------------------------------------------------------------------------
class TestCurrentGuidedStage:
    def test_fresh_organisation_resolves_to_stage_1(self, org_a):
        stage = current_guided_stage(org_a)
        assert stage.number == 1
        assert stage.name == "Your Business"
        assert stage.url == reverse("organisations:stage1_business", args=[org_a.id])
        assert stage.is_complete is False

    def test_completing_stage1_only_moves_to_stage_2(self, client_a, org_a):
        _complete_stage1(client_a, org_a)

        stage = current_guided_stage(org_a)
        assert stage.number == 2
        assert stage.name == "Your People & Workplaces"
        assert stage.url == reverse("organisations:stage2_people_workplaces", args=[org_a.id])

    def test_completing_stage2_moves_to_stage_3(self, client_a, org_a, user_a):
        _complete_stage1(client_a, org_a)
        _complete_stage2(client_a, org_a, user_a)

        stage = current_guided_stage(org_a)
        assert stage.number == 3
        assert stage.name == "Your Technology & Data"
        assert stage.url == reverse("organisations:stage3_technology_data", args=[org_a.id])

    def test_completing_stage3_moves_to_stage_4_without_any_key_asset(self, client_a, org_a, user_a):
        """Judgement call 1 (guided_journey module docstring): Stage 3
        completion does NOT require any confirmed KeyAsset - zero
        KeyAsset rows exist anywhere in this test, and Stage 3 still
        resolves complete."""
        _complete_stage1(client_a, org_a)
        _complete_stage2(client_a, org_a, user_a)
        _complete_stage3(client_a, org_a)

        stage = current_guided_stage(org_a)
        assert stage.number == 4
        assert stage.name == "Your Security Foundations"
        assert stage.url == reverse("security_baseline:foundations_start", args=[org_a.id])

    def test_completing_stage4_moves_straight_to_stage_6_skipping_stage_5(
        self, client_a, org_a, user_a
    ):
        """Judgement call 2: Stage 5 ('Your Risks & Actions') never gates
        - no Risk/RemediationAction row exists anywhere in this test, and
        the resolver still moves straight from Stage 4 to Stage 6."""
        _complete_stage1(client_a, org_a)
        _complete_stage2(client_a, org_a, user_a)
        _complete_stage3(client_a, org_a)
        _complete_stage4(org_a, user_a)

        stage = current_guided_stage(org_a)
        assert stage.number == 6
        assert stage.name == "Your Security Policy"
        assert stage.url == reverse("policy:detail", args=[org_a.id])
        assert stage.is_complete is False

    def test_approved_policy_reaches_the_stage_6_terminal_state(self, client_a, org_a, user_a):
        """Judgement call 3: once an approved PolicyVersion exists, there
        is nothing further to 'Continue' to - the resolver reports the
        terminal state (still Stage 6, `is_complete=True`)."""
        _complete_stage1(client_a, org_a)
        _complete_stage2(client_a, org_a, user_a)
        _complete_stage3(client_a, org_a)
        _complete_stage4(org_a, user_a)

        draft = generate_policy_draft_deterministic(org_a, actor=user_a)
        approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date.today() + datetime.timedelta(days=180)
        )

        stage = current_guided_stage(org_a)
        assert stage.number == 6
        assert stage.name == "Your Security Policy"
        assert stage.url == reverse("policy:detail", args=[org_a.id])
        assert stage.is_complete is True

    def test_only_a_deliberately_reviewed_not_sure_answer_still_counts_toward_stage_4(
        self, client_a, org_a, user_a
    ):
        """Stage 4 completion is `reviewed == 12`, never `complete`
        (M008C-UX-FLOW-DESIGN.md §6) - an honest 'Not sure' on every
        control is still 12 reviewed, so the resolver must still move on
        to Stage 6, not get stuck re-showing Stage 4."""
        _complete_stage1(client_a, org_a)
        _complete_stage2(client_a, org_a, user_a)
        _complete_stage3(client_a, org_a)
        for control_key in CATALOGUE_KEYS:
            not_sure_code = next(
                code for code in STRUCTURED_OPTIONS[control_key] if code.endswith("_NOT_SURE")
            )
            record_structured_baseline_answer(org_a, control_key, not_sure_code, actor=user_a)

        stage = current_guided_stage(org_a)
        assert stage.number == 6

    def test_takes_a_real_organisation_object_two_orgs_resolve_independently(
        self, client_a, org_a, client_b, org_b, user_a
    ):
        """Tenant-scoping sanity check: `current_guided_stage` takes a
        real `organisation` object (never a bare id with its own lookup)
        - completing org_a's Stage 1 must never affect org_b's own,
        completely independent resolution."""
        assert current_guided_stage(org_a).number == 1
        assert current_guided_stage(org_b).number == 1

        _complete_stage1(client_a, org_a)

        assert current_guided_stage(org_a).number == 2
        assert current_guided_stage(org_b).number == 1


# ---------------------------------------------------------------------------
# Home view wiring (organisations.views.organisation_detail).
# ---------------------------------------------------------------------------
class TestHomeCTAWiring:
    def test_fresh_org_home_shows_stage_1_cta(self, client_a, org_a, user_a):
        from entitlements.tests.conftest import set_session_tier
        from entitlements.tiers import TIER_FOUNDATION

        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "Continue Security Foundations" in content
        assert "Stage 1 of 6 — Your Business" in content
        assert reverse("organisations:stage1_business", args=[org_a.id]) in content

    def test_terminal_state_shows_review_policy_wording(self, client_a, org_a, user_a):
        from entitlements.tests.conftest import set_session_tier
        from entitlements.tiers import TIER_FOUNDATION

        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _complete_stage1(client_a, org_a)
        _complete_stage2(client_a, org_a, user_a)
        _complete_stage3(client_a, org_a)
        _complete_stage4(org_a, user_a)
        draft = generate_policy_draft_deterministic(org_a, actor=user_a)
        approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date.today() + datetime.timedelta(days=180)
        )

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "Review your Security Policy" in content
        assert "All 6 guided Foundations stages are complete" in content
        assert "Continue Security Foundations" not in content

    def test_paused_home_never_calls_the_guided_stage_resolver(self, client_a, org_a, user_a, monkeypatch):
        """PID §13.1 / this WI's own non-negotiable: the Paused branch gets
        ZERO new calls. Patches `organisations.views.current_guided_stage`
        itself to raise if it is ever called, then proves a Paused
        request still renders 200."""
        from entitlements.tests.conftest import set_session_tier
        from entitlements.tiers import TIER_PAUSED

        def _boom(_organisation):
            raise AssertionError("current_guided_stage must never be called for a Paused session")

        monkeypatch.setattr("organisations.views.current_guided_stage", _boom)

        set_session_tier(client_a, user_a, TIER_PAUSED)
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert "Continue Security Foundations" not in response.content.decode()
