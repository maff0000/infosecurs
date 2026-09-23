"""
Tests for risk_register.services.generate_draft_risks - the seam between
the view and ai_platform.orchestration.generate_risks (PID §14, §15).

Only ever uses ai_platform.testing.FakeGateway - never a live external LLM
(PID §17, forge-engineer.md rule 8).
"""
import pytest

from ai_platform.contracts import GenerationResult, RiskCandidate
from ai_platform.models import AIInvocationRecord
from ai_platform.orchestration import GenerationFailed
from ai_platform.testing import FakeGateway

from key_assets.models import KeyAsset
from risk_register.models import Risk
from risk_register.services import generate_draft_risks


@pytest.mark.django_db
class TestGenerateDraftRisksHappyPath:
    def test_persists_one_risk_per_candidate_as_draft_ai_suggested(self, org_a, profile_a):
        gw = FakeGateway(mode="valid")
        created, record = generate_draft_risks(org_a, gateway=gw)

        assert len(created) == 1
        risk = created[0]
        assert risk.organisation_id == org_a.pk
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED
        assert risk.source == Risk.SOURCE_AI
        assert risk.ai_invocation_record_id == record.pk
        assert risk.title == "Weak endpoint protection on staff devices"
        assert risk.impact == 4
        assert risk.likelihood == 3
        assert risk.grounding_refs == ["profile.endpoint_management", "baseline.endpoint_protection"]
        assert Risk.objects.filter(organisation=org_a).count() == 1

    def test_does_not_require_a_completed_profile_or_baseline(self, org_a):
        """
        A brand-new organisation with no profile/baseline/assets yet must
        still be able to call generation (the grounding payload is simply
        mostly empty) rather than erroring - PID §14 does not gate
        generation on profile completeness.
        """
        gw = FakeGateway(mode="valid")
        created, _record = generate_draft_risks(org_a, gateway=gw)
        assert len(created) == 1
        assert len(gw.calls) == 1
        grounding_sent, _prompt_version = gw.calls[0]
        assert grounding_sent.organisation_id == str(org_a.pk)
        assert grounding_sent.profile_facts == {}

    def test_resolves_key_asset_fk_when_asset_reference_matches_a_real_confirmed_asset(
        self, org_a, profile_a
    ):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Fixture endpoint",
            category="endpoint",
            criticality="medium",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        candidate = RiskCandidate(
            title="Risk against a real asset",
            asset_reference=f"asset:{asset.id}",
            threat="t",
            vulnerability="v",
            suggested_impact=3,
            suggested_likelihood=3,
            rationale="r",
            proposed_treatment="p",
            grounding_refs=[f"asset:{asset.id}"],
        )
        result = GenerationResult(candidates=[candidate], prompt_version="risk_generation_v1")
        gw = FakeGateway(mode="valid", result=result)

        created, _record = generate_draft_risks(org_a, gateway=gw)
        assert created[0].key_asset_id == asset.id
        assert created[0].asset_reference == f"asset:{asset.id}"

    def test_asset_reference_that_does_not_resolve_is_kept_as_raw_string_with_null_fk(
        self, org_a, profile_a
    ):
        candidate = RiskCandidate(
            title="Risk against a profile fact, not an asset",
            asset_reference="profile.endpoint_management",
            threat="t",
            vulnerability="v",
            suggested_impact=3,
            suggested_likelihood=3,
            rationale="r",
            proposed_treatment="p",
            grounding_refs=["profile.endpoint_management"],
        )
        result = GenerationResult(candidates=[candidate], prompt_version="risk_generation_v1")
        gw = FakeGateway(mode="valid", result=result)

        created, _record = generate_draft_risks(org_a, gateway=gw)
        assert created[0].key_asset_id is None
        assert created[0].asset_reference == "profile.endpoint_management"

    def test_asset_reference_pointing_at_another_organisations_asset_never_resolves(
        self, org_a, org_b, profile_a
    ):
        """
        A hallucinated or malformed asset_reference must never link a Risk
        to another organisation's KeyAsset, even if the UUID happens to be
        syntactically valid and real (PID §16).
        """
        other_org_asset = KeyAsset.objects.create(
            organisation=org_b,
            name="Org B's asset",
            category="endpoint",
            criticality="medium",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        candidate = RiskCandidate(
            title="Suspicious cross-tenant reference",
            asset_reference=f"asset:{other_org_asset.id}",
            threat="t",
            vulnerability="v",
            suggested_impact=3,
            suggested_likelihood=3,
            rationale="r",
            proposed_treatment="p",
            grounding_refs=[f"asset:{other_org_asset.id}"],
        )
        result = GenerationResult(candidates=[candidate], prompt_version="risk_generation_v1")
        gw = FakeGateway(mode="valid", result=result)

        created, _record = generate_draft_risks(org_a, gateway=gw)
        assert created[0].key_asset_id is None
        assert created[0].organisation_id == org_a.pk


@pytest.mark.django_db
class TestGenerateDraftRisksFailureSafety:
    """PID §14: a gateway outage must leave existing state untouched."""

    def test_generation_failure_creates_no_risk_rows(self, org_a, profile_a):
        gw = FakeGateway(mode="invalid_schema")
        with pytest.raises(GenerationFailed):
            generate_draft_risks(org_a, gateway=gw)
        assert Risk.objects.filter(organisation=org_a).count() == 0

    def test_generation_failure_still_records_a_failed_invocation(self, org_a, profile_a):
        gw = FakeGateway(mode="auth_error")
        with pytest.raises(GenerationFailed) as exc_info:
            generate_draft_risks(org_a, gateway=gw)
        record = exc_info.value.invocation_record
        assert record.status == AIInvocationRecord.STATUS_FAILED
        assert Risk.objects.filter(ai_invocation_record=record).count() == 0


@pytest.mark.django_db
class TestRegenerationDoesNotOverwriteConfirmedRisks:
    """PID §15, §21 -> regeneration does not overwrite confirmed risks."""

    def test_confirmed_risk_survives_a_second_generation_byte_for_byte(self, org_a, profile_a):
        gw1 = FakeGateway(mode="valid")
        first_created, _record1 = generate_draft_risks(org_a, gateway=gw1)
        confirmed = first_created[0]
        confirmed.status = Risk.STATUS_CONFIRMED
        confirmed.title = "Customer-edited title"
        confirmed.impact = 5
        confirmed.likelihood = 5
        confirmed.save()

        before = Risk.objects.get(pk=confirmed.pk)

        gw2 = FakeGateway(mode="valid")
        second_created, record2 = generate_draft_risks(org_a, gateway=gw2)

        after = Risk.objects.get(pk=confirmed.pk)
        assert after.title == before.title == "Customer-edited title"
        assert after.status == Risk.STATUS_CONFIRMED
        assert after.impact == 5
        assert after.likelihood == 5
        assert after.updated_at == before.updated_at

        # Regeneration created a brand new draft, distinct from the
        # confirmed one, tied to the new invocation record.
        assert len(second_created) == 1
        assert second_created[0].pk != confirmed.pk
        assert second_created[0].status == Risk.STATUS_DRAFT_AI_SUGGESTED
        assert second_created[0].ai_invocation_record_id == record2.pk
        assert Risk.objects.filter(organisation=org_a).count() == 2

    def test_confirmed_risk_survives_a_second_generation_when_title_is_unchanged(self, org_a, profile_a):
        """
        Companion to the byte-for-byte test above, deliberately WITHOUT
        editing the title first: the second generation's candidate will
        have the exact same title as the confirmed risk (FakeGateway's
        fixture is deterministic), so this is the specific shape a
        title-keyed "upsert" regression would silently overwrite while the
        title-changed variant above would not catch it - see the dispatch
        report's revert-and-rerun evidence for why this test exists.
        """
        gw1 = FakeGateway(mode="valid")
        first_created, _record1 = generate_draft_risks(org_a, gateway=gw1)
        confirmed = first_created[0]
        original_title = confirmed.title
        confirmed.status = Risk.STATUS_CONFIRMED
        confirmed.save()

        gw2 = FakeGateway(mode="valid")
        generate_draft_risks(org_a, gateway=gw2)

        confirmed.refresh_from_db()
        assert confirmed.title == original_title
        assert confirmed.status == Risk.STATUS_CONFIRMED
        assert Risk.objects.filter(organisation=org_a).count() == 2

    def test_dismissed_risk_also_survives_a_second_generation(self, org_a, profile_a):
        gw1 = FakeGateway(mode="valid")
        first_created, _record1 = generate_draft_risks(org_a, gateway=gw1)
        dismissed = first_created[0]
        dismissed.status = Risk.STATUS_DISMISSED
        dismissed.save()

        gw2 = FakeGateway(mode="valid")
        generate_draft_risks(org_a, gateway=gw2)

        dismissed.refresh_from_db()
        assert dismissed.status == Risk.STATUS_DISMISSED
