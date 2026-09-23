import dataclasses

import pytest

from ai_platform.contracts import GenerationResult, GroundingPayload, RiskCandidate
from ai_platform.gateway import DEFAULT_MODEL_ALIAS
from ai_platform.models import AIInvocationRecord
from ai_platform.orchestration import GenerationFailed, generate_risks
from ai_platform.testing import FakeGateway, default_valid_result

PROMPT_VERSION = "risk_generation_v1"


# --- Happy path ---------------------------------------------------------------

def test_generate_risks_success_persists_succeeded_record(grounding, organisation):
    gw = FakeGateway(mode="valid")
    result, returned_record = generate_risks(gw, grounding, PROMPT_VERSION)

    assert isinstance(result, GenerationResult)
    assert len(gw.calls) == 1  # no retry needed

    record = AIInvocationRecord.objects.get(organisation=organisation)
    assert returned_record.pk == record.pk  # generate_risks returns (result, record) - PL integration note
    assert record.status == AIInvocationRecord.STATUS_SUCCEEDED
    assert record.error_category is None
    assert record.prompt_version == PROMPT_VERSION
    assert record.model_alias == DEFAULT_MODEL_ALIAS
    assert record.candidate_count == len(result.candidates)
    assert record.resolved_model == result.resolved_model
    assert record.prompt_tokens == result.prompt_tokens
    assert record.completion_tokens == result.completion_tokens
    assert record.completed_at is not None
    assert record.task_type == AIInvocationRecord.TASK_INITIAL_RISK_GENERATION


def test_generate_risks_records_custom_model_alias(grounding):
    gw = FakeGateway(mode="valid")
    generate_risks(gw, grounding, PROMPT_VERSION, model_alias="trinity-fast")
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.model_alias == "trinity-fast"


def test_generate_risks_input_snapshot_hash_is_deterministic_and_not_the_raw_payload(grounding):
    gw = FakeGateway(mode="valid")
    generate_risks(gw, grounding, PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")

    expected_hash = AIInvocationRecord.hash_grounding(grounding)
    assert record.input_snapshot_hash == expected_hash
    # Not the raw payload - a 64-char hex digest, nothing resembling the
    # actual profile/baseline/asset facts should appear in the stored value.
    assert len(record.input_snapshot_hash) == 64
    int(record.input_snapshot_hash, 16)  # must be valid hex


def test_generate_risks_scopes_invocation_record_to_grounding_organisation(organisation, other_organisation):
    grounding = GroundingPayload(
        organisation_id=str(organisation.pk),
        profile_facts={},
        baseline_facts={},
        asset_facts=[],
    )
    gw = FakeGateway(mode="valid")
    generate_risks(gw, grounding, PROMPT_VERSION)

    record = AIInvocationRecord.objects.latest("started_at")
    assert record.organisation_id == organisation.pk
    assert record.organisation_id != other_organisation.pk


# --- Invalid/unparseable output: never partially persisted -------------------

def test_generate_risks_invalid_response_fails_with_no_retry(grounding):
    gw = FakeGateway(mode="invalid_schema")
    with pytest.raises(GenerationFailed):
        generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(gw.calls) == 1  # invalid/unparseable output is NOT retried (PID §14)

    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_INVALID_RESPONSE
    assert record.candidate_count == 0
    assert record.completed_at is not None


def test_generate_risks_auth_error_fails_with_no_retry(grounding):
    gw = FakeGateway(mode="auth_error")
    with pytest.raises(GenerationFailed):
        generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(gw.calls) == 1  # auth errors are not retryable either
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_AUTH


# --- Retry policy: exactly one retry, retryable failures only ---------------

def test_generate_risks_retries_exactly_once_then_fails(grounding):
    gw = FakeGateway(mode="always_fail_retryable")
    with pytest.raises(GenerationFailed):
        generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(gw.calls) == 2  # one initial attempt + exactly one retry
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_CONNECTION


def test_generate_risks_retry_recovers_on_transient_failure(grounding):
    gw = FakeGateway(mode="fail_then_succeed")
    result, _record = generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(gw.calls) == 2
    assert isinstance(result, GenerationResult)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_SUCCEEDED


def test_generate_risks_timeout_retries_then_fails_with_timeout_category(grounding):
    gw = FakeGateway(mode="timeout")
    with pytest.raises(GenerationFailed):
        generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.error_category == AIInvocationRecord.ERROR_TIMEOUT


def test_generate_risks_rate_limit_retries_then_fails_with_rate_limit_category(grounding):
    gw = FakeGateway(mode="rate_limit")
    with pytest.raises(GenerationFailed):
        generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(gw.calls) == 2
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.error_category == AIInvocationRecord.ERROR_RATE_LIMIT


# --- Revert-proof: prove the retry cap actually bounds retries --------------

def test_generate_risks_never_makes_a_third_attempt_even_if_retryable_forever(grounding):
    # Belt-and-braces variant of test_generate_risks_retries_exactly_once_then_fails:
    # explicitly asserts the loop cannot be coaxed into more than 2 calls by
    # asserting call count directly against a gateway that would fail
    # indefinitely if ever called a 3rd time (it doesn't grow beyond 2
    # regardless, since FakeGateway just keeps raising - the assertion is
    # what proves the bound, not the fixture).
    gw = FakeGateway(mode="always_fail_retryable")
    with pytest.raises(GenerationFailed):
        generate_risks(gw, grounding, PROMPT_VERSION)
    assert len(gw.calls) == 2


# --- Candidate cap: truncate over the limit (documented choice) -------------

def test_generate_risks_truncates_over_cap_candidates(grounding):
    over_cap = default_valid_result(PROMPT_VERSION)
    ten_candidates = [over_cap.candidates[0]] * 10
    over_cap_result = dataclasses.replace(over_cap, candidates=ten_candidates)

    gw = FakeGateway(mode="valid", result=over_cap_result)
    result, _record = generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(result.candidates) == 8  # MAX_CANDIDATES
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.candidate_count == 8


def test_generate_risks_does_not_truncate_at_or_under_cap(grounding):
    at_cap = default_valid_result(PROMPT_VERSION)
    eight_candidates = [at_cap.candidates[0]] * 8
    at_cap_result = dataclasses.replace(at_cap, candidates=eight_candidates)

    gw = FakeGateway(mode="valid", result=at_cap_result)
    result, _record = generate_risks(gw, grounding, PROMPT_VERSION)

    assert len(result.candidates) == 8


# --- Revert-and-rerun proof (forge-engineer rule 14) -------------------------
# Measured, not assumed: with `max_attempts` in orchestration.py temporarily
# forced to 1 (retry disabled) and the MAX_CANDIDATES truncation block
# temporarily commented out, re-running this file failed exactly the 6 tests
# that exercise those two behaviours (retries_exactly_once_then_fails,
# retry_recovers_on_transient_failure, timeout_retries_then_fails_with_
# timeout_category, rate_limit_retries_then_fails_with_rate_limit_category,
# never_makes_a_third_attempt_even_if_retryable_forever,
# truncates_over_cap_candidates) - 6 of 13 - and passed the other 7 that do
# not depend on retry/truncation. The fix was then restored and the full
# ai_platform suite re-ran green (89/89). See the dispatch report for the
# exact commands.
