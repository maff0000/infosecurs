"""
`policy.services.generate_policy_draft` tests (PID §14-15, §22, §26 "Policy
lifecycle" - m004-2a-policy-foundation dispatch's own scope: draft
generation only). Uses `ai_platform.testing.FakePolicyGateway` throughout -
no live AI credential needed, matching this project's existing test
discipline.
"""
import pytest

from activity.models import ActivityEvent
from ai_platform.models import AIInvocationRecord
from ai_platform.policy_contracts import PolicyGenerationResult, PolicyReviewWarning, PolicySection
from ai_platform.policy_orchestration import PolicyGenerationFailed
from ai_platform.testing import FakePolicyGateway
from policy.models import PolicyDocument, PolicyVersion
from policy.services import (
    _deterministic_review_warnings,
    _merge_review_warnings,
    generate_policy_draft,
)


@pytest.mark.django_db
class TestGeneratePolicyDraftSuccess:
    def test_creates_exactly_one_document_and_first_draft_version(self, org_a, user_a):
        version = generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="valid"))

        assert PolicyDocument.objects.filter(organisation=org_a).count() == 1
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 1
        assert version.status == PolicyVersion.STATUS_DRAFT
        assert version.version_number == 1
        assert version.generation_source == PolicyVersion.GENERATION_SOURCE_AI
        assert version.created_by == user_a
        assert version.sections  # non-empty
        assert version.ai_invocation_record is not None
        assert version.ai_invocation_record.task_type == AIInvocationRecord.TASK_POLICY_GENERATION

    def test_second_call_creates_a_new_version_not_a_mutation(self, org_a, user_a):
        first = generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="valid"))
        second = generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="valid"))

        assert PolicyDocument.objects.filter(organisation=org_a).count() == 1
        assert second.version_number == first.version_number + 1
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 2
        # The first version's own row is untouched.
        first.refresh_from_db()
        assert first.version_number == 1

    def test_emits_exactly_one_policy_draft_generated_event(self, org_a, user_a):
        version = generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="valid"))

        events = ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_DRAFT_GENERATED
        )
        assert events.count() == 1
        event = events.get()
        assert event.related_object_type == "policy_version"
        assert event.related_object_id == str(version.id)
        assert event.metadata == {"version_number": version.version_number}
        assert event.actor == user_a


@pytest.mark.django_db
class TestGeneratePolicyDraftFailure:
    def test_invalid_response_creates_nothing(self, org_a, user_a):
        with pytest.raises(PolicyGenerationFailed):
            generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="invalid_schema"))

        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_POLICY_DRAFT_GENERATED
        ).exists()

    def test_auth_error_creates_nothing(self, org_a, user_a):
        with pytest.raises(PolicyGenerationFailed):
            generate_policy_draft(org_a, actor=user_a, gateway=FakePolicyGateway(mode="auth_error"))

        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0

    def test_always_fail_retryable_retries_once_then_creates_nothing(self, org_a, user_a):
        gateway = FakePolicyGateway(mode="always_fail_retryable")
        with pytest.raises(PolicyGenerationFailed):
            generate_policy_draft(org_a, actor=user_a, gateway=gateway)

        assert len(gateway.calls) == 2
        assert PolicyDocument.objects.filter(organisation=org_a).count() == 0
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0

    def test_fail_then_succeed_recovers_and_creates_the_draft(self, org_a, user_a):
        gateway = FakePolicyGateway(mode="fail_then_succeed")
        version = generate_policy_draft(org_a, actor=user_a, gateway=gateway)

        assert len(gateway.calls) == 2
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 1
        assert version.status == PolicyVersion.STATUS_DRAFT


# --- Deterministic review warnings (G1 correction §7, M006-AUDIT-0002) --------

_UNCONFIRMED_STATE = {
    "area": "Some control",
    "answer": "unknown",
    "answer_label": "Not confirmed",
    "assurance_label": "Not confirmed",
    "open_remediation_count": 0,
}


