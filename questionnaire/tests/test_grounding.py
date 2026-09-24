"""
Tenant-safety + shape tests for
`questionnaire.grounding.build_questionnaire_grounding_snapshot` (M005 PID
§7.3, §11, §23, §27 - m005-1-foundation dispatch), mirroring
`policy/tests/test_grounding.py`'s own "two organisations, prove org A's
snapshot never contains org B's facts" discipline.
"""
import datetime

import pytest

from evidence.models import ControlEvidenceLink, EvidenceItem
from organisations.models import OrganisationProfile
from policy.models import PolicyDocument, PolicyVersion
from remediation.models import RemediationAction
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment
from questionnaire.grounding import build_questionnaire_grounding_snapshot

pytestmark = pytest.mark.django_db

CONTROL_KEY = "control:mfa_privileged_accounts"
BASELINE_KEY = "mfa_privileged_accounts"


def _set_answer(org, key, answer, note=""):
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    return BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=key, defaults={"answer": answer, "note": note}
    )[0]


def _profile(org, **overrides):
    defaults = dict(
        legal_trading_name=f"{org.name} Legal",
        cyber_essentials_status="certified",
        iso27001_status="in_progress",
        working_model="hybrid",
        handles_personal_data="yes",
    )
    defaults.update(overrides)
    return OrganisationProfile.objects.create(organisation=org, **defaults)


def _approved_policy_version(org, sections):
    document, _ = PolicyDocument.objects.get_or_create(organisation=org)
    return PolicyVersion.objects.create(
        document=document,
        organisation=org,
        version_number=1,
        status=PolicyVersion.STATUS_APPROVED,
        title="Org Information Security Policy",
        sections=sections,
        review_warnings=[],
    )


# --- Control facts -------------------------------------------------------------

def test_control_fact_basic_shape(org_a):
    _set_answer(org_a, BASELINE_KEY, "yes")
    snapshot = build_questionnaire_grounding_snapshot(org_a, [CONTROL_KEY])
    entry = snapshot[CONTROL_KEY]
    assert entry["answer"] == "yes"
    assert entry["assurance_label"]
    assert entry["active_supporting_evidence_count"] == 0
    assert entry["active_contradicting_evidence_count"] == 0
    assert entry["stale_evidence_count"] == 0
    assert entry["open_remediation_count"] == 0
    assert entry["relevant_remediation"] == []


def test_control_fact_never_carries_evidence_bytes_or_free_text(org_a, user_a):
    _set_answer(org_a, BASELINE_KEY, "yes")
    evidence = EvidenceItem.objects.create(
        organisation=org_a,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title="Secret evidence title",
        description="Secret evidence description that must never leave the tenant boundary.",
        reference_url="https://example.test/secret",
        recorded_by=user_a,
    )
    ControlEvidenceLink.objects.create(
        organisation=org_a,
        evidence=evidence,
        control_key=BASELINE_KEY,
        relationship=ControlEvidenceLink.RELATIONSHIP_SUPPORTS,
        linked_by=user_a,
    )
    snapshot = build_questionnaire_grounding_snapshot(org_a, [CONTROL_KEY])
    entry = snapshot[CONTROL_KEY]
    assert entry["active_supporting_evidence_count"] == 1
    serialised = str(entry)
    assert "Secret evidence title" not in serialised
    assert "Secret evidence description" not in serialised
    assert "example.test/secret" not in serialised


# --- Owner/target-date honesty (ADR-0003 §5, PID §11 "Do not invent owner/date") --

def test_remediation_owner_and_target_date_are_none_when_absent(org_a):
    _set_answer(org_a, BASELINE_KEY, "partial")
    RemediationAction.objects.create(
        organisation=org_a,
        title="Enable MFA on remaining privileged accounts",
        control_key=BASELINE_KEY,
        status=RemediationAction.STATUS_OPEN,
        assigned_to=None,
        target_date=None,
    )
    snapshot = build_questionnaire_grounding_snapshot(org_a, [CONTROL_KEY])
    remediation = snapshot[CONTROL_KEY]["relevant_remediation"]
    assert len(remediation) == 1
    assert remediation[0]["owner"] is None
    assert remediation[0]["target_date"] is None
    assert remediation[0]["status"] == RemediationAction.STATUS_OPEN
    assert remediation[0]["treatment_summary"] == "Enable MFA on remaining privileged accounts"


def test_remediation_owner_and_target_date_present_when_recorded(org_a, user_a):
    _set_answer(org_a, BASELINE_KEY, "partial")
    user_a.first_name = "Ada"
    user_a.last_name = "Holder"
    user_a.save()
    RemediationAction.objects.create(
        organisation=org_a,
        title="Enable MFA on remaining privileged accounts",
        control_key=BASELINE_KEY,
        status=RemediationAction.STATUS_IN_PROGRESS,
        assigned_to=user_a,
        target_date=datetime.date(2026, 12, 1),
    )
    snapshot = build_questionnaire_grounding_snapshot(org_a, [CONTROL_KEY])
    remediation = snapshot[CONTROL_KEY]["relevant_remediation"][0]
    assert remediation["owner"] == "Ada Holder"
    assert remediation["target_date"] == "2026-12-01"


