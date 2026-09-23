"""
Tests for risk_register.grounding.build_grounding_payload.

PID.md M002 §16, "the last item is critical": a cross-tenant fact appearing
in an AI prompt/request is a catastrophic defect even if the UI never
displays it. These tests exercise the grounding function directly (not
through the AI adapter), proving org A's payload can never contain org B's
data - see test_tenant_isolation.py for the companion test that inspects
what actually reached the (Fake) gateway end-to-end.
"""
import pytest

from key_assets.models import KeyAsset
from risk_register.grounding import build_grounding_payload


@pytest.mark.django_db
class TestGroundingPayloadShape:
    def test_empty_organisation_returns_empty_fact_groups(self, org_a):
        grounding = build_grounding_payload(org_a)
        assert grounding.organisation_id == str(org_a.pk)
        assert grounding.profile_facts == {}
        assert grounding.baseline_facts == {}
        assert grounding.asset_facts == []

    def test_organisation_id_matches_the_organisation_passed_in(self, org_a, org_b):
        grounding_a = build_grounding_payload(org_a)
        grounding_b = build_grounding_payload(org_b)
        assert grounding_a.organisation_id == str(org_a.pk)
        assert grounding_b.organisation_id == str(org_b.pk)
        assert grounding_a.organisation_id != grounding_b.organisation_id

    def test_profile_facts_include_expected_keys(self, org_a, profile_a):
        grounding = build_grounding_payload(org_a)
        assert grounding.profile_facts["working_model"] == "hybrid"
        assert grounding.profile_facts["endpoint_management"] == "byod"
        assert grounding.profile_facts["handles_personal_data"] == "yes"
        assert grounding.profile_facts["description"] == profile_a.description

    def test_baseline_facts_include_answer_and_note(self, org_a, baseline_a):
        grounding = build_grounding_payload(org_a)
        assert grounding.baseline_facts["mfa_user_accounts"]["answer"] == "no"
        assert grounding.baseline_facts["backups"]["answer"] == "unknown"
        assert "Org A's own baseline note" in grounding.baseline_facts["mfa_user_accounts"]["note"]

    def test_only_confirmed_assets_are_included(self, org_a):
        confirmed = KeyAsset.objects.create(
            organisation=org_a,
            name="Confirmed asset",
            category="endpoint",
            criticality="medium",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        KeyAsset.objects.create(
            organisation=org_a,
            name="Suggested asset - not yet reviewed",
            category="endpoint",
            criticality="medium",
            status=KeyAsset.STATUS_SUGGESTED,
        )
        KeyAsset.objects.create(
            organisation=org_a,
            name="Dismissed asset - explicitly rejected",
            category="endpoint",
            criticality="medium",
            status=KeyAsset.STATUS_DISMISSED,
        )
        grounding = build_grounding_payload(org_a)
        names = [a["name"] for a in grounding.asset_facts]
        assert names == ["Confirmed asset"]
        assert grounding.asset_facts[0]["id"] == str(confirmed.id)


@pytest.mark.django_db
class TestGroundingPayloadTenantIsolation:
    """
    Release-blocking (PID.md M002 §16 "the last item is critical").

    Builds distinct, uniquely-identifiable content for org_a and org_b
    across profile, baseline and assets, then proves org A's payload
    contains none of org B's content and vice versa - not just that the
    organisation_id differs.
    """

    def test_org_a_payload_never_contains_org_b_profile_facts(
        self, org_a, org_b, profile_a, profile_b
    ):
        grounding_a = build_grounding_payload(org_a)
        assert grounding_a.profile_facts["description"] == profile_a.description
        assert profile_b.description not in grounding_a.profile_facts.values()
        assert profile_b.commercial_security_driver not in grounding_a.profile_facts.values()
        assert grounding_a.profile_facts["commercial_security_driver"] != profile_b.commercial_security_driver

    def test_org_b_payload_never_contains_org_a_profile_facts(
        self, org_a, org_b, profile_a, profile_b
    ):
        grounding_b = build_grounding_payload(org_b)
        assert grounding_b.profile_facts["description"] == profile_b.description
        assert profile_a.description not in grounding_b.profile_facts.values()

    def test_org_a_payload_never_contains_org_b_baseline_facts(
        self, org_a, org_b, baseline_a, baseline_b
    ):
        grounding_a = build_grounding_payload(org_a)
        all_notes = [entry["note"] for entry in grounding_a.baseline_facts.values()]
        assert not any("never for org A" in note for note in all_notes)
        assert "Org A's own baseline note" in grounding_a.baseline_facts["mfa_user_accounts"]["note"]

    def test_org_a_payload_never_contains_org_b_asset_facts(
        self, org_a, org_b, confirmed_asset_a, confirmed_asset_b
    ):
        grounding_a = build_grounding_payload(org_a)
        asset_ids = [a["id"] for a in grounding_a.asset_facts]
        asset_names = [a["name"] for a in grounding_a.asset_facts]
        assert str(confirmed_asset_b.id) not in asset_ids
        assert confirmed_asset_b.name not in asset_names
        assert str(confirmed_asset_a.id) in asset_ids

    def test_org_b_payload_never_contains_org_a_asset_facts(
        self, org_a, org_b, confirmed_asset_a, confirmed_asset_b
    ):
        grounding_b = build_grounding_payload(org_b)
        asset_ids = [a["id"] for a in grounding_b.asset_facts]
        assert str(confirmed_asset_a.id) not in asset_ids
        assert str(confirmed_asset_b.id) in asset_ids

    def test_full_payload_serialised_as_json_has_no_cross_tenant_leakage(
        self, org_a, org_b, profile_a, profile_b, baseline_a, baseline_b,
        confirmed_asset_a, confirmed_asset_b,
    ):
        """
        Belt-and-braces: serialise org A's entire payload to JSON (the same
        transformation ai_platform.prompts.risk_generation_v1.build_messages
        performs before it ever leaves the process) and assert none of org
        B's uniquely-identifiable strings appear anywhere in it.
        """
        import json

        grounding_a = build_grounding_payload(org_a)
        serialised = json.dumps(
            {
                "profile_facts": grounding_a.profile_facts,
                "baseline_facts": grounding_a.baseline_facts,
                "asset_facts": grounding_a.asset_facts,
            }
        )
        assert profile_b.description not in serialised
        assert profile_b.commercial_security_driver not in serialised
        assert confirmed_asset_b.name not in serialised
        assert str(confirmed_asset_b.id) not in serialised
        assert str(org_b.pk) not in serialised
