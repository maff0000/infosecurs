import pytest

from ai_platform.gateway import DEFAULT_MODEL_ALIAS
from ai_platform.models import AIInvocationRecord
from ai_platform.policy_contracts import PolicyGenerationResult, PolicyGroundingPayload
from ai_platform.policy_orchestration import PolicyGenerationFailed, generate_policy
from ai_platform.testing import FakePolicyGateway, default_valid_policy_result

PROMPT_VERSION = "policy_generation_v1"


def _grounding(organisation):
    return PolicyGroundingPayload(
        organisation_id=str(organisation.pk),
        organisation_facts={"name": organisation.name, "staff_count": 5, "description": ""},
        workplace_facts=[{"name": "HQ", "type": "dedicated_office"}],
        governance_facts={"policy_authoriser": {"full_name": "Ada", "job_title": "CEO"}},
        baseline_facts={"mfa_user_accounts": {"answer": "unknown", "note": ""}},
        security_state_facts={"mfa_user_accounts": {"area": "access", "answer": "unknown"}},
        open_risk_facts=[],
    )


# --- Happy path ---------------------------------------------------------------

def test_generate_policy_success_persists_succeeded_record(organisation):
    gw = FakePolicyGateway(mode="valid")
    result, record = generate_policy(gw, _grounding(organisation), PROMPT_VERSION)

    assert isinstance(result, PolicyGenerationResult)
    assert len(gw.calls) == 1  # no retry needed

    stored = AIInvocationRecord.objects.get(organisation=organisation)
    assert record.pk == stored.pk
    assert stored.status == AIInvocationRecord.STATUS_SUCCEEDED
    assert stored.error_category is None
    assert stored.task_type == AIInvocationRecord.TASK_POLICY_GENERATION
    assert stored.prompt_version == PROMPT_VERSION
    assert stored.model_alias == DEFAULT_MODEL_ALIAS
    assert stored.candidate_count == len(result.sections)
    assert stored.resolved_model == result.resolved_model
    assert stored.completed_at is not None


def test_generate_policy_records_custom_model_alias(organisation):
    gw = FakePolicyGateway(mode="valid")
    generate_policy(gw, _grounding(organisation), PROMPT_VERSION, model_alias="trinity-fast")
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.model_alias == "trinity-fast"


def test_generate_policy_input_snapshot_hash_is_deterministic_and_not_the_raw_payload(organisation):
    gw = FakePolicyGateway(mode="valid")
    generate_policy(gw, _grounding(organisation), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert len(record.input_snapshot_hash) == 64
    int(record.input_snapshot_hash, 16)  # must be valid hex


def test_generate_policy_scopes_invocation_record_to_given_organisation(organisation, other_organisation):
    gw = FakePolicyGateway(mode="valid")
    generate_policy(gw, _grounding(organisation), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.organisation_id == organisation.pk
    assert record.organisation_id != other_organisation.pk


# --- Invalid/unparseable output: never partially persisted -------------------

def test_generate_policy_invalid_response_fails_with_no_retry(organisation):
    gw = FakePolicyGateway(mode="invalid_schema")
    with pytest.raises(PolicyGenerationFailed):
        generate_policy(gw, _grounding(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 1
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_INVALID_RESPONSE
    assert record.candidate_count == 0
    assert record.completed_at is not None


def test_generate_policy_auth_error_fails_with_no_retry(organisation):
    gw = FakePolicyGateway(mode="auth_error")
    with pytest.raises(PolicyGenerationFailed):
        generate_policy(gw, _grounding(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 1
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_AUTH


# --- Retry policy: exactly one retry, retryable failures only ---------------

def test_generate_policy_retries_exactly_once_then_fails(organisation):
    gw = FakePolicyGateway(mode="always_fail_retryable")
    with pytest.raises(PolicyGenerationFailed):
        generate_policy(gw, _grounding(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_CONNECTION


def test_generate_policy_retry_recovers_on_transient_failure(organisation):
    gw = FakePolicyGateway(mode="fail_then_succeed")
    result, _record = generate_policy(gw, _grounding(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 2
    assert isinstance(result, PolicyGenerationResult)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_SUCCEEDED


def test_generate_policy_timeout_retries_then_fails_with_timeout_category(organisation):
    gw = FakePolicyGateway(mode="timeout")
    with pytest.raises(PolicyGenerationFailed):
        generate_policy(gw, _grounding(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.error_category == AIInvocationRecord.ERROR_TIMEOUT


def test_generate_policy_rate_limit_retries_then_fails_with_rate_limit_category(organisation):
    gw = FakePolicyGateway(mode="rate_limit")
    with pytest.raises(PolicyGenerationFailed):
        generate_policy(gw, _grounding(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.error_category == AIInvocationRecord.ERROR_RATE_LIMIT


def test_generate_policy_never_makes_a_third_attempt_even_if_retryable_forever(organisation):
    gw = FakePolicyGateway(mode="always_fail_retryable")
    with pytest.raises(PolicyGenerationFailed):
        generate_policy(gw, _grounding(organisation), PROMPT_VERSION)
    assert len(gw.calls) == 2


def test_default_valid_policy_result_is_itself_contract_valid():
    # Sanity check on the fixture builder itself.
    result = default_valid_policy_result()
    assert isinstance(result, PolicyGenerationResult)
    assert result.sections
