"""
End-to-end pipeline tests for `questionnaire.services.
generate_questionnaire_response` (M005 PID §4, §22, §27 -
m005-1-foundation dispatch) - proves the FULL wiring (interpret -> ground ->
derive outcome -> draft -> persist) against the fake gateways, not just the
pure `derive_outcome` unit, for a handful of representative scenarios.
"""
import pytest

from ai_platform.models import AIInvocationRecord
from ai_platform.questionnaire_drafting_contracts import OUTCOME_CONFIRM, OUTCOME_GAP, OUTCOME_SUPPORTED
from ai_platform.questionnaire_drafting_orchestration import QuestionnaireDraftingFailed
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation
from ai_platform.questionnaire_interpretation_orchestration import QuestionnaireInterpretationFailed
from ai_platform.testing import FakeQuestionnaireDraftingGateway, FakeQuestionnaireInterpretationGateway
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment

from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.services import generate_questionnaire_response

pytestmark = pytest.mark.django_db

CONTROL_KEY = "control:mfa_privileged_accounts"
BASELINE_KEY = "mfa_privileged_accounts"


def _set_answer(org, key, answer):
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    return BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=key, defaults={"answer": answer}
    )[0]


def _question(org, actor, text="Do all privileged accounts use MFA?"):
    return QuestionnaireQuestion.objects.create(organisation=org, question_text=text, created_by=actor)


def _interpretation_result(selected_keys, *, intent_type="implementation", requirement_scope="all"):
    return QuestionnaireInterpretation(
        intent_type=intent_type,
        requirement_scope=requirement_scope,
        requirement_summary="Asks whether MFA is enabled for all privileged accounts.",
        selected_keys=selected_keys,
        evidence_explicitly_requested=False,
        ambiguous=False,
        ambiguity_note="",
        resolved_model="fixture-model",
        prompt_version="questionnaire_interpretation_v1",
    )


# --- Happy path, three outcome classes end to end ------------------------------

def test_supported_outcome_persists_correctly(org_a, user_a):
    _set_answer(org_a, BASELINE_KEY, "yes")
    question = _question(org_a, user_a)

    interp_gw = FakeQuestionnaireInterpretationGateway(
        mode="valid", result=_interpretation_result([CONTROL_KEY])
    )
    draft_gw = FakeQuestionnaireDraftingGateway(mode="valid")

    response = generate_questionnaire_response(
        org_a, question, actor=user_a, interpretation_gateway=interp_gw, drafting_gateway=draft_gw
    )

    assert response.status == QuestionnaireResponse.STATUS_DRAFT
    assert response.outcome == OUTCOME_SUPPORTED
    assert response.selected_keys == [CONTROL_KEY]
    assert response.current_answer_text == response.ai_draft_text
    assert response.current_answer_text
    assert response.grounding_snapshot_hash and len(response.grounding_snapshot_hash) == 64
    assert response.grounding_snapshot[CONTROL_KEY]["answer"] == "yes"
    assert response.interpretation_invocation_record is not None
    assert response.drafting_invocation_record is not None
    assert response.interpretation_invocation_record.task_type == AIInvocationRecord.TASK_QUESTIONNAIRE_INTERPRETATION
    assert response.drafting_invocation_record.task_type == AIInvocationRecord.TASK_QUESTIONNAIRE_DRAFTING
    assert response.question_id == question.id
    assert response.organisation_id == org_a.pk


def test_gap_outcome_persists_correctly(org_a, user_a):
    _set_answer(org_a, BASELINE_KEY, "no")
    question = _question(org_a, user_a)

    interp_gw = FakeQuestionnaireInterpretationGateway(
        mode="valid", result=_interpretation_result([CONTROL_KEY])
    )
    draft_gw = FakeQuestionnaireDraftingGateway(mode="valid")

    response = generate_questionnaire_response(
        org_a, question, actor=user_a, interpretation_gateway=interp_gw, drafting_gateway=draft_gw
    )
    assert response.outcome == OUTCOME_GAP


def test_confirm_outcome_persists_correctly(org_a, user_a):
    # No BaselineAnswer at all -> canonical "unknown".
    question = _question(org_a, user_a)

    interp_gw = FakeQuestionnaireInterpretationGateway(
        mode="valid", result=_interpretation_result([CONTROL_KEY])
    )
    draft_gw = FakeQuestionnaireDraftingGateway(mode="valid")

    response = generate_questionnaire_response(
        org_a, question, actor=user_a, interpretation_gateway=interp_gw, drafting_gateway=draft_gw
    )
    assert response.outcome == OUTCOME_CONFIRM
    assert response.review_warnings


# --- Failure modes (PID §22) ---------------------------------------------------

def test_interpretation_failure_persists_no_response_but_keeps_question(org_a, user_a):
    question = _question(org_a, user_a)
    interp_gw = FakeQuestionnaireInterpretationGateway(mode="always_fail_retryable")
    draft_gw = FakeQuestionnaireDraftingGateway(mode="valid")

    with pytest.raises(QuestionnaireInterpretationFailed):
        generate_questionnaire_response(
            org_a, question, actor=user_a, interpretation_gateway=interp_gw, drafting_gateway=draft_gw
        )

    assert QuestionnaireResponse.objects.count() == 0
    # The question itself was created by the caller before this function
    # ran and is untouched by the failure.
    question.refresh_from_db()
    assert question.question_text == "Do all privileged accounts use MFA?"
    assert len(draft_gw.calls) == 0  # never reached drafting


def test_drafting_failure_persists_no_response(org_a, user_a):
    _set_answer(org_a, BASELINE_KEY, "yes")
    question = _question(org_a, user_a)

    interp_gw = FakeQuestionnaireInterpretationGateway(
        mode="valid", result=_interpretation_result([CONTROL_KEY])
    )
    draft_gw = FakeQuestionnaireDraftingGateway(mode="always_fail_retryable")

    with pytest.raises(QuestionnaireDraftingFailed):
        generate_questionnaire_response(
            org_a, question, actor=user_a, interpretation_gateway=interp_gw, drafting_gateway=draft_gw
        )

    # PID §22 minimal-scope simplification (documented in questionnaire.
    # services module docstring): nothing is persisted at all, including
    # the interpretation/outcome/grounding that already succeeded - a
    # retry re-runs the whole pipeline, including interpretation again.
    assert QuestionnaireResponse.objects.count() == 0
    assert len(interp_gw.calls) == 1


def test_customer_review_note_folded_into_review_warnings(org_a, user_a):
    from ai_platform.questionnaire_drafting_contracts import QuestionnaireDraft

    _set_answer(org_a, BASELINE_KEY, "yes")
    question = _question(org_a, user_a)

    interp_gw = FakeQuestionnaireInterpretationGateway(
        mode="valid", result=_interpretation_result([CONTROL_KEY])
    )
    draft_gw = FakeQuestionnaireDraftingGateway(
        mode="valid",
        result=QuestionnaireDraft(
            answer_text="Yes, MFA is enabled for all privileged accounts.",
            answer_summary="",
            grounding_handles_used=[CONTROL_KEY],
            customer_review_note="Please double-check this before sending.",
            resolved_model="fixture-model",
            prompt_version="questionnaire_drafting_v1",
        ),
    )

    response = generate_questionnaire_response(
        org_a, question, actor=user_a, interpretation_gateway=interp_gw, drafting_gateway=draft_gw
    )
    assert "Please double-check this before sending." in response.review_warnings
