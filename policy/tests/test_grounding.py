"""
Tenant-safety + shape tests for `policy.grounding.build_policy_grounding_payload`
(PID §12, §23, §26 "Policy grounding" - m004-2a-policy-foundation dispatch).
"""
import pytest

from ai_platform.policy_contracts import PolicyGroundingPayload
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from organisations.models import OrganisationProfile
from policy.grounding import build_policy_grounding_payload
from risk_register.models import Risk
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAssessment, BaselineAnswer
from workplace.models import Workplace


def _full_setup(organisation, *, suffix):
    OrganisationProfile.objects.create(
        organisation=organisation,
        legal_trading_name=f"{organisation.name} Legal",
        description=f"Secret description for {suffix}",
        staff_count=42,
    )
    Workplace.objects.create(
        organisation=organisation,
        name=f"Secret workplace {suffix}",
        type=Workplace.TYPE_DEDICATED_OFFICE,
        location_label=f"Secret location {suffix}",
        approx_people_count=10,
        is_active=True,
    )
    # An inactive workplace must never surface.
    Workplace.objects.create(
        organisation=organisation,
        name=f"Inactive workplace {suffix}",
        type=Workplace.TYPE_DISTRIBUTED_HOME,
        is_active=False,
    )
    person = OrganisationPerson.objects.create(
        organisation=organisation,
        full_name=f"Secret Person {suffix}",
        job_title=f"Secret Title {suffix}",
    )
    GovernanceRoleAssignment.objects.create(
        organisation=organisation,
        role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
        person=person,
    )
    assessment = BaselineAssessment.objects.create(
        organisation=organisation, catalogue_version=CATALOGUE_VERSION
    )
    BaselineAnswer.objects.create(
        assessment=assessment,
        question_key="mfa_user_accounts",
        answer="unknown",
        note=f"Secret baseline note {suffix}",
    )
    Risk.objects.create(
        organisation=organisation,
        title=f"Secret confirmed risk {suffix}",
        threat="t",
        vulnerability="v",
        impact=4,
        likelihood=3,
        rationale="r",
        proposed_treatment="p",
        status=Risk.STATUS_CONFIRMED,
        source=Risk.SOURCE_MANUAL,
    )
    # A draft/dismissed risk must never surface in open_risk_facts.
    Risk.objects.create(
        organisation=organisation,
        title=f"Secret draft risk {suffix}",
        threat="t",
        vulnerability="v",
        impact=2,
        likelihood=2,
        rationale="r",
        proposed_treatment="p",
        status=Risk.STATUS_DRAFT_AI_SUGGESTED,
        source=Risk.SOURCE_AI,
    )
    return person


@pytest.mark.django_db
class TestPolicyGroundingShape:
    def test_returns_a_valid_policy_grounding_payload(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        assert isinstance(payload, PolicyGroundingPayload)
        assert payload.organisation_id == str(org_a.pk)

    def test_organisation_facts_shape(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        assert payload.organisation_facts["name"] == org_a.name
        assert payload.organisation_facts["staff_count"] == 42
        assert payload.organisation_facts["description"] == "Secret description for A"

    def test_organisation_facts_default_when_no_profile(self, org_a):
        payload = build_policy_grounding_payload(org_a)
        assert payload.organisation_facts["name"] == org_a.name
        assert payload.organisation_facts["staff_count"] is None

    def test_workplace_facts_only_active(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        names = {w["name"] for w in payload.workplace_facts}
        assert "Secret workplace A" in names
        assert "Inactive workplace A" not in names

    def test_governance_facts_keyed_by_role(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        entry = payload.governance_facts[GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER]
        assert entry["full_name"] == "Secret Person A"
        assert entry["job_title"] == "Secret Title A"

    def test_baseline_facts_preserve_unknown_not_convert_to_yes_or_no(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        assert payload.baseline_facts["mfa_user_accounts"]["answer"] == "unknown"
        assert payload.baseline_facts["mfa_user_accounts"]["note"] == "Secret baseline note A"

    def test_security_state_facts_only_permitted_keys(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        entry = payload.security_state_facts["mfa_user_accounts"]
        assert set(entry.keys()) == {
            "area",
            "answer",
            "answer_label",
            "assurance_label",
            "open_remediation_count",
        }
        assert entry["answer"] == "unknown"

    def test_security_state_facts_never_carry_evidence(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        for entry in payload.security_state_facts.values():
            assert "active_supporting_evidence" not in entry
            assert "active_contradictory_evidence" not in entry
            assert "context_evidence" not in entry
            assert "evidence_counts" not in entry

    def test_open_risk_facts_only_confirmed(self, org_a):
        _full_setup(org_a, suffix="A")
        payload = build_policy_grounding_payload(org_a)
        titles = {r["title"] for r in payload.open_risk_facts}
        assert "Secret confirmed risk A" in titles
        assert "Secret draft risk A" not in titles
        for entry in payload.open_risk_facts:
            assert set(entry.keys()) == {"title", "risk_band", "status"}


@pytest.mark.django_db
class TestPolicyGroundingTenantIsolation:
    """PID §23, §26 'Policy grounding': exact tenant only."""

    def test_organisation_a_payload_never_contains_organisation_bs_data(self, org_a, org_b):
        _full_setup(org_a, suffix="A")
        _full_setup(org_b, suffix="B")

        payload_a = build_policy_grounding_payload(org_a)

        assert payload_a.organisation_facts["description"] == "Secret description for A"
        assert "B" not in payload_a.organisation_facts["description"]

        workplace_names = {w["name"] for w in payload_a.workplace_facts}
        assert workplace_names == {"Secret workplace A"}
        assert "Secret workplace B" not in workplace_names

        governance_names = {v["full_name"] for v in payload_a.governance_facts.values()}
        assert governance_names == {"Secret Person A"}
        assert "Secret Person B" not in governance_names

        baseline_notes = {v["note"] for v in payload_a.baseline_facts.values()}
        assert "Secret baseline note B" not in baseline_notes

        risk_titles = {r["title"] for r in payload_a.open_risk_facts}
        assert risk_titles == {"Secret confirmed risk A"}
        assert "Secret confirmed risk B" not in risk_titles

    def test_organisation_b_payload_never_contains_organisation_as_data(self, org_a, org_b):
        _full_setup(org_a, suffix="A")
        _full_setup(org_b, suffix="B")

        payload_b = build_policy_grounding_payload(org_b)

        workplace_names = {w["name"] for w in payload_b.workplace_facts}
        assert workplace_names == {"Secret workplace B"}

        risk_titles = {r["title"] for r in payload_b.open_risk_facts}
        assert risk_titles == {"Secret confirmed risk B"}
