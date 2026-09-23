import uuid

import pytest
from django.urls import reverse

from ai_platform.testing import FakeGateway

from risk_register.models import Risk
from risk_register.services import generate_draft_risks


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
class TestAIRequestPayloadTenantIsolation:
    """
    PID.md M002 §16, "the last item is critical": a cross-tenant fact
    appearing in an AI prompt/request is a catastrophic defect even if the
    UI never displays it.

    This directly inspects what `GroundingPayload` was actually passed to
    the (Fake) gateway for organisation A, and asserts organisation B's
    profile/baseline/asset facts never appear in it - not merely that the
    HTTP responses are isolated.
    """

    def test_fake_gateway_receives_only_organisation_as_own_facts(
        self, org_a, org_b, profile_a, profile_b, baseline_a, baseline_b,
        confirmed_asset_a, confirmed_asset_b,
    ):
        gw = FakeGateway(mode="valid")
        generate_draft_risks(org_a, gateway=gw)

        assert len(gw.calls) == 1
        grounding_sent, _prompt_version = gw.calls[0]

        # Correct tenant.
        assert grounding_sent.organisation_id == str(org_a.pk)

        # Org A's own facts are present.
        assert grounding_sent.profile_facts["description"] == profile_a.description
        assert any(a["id"] == str(confirmed_asset_a.id) for a in grounding_sent.asset_facts)

        # Org B's facts are absent, in every fact group, by value.
        assert profile_b.description not in grounding_sent.profile_facts.values()
        assert profile_b.commercial_security_driver not in grounding_sent.profile_facts.values()
        assert not any(a["id"] == str(confirmed_asset_b.id) for a in grounding_sent.asset_facts)
        assert not any(a["name"] == confirmed_asset_b.name for a in grounding_sent.asset_facts)
        baseline_notes = [entry["note"] for entry in grounding_sent.baseline_facts.values()]
        assert not any("never for org A" in note for note in baseline_notes)

        # Full JSON-serialised form (what would actually leave the process
        # via ai_platform.prompts.risk_generation_v1.build_messages) must
        # not contain org B's organisation id or any of its unique strings.
        import json

        serialised = json.dumps(
            {
                "profile_facts": grounding_sent.profile_facts,
                "baseline_facts": grounding_sent.baseline_facts,
                "asset_facts": grounding_sent.asset_facts,
            }
        )
        assert str(org_b.pk) not in serialised
        assert confirmed_asset_b.name not in serialised
        assert profile_b.description not in serialised

    def test_fake_gateway_receives_only_organisation_b_own_facts_when_called_for_b(
        self, org_a, org_b, profile_a, profile_b, confirmed_asset_a, confirmed_asset_b,
    ):
        gw = FakeGateway(mode="valid")
        generate_draft_risks(org_b, gateway=gw)

        grounding_sent, _prompt_version = gw.calls[0]
        assert grounding_sent.organisation_id == str(org_b.pk)
        assert grounding_sent.profile_facts["description"] == profile_b.description
        assert profile_a.description not in grounding_sent.profile_facts.values()
        assert not any(a["id"] == str(confirmed_asset_a.id) for a in grounding_sent.asset_facts)
