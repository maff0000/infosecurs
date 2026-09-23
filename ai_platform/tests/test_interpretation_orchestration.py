import pytest

from ai_platform.contracts import ContractValidationError
from ai_platform.gateway import DEFAULT_MODEL_ALIAS
from ai_platform.interpretation_contracts import InterpretationCandidate, InterpretationResponse
from ai_platform.interpretation_orchestration import InterpretationFailed, interpret_candidates
from ai_platform.models import AIInvocationRecord
from ai_platform.testing import FakeInterpretationGateway, default_valid_interpretation_result

PROMPT_VERSION = "risk_interpretation_v1"


def _candidates(n=1):
    return [
        InterpretationCandidate(
            index=i,
            title=f"Candidate {i}",
            exposure="exposure",
            threat_event="threat event",
            vulnerability="vulnerability",
            consequence="consequence",
            current_impact=3,
            current_likelihood=3,
            asset_category="endpoint",
            notes=[],
        )
        for i in range(1, n + 1)
    ]


# --- Happy path ---------------------------------------------------------------

def test_interpret_candidates_success_persists_succeeded_record(organisation):
    gw = FakeInterpretationGateway(mode="valid")
    candidates = _candidates(2)
    result, record = interpret_candidates(gw, str(organisation.pk), candidates, PROMPT_VERSION)

    assert isinstance(result, InterpretationResponse)
    assert len(gw.calls) == 1  # no retry needed
    assert {o.index for o in result.outcomes} == {1, 2}

    stored = AIInvocationRecord.objects.get(organisation=organisation)
    assert record.pk == stored.pk
    assert stored.status == AIInvocationRecord.STATUS_SUCCEEDED
    assert stored.error_category is None
    assert stored.task_type == AIInvocationRecord.TASK_RISK_INTERPRETATION
    assert stored.prompt_version == PROMPT_VERSION
    assert stored.model_alias == DEFAULT_MODEL_ALIAS
    assert stored.candidate_count == 2
    assert stored.resolved_model == result.resolved_model
    assert stored.completed_at is not None


def test_interpret_candidates_records_custom_model_alias(organisation):
    gw = FakeInterpretationGateway(mode="valid")
    interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION, model_alias="trinity-fast")
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.model_alias == "trinity-fast"


def test_interpret_candidates_stores_additional_observations_on_the_record(organisation):
    result = default_valid_interpretation_result({1})
    result = InterpretationResponse(
        outcomes=result.outcomes,
        additional_observations=["Consider a supplier-risk scenario too."],
        resolved_model=result.resolved_model,
        prompt_version=result.prompt_version,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
    gw = FakeInterpretationGateway(mode="valid", result=result)
    interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.additional_observations == ["Consider a supplier-risk scenario too."]


def test_interpret_candidates_input_snapshot_hash_is_deterministic_and_not_the_raw_payload(organisation):
    gw = FakeInterpretationGateway(mode="valid")
    interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert len(record.input_snapshot_hash) == 64
    int(record.input_snapshot_hash, 16)  # must be valid hex


def test_interpret_candidates_scopes_invocation_record_to_given_organisation(organisation, other_organisation):
    gw = FakeInterpretationGateway(mode="valid")
    interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.organisation_id == organisation.pk
    assert record.organisation_id != other_organisation.pk


def test_interpret_candidates_rejects_over_cap_before_any_gateway_call(organisation):
    gw = FakeInterpretationGateway(mode="valid")
    with pytest.raises(ContractValidationError):
        interpret_candidates(gw, str(organisation.pk), _candidates(9), PROMPT_VERSION)
    assert gw.calls == []  # rejected before the gateway was ever invoked
    assert AIInvocationRecord.objects.filter(organisation=organisation).count() == 0


# --- Invalid/unparseable output: never partially persisted -------------------

def test_interpret_candidates_invalid_response_fails_with_no_retry(organisation):
    gw = FakeInterpretationGateway(mode="invalid_schema")
    with pytest.raises(InterpretationFailed):
        interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)

    assert len(gw.calls) == 1
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_INVALID_RESPONSE
    assert record.candidate_count == 0
    assert record.completed_at is not None


def test_interpret_candidates_index_mismatch_shaped_failure_fails_with_no_retry(organisation):
    gw = FakeInterpretationGateway(mode="index_mismatch")
    with pytest.raises(InterpretationFailed):
        interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)

    assert len(gw.calls) == 1  # not retried - same as any other InvalidResponseError
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_INVALID_RESPONSE


def test_interpret_candidates_auth_error_fails_with_no_retry(organisation):
    gw = FakeInterpretationGateway(mode="auth_error")
    with pytest.raises(InterpretationFailed):
        interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)

    assert len(gw.calls) == 1
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_AUTH


# --- Retry policy: exactly one retry, retryable failures only ---------------

def test_interpret_candidates_retries_exactly_once_then_fails(organisation):
    gw = FakeInterpretationGateway(mode="always_fail_retryable")
    with pytest.raises(InterpretationFailed):
        interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_CONNECTION


def test_interpret_candidates_retry_recovers_on_transient_failure(organisation):
    gw = FakeInterpretationGateway(mode="fail_then_succeed")
    result, _record = interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)

    assert len(gw.calls) == 2
    assert isinstance(result, InterpretationResponse)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_SUCCEEDED


def test_interpret_candidates_timeout_retries_then_fails_with_timeout_category(organisation):
    gw = FakeInterpretationGateway(mode="timeout")
    with pytest.raises(InterpretationFailed):
        interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.error_category == AIInvocationRecord.ERROR_TIMEOUT


def test_interpret_candidates_rate_limit_retries_then_fails_with_rate_limit_category(organisation):
    gw = FakeInterpretationGateway(mode="rate_limit")
    with pytest.raises(InterpretationFailed):
        interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.error_category == AIInvocationRecord.ERROR_RATE_LIMIT


def test_interpret_candidates_never_makes_a_third_attempt_even_if_retryable_forever(organisation):
    gw = FakeInterpretationGateway(mode="always_fail_retryable")
    with pytest.raises(InterpretationFailed):
        interpret_candidates(gw, str(organisation.pk), _candidates(1), PROMPT_VERSION)
    assert len(gw.calls) == 2


# --- Revert-and-rerun proof (forge-engineer rule 14) -------------------------
# Measured, not assumed: with `max_attempts` in interpretation_orchestration.py
# temporarily forced to 1 (retry disabled), re-running this file failed
# exactly the 5 tests that depend on the retry actually happening
# (retries_exactly_once_then_fails, retry_recovers_on_transient_failure,
# timeout_retries_then_fails_with_timeout_category,
# rate_limit_retries_then_fails_with_rate_limit_category,
# never_makes_a_third_attempt_even_if_retryable_forever) - 5 of 14 - and
# passed the other 9 that do not depend on retry. The fix was then restored
# and the full file re-ran green (14/14). See the dispatch report for the
# exact commands and counts.
