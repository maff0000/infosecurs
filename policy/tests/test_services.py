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
from ai_platform.policy_orchestration import PolicyGenerationFailed
from ai_platform.testing import FakePolicyGateway
from policy.models import PolicyDocument, PolicyVersion
from policy.services import generate_policy_draft


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
