"""
Release-blocking test for M003 PID §6.5/§13's non-negotiable invariant:

    Completing a RemediationAction (status -> done or accepted) must NEVER
    automatically:
      - change a BaselineAnswer;
      - mark the linked Risk resolved;
      - claim a control is implemented.

This test proves it directly by querying `Risk` and `BaselineAnswer`
independently after completion - not by inspecting the action's own
fields, which would only prove the action's row changed, not that nothing
else did (forge-engineer.md's "attribution" caution).

forge-engineer.md rule 14 applies to this file: reverting the "never
touch BaselineAnswer/Risk" guarantee in remediation/views.py and re-running
this file is the evidence reported back to the PL (see the dispatch
report), not recorded as a separate test artefact here.
"""
import pytest
from django.urls import reverse

from remediation.models import RemediationAction
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _baseline_answer(org, *, question_key="mfa_user_accounts", answer="no"):
    assessment = BaselineAssessment.objects.create(
        organisation=org, catalogue_version=CATALOGUE_VERSION
    )
    return BaselineAnswer.objects.create(
        assessment=assessment, question_key=question_key, answer=answer, note="original note"
    )


@pytest.mark.django_db
class TestCompletionDoesNotCascade:
    def test_marking_done_does_not_change_linked_risk_status_or_any_baseline_answer(
        self, client_a, org_a, risk_a, user_a
    ):
        baseline_answer = _baseline_answer(org_a)
        original_risk_status = risk_a.status
        original_answer_value = baseline_answer.answer
        original_answer_updated_at = baseline_answer.updated_at

        action = RemediationAction.objects.create(
            organisation=org_a,
            title="Address MFA gap",
            created_by=user_a,
            risk=risk_a,
            control_key=baseline_answer.question_key,
        )

        response = client_a.post(reverse("remediation:complete", args=[org_a.id, action.id]))
        assert response.status_code == 302

        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_DONE

        # Independent objects, queried fresh from the DB - not the
        # action's own fields.
        risk_a.refresh_from_db()
        assert risk_a.status == original_risk_status

        reloaded_answer = BaselineAnswer.objects.get(pk=baseline_answer.pk)
        assert reloaded_answer.answer == original_answer_value
        assert reloaded_answer.updated_at == original_answer_updated_at
        assert reloaded_answer.note == "original note"

        # No BaselineAnswer row at all was created or deleted anywhere in
        # this organisation as a side effect of completion.
        assert BaselineAnswer.objects.filter(assessment__organisation=org_a).count() == 1

    def test_marking_accepted_does_not_change_linked_risk_status_or_any_baseline_answer(
        self, client_a, org_a, risk_a, user_a
    ):
        baseline_answer = _baseline_answer(org_a, question_key="backups", answer="unknown")
        original_risk_status = risk_a.status
        original_answer_value = baseline_answer.answer

        action = RemediationAction.objects.create(
            organisation=org_a,
            title="Accept the backups gap for now",
            created_by=user_a,
            risk=risk_a,
            control_key=baseline_answer.question_key,
        )

        response = client_a.post(reverse("remediation:accept", args=[org_a.id, action.id]))
        assert response.status_code == 302

        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_ACCEPTED

        risk_a.refresh_from_db()
        assert risk_a.status == original_risk_status

        reloaded_answer = BaselineAnswer.objects.get(pk=baseline_answer.pk)
        assert reloaded_answer.answer == original_answer_value
