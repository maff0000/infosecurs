"""
Tests for security_state.services.get_security_state - the Current
Security State projection (PID §7, §7.1, §19 'Security State').
"""
import datetime

import pytest

from evidence import link_services
from evidence.models import ControlEvidenceLink, EvidenceItem
from remediation.models import RemediationAction
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
    BaselineAnswer,
    BaselineAssessment,
)
from security_state.services import (
    LABEL_CUSTOMER_STATED,
    LABEL_EVIDENCE_CONFLICT,
    LABEL_EVIDENCE_STALE,
    LABEL_NOT_APPLICABLE,
    LABEL_NOT_CONFIRMED,
    LABEL_SUPPORTING_EVIDENCE,
    get_security_state,
)

TODAY = datetime.date(2026, 9, 23)
CONTROL_KEY = "mfa_user_accounts"


def _set_answer(org, key, answer, note=""):
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": "test-v1"}
    )
    return BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=key, defaults={"answer": answer, "note": note}
    )[0]


def _reference_evidence(org, actor, valid_until=None, status=EvidenceItem.STATUS_ACTIVE, title="Evidence"):
    item = EvidenceItem.objects.create(
        organisation=org,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title=title,
        reference_url="https://example.test/evidence",
        recorded_by=actor,
        valid_until=valid_until,
    )
    if status != EvidenceItem.STATUS_ACTIVE:
        item.status = status
        item.save(update_fields=["status", "updated_at"])
    return item


def _link(org, evidence, key, relationship, actor):
    return link_services.link_evidence_to_control(org, evidence, key, relationship, "", actor)


def _row(org, key=CONTROL_KEY, today=TODAY):
    rows = {r["control_key"]: r for r in get_security_state(org, today=today)}
    return rows[key]


@pytest.mark.django_db
class TestNotConfirmed:
    def test_no_baseline_answer_row_at_all_is_not_confirmed(self, org_a):
        assert _row(org_a)["assurance_label"] == LABEL_NOT_CONFIRMED

    def test_explicit_unknown_answer_is_not_confirmed(self, org_a):
        _set_answer(org_a, CONTROL_KEY, ANSWER_UNKNOWN)
        assert _row(org_a)["assurance_label"] == LABEL_NOT_CONFIRMED

    def test_unknown_remains_not_confirmed_even_with_active_supporting_evidence(self, org_a, user_a):
        """
        PID §7.1: 'Evidence must never silently turn unknown into yes.'
        Unconditional - no evidence state overrides this.
        """
        _set_answer(org_a, CONTROL_KEY, ANSWER_UNKNOWN)
        evidence = _reference_evidence(org_a, user_a)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_NOT_CONFIRMED

    def test_evidence_never_silently_changes_the_canonical_baseline_answer(self, org_a, user_a):
        """
        PID §19: evidence never silently changes the canonical answer.
        Assert the DB row is unchanged after computing state.
        """
        answer_row = _set_answer(org_a, CONTROL_KEY, ANSWER_UNKNOWN)
        evidence = _reference_evidence(org_a, user_a)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        get_security_state(org_a, today=TODAY)
        answer_row.refresh_from_db()
        assert answer_row.answer == ANSWER_UNKNOWN


@pytest.mark.django_db
class TestNotApplicable:
    def test_not_applicable_is_unconditional_and_distinct(self, org_a, user_a):
        _set_answer(org_a, CONTROL_KEY, ANSWER_NOT_APPLICABLE)
        evidence = _reference_evidence(org_a, user_a)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_CONTRADICTS, user_a)
        row = _row(org_a)
        assert row["assurance_label"] == LABEL_NOT_APPLICABLE
        assert row["assurance_label"] not in (
            LABEL_NOT_CONFIRMED,
            LABEL_CUSTOMER_STATED,
            LABEL_SUPPORTING_EVIDENCE,
            LABEL_EVIDENCE_CONFLICT,
            LABEL_EVIDENCE_STALE,
        )


@pytest.mark.django_db
class TestCustomerStated:
    @pytest.mark.parametrize("answer", [ANSWER_YES, ANSWER_PARTIAL, ANSWER_NO])
    def test_answered_with_no_evidence_is_customer_stated(self, org_a, answer):
        _set_answer(org_a, CONTROL_KEY, answer)
        assert _row(org_a)["assurance_label"] == LABEL_CUSTOMER_STATED

    def test_context_only_evidence_does_not_change_customer_stated(self, org_a, user_a):
        """relationship=context links never affect the label."""
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        evidence = _reference_evidence(org_a, user_a)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_CONTEXT, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_CUSTOMER_STATED


@pytest.mark.django_db
class TestSupportingEvidence:
    def test_active_current_supporting_evidence_gives_supporting_label(self, org_a, user_a):
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        evidence = _reference_evidence(org_a, user_a)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_SUPPORTING_EVIDENCE

    def test_supporting_evidence_with_no_valid_until_counts_as_current(self, org_a, user_a):
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        evidence = _reference_evidence(org_a, user_a, valid_until=None)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_SUPPORTING_EVIDENCE

    def test_supporting_evidence_valid_until_today_counts_as_current(self, org_a, user_a):
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        evidence = _reference_evidence(org_a, user_a, valid_until=TODAY)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_SUPPORTING_EVIDENCE


