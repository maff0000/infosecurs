"""
M008C-WI3: Stage 5 "Your Risks & Actions"
(`risk_register.views.foundations_risks_actions`) - a deterministic,
zero-AI guided summary that re-derives, LIVE, whether each draft risk is
currently CONFIRMED (its scenario's winning control answer is 'no') or
still NEEDS CONFIRMATION (the winning answer is 'unknown'), never trusting
anything cached on the `Risk` row itself.
"""
import uuid

import pytest
from django.urls import reverse

from key_assets.models import (
    CATEGORY_ENDPOINT,
    CATEGORY_INFORMATION,
    CATEGORY_NETWORK_OR_LOCATION,
    KeyAsset,
)
from risk_register.models import Risk
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _asset(org, category, name="Test asset"):
    return KeyAsset.objects.create(
        organisation=org, name=name, category=category, criticality="medium",
        status=KeyAsset.STATUS_CONFIRMED,
    )


def _set_answer(org, question_key, answer):
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=question_key, defaults={"answer": answer}
    )
    return assessment


@pytest.mark.django_db
class TestFoundationsRisksActionsView:
    def test_get_is_allowed_and_renders(self, client_a, org_a):
        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        assert response.status_code == 200

    def test_get_auto_generates_risks_from_current_facts(self, client_a, org_a):
        _asset(org_a, CATEGORY_ENDPOINT)
        _set_answer(org_a, "device_encryption", "no")
        assert Risk.objects.filter(organisation=org_a).count() == 0

        client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))

        assert Risk.objects.filter(
            organisation=org_a, scenario_id="endpoint_device_encryption_loss_theft"
        ).exists()

    def test_headline_copy_exact_format(self, client_a, org_a):
        # CATEGORY_NETWORK_OR_LOCATION has exactly ONE catalogue scenario
        # (network_remote_access_uncontrolled_path, control_keys=
        # ("remote_access_control",)) - unlike CATEGORY_ENDPOINT (3
        # scenarios), so a single asset here produces exactly one risk,
        # keeping this test's headline-count arithmetic unambiguous.
        _asset(org_a, CATEGORY_NETWORK_OR_LOCATION)
        _set_answer(org_a, "remote_access_control", "no")

        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        content = response.content.decode()
        assert "1 security risks identified · 0 things still need confirming" in content

    def test_no_baseline_answer_at_all_is_classified_as_needing_confirmation(
        self, client_a, org_a
    ):
        """A control that was never answered at all defaults to 'unknown',
        same as an explicit 'not sure' (scenario_engine's own
        'missing answer -> unknown' rule) - so the risk must land in
        'needing confirmation', never silently dropped or confirmed."""
        _asset(org_a, CATEGORY_NETWORK_OR_LOCATION)
        # No BaselineAnswer row for remote_access_control at all.

        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        content = response.content.decode()
        assert "1 security risks identified · 1 things still need confirming" in content

    def test_no_answer_resolves_to_needing_confirmation_with_a_question_link(
        self, client_a, org_a
    ):
        asset = _asset(org_a, CATEGORY_ENDPOINT)
        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        content = response.content.decode()
        risk = Risk.objects.get(
            organisation=org_a, scenario_id="endpoint_device_encryption_loss_theft", key_asset=asset
        )
        assert risk.title in content
        question_url = reverse(
            "security_baseline:foundations_question",
            kwargs={"organisation_id": org_a.id, "question_key": "device_encryption"},
        )
        assert question_url in content

    def test_no_answer_resolves_to_confirmed_with_no_question_link(self, client_a, org_a):
        _asset(org_a, CATEGORY_ENDPOINT)
        _set_answer(org_a, "device_encryption", "no")

        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        content = response.content.decode()
        risk = Risk.objects.get(
            organisation=org_a, scenario_id="endpoint_device_encryption_loss_theft"
        )
        assert risk.title in content
        question_url = reverse(
            "security_baseline:foundations_question",
            kwargs={"organisation_id": org_a.id, "question_key": "device_encryption"},
        )
        assert question_url not in content

    def test_risk_whose_trigger_has_resolved_away_is_excluded_from_both_groups(
        self, client_a, org_a
    ):
        """
        The control was 'no' when the risk was generated, then the
        organisation answered it 'yes' since - the risk's scenario no
        longer applies to current facts at all. It must never be
        misclassified as confirmed (nor needing confirmation): excluded
        from both groups and the headline count entirely.
        """
        _asset(org_a, CATEGORY_NETWORK_OR_LOCATION)
        _set_answer(org_a, "remote_access_control", "no")
        client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        risk = Risk.objects.get(
            organisation=org_a, scenario_id="network_remote_access_uncontrolled_path"
        )
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED  # still draft, never mutated

        _set_answer(org_a, "remote_access_control", "yes")

        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        content = response.content.decode()
        assert risk.title not in content
        assert "0 security risks identified · 0 things still need confirming" in content

    def test_confirmed_and_unconfirmed_risks_both_appear_together(self, client_a, org_a):
        # Two single-scenario categories (see test_headline_copy_exact_format's
        # own comment on why CATEGORY_ENDPOINT - 3 scenarios - is avoided
        # here): CATEGORY_NETWORK_OR_LOCATION's one scenario is answered
        # 'no' (confirmed); CATEGORY_INFORMATION's one scenario
        # (information_backups_loss_or_corruption, control_keys=
        # ("backups",)) is left unanswered (needing confirmation).
        _asset(org_a, CATEGORY_NETWORK_OR_LOCATION, name="Confirmed-gap asset")
        _asset(org_a, CATEGORY_INFORMATION, name="Unconfirmed-gap asset")
        _set_answer(org_a, "remote_access_control", "no")
        # backups left unanswered -> defaults to unknown.

        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        content = response.content.decode()
        assert "2 security risks identified · 1 things still need confirming" in content


@pytest.mark.django_db
class TestFoundationsRisksActionsTenantIsolation:
    def test_non_member_gets_404(self, client_b, org_a):
        response = client_b.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        assert response.status_code == 404

    def test_anonymous_user_is_redirected_to_login(self, client, org_a):
        response = client.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        assert response.status_code == 302
        assert "login" in response.url

    def test_nonexistent_organisation_id_is_404(self, client_a):
        response = client_a.get(
            reverse("risk_register:foundations_risks_actions", args=[uuid.uuid4()])
        )
        assert response.status_code == 404

    def test_member_does_not_see_other_organisations_risks(self, client_a, org_a, org_b):
        _asset(org_a, CATEGORY_ENDPOINT)
        _set_answer(org_a, "device_encryption", "no")
        other_risk = Risk.objects.create(
            organisation=org_b,
            title="Org B secret risk",
            scenario_id="endpoint_device_encryption_loss_theft",
            threat="t",
            vulnerability="v",
            impact=3,
            likelihood=3,
            rationale="impact_3_confidential_data",
            proposed_treatment="treatment_mitigate_suggested",
            status=Risk.STATUS_DRAFT_AI_SUGGESTED,
            source=Risk.SOURCE_AI,
        )

        response = client_a.get(reverse("risk_register:foundations_risks_actions", args=[org_a.id]))
        content = response.content.decode()
        assert other_risk.title not in content
