"""
Review/accept/edit/regenerate lifecycle tests (M005 PID §17, §18, §24,
§27 "Review/history" - m005-2-review-history dispatch).

HTTP-client shaped (`client_a`/`client_b`), so this lives under
`ci/integration`, not `ci/unit` - matches this dispatch's own instruction
(CI wiring is the PL's job, not this file's).
"""
import pytest
from django.urls import reverse

from activity.models import ActivityEvent
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment

from questionnaire.models import ImmutableQuestionnaireResponseError, QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.services import accept_questionnaire_response, edit_questionnaire_response_text

from questionnaire.tests.conftest import patch_questionnaire_generation_gateways

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


def _draft_response(org, question, actor, **overrides):
    """Build+persist a `QuestionnaireResponse` directly (no AI call), for
    tests that only need a well-formed draft to act on."""
    defaults = dict(
        organisation=org,
        question=question,
        status=QuestionnaireResponse.STATUS_DRAFT,
        interpreted_requirement_summary="Asks whether MFA is enabled for all privileged accounts.",
        intent_type="implementation",
        requirement_scope="all",
        selected_keys=[CONTROL_KEY],
        evidence_explicitly_requested=False,
        outcome="GAP",
        ai_draft_text="No, MFA is not enabled for all privileged accounts.",
        current_answer_text="No, MFA is not enabled for all privileged accounts.",
        review_warnings=[],
        grounding_snapshot={CONTROL_KEY: {"answer": "no"}},
        grounding_snapshot_hash="deadbeef",
        interpretation_prompt_version="questionnaire_interpretation_v1",
        drafting_prompt_version="questionnaire_drafting_v1",
        created_by=actor,
    )
    defaults.update(overrides)
    return QuestionnaireResponse.objects.create(**defaults)


# --- Accept --------------------------------------------------------------

def test_accepting_draft_response_sets_status_actor_timestamp_and_event(org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a)

    accept_questionnaire_response(response, actor=user_a)
    response.refresh_from_db()

    assert response.status == QuestionnaireResponse.STATUS_ACCEPTED
    assert response.accepted_by == user_a
    assert response.accepted_at is not None

    event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_ACCEPTED,
        related_object_id=str(response.id),
    )
    assert event.metadata["outcome"] == response.outcome
    assert event.metadata["question_id"] == str(question.id)


def test_accepting_second_response_supersedes_first_byte_identical_protected_fields(org_a, user_a):
    question = _question(org_a, user_a)
    first = _draft_response(org_a, question, user_a, outcome="GAP", current_answer_text="First answer.")
    accept_questionnaire_response(first, actor=user_a)
    first.refresh_from_db()

    # Snapshot every protected field's post-acceptance value BEFORE the
    # second response supersedes it - the load-bearing assertion below
    # proves these are byte-identical after supersession, not just "no
    # exception raised".
    pre_supersede = {
        "current_answer_text": first.current_answer_text,
        "outcome": first.outcome,
        "grounding_snapshot": dict(first.grounding_snapshot),
        "selected_keys": list(first.selected_keys),
    }

    second = _draft_response(
        org_a, question, user_a, outcome="SUPPORTED", current_answer_text="Second, stronger answer."
    )
    accept_questionnaire_response(second, actor=user_a)

    first.refresh_from_db()
    second.refresh_from_db()

    assert first.status == QuestionnaireResponse.STATUS_SUPERSEDED
    assert first.superseded_by_id == second.id
    assert second.status == QuestionnaireResponse.STATUS_ACCEPTED

    assert first.current_answer_text == pre_supersede["current_answer_text"]
    assert first.outcome == pre_supersede["outcome"]
    assert first.grounding_snapshot == pre_supersede["grounding_snapshot"]
    assert first.selected_keys == pre_supersede["selected_keys"]

    superseded_event = ActivityEvent.objects.get(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_SUPERSEDED,
        related_object_id=str(first.id),
    )
    assert superseded_event.metadata["superseded_by"] == str(second.id)


def test_accepting_when_no_previous_accepted_response_supersedes_nothing(org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a)
    accept_questionnaire_response(response, actor=user_a)
    assert not ActivityEvent.objects.filter(
        organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_SUPERSEDED
    ).exists()


# --- Edit ------------------------------------------------------------------

def test_editing_draft_response_changes_text_and_emits_event_once(org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, current_answer_text="Original wording.")

    edit_questionnaire_response_text(response, new_text="Improved wording.", actor=user_a)
    response.refresh_from_db()

    assert response.current_answer_text == "Improved wording."
    events = ActivityEvent.objects.filter(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_EDITED,
        related_object_id=str(response.id),
    )
    assert events.count() == 1
    assert events.first().metadata == {"answer_text_changed": True}


