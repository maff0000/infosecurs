import uuid

import pytest
from django.urls import reverse

from key_assets.models import KeyAsset
from risk_register.models import Risk
from risk_register.services import generate_draft_risks
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _draft(org, **overrides):
    defaults = dict(
        organisation=org, title="Org risk", threat="t", vulnerability="v",
        impact=3, likelihood=3, rationale="r", proposed_treatment="p",
        status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_AI,
    )
    defaults.update(overrides)
    return Risk.objects.create(**defaults)


@pytest.mark.django_db
class TestRiskTenantIsolation:
    """
    Release-blocking (PID.md M002 §16, §21 "Risk domain" -> tenant
    isolation). Two synthetic organisations, two users each a member of
    exactly one, proving organisation A cannot read, edit, confirm, dismiss
    or otherwise reach organisation B's risk register.
    """

    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_own_organisations_risk_list(self, client_a, org_a):
        _draft(org_a, title="Org A test risk")
        response = client_a.get(reverse("risk_register:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Org A test risk" in response.content

    # --- cross-tenant read negative ---------------------------------------
    def test_member_cannot_read_other_organisations_risk_list(self, client_b, org_a):
        _draft(org_a, title="Org A secret risk")
        response = client_b.get(reverse("risk_register:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_risk_detail(self, client_b, org_a):
        risk = _draft(org_a)
        response = client_b.get(reverse("risk_register:detail", args=[org_a.id, risk.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_risk_edit_form(self, client_b, org_a):
        risk = _draft(org_a)
        response = client_b.get(reverse("risk_register:edit", args=[org_a.id, risk.id]))
        assert response.status_code == 404

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_edit_other_organisations_risk(self, client_b, org_a):
        risk = _draft(org_a, title="Original title")
        response = client_b.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            {
                "title": "Hijacked by user_b", "threat": "t", "vulnerability": "v",
                "impact": "5", "likelihood": "5", "rationale": "r", "proposed_treatment": "p",
            },
        )
        assert response.status_code == 404
        risk.refresh_from_db()
        assert risk.title == "Original title"

    def test_member_cannot_confirm_other_organisations_risk(self, client_b, org_a):
        risk = _draft(org_a)
        response = client_b.post(reverse("risk_register:confirm", args=[org_a.id, risk.id]))
        assert response.status_code == 404
        risk.refresh_from_db()
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED
        assert risk.confirmed_by_id is None

    def test_member_cannot_dismiss_other_organisations_risk(self, client_b, org_a):
        risk = _draft(org_a)
        response = client_b.post(reverse("risk_register:dismiss", args=[org_a.id, risk.id]))
        assert response.status_code == 404
        risk.refresh_from_db()
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED
        assert risk.dismissed_by_id is None

    def test_member_cannot_trigger_generation_on_other_organisation(self, client_b, org_a):
        response = client_b.post(reverse("risk_register:generate", args=[org_a.id]))
        assert response.status_code == 404
        assert Risk.objects.filter(organisation=org_a).count() == 0

    # --- URL / cross-organisation risk-id manipulation ---------------------
    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("risk_register:list", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_risk_id_from_a_different_organisation_is_404_even_for_a_member(
        self, client_a, org_a, org_b
    ):
        """
        user_a is a member of org_a. A risk that belongs to org_b must not
        be reachable through org_a's URL prefix, even though user_a is
        authenticated and a genuine member of *some* organisation.
        """
        other_org_risk = _draft(org_b, title="Org B test risk")
        response = client_a.get(reverse("risk_register:detail", args=[org_a.id, other_org_risk.id]))
        assert response.status_code == 404

    def test_member_does_not_see_other_organisations_risks_mixed_into_their_own_list(
        self, client_a, org_a, org_b
    ):
        _draft(org_a, title="Org A own risk")
        _draft(org_b, title="Org B test risk")
        response = client_a.get(reverse("risk_register:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Org A own risk" in content
        assert "Org B test risk" not in content


@pytest.mark.django_db
class TestScenarioEngineTenantIsolation:
    """
    PID.md M002 §16, "the last item is critical", carried forward to the
    deterministic scenario-instantiation engine that replaced the AI
    request payload (M002-3b dispatch, PID §0.6). There is no outbound AI
    prompt to inspect any more - this proves organisation A's generation
    run can never be influenced by, or leak, organisation B's confirmed
    assets or canonical baseline answers, by inspecting the actual created
    `Risk` rows (title/vulnerability/grounding_refs/assumptions) rather
    than an outbound payload, mirroring the rigour of the retired
    payload-inspection test above.
    """

    def test_org_as_generation_ignores_org_bs_answer_to_the_same_control(self, org_a, org_b):
        """
        Org B answers a control 'no' for a scenario org A's confirmed
        asset would also be eligible for; org A answers the SAME control
        'yes' (so no risk should be generated for org A at all). If the
        engine ever mixed up organisations when reading canonical baseline
        answers, org A would incorrectly pick up org B's 'no'.
        """
        KeyAsset.objects.create(
            organisation=org_a, name="Org A endpoint", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        KeyAsset.objects.create(
            organisation=org_b, name="Org B endpoint", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        assessment_a = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(
            assessment=assessment_a, question_key="device_encryption", answer="yes"
        )
        assessment_b = BaselineAssessment.objects.create(
            organisation=org_b, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(
            assessment=assessment_b, question_key="device_encryption", answer="no",
            note="org B secret note - never for org A",
        )

        created_a = generate_draft_risks(org_a)

        matching = [r for r in created_a if r.scenario_id == "endpoint_device_encryption_loss_theft"]
        assert matching == []  # org A answered 'yes' - must not trigger regardless of org B
        assert not any("org B secret note" in str(r.assumptions) for r in created_a)

    def test_org_as_generation_never_creates_a_risk_referencing_org_bs_asset(self, org_a, org_b):
        KeyAsset.objects.create(
            organisation=org_a, name="Org A endpoint", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        other_org_asset = KeyAsset.objects.create(
            organisation=org_b, name="Org B endpoint", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )

        created = generate_draft_risks(org_a)

        assert created  # sanity: org A's own asset did produce candidates
        assert all(r.key_asset_id != other_org_asset.id for r in created)
        assert all(r.organisation_id == org_a.pk for r in created)
        assert not any(str(other_org_asset.id) in ref for r in created for ref in r.grounding_refs)
        assert not any(other_org_asset.name in r.title for r in created)

    def test_org_as_generation_never_reads_org_bs_baseline_when_org_a_has_none_of_its_own(
        self, org_a, org_b
    ):
        """
        Org A has no BaselineAssessment at all; org B has one answering the
        same control 'no'. Every one of org A's device-encryption-scenario
        risks must resolve via the 'missing answer -> unknown' default,
        never via org B's row.
        """
        KeyAsset.objects.create(
            organisation=org_a, name="Org A endpoint", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        assessment_b = BaselineAssessment.objects.create(
            organisation=org_b, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(
            assessment=assessment_b, question_key="device_encryption", answer="no",
            note="org B only",
        )

        created = generate_draft_risks(org_a)

        risk = next(r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft")
        assert "not confirmed" in risk.vulnerability
        assert "is not enabled" not in risk.vulnerability  # the assertive 'no' wording org B's answer would produce
        assert "org B only" not in str(risk.assumptions)
