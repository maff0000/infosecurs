"""
Tenant isolation for M005's review/accept/edit/regenerate actions (PID §23
- m005-2-review-history dispatch). Mirrors `policy/tests/test_tenant_
isolation.py`'s own discipline exactly: organisation B's client cannot
accept/edit/regenerate organisation A's response - every case is an
ordinary 404, never a 403 or silent no-op, and a rejected cross-tenant
attempt never creates an `ActivityEvent` row as a side effect.

(`questionnaire/tests/test_services.py`'s existing scope already covers
generate/list/detail negative cases from the m005-1-foundation dispatch;
this file covers only the three NEW actions this dispatch adds.)
"""
import uuid

import pytest
from django.urls import reverse

from activity.models import ActivityEvent

from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse

pytestmark = pytest.mark.django_db

CONTROL_KEY = "control:mfa_privileged_accounts"


def _org_a_draft_response(org_a, user_a, **overrides):
    question = QuestionnaireQuestion.objects.create(
        organisation=org_a, question_text="Do you use MFA?", created_by=user_a
    )
    defaults = dict(
        organisation=org_a,
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
        created_by=user_a,
    )
    defaults.update(overrides)
    return question, QuestionnaireResponse.objects.create(**defaults)


class TestQuestionnaireReviewTenantIsolation:
    def test_member_cannot_accept_other_organisations_response(self, client_b, org_a, user_a):
        _, response = _org_a_draft_response(org_a, user_a)
        resp = client_b.post(reverse("questionnaire:response_accept", args=[org_a.id, response.id]))
        assert resp.status_code == 404
        response.refresh_from_db()
        assert response.status == QuestionnaireResponse.STATUS_DRAFT
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_ACCEPTED
        ).exists()

    def test_member_cannot_edit_other_organisations_response(self, client_b, org_a, user_a):
        _, response = _org_a_draft_response(org_a, user_a)
        resp = client_b.post(
            reverse("questionnaire:response_edit", args=[org_a.id, response.id]),
            data={"current_answer_text": "hijacked"},
        )
        assert resp.status_code == 404
        response.refresh_from_db()
        assert response.current_answer_text == "No."
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_EDITED
        ).exists()

    def test_member_cannot_view_other_organisations_edit_form(self, client_b, org_a, user_a):
        _, response = _org_a_draft_response(org_a, user_a)
        resp = client_b.get(reverse("questionnaire:response_edit", args=[org_a.id, response.id]))
        assert resp.status_code == 404

    def test_member_cannot_regenerate_other_organisations_response(self, client_b, org_a, user_a):
        question, response = _org_a_draft_response(org_a, user_a)
        resp = client_b.post(reverse("questionnaire:response_regenerate", args=[org_a.id, response.id]))
        assert resp.status_code == 404
        assert QuestionnaireResponse.objects.filter(question=question).count() == 1
        assert not ActivityEvent.objects.filter(
            organisation=org_a, event_type=ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_GENERATED
        ).exists()

    def test_org_b_response_id_used_against_org_a_url_is_404(self, client_a, org_a, org_b, user_b):
        """A response that genuinely exists (for org_b), but referenced
        through org_a's URL segment - must be an ordinary 404, never a
        cross-tenant read via a mismatched organisation_id/response_id
        pairing."""
        _, response_b = _org_a_draft_response(org_b, user_b)
        for url_name in ("response_accept", "response_edit", "response_regenerate"):
            resp = client_a.post(reverse(f"questionnaire:{url_name}", args=[org_a.id, response_b.id]))
            assert resp.status_code == 404

    def test_nonexistent_response_id_in_url_is_404(self, client_a, org_a):
        for url_name in ("response_accept", "response_edit", "response_regenerate"):
            resp = client_a.post(reverse(f"questionnaire:{url_name}", args=[org_a.id, uuid.uuid4()]))
            assert resp.status_code == 404

    def test_cross_tenant_attempt_never_creates_response_for_wrong_org(self, client_b, org_a, org_b, user_a):
        _, response = _org_a_draft_response(org_a, user_a)
        client_b.post(reverse("questionnaire:response_regenerate", args=[org_a.id, response.id]))
        assert QuestionnaireResponse.objects.filter(organisation=org_b).count() == 0
