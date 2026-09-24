"""
Bounded-retry-orchestration tests for
`ai_platform.questionnaire_drafting_orchestration.
draft_questionnaire_answer` (M005 PID §21, §27 - m005-1-foundation
dispatch), mirroring `test_questionnaire_interpretation_orchestration.py`/
`test_policy_orchestration.py`'s own shape exactly.
"""
import pytest

from ai_platform.gateway import DEFAULT_MODEL_ALIAS
from ai_platform.models import AIInvocationRecord
from ai_platform.questionnaire_drafting_contracts import (
    OUTCOME_SUPPORTED,
    QuestionnaireDraft,
    QuestionnaireDraftingRequest,
)
from ai_platform.questionnaire_drafting_orchestration import (
    QuestionnaireDraftingFailed,
    draft_questionnaire_answer,
)
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation
from ai_platform.testing import FakeQuestionnaireDraftingGateway

PROMPT_VERSION = "questionnaire_drafting_v1"


def _interpretation():
    return QuestionnaireInterpretation(
        intent_type="implementation",
        requirement_scope="all",
        requirement_summary="Asks whether MFA is enabled for all privileged accounts.",
        selected_keys=["control:mfa_privileged_accounts"],
        evidence_explicitly_requested=False,
        ambiguous=False,
        ambiguity_note="",
    )


def _request(organisation):
    return QuestionnaireDraftingRequest(
        organisation_id=str(organisation.pk),
        question_text="Do all privileged accounts use MFA?",
        interpretation=_interpretation(),
        outcome=OUTCOME_SUPPORTED,
        grounding_snapshot={"control:mfa_privileged_accounts": {"answer": "yes"}},
    )


def test_draft_success_persists_succeeded_record(organisation):
    gw = FakeQuestionnaireDraftingGateway(mode="valid")
    result, record = draft_questionnaire_answer(gw, _request(organisation), PROMPT_VERSION)

    assert isinstance(result, QuestionnaireDraft)
    assert len(gw.calls) == 1

    stored = AIInvocationRecord.objects.get(organisation=organisation)
    assert record.pk == stored.pk
    assert stored.status == AIInvocationRecord.STATUS_SUCCEEDED
    assert stored.task_type == AIInvocationRecord.TASK_QUESTIONNAIRE_DRAFTING
    assert stored.prompt_version == PROMPT_VERSION
    assert stored.model_alias == DEFAULT_MODEL_ALIAS


def test_draft_scopes_invocation_record_to_given_organisation(organisation, other_organisation):
    gw = FakeQuestionnaireDraftingGateway(mode="valid")
    draft_questionnaire_answer(gw, _request(organisation), PROMPT_VERSION)
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.organisation_id == organisation.pk
    assert record.organisation_id != other_organisation.pk


def test_draft_invalid_response_fails_with_no_retry(organisation):
    gw = FakeQuestionnaireDraftingGateway(mode="invalid_schema")
    with pytest.raises(QuestionnaireDraftingFailed):
        draft_questionnaire_answer(gw, _request(organisation), PROMPT_VERSION)

    assert len(gw.calls) == 1
    record = AIInvocationRecord.objects.latest("started_at")
    assert record.status == AIInvocationRecord.STATUS_FAILED
    assert record.error_category == AIInvocationRecord.ERROR_INVALID_RESPONSE


def test_draft_retries_exactly_once_then_fails(organisation):
    gw = FakeQuestionnaireDraftingGateway(mode="always_fail_retryable")
    with pytest.raises(QuestionnaireDraftingFailed):
        draft_questionnaire_answer(gw, _request(organisation), PROMPT_VERSION)
    assert len(gw.calls) == 2


def test_draft_retry_recovers_on_transient_failure(organisation):
    gw = FakeQuestionnaireDraftingGateway(mode="fail_then_succeed")
    result, _record = draft_questionnaire_answer(gw, _request(organisation), PROMPT_VERSION)
    assert len(gw.calls) == 2
    assert isinstance(result, QuestionnaireDraft)