@pytest.mark.django_db
class TestEvidenceConflict:
    def test_active_contradicting_evidence_gives_conflict_label(self, org_a, user_a):
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        evidence = _reference_evidence(org_a, user_a)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_CONTRADICTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_EVIDENCE_CONFLICT

    def test_conflict_outranks_a_simultaneously_present_supporting_link(self, org_a, user_a):
        """PID §7.1: 'This outranks supporting/stale labels.'"""
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        supporting = _reference_evidence(org_a, user_a, title="Supporting")
        contradicting = _reference_evidence(org_a, user_a, title="Contradicting")
        _link(org_a, supporting, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        _link(org_a, contradicting, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_CONTRADICTS, user_a)
        row = _row(org_a)
        assert row["assurance_label"] == LABEL_EVIDENCE_CONFLICT
        assert len(row["active_supporting_evidence"]) == 1
        assert len(row["active_contradictory_evidence"]) == 1


@pytest.mark.django_db
class TestEvidenceStale:
    def test_expired_valid_until_supporting_evidence_with_no_active_support_is_stale(self, org_a, user_a):
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        evidence = _reference_evidence(org_a, user_a, valid_until=TODAY - datetime.timedelta(days=1))
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_EVIDENCE_STALE

    def test_superseded_supporting_evidence_is_stale(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a, status=EvidenceItem.STATUS_SUPERSEDED)
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_EVIDENCE_STALE

    def test_withdrawn_supporting_evidence_is_stale(self, org_a, user_a):
        evidence = _reference_evidence(org_a, user_a, status=EvidenceItem.STATUS_WITHDRAWN)
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        _link(org_a, evidence, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        assert _row(org_a)["assurance_label"] == LABEL_EVIDENCE_STALE


@pytest.mark.django_db
class TestFullPrecedenceOrder:
    def test_active_current_support_wins_over_a_simultaneous_stale_support(self, org_a, user_a):
        """
        PID §19: construct a control with both an active-current
        supporting link and a stale supporting link - confirm it reports
        'Supporting evidence attached', not 'Evidence stale'.
        """
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        current = _reference_evidence(org_a, user_a, title="Current", valid_until=None)
        stale = _reference_evidence(
            org_a, user_a, title="Stale", valid_until=TODAY - datetime.timedelta(days=30)
        )
        _link(org_a, current, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        _link(org_a, stale, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_SUPPORTS, user_a)
        row = _row(org_a)
        assert row["assurance_label"] == LABEL_SUPPORTING_EVIDENCE
        assert row["assurance_label"] != LABEL_EVIDENCE_STALE
        assert len(row["active_supporting_evidence"]) == 1
        assert len(row["stale_evidence"]) == 1


@pytest.mark.django_db
class TestOpenRemediationCount:
    def test_counts_only_active_status_actions_for_this_control(self, org_a, user_a):
        RemediationAction.objects.create(
            organisation=org_a, title="Open one", control_key=CONTROL_KEY,
            status=RemediationAction.STATUS_OPEN, created_by=user_a,
        )
        RemediationAction.objects.create(
            organisation=org_a, title="In progress one", control_key=CONTROL_KEY,
            status=RemediationAction.STATUS_IN_PROGRESS, created_by=user_a,
        )
        RemediationAction.objects.create(
            organisation=org_a, title="Done one", control_key=CONTROL_KEY,
            status=RemediationAction.STATUS_DONE, created_by=user_a,
        )
        RemediationAction.objects.create(
            organisation=org_a, title="Unrelated control", control_key="backups",
            status=RemediationAction.STATUS_OPEN, created_by=user_a,
        )
        assert _row(org_a)["open_remediation_count"] == 2


@pytest.mark.django_db
class TestTenantIsolationOfProjection:
    """PID §16/§19: organisation A's projection must never include
    organisation B's evidence/links/actions."""

    def test_org_b_evidence_and_links_never_affect_org_as_projection(self, org_a, org_b, user_a, user_b):
        _set_answer(org_a, CONTROL_KEY, ANSWER_YES)
        _set_answer(org_b, CONTROL_KEY, ANSWER_YES)
        # Org B has contradicting evidence, which would flip org A's label
        # to "Evidence conflict" if it leaked across tenants.
        evidence_b = _reference_evidence(org_b, user_b, title="Org B contradicting evidence")
        _link(org_b, evidence_b, CONTROL_KEY, ControlEvidenceLink.RELATIONSHIP_CONTRADICTS, user_b)

        row_a = _row(org_a)
        assert row_a["assurance_label"] == LABEL_CUSTOMER_STATED
        assert row_a["active_contradictory_evidence"] == []
        assert row_a["evidence_counts"]["contradicts"] == 0

    def test_org_b_remediation_actions_never_affect_org_as_open_count(self, org_a, org_b, user_a, user_b):
        RemediationAction.objects.create(
            organisation=org_b, title="Org B action", control_key=CONTROL_KEY,
            status=RemediationAction.STATUS_OPEN, created_by=user_b,
        )
        assert _row(org_a)["open_remediation_count"] == 0
