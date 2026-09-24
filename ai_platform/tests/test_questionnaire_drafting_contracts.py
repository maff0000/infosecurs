"""
Structural-validation tests for `ai_platform.questionnaire_drafting_contracts`
(M005 PID §13, §27 - m005-1-foundation dispatch).
"""
import pytest

from ai_platform.contracts import ContractValidationError
from ai_platform.questionnaire_drafting_contracts import (
    ALLOWED_OUTCOMES,
    OUTCOME_GAP,
    OUTCOME_SUPPORTED,
    QuestionnaireDraft,
    QuestionnaireDraftingRequest,
)
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation


def _interpretation(selected_keys):
    return QuestionnaireInterpretation(
        intent_type="implementation",
        requirement_scope="all",
        requirement_summary="x",
        selected_keys=selected_keys,
        evidence_explicitly_requested=False,
        ambiguous=False,
        ambiguity_note="",
    )


def test_request_rejects_non_allowed_outcome():
    with pytest.raises(ContractValidationError):
        QuestionnaireDraftingRequest(
            organisation_id="org-1",
            question_text="Do you use MFA?",
            interpretation=_interpretation(["control:mfa_privileged_accounts"]),
            outcome="MAYBE",
            grounding_snapshot={},
        )


def test_request_accepts_every_allowed_outcome():
    for outcome in ALLOWED_OUTCOMES:
        request = QuestionnaireDraftingRequest(
            organisation_id="org-1",
            question_text="Do you use MFA?",
            interpretation=_interpretation(["control:mfa_privileged_accounts"]),
            outcome=outcome,
            grounding_snapshot={"control:mfa_privileged_accounts": {"answer": "yes"}},
        )
        assert request.outcome == outcome


def test_from_response_dict_valid_payload_parses():
    draft = QuestionnaireDraft.from_response_dict(
        {
            "answer_text": "Yes, MFA is enabled for all privileged accounts.",
            "answer_summary": "",
            "grounding_handles_used": ["control:mfa_privileged_accounts"],
            "customer_review_note": "",
        },
        selected_keys=["control:mfa_privileged_accounts"],
        resolved_model="fixture-model",
        prompt_version="questionnaire_drafting_v1",
    )
    assert draft.answer_text.startswith("Yes")
    assert draft.grounding_handles_used == ["control:mfa_privileged_accounts"]


def test_grounding_handles_used_must_be_subset_of_selected_keys():
    with pytest.raises(ContractValidationError):
        QuestionnaireDraft.from_response_dict(
            {
                "answer_text": "Some answer.",
                "grounding_handles_used": ["control:this_was_never_selected"],
            },
            selected_keys=["control:mfa_privileged_accounts"],
            resolved_model=None,
            prompt_version="v1",
        )


def test_grounding_handles_used_may_be_empty():
    draft = QuestionnaireDraft.from_response_dict(
        {"answer_text": "Some answer.", "grounding_handles_used": []},
        selected_keys=["control:mfa_privileged_accounts"],
        resolved_model=None,
        prompt_version="v1",
    )
    assert draft.grounding_handles_used == []


def test_missing_answer_text_rejected():
    with pytest.raises(ContractValidationError):
        QuestionnaireDraft.from_response_dict(
            {"grounding_handles_used": []},
            selected_keys=[],
            resolved_model=None,
            prompt_version="v1",
        )


def test_draft_carries_no_outcome_field():
    """Structural proof of PID §20's second safety boundary: the drafting
    response contract has no field an AI response could populate to
    attempt to upgrade the application-derived outcome."""
    draft = QuestionnaireDraft.from_response_dict(
        {"answer_text": "No, this control is not implemented.", "grounding_handles_used": []},
        selected_keys=[],
        resolved_model=None,
        prompt_version="v1",
    )
    assert not hasattr(draft, "outcome")
    assert "outcome" not in draft.__dataclass_fields__
