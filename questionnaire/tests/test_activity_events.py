"""
Activity/provenance event coverage for M005's six event types (PID §24 -
m005-2-review-history dispatch): proves each real emitter actually fires,
with the metadata shape the dispatch specifies - not just that
`ActivityEvent.EVENT_TYPE_CHOICES` lists the type (that's covered by
`activity/tests/test_models.py`'s `human_summary()` additions instead).
"""
import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation

from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.services import accept_questionnaire_response, edit_questionnaire_response_text

from questionnaire.tests.conftest import patch_questionnaire_generation_gateways

pytestmark = pytest.mark.django_db

CONTROL_KEY = "control:mfa_privileged_accounts"


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


def _draft_response(org, question, actor, **overrides):
    defaults = dict(
        organisation=org,
        question=question,
        status=QuestionnaireResponse.STATUS_DRAFT,
        interpreted_requirement_summary="Asks about MFA.",
        intent_type="implementation",
        requirement_scope="all",
        selected_keys=[CONTROL_KEY],
        evidence_explicitly_requested=False,
        outcome="GAP",
        ai_draft_text="No.",
        current_answer_text="No.",
        review_warnings=[],
        grounding_snapshot={CONTROL_KEY: {"answer": "no"}},
        grounding_snapshot_hash="deadbeef",
        interpretation_prompt_version="questionnaire_interpretation_v1",
        drafting_prompt_version="questionnaire_drafting_v1",
        created_by=actor,
    )
    defaults.update(overrides)
    return QuestionnaireResponse.objects.create(**defaults)


def test_question_created_event_fires_on_analyse(client_a, org_a, monkeypatch):
    patch_questionnaire_generation_gateways(monkeypatch, interpretation_result=_interpretation_result([]))

    resp = client_a.post(
        reverse("questionnaire:analyse", args=[org_a.id]),
        data={"question_text": "Do you have an Information Security Policy?", "source_label": "Acme"},
    )
    assert resp.status_code == 302

    question = QuestionnaireQuestion.objects.get(organisation=org_a)
    event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTION_CREATED,
        related_object_id=str(question.id),
    )
    assert event.metadata == {"has_source_label": True}
    assert event.human_summary() == "A questionnaire question was submitted"


def test_question_interpreted_and_response_generated_events_fire_on_analyse(client_a, org_a, monkeypatch):
    patch_questionnaire_generation_gateways(
        monkeypatch, interpretation_result=_interpretation_result([CONTROL_KEY])
    )

    resp = client_a.post(
        reverse("questionnaire:analyse", args=[org_a.id]),
        data={"question_text": "Do all privileged accounts use MFA?", "source_label": ""},
    )
    assert resp.status_code == 302

    question = QuestionnaireQuestion.objects.get(organisation=org_a)
    response = QuestionnaireResponse.objects.get(question=question)

    interpreted_event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTION_INTERPRETED,
        related_object_id=str(question.id),
    )
    assert interpreted_event.metadata["intent_type"] == "implementation"
    assert interpreted_event.metadata["requirement_scope"] == "all"
    assert interpreted_event.metadata["selected_keys"] == [CONTROL_KEY]
    assert interpreted_event.metadata["evidence_explicitly_requested"] is False
    assert interpreted_event.human_summary() == "Question interpreted as 'implementation'"

    generated_event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_GENERATED,
        related_object_id=str(response.id),
    )
    assert generated_event.metadata["outcome"] == response.outcome
    assert "review_warning_count" in generated_event.metadata
    assert (
        generated_event.human_summary()
        == f"Questionnaire response drafted (outcome: {response.outcome})"
    )


def test_response_edited_event_metadata_shape(org_a, user_a):
    question = QuestionnaireQuestion.objects.create(
        organisation=org_a, question_text="Do you use MFA?", created_by=user_a
    )
    response = _draft_response(org_a, question, user_a, current_answer_text="Old.")
    edit_questionnaire_response_text(response, new_text="New.", actor=user_a)

    event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_EDITED,
        related_object_id=str(response.id),
    )
    assert event.metadata == {"answer_text_changed": True}
    assert event.human_summary() == "Questionnaire response wording edited"
    # Never the text content itself.
    assert "Old." not in str(event.metadata)
    assert "New." not in str(event.metadata)


def test_response_accepted_and_superseded_event_metadata_shape(org_a, user_a):
    question = QuestionnaireQuestion.objects.create(
        organisation=org_a, question_text="Do you use MFA?", created_by=user_a
    )
    first = _draft_response(org_a, question, user_a, outcome="GAP")
    accept_questionnaire_response(first, actor=user_a)

    second = _draft_response(org_a, question, user_a, outcome="SUPPORTED")
    accept_questionnaire_response(second, actor=user_a)

    accepted_event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_ACCEPTED,
        related_object_id=str(second.id),
    )
    assert accepted_event.metadata == {"outcome": "SUPPORTED", "question_id": str(question.id)}
    assert accepted_event.human_summary() == "Questionnaire response accepted (outcome: SUPPORTED)"

    superseded_event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_SUPERSEDED,
        related_object_id=str(first.id),
    )
    assert superseded_event.metadata == {"superseded_by": str(second.id)}
    assert superseded_event.human_summary() == "Questionnaire response superseded by a newer response"