def test_editing_with_identical_text_fires_no_event(org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, current_answer_text="Unchanged wording.")

    before = ActivityEvent.objects.filter(
        organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_EDITED
    ).count()
    edit_questionnaire_response_text(response, new_text="Unchanged wording.", actor=user_a)

    after = ActivityEvent.objects.filter(
        organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_EDITED
    ).count()
    assert after == before


# --- Hostile: edit form cannot smuggle outcome ------------------------------

def test_hostile_edit_post_with_outcome_field_has_no_effect(client_a, org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, outcome="GAP", current_answer_text="Old wording.")

    resp = client_a.post(
        reverse("questionnaire:response_edit", args=[org_a.id, response.id]),
        data={"current_answer_text": "New wording, honestly submitted.", "outcome": "SUPPORTED"},
    )
    assert resp.status_code == 302
    response.refresh_from_db()
    assert response.outcome == "GAP"  # unchanged - the form has no outcome field at all
    assert response.current_answer_text == "New wording, honestly submitted."


def test_hostile_edit_post_outcome_field_confirm_baseline_also_unaffected(client_a, org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, outcome="CONFIRM", current_answer_text="Old wording.")

    resp = client_a.post(
        reverse("questionnaire:response_edit", args=[org_a.id, response.id]),
        data={"current_answer_text": "New wording.", "outcome": "SUPPORTED", "selected_keys": '["control:x"]'},
    )
    assert resp.status_code == 302
    response.refresh_from_db()
    assert response.outcome == "CONFIRM"
    assert response.selected_keys == [CONTROL_KEY]


# --- Cannot edit/accept a non-draft response --------------------------------

def test_cannot_edit_already_accepted_response(client_a, org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED)

    resp = client_a.post(
        reverse("questionnaire:response_edit", args=[org_a.id, response.id]),
        data={"current_answer_text": "Trying to sneak an edit in."},
    )
    assert resp.status_code == 302
    response.refresh_from_db()
    assert response.current_answer_text != "Trying to sneak an edit in."
    assert not ActivityEvent.objects.filter(
        organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_EDITED
    ).exists()


def test_cannot_edit_already_superseded_response(client_a, org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_SUPERSEDED)

    resp = client_a.post(
        reverse("questionnaire:response_edit", args=[org_a.id, response.id]),
        data={"current_answer_text": "Trying to sneak an edit in."},
    )
    assert resp.status_code == 302
    response.refresh_from_db()
    assert response.current_answer_text != "Trying to sneak an edit in."


def test_cannot_accept_already_accepted_response(client_a, org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED)
    original_accepted_at = response.accepted_at

    resp = client_a.post(reverse("questionnaire:response_accept", args=[org_a.id, response.id]))
    assert resp.status_code == 302
    response.refresh_from_db()
    assert response.accepted_at == original_accepted_at
    assert not ActivityEvent.objects.filter(
        organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_ACCEPTED
    ).exists()


def test_cannot_accept_already_superseded_response(client_a, org_a, user_a):
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_SUPERSEDED)

    resp = client_a.post(reverse("questionnaire:response_accept", args=[org_a.id, response.id]))
    assert resp.status_code == 302
    response.refresh_from_db()
    assert response.status == QuestionnaireResponse.STATUS_SUPERSEDED


def test_view_layer_check_prevents_immutable_error_ever_being_raised(client_a, org_a, user_a):
    """The view-level draft-only check must catch this BEFORE the model
    layer would - `ImmutableQuestionnaireResponseError` must never surface
    at the HTTP boundary."""
    question = _question(org_a, user_a)
    response = _draft_response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED)

    # If the view's guard were missing, edit_questionnaire_response_text's
    # own .save() would raise ImmutableQuestionnaireResponseError given a
    # real change - proving the view never gets that far.
    try:
        resp = client_a.post(
            reverse("questionnaire:response_edit", args=[org_a.id, response.id]),
            data={"current_answer_text": "Different text entirely."},
        )
    except ImmutableQuestionnaireResponseError:
        pytest.fail("ImmutableQuestionnaireResponseError leaked to the HTTP layer")
    assert resp.status_code == 302


# --- Regenerate --------------------------------------------------------------

