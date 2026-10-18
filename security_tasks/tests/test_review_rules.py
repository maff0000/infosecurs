"""
M010D rule-registry tests (docs/pids/M010D-REVIEW-RULES-SCHEDULER.md §1/§2/§6).
Pure candidate-computation tests for `security_tasks.review_rules` - no
task is ever created here (see test_review_scheduler.py for the
emission/reconciliation layer).
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone as django_timezone

from evidence.models import EvidenceItem
from policy.models import PolicyDocument, PolicyVersion
from remediation.models import RemediationAction
from security_tasks import review_rules
from security_tasks.models import TaskKind


UTC = dt.timezone.utc


def _make_policy_version(org, *, status=PolicyVersion.STATUS_APPROVED, next_review_date=None, version_number=1):
    document, _ = PolicyDocument.objects.get_or_create(organisation=org)
    return PolicyVersion.objects.create(
        document=document,
        organisation=org,
        version_number=version_number,
        status=status,
        title="Information Security Policy",
        next_review_date=next_review_date,
        approved_at=django_timezone.now() if status != PolicyVersion.STATUS_DRAFT else None,
    )


def _make_remediation_action(org, *, status=RemediationAction.STATUS_OPEN, target_date=None, assigned_to=None):
    return RemediationAction.objects.create(
        organisation=org,
        title="Enable MFA on the admin console",
        status=status,
        target_date=target_date,
        assigned_to=assigned_to,
    )


def _make_evidence_item(org, *, status=EvidenceItem.STATUS_ACTIVE, valid_until=None):
    return EvidenceItem.objects.create(
        organisation=org,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title="Cyber Essentials certificate",
        status=status,
        valid_until=valid_until,
        reference_url="https://example.invalid/certificate",
    )


# ---------------------------------------------------------------------------
# Pure arithmetic: due_at_from_local_date / warning_window_for
# ---------------------------------------------------------------------------
class TestDueAtConversion:
    def test_winter_date_converts_at_utc_plus_zero(self):
        # 15 January is always GMT (UTC+0) in Europe/London.
        due_at = review_rules.due_at_from_local_date(dt.date(2026, 1, 15))
        assert due_at == dt.datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)

    def test_summer_date_converts_at_utc_plus_one(self):
        # 15 July is always BST (UTC+1) in Europe/London - local midnight
        # is therefore 23:00 UTC on the PREVIOUS day, not the naive
        # "same clock reading" a timezone-unaware conversion would give.
        due_at = review_rules.due_at_from_local_date(dt.date(2026, 7, 15))
        assert due_at == dt.datetime(2026, 7, 14, 23, 0, 0, tzinfo=UTC)

    def test_spring_forward_transition_date_2026(self):
        # UK clocks spring forward at 01:00 GMT on the last Sunday of
        # March. 2026's transition is Sunday 29 March. The date BEFORE
        # the transition is still GMT; the date OF/AFTER it is BST.
        before = review_rules.due_at_from_local_date(dt.date(2026, 3, 28))
        on_day = review_rules.due_at_from_local_date(dt.date(2026, 3, 29))
        after = review_rules.due_at_from_local_date(dt.date(2026, 3, 30))
        assert before == dt.datetime(2026, 3, 28, 0, 0, 0, tzinfo=UTC)
        # Midnight local on the transition day itself is still before the
        # 01:00 changeover instant, so it is still GMT (+0).
        assert on_day == dt.datetime(2026, 3, 29, 0, 0, 0, tzinfo=UTC)
        # The following day is fully inside BST (+1) - local midnight is
        # 23:00 UTC the day before.
        assert after == dt.datetime(2026, 3, 29, 23, 0, 0, tzinfo=UTC)

    def test_autumn_back_transition_date_2026(self):
        # UK clocks fall back at 02:00 BST (01:00 UTC) on the last Sunday
        # of October. 2026's transition is Sunday 25 October.
        before = review_rules.due_at_from_local_date(dt.date(2026, 10, 24))
        on_day = review_rules.due_at_from_local_date(dt.date(2026, 10, 25))
        after = review_rules.due_at_from_local_date(dt.date(2026, 10, 26))
        # The day before is still fully BST.
        assert before == dt.datetime(2026, 10, 23, 23, 0, 0, tzinfo=UTC)
        # Midnight local ON the transition day is still before the 02:00
        # BST changeover instant, so it is still BST (+1) too.
        assert on_day == dt.datetime(2026, 10, 24, 23, 0, 0, tzinfo=UTC)
        # The day after has fully reverted to GMT (+0).
        assert after == dt.datetime(2026, 10, 26, 0, 0, 0, tzinfo=UTC)

    def test_utc_midnight_boundary_is_handled_without_off_by_one(self):
        due_at = review_rules.due_at_from_local_date(dt.date(2026, 1, 1))
        now = due_at  # exactly the due instant
        # due_at == now is NOT "overdue" (overdue means genuinely past).
        assert review_rules.warning_window_for(due_at, now=now) != review_rules.WINDOW_OVERDUE
        one_microsecond_later = now + dt.timedelta(microseconds=1)
        assert review_rules.warning_window_for(due_at, now=one_microsecond_later) == review_rules.WINDOW_OVERDUE


class TestWarningWindowBucketing:
    def setup_method(self):
        self.now = dt.datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)

    def test_due_yesterday_is_overdue(self):
        due_at = self.now - dt.timedelta(days=1)
        assert review_rules.warning_window_for(due_at, now=self.now) == review_rules.WINDOW_OVERDUE

    def test_due_today_is_not_overdue(self):
        due_at = self.now  # "today", same instant
        assert review_rules.warning_window_for(due_at, now=self.now) != review_rules.WINDOW_OVERDUE

    def test_due_in_seven_days_is_due_7d(self):
        due_at = self.now + dt.timedelta(days=7)
        assert review_rules.warning_window_for(due_at, now=self.now) == review_rules.WINDOW_DUE_7D

    def test_due_in_thirty_days_is_due_30d(self):
        due_at = self.now + dt.timedelta(days=29, hours=23)
        assert review_rules.warning_window_for(due_at, now=self.now) == review_rules.WINDOW_DUE_30D

    def test_due_beyond_thirty_days_is_future(self):
        due_at = self.now + dt.timedelta(days=31)
        assert review_rules.warning_window_for(due_at, now=self.now) == review_rules.WINDOW_FUTURE

    def test_window_bucketing_is_stable_across_a_dst_transition(self):
        # now is in GMT, due_at is exactly 30*24h later by absolute UTC
        # time, crossing the 2026-03-29 spring-forward transition. A
        # naive "add 30 calendar days then compare local clock" bug would
        # misclassify this; comparing full UTC-aware datetimes does not.
        now = dt.datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
        due_at = now + dt.timedelta(days=30)
        assert review_rules.warning_window_for(due_at, now=now) == review_rules.WINDOW_DUE_30D
        just_inside = now + dt.timedelta(days=30) - dt.timedelta(seconds=1)
        assert review_rules.warning_window_for(just_inside, now=now) == review_rules.WINDOW_DUE_30D
        just_outside = now + dt.timedelta(days=30) + dt.timedelta(seconds=1)
        assert review_rules.warning_window_for(just_outside, now=now) == review_rules.WINDOW_FUTURE


# ---------------------------------------------------------------------------
# Rule registry shape - enabled vs explicitly disabled
# ---------------------------------------------------------------------------
class TestRuleRegistry:
    def test_exactly_three_rules_are_enabled(self):
        enabled = [spec for spec in review_rules.REGISTERED_RULES.values() if spec.enabled]
        assert {spec.rule_id for spec in enabled} == {
            review_rules.RULE_ID_POLICY_REVIEW,
            review_rules.RULE_ID_REMEDIATION_FOLLOWUP,
            review_rules.RULE_ID_EVIDENCE_REVIEW,
        }
        for spec in enabled:
            assert spec.function is not None

    def test_risk_review_is_disabled_with_a_real_reason(self):
        spec = review_rules.REGISTERED_RULES[review_rules.RULE_ID_RISK_REVIEW]
        assert spec.enabled is False
        assert spec.function is None
        assert "no review-date-shaped field" in spec.disabled_reason
        assert "confirmed_at" in spec.disabled_reason

    def test_supplier_review_is_disabled_with_a_real_reason(self):
        spec = review_rules.REGISTERED_RULES[review_rules.RULE_ID_SUPPLIER_REVIEW]
        assert spec.enabled is False
        assert spec.function is None
        assert "No supplier/vendor-management Django app exists" in spec.disabled_reason

    def test_no_foundations_recurrence_rule_is_registered_at_all(self):
        assert "foundations_recurrence" not in review_rules.REGISTERED_RULES
        assert not any("foundations" in key for key in review_rules.REGISTERED_RULES)


# ---------------------------------------------------------------------------
# rule_policy_review
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestPolicyReviewRule:
    def test_approved_version_with_date_yields_one_candidate(self, org_a):
        due_date = dt.date(2026, 11, 20)
        version = _make_policy_version(org_a, next_review_date=due_date)
        now = dt.datetime(2026, 11, 1, tzinfo=UTC)
        candidates = review_rules.rule_policy_review(org_a, now=now)
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.rule_id == review_rules.RULE_ID_POLICY_REVIEW
        assert candidate.task_kind == TaskKind.POLICY_REVIEW
        assert candidate.source_object_id == str(version.id)
        assert candidate.due_occurrence == "2026-11-20"
        assert candidate.owner_user_id is None

    def test_no_date_at_all_is_skipped_never_fabricated(self, org_a):
        _make_policy_version(org_a, next_review_date=None)
        candidates = review_rules.rule_policy_review(org_a, now=django_timezone.now())
        assert candidates == []

    def test_superseded_policy_version_is_skipped(self, org_a):
        _make_policy_version(
            org_a, status=PolicyVersion.STATUS_SUPERSEDED, next_review_date=dt.date(2026, 11, 20)
        )
        candidates = review_rules.rule_policy_review(org_a, now=django_timezone.now())
        assert candidates == []

    def test_draft_policy_version_is_skipped(self, org_a):
        _make_policy_version(org_a, status=PolicyVersion.STATUS_DRAFT, next_review_date=dt.date(2026, 11, 20))
        candidates = review_rules.rule_policy_review(org_a, now=django_timezone.now())
        assert candidates == []

    def test_never_queries_another_organisations_policy_version(self, org_a, org_b):
        _make_policy_version(org_b, next_review_date=dt.date(2026, 11, 20))
        candidates = review_rules.rule_policy_review(org_a, now=django_timezone.now())
        assert candidates == []


# ---------------------------------------------------------------------------
# rule_remediation_followup
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestRemediationFollowupRule:
    def test_open_action_with_date_yields_one_candidate(self, org_a, user_a, member_a):
        due_date = dt.date(2026, 11, 20)
        action = _make_remediation_action(org_a, target_date=due_date, assigned_to=user_a)
        candidates = review_rules.rule_remediation_followup(org_a, now=django_timezone.now())
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.task_kind == TaskKind.REMEDIATION_FOLLOWUP
        assert candidate.source_object_id == str(action.id)
        assert candidate.owner_user_id == user_a.id

    def test_no_date_at_all_is_skipped(self, org_a):
        _make_remediation_action(org_a, target_date=None)
        candidates = review_rules.rule_remediation_followup(org_a, now=django_timezone.now())
        assert candidates == []

    def test_already_completed_source_is_skipped(self, org_a):
        _make_remediation_action(
            org_a, status=RemediationAction.STATUS_DONE, target_date=dt.date(2026, 11, 20)
        )
        candidates = review_rules.rule_remediation_followup(org_a, now=django_timezone.now())
        assert candidates == []

    def test_accepted_source_is_skipped(self, org_a):
        _make_remediation_action(
            org_a, status=RemediationAction.STATUS_ACCEPTED, target_date=dt.date(2026, 11, 20)
        )
        candidates = review_rules.rule_remediation_followup(org_a, now=django_timezone.now())
        assert candidates == []

    def test_never_queries_another_organisations_action(self, org_a, org_b):
        _make_remediation_action(org_b, target_date=dt.date(2026, 11, 20))
        candidates = review_rules.rule_remediation_followup(org_a, now=django_timezone.now())
        assert candidates == []


# ---------------------------------------------------------------------------
# rule_evidence_review
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestEvidenceReviewRule:
    def test_active_item_with_date_yields_one_candidate(self, org_a):
        due_date = dt.date(2026, 11, 20)
        item = _make_evidence_item(org_a, valid_until=due_date)
        candidates = review_rules.rule_evidence_review(org_a, now=django_timezone.now())
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.task_kind == TaskKind.EVIDENCE_REVIEW
        assert candidate.source_object_id == str(item.id)
        assert candidate.owner_user_id is None

    def test_no_date_at_all_is_skipped(self, org_a):
        _make_evidence_item(org_a, valid_until=None)
        candidates = review_rules.rule_evidence_review(org_a, now=django_timezone.now())
        assert candidates == []

    def test_superseded_evidence_is_skipped(self, org_a):
        _make_evidence_item(org_a, status=EvidenceItem.STATUS_SUPERSEDED, valid_until=dt.date(2026, 11, 20))
        candidates = review_rules.rule_evidence_review(org_a, now=django_timezone.now())
        assert candidates == []

    def test_withdrawn_evidence_is_skipped(self, org_a):
        _make_evidence_item(org_a, status=EvidenceItem.STATUS_WITHDRAWN, valid_until=dt.date(2026, 11, 20))
        candidates = review_rules.rule_evidence_review(org_a, now=django_timezone.now())
        assert candidates == []

    def test_never_queries_another_organisations_evidence(self, org_a, org_b):
        _make_evidence_item(org_b, valid_until=dt.date(2026, 11, 20))
        candidates = review_rules.rule_evidence_review(org_a, now=django_timezone.now())
        assert candidates == []


# ---------------------------------------------------------------------------
# evaluate_organisation - combined, cross-tenant-safe entrypoint
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestEvaluateOrganisation:
    def test_combines_all_enabled_rules_for_one_organisation_only(self, org_a, org_b):
        _make_policy_version(org_a, next_review_date=dt.date(2026, 11, 1))
        _make_remediation_action(org_a, target_date=dt.date(2026, 11, 2))
        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 3))
        # org_b's own data must never appear in org_a's candidate list.
        _make_policy_version(org_b, next_review_date=dt.date(2026, 11, 1))

        candidates = review_rules.evaluate_organisation(org_a, now=django_timezone.now())
        assert len(candidates) == 3
        assert {c.rule_id for c in candidates} == {
            review_rules.RULE_ID_POLICY_REVIEW,
            review_rules.RULE_ID_REMEDIATION_FOLLOWUP,
            review_rules.RULE_ID_EVIDENCE_REVIEW,
        }
        assert all(c.organisation_id == org_a.id for c in candidates)