def test_only_active_remediation_statuses_are_included(org_a):
    _set_answer(org_a, BASELINE_KEY, "partial")
    RemediationAction.objects.create(
        organisation=org_a,
        title="Already done",
        control_key=BASELINE_KEY,
        status=RemediationAction.STATUS_DONE,
    )
    snapshot = build_questionnaire_grounding_snapshot(org_a, [CONTROL_KEY])
    assert snapshot[CONTROL_KEY]["relevant_remediation"] == []


# --- Policy-section facts -------------------------------------------------------

def test_policy_section_fact_no_approved_policy(org_a):
    key = "policy_section:access_and_authentication"
    snapshot = build_questionnaire_grounding_snapshot(org_a, [key])
    entry = snapshot[key]
    assert entry["policy_exists"] is False
    assert entry["approved_version_number"] is None
    assert entry["section_present"] is False
    assert entry["section_content"] is None


def test_policy_section_fact_approved_with_matching_section(org_a):
    _approved_policy_version(
        org_a,
        sections=[
            {"section_key": "access_and_authentication", "content": "MFA is required for privileged accounts."}
        ],
    )
    key = "policy_section:access_and_authentication"
    snapshot = build_questionnaire_grounding_snapshot(org_a, [key])
    entry = snapshot[key]
    assert entry["policy_exists"] is True
    assert entry["approved_version_number"] == 1
    assert entry["section_present"] is True
    assert entry["section_content"] == "MFA is required for privileged accounts."


def test_policy_section_fact_approved_but_section_missing(org_a):
    _approved_policy_version(
        org_a, sections=[{"section_key": "purpose_and_scope", "content": "Purpose text."}]
    )
    key = "policy_section:access_and_authentication"
    snapshot = build_questionnaire_grounding_snapshot(org_a, [key])
    entry = snapshot[key]
    assert entry["policy_exists"] is True
    assert entry["section_present"] is False
    assert entry["section_content"] is None


def test_draft_policy_version_does_not_count_as_existing(org_a):
    document, _ = PolicyDocument.objects.get_or_create(organisation=org_a)
    PolicyVersion.objects.create(
        document=document,
        organisation=org_a,
        version_number=1,
        status=PolicyVersion.STATUS_DRAFT,
        title="Draft only",
        sections=[{"section_key": "access_and_authentication", "content": "Draft text."}],
    )
    key = "policy_section:access_and_authentication"
    snapshot = build_questionnaire_grounding_snapshot(org_a, [key])
    assert snapshot[key]["policy_exists"] is False


# --- Organisation facts ---------------------------------------------------------

def test_org_certification_facts(org_a):
    _profile(org_a)
    snapshot = build_questionnaire_grounding_snapshot(
        org_a, ["org:certification_cyber_essentials", "org:certification_iso27001"]
    )
    assert snapshot["org:certification_cyber_essentials"]["value"] == "certified"
    assert snapshot["org:certification_iso27001"]["value"] == "in_progress"


def test_org_working_model_includes_workplace_summary(org_a):
    from workplace.models import Workplace

    _profile(org_a)
    Workplace.objects.create(
        organisation=org_a,
        name="HQ",
        type=Workplace.TYPE_DEDICATED_OFFICE,
        location_label="London",
        approx_people_count=12,
        is_active=True,
    )
    snapshot = build_questionnaire_grounding_snapshot(org_a, ["org:working_model"])
    entry = snapshot["org:working_model"]
    assert entry["value"] == "hybrid"
    assert entry["workplaces"] == [
        {"name": "HQ", "type": Workplace.TYPE_DEDICATED_OFFICE, "location_label": "London", "approx_people_count": 12}
    ]


def test_org_fact_without_profile_defaults_to_unknown(org_a):
    snapshot = build_questionnaire_grounding_snapshot(org_a, ["org:handles_personal_data"])
    assert snapshot["org:handles_personal_data"]["value"] == "unknown"


# --- Tenant isolation (PID §23, §11) --------------------------------------------

def test_grounding_snapshot_never_contains_other_organisations_facts(org_a, org_b, user_a, user_b):
    _set_answer(org_a, BASELINE_KEY, "yes")
    _set_answer(org_b, BASELINE_KEY, "no")

    RemediationAction.objects.create(
        organisation=org_b,
        title="SECRET ORG B REMEDIATION TITLE",
        control_key=BASELINE_KEY,
        status=RemediationAction.STATUS_OPEN,
    )
    _profile(org_b, legal_trading_name="Secret Org B Legal Name", working_model="office")
    _approved_policy_version(
        org_b, sections=[{"section_key": "access_and_authentication", "content": "SECRET ORG B POLICY TEXT"}]
    )

    snapshot = build_questionnaire_grounding_snapshot(
        org_a, [CONTROL_KEY, "policy_section:access_and_authentication", "org:working_model"]
    )

    serialised = str(snapshot)
    assert "SECRET ORG B REMEDIATION TITLE" not in serialised
    assert "SECRET ORG B POLICY TEXT" not in serialised
    assert "Secret Org B Legal Name" not in serialised
    # org_a has no policy/profile set up at all in this test, so the
    # control answer must be org_a's own ("yes"), never org_b's ("no").
    assert snapshot[CONTROL_KEY]["answer"] == "yes"


def test_grounding_snapshot_only_covers_selected_keys(org_a):
    _set_answer(org_a, BASELINE_KEY, "yes")
    _set_answer(org_a, "backups", "no")
    snapshot = build_questionnaire_grounding_snapshot(org_a, [CONTROL_KEY])
    assert list(snapshot.keys()) == [CONTROL_KEY]
    assert "control:backups" not in snapshot
