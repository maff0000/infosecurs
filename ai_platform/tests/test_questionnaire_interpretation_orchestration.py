"""
Bounded-retry-orchestration tests for
`ai_platform.questionnaire_interpretation_orchestration.
interpret_questionnaire_question` (M005 PID §21, §27 - m005-1-foundation
dispatch), mirroring `ai_platform/tests/test_policy_orchestration.py`'s
own shape exactly for this sibling task.
"""
import pytest

from ai_platform.gateway import DEFAULT_MODEL_ALIAS
from ai_platform.models import AIInvocationRecord
from ai_platform.questionnaire_interpretation_contracts import (
    QuestionnaireInterpretation,
    QuestionnaireInterpretationRequest,
)
from ai_platform.questionnaire_interpretation_orchestration import (
    QuestionnaireInterpretationFailed,
    interpret_questionnaire_question,
)
from ai_platform.testing import (
    FakeQuestionnaireInterpretationGateway,
    default_valid_questionnaire_interpretation_result,
)

PROMPT_VERSION = "questionnaire_interpretation_v1"

_AVAILABLE_KEYS = [{"key": "control:mfa_privileged_accounts", "description": "MFA for admin accounts."}]


def _request(organisation):
    return QuestionnaireInterpretationRequest(
        organisation_id=str(organisation.pk),
        question_text="Do all privileged accounts use MFA?",
        source_label="",
        available_keys=_AVAILABLE_KEYS,
    )


# --- Happy path ---------------------------------------------------------------

def test_interpret_success_persists_succeeded_record(organisation):
    gw = FakeQuestionnaireInterpretationGateway(mode="valid")
    result, record = interpret_questionnaire_question(gw, _request(organisation), PROMPT_VERSION)

    assert isinstance(result, QuestionnaireInterpretation)
    assert len(gw.calls) == 1

    stored = AIInvocationRecord.objects.get(organisation=organisation)
    assert record.pk == stored.pk
    assert stored.status == AIInvocationRecord.STATUS_SUCCEEDED
    assert stored.task_type == AIInvocationRecord.TASK_QUESTIONNAIRE_INTERPRETATION
    assert stored.prompt_version == PROMPT_VERSION
    assert stored.model_alias == DEFAULT_MODEL_ALIAS
    assert stored.completed_at is not None


def test_interpret_scopes_invocation_record_to_given_organisation(organisation, other_organisation):
    gw = FakeQuestionnaireInterpretationGateway(mode="valid")
    interpret_questionnaire_question(gw, _request(organisation), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.organisation_id == organisation.pk
    assert record.organisation_id != other_organisation.pk


def test_interpret_input_snapshot_hash_is_deterministic_hex(organisation):
    gw = FakeQuestionnaireInterpretationGateway(mode="valid")
    interpret_questionnaire_question(gw, _request(organisation), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert len(record.input_snapshot_hash) == 64
    int(record.input_snapshot_hash, 16)


# --- Invalid/unparseable output: never partially persisted -------------------

def test_interpret_invalid_response_fails_with_no_retry(organisation):
    gw = FakeQuestionnaireInterpretationGateway(mode="invalid_schema")
    with pytest.raises(QuestionnaireInterpretationFailed):
        interpret_questionnaire_question(gw, _request(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 1
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_INVALID_RESPONSE


def test_interpret_auth_error_fails_with_no_retry(organisation):
    gw = FakeQuestionnaireInterpretationGateway(mode="auth_error")
    with pytest.raises(QuestionnaireInterpretationFailed):
        interpret_questionnaire_question(gw, _request(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 1
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.error_category == AIInvocationRecord.ERROR_AUTH


# --- Retry policy --------------------------------------------------------------

def test_interpret_retries_exactly_once_then_fails(organisation):
    gw = FakeQuestionnaireInterpretationGateway(mode="always_fail_retryable")
    with pytest.raises(QuestionnaireInterpretationFailed):
        interpret_questionnaire_question(gw, _request(organisation), PROMPT_VERSION)
    assert len(gw.calls) == 2


def test_interpret_retry_recovers_on_transient_failure(organisation):
    gw = FakeQuestionnaireInterpretationGateway(mode="fail_then_succeed")
    result, _record = interpret_questionnaire_question(gw, _request(organisation), PROMPT_VERSION)
    assert len(gw.calls) == 2
    assert isinstance(result, QuestionnaireInterpretation)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_SUCCEEDED


def test_default_valid_questionnaire_interpretation_result_matches_request_keys(organisation):
    result = default_valid_questionnaire_interpretation_result(_request(organisation))
    assert isinstance(result, QuestionnaireInterpretation)
    assert result.selected_keys == []