def test_regenerate_creates_new_draft_response_same_question_old_unchanged(
    client_a, org_a, user_a, monkeypatch
):
    _set_answer(org_a, BASELINE_KEY, "yes")
    question = _question(org_a, user_a)
    old_response = _draft_response(
        org_a, question, user_a, status=QuestionnaireResponse.STATUS_ACCEPTED, outcome="GAP"
    )
    old_updated_at = old_response.updated_at

    patch_questionnaire_generation_gateways(
        monkeypatch, interpretation_result=_interpretation_result([CONTROL_KEY])
    )

    resp = client_a.post(reverse("questionnaire:response_regenerate", args=[org_a.id, old_response.id]))
    assert resp.status_code == 302

    old_response.refresh_from_db()
    assert old_response.status == QuestionnaireResponse.STATUS_ACCEPTED  # untouched
    assert old_response.outcome == "GAP"
    assert old_response.updated_at == old_updated_at

    new_responses = QuestionnaireResponse.objects.filter(question=question).exclude(pk=old_response.pk)
    assert new_responses.count() == 1
    new_response = new_responses.first()
    assert new_response.status == QuestionnaireResponse.STATUS_DRAFT
    assert new_response.question_id == question.id
    assert new_response.pk != old_response.pk

    assert ActivityEvent.objects.filter(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_GENERATED,
        related_object_id=str(new_response.id),
    ).exists()
    assert ActivityEvent.objects.filter(
        organisation=org_a,
        event_type=ActivityEvent.EVENT_QUESTION_INTERPRETED,
        related_object_id=str(question.id),
    ).exists()


def test_regenerate_from_a_draft_response_also_allowed(client_a, org_a, user_a, monkeypatch):
    """PID §18: regenerating is allowed regardless of the response being
    regenerated FROM's status - draft included."""
    question = _question(org_a, user_a)
    draft_response = _draft_response(org_a, question, user_a, status=QuestionnaireResponse.STATUS_DRAFT)

    patch_questionnaire_generation_gateways(
        monkeypatch, interpretation_result=_interpretation_result([])
    )
    resp = client_a.post(reverse("questionnaire:response_regenerate", args=[org_a.id, draft_response.id]))
    assert resp.status_code == 302
    assert QuestionnaireResponse.objects.filter(question=question).count() == 2


# --- Full history scenario end-to-end (PID §18) -----------------------------

def test_full_history_scenario_generate_accept_state_change_regenerate_accept(
    client_a, org_a, user_a, monkeypatch
):
    # 1. Partial state -> generate response A -> GAP.
    _set_answer(org_a, BASELINE_KEY, "partial")
    question_text = "Do all privileged accounts use MFA?"

    patch_questionnaire_generation_gateways(
        monkeypatch, interpretation_result=_interpretation_result([CONTROL_KEY])
    )
    resp = client_a.post(
        reverse("questionnaire:analyse", args=[org_a.id]),
        data={"question_text": question_text, "source_label": ""},
    )
    assert resp.status_code == 302
    created_question = QuestionnaireQuestion.objects.get(organisation=org_a, question_text=question_text)
    response_a = QuestionnaireResponse.objects.get(question=created_question)
    assert response_a.outcome == "GAP"

    # 2. Accept A.
    accept_url = reverse("questionnaire:response_accept", args=[org_a.id, response_a.id])
    resp = client_a.post(accept_url)
    assert resp.status_code == 302
    response_a.refresh_from_db()
    assert response_a.status == QuestionnaireResponse.STATUS_ACCEPTED
    post_accept_answer_text = response_a.current_answer_text
    post_accept_outcome = response_a.outcome
    post_accept_grounding = dict(response_a.grounding_snapshot)
    post_accept_selected_keys = list(response_a.selected_keys)

    # 3. Underlying state changes -> now fully "yes".
    _set_answer(org_a, BASELINE_KEY, "yes")

    # 4. Regenerate -> response B, different (stronger) outcome.
    regenerate_url = reverse("questionnaire:response_regenerate", args=[org_a.id, response_a.id])
    resp = client_a.post(regenerate_url)
    assert resp.status_code == 302
    response_b = QuestionnaireResponse.objects.filter(question=created_question).exclude(
        pk=response_a.pk
    ).get()
    assert response_b.status == QuestionnaireResponse.STATUS_DRAFT
    assert response_b.outcome == "SUPPORTED"
    assert response_b.outcome != response_a.outcome

    # 5. Accept B -> A becomes superseded, unchanged since acceptance.
    resp = client_a.post(reverse("questionnaire:response_accept", args=[org_a.id, response_b.id]))
    assert resp.status_code == 302

    response_a.refresh_from_db()
    response_b.refresh_from_db()
    assert response_a.status == QuestionnaireResponse.STATUS_SUPERSEDED
    assert response_a.superseded_by_id == response_b.id
    assert response_a.current_answer_text == post_accept_answer_text
    assert response_a.outcome == post_accept_outcome
    assert response_a.grounding_snapshot == post_accept_grounding
    assert response_a.selected_keys == post_accept_selected_keys
    assert response_b.status == QuestionnaireResponse.STATUS_ACCEPTED