class TestDeterministicReviewWarnings:
    def test_unknown_partial_no_all_trigger_a_warning(self):
        facts = {
            "a": {**_UNCONFIRMED_STATE, "area": "A", "answer": "unknown"},
            "b": {**_UNCONFIRMED_STATE, "area": "B", "answer": "partial", "answer_label": "Partially"},
            "c": {**_UNCONFIRMED_STATE, "area": "C", "answer": "no", "answer_label": "No"},
        }
        warnings = _deterministic_review_warnings(facts)
        assert {w.subject for w in warnings} == {"A - a", "B - b", "C - c"}

    def test_yes_with_no_conflict_never_triggers_a_warning(self):
        facts = {
            "a": {
                "area": "A",
                "answer": "yes",
                "answer_label": "Yes",
                "assurance_label": "Customer stated",
                "open_remediation_count": 0,
            }
        }
        assert _deterministic_review_warnings(facts) == []

    def test_not_applicable_never_triggers_a_warning(self):
        facts = {
            "a": {
                "area": "A",
                "answer": "not_applicable",
                "answer_label": "Not applicable",
                "assurance_label": "Not applicable",
                "open_remediation_count": 0,
            }
        }
        assert _deterministic_review_warnings(facts) == []

    def test_evidence_conflict_or_stale_on_a_confirmed_yes_still_triggers_a_warning(self):
        facts = {
            "a": {
                "area": "A",
                "answer": "yes",
                "answer_label": "Yes",
                "assurance_label": "Evidence conflict",
                "open_remediation_count": 0,
            },
            "b": {
                "area": "B",
                "answer": "yes",
                "answer_label": "Yes",
                "assurance_label": "Evidence stale",
                "open_remediation_count": 0,
            },
        }
        warnings = _deterministic_review_warnings(facts)
        assert {w.subject for w in warnings} == {"A - a", "B - b"}


class TestMergeReviewWarnings:
    def test_ai_warning_covering_the_exact_area_deduplicates(self):
        facts = {"backups": {**_UNCONFIRMED_STATE, "area": "Backups", "answer": "no"}}
        ai_warnings = [PolicyReviewWarning(subject="Backups not currently implemented", detail="...")]
        merged = _merge_review_warnings(ai_warnings, facts)
        assert len(merged) == 1
        assert merged[0].subject == "Backups not currently implemented"

    def test_unrelated_ai_warning_does_not_suppress_a_genuine_gap(self):
        """Direct regression test for the exact bug a live run of this
        mechanism caught: an AI warning about `mfa_privileged_accounts`
        happened to use the phrase "privileged access" in its own DETAIL
        prose ("...privileged access is not currently protected by
        MFA..."), which - before this fix - falsely deduplicated the
        completely different `privileged_access_separation` control's own
        deterministic warning purely because that control's `area` label
        ("Privileged access") is a substring of that unrelated sentence.
        Matching is now scoped to each AI warning's own short `subject`
        line, never its `detail` prose, for exactly this reason."""
        facts = {
            "mfa_privileged_accounts": {
                **_UNCONFIRMED_STATE,
                "area": "Multi-factor authentication (admin)",
            },
            "privileged_access_separation": {**_UNCONFIRMED_STATE, "area": "Privileged access"},
        }
        ai_warnings = [
            PolicyReviewWarning(
                subject="MFA for privileged accounts not confirmed",
                detail=(
                    "This represents a critical gap, as privileged access is not "
                    "currently protected by MFA."
                ),
            )
        ]
        merged = _merge_review_warnings(ai_warnings, facts)
        subjects = {w.subject for w in merged}
        # The AI's own warning is kept, PLUS a deterministic warning for
        # EACH control - crucially including privileged_access_separation,
        # which the AI never actually addressed.
        assert "MFA for privileged accounts not confirmed" in subjects
        assert "Privileged access - privileged_access_separation" in subjects
        assert (
            "Multi-factor authentication (admin) - mfa_privileged_accounts" in subjects
        )
        assert len(merged) == 3

    def test_control_key_match_anywhere_in_ai_text_still_deduplicates(self):
        facts = {"device_encryption": {**_UNCONFIRMED_STATE, "area": "Device encryption"}}
        ai_warnings = [
            PolicyReviewWarning(
                subject="A gap", detail="See control device_encryption for details."
            )
        ]
        merged = _merge_review_warnings(ai_warnings, facts)
        assert len(merged) == 1  # deduplicated via the control_key match


@pytest.mark.django_db
class TestGeneratePolicyDraftDeterministicWarnings:
    def test_generate_policy_draft_merges_deterministic_warnings_into_persisted_version(
        self, org_a, user_a
    ):
        """End-to-end: `org_a` has no baseline/security state at all, so
        every catalogue control projects as `answer=unknown` - the
        deterministic mechanism must add a warning for every one of them,
        even though the fixture AI result's own `review_warnings` only
        mentions "Backups"."""
        result = PolicyGenerationResult(
            policy_title="Fixture Ltd Information Security Policy",
            sections=[PolicySection(section_key="purpose_and_scope", content="Purpose text.")],
            review_warnings=[PolicyReviewWarning(subject="Backups", detail="Not yet confirmed.")],
            resolved_model="fixture-model/fake-v1",
            prompt_version="policy_generation_v2",
        )
        gateway = FakePolicyGateway(mode="valid", result=result)
        version = generate_policy_draft(org_a, actor=user_a, gateway=gateway)

        subjects = {w["subject"] for w in version.review_warnings}
        assert "Backups" in subjects  # the AI's own warning survives
        # At least one deterministic warning for an unconfirmed control was
        # added (org_a has no baseline state at all - every control is
        # "unknown").
        assert len(subjects) > 1
