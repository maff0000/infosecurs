"""
Model-layer tests for `questionnaire.models` (M005 PID §7.2, §17, §27 -
m005-1-foundation dispatch) - principally the immutability guarantee on
`QuestionnaireResponse`, mirroring `policy/tests/test_models.py`'s own
"mutate directly at the model layer, confirm rejection" discipline for the
sibling `PolicyVersion.save()` guard.
"""
import pytest

from questionnaire.models import ImmutableQuestionnaireResponseError, QuestionnaireQuestion, QuestionnaireResponse

pytestmark = pytest.mark.django_db


def _question(org, actor):
    return QuestionnaireQuestion.objects.create(
        organisation=org, question_text="Do you use MFA?", created_by=actor
    )


def _response(org, question, actor, **overrides):
    defaults = dict(
        organisation=org,
        question=question,
        status=QuestionnaireResponse.STATUS_DRAFT,
        interpreted_requirement_summary="Asks about MFA.",
        intent_type="implementation",
        requirement_scope="all",
        selected_keys=["control:mfa_privileged_accounts"],
        evidence_explicitly_requested=False,
        outcome="SUPPORTED",
        ai_draft_text="Yes, MFA is enabled.",
        current_answer_text="Yes, MFA is enabled.",
        review_warnings=[],
        grounding_snapshot={"control:mfa_privileged_accounts": {"answer": "yes"}},
        grounding_snapshot_hash="deadbeef",
        interpretation_prompt_version="questionnaire_interpretation_v1",
        drafting_prompt_version="questionnaire_drafting_v1",
        created_by=actor,
    )
    defaults.update(overrides)
    return QuestionnaireResponse.objects.create(**defaults)


def test_question_preserves_text_exactly(org_a, user_a):
    text = "  Do you use   MFA?  \nExtra line."
    question = QuestionnaireQuestion.objects.create(
        organisation=org_a, question_text=text, created_by=user_a
    )
    question.refresh_from_db()
    assert question.question_text == text


def test_question_source_label_optional(org_a, user_a):
    question = QuestionnaireQuestion.objects.create(
        organisation=org_a, question_text="Do you use MFA?", created_by=user_a
    )
    assert question.source_label == ""


def test_draft_response_current_answer_text_is_mutable(org_a, user_a):
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a)
    response.current_answer_text = "Edited answer."
    response.save()  # must not raise - still draft
    response.refresh_from_db()
    assert response.current_answer_text == "Edited answer."


def test_accepted_response_current_answer_text_is_immutable(org_a, user_a):
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED)

    response.current_answer_text = "Trying to upgrade the wording after acceptance."
    with pytest.raises(ImmutableQuestionnaireResponseError):
        response.save()


def test_accepted_response_outcome_is_immutable(org_a, user_a):
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED)

    response.outcome = "SUPPORTED_UPGRADED_BY_BUG"
    with pytest.raises(ImmutableQuestionnaireResponseError):
        response.save()


def test_accepted_response_grounding_snapshot_is_immutable(org_a, user_a):
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED)

    response.grounding_snapshot = {"control:mfa_privileged_accounts": {"answer": "no"}}
    with pytest.raises(ImmutableQuestionnaireResponseError):
        response.save()


def test_accepted_response_selected_keys_is_immutable(org_a, user_a):
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED)

    response.selected_keys = ["control:some_other_key"]
    with pytest.raises(ImmutableQuestionnaireResponseError):
        response.save()


def test_superseded_response_is_also_immutable(org_a, user_a):
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_SUPERSEDED)

    response.outcome = "GAP"
    with pytest.raises(ImmutableQuestionnaireResponseError):
        response.save()


def test_accepted_response_non_protected_field_can_still_change(org_a, user_a):
    """`review_warnings` is not in PROTECTED_WHILE_DRAFT_FIELDS - a later
    dispatch's accept flow needs to be able to set accepted_by/accepted_at
    etc. on the same save that transitions status. Mirrors
    `policy/tests/test_models.py::test_non_protected_field_can_still_change_after_approval`.
    """
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_DRAFT)

    response.status = QuestionnaireResponse.STATUS_ACCEPTED
    response.accepted_by = user_a
    response.save()  # the draft -> accepted transition itself must be allowed

    response.review_warnings = ["A brand new warning added after acceptance."]
    response.save()  # not a protected field - must not raise
    response.refresh_from_db()
    assert response.review_warnings == ["A brand new warning added after acceptance."]


def test_draft_to_accepted_transition_itself_is_allowed(org_a, user_a):
    question = _question(org_a, user_a)
    response = _response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_DRAFT)
    response.status = QuestionnaireResponse.STATUS_ACCEPTED
    response.save()
    response.refresh_from_db()
    assert response.status == QuestionnaireResponse.STATUS_ACCEPTED
