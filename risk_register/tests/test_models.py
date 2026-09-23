import pytest
from django.core.exceptions import ValidationError

from risk_register.models import Risk, band_for, score_for


def _make_risk(organisation, **overrides):
    defaults = dict(
        organisation=organisation,
        title="Weak MFA on staff accounts",
        threat="Account takeover",
        vulnerability="No MFA on ordinary user accounts",
        impact=4,
        likelihood=3,
        rationale="Baseline indicates a gap.",
        proposed_treatment="Enable MFA for all staff accounts.",
        grounding_refs=["baseline.mfa_user_accounts"],
        assumptions=[],
        source=Risk.SOURCE_AI,
        status=Risk.STATUS_DRAFT_AI_SUGGESTED,
    )
    defaults.update(overrides)
    return Risk.objects.create(**defaults)


@pytest.mark.django_db
class TestRiskScoring:
    """PID §21 'Risk domain' -> risk score/band deterministic."""

    @pytest.mark.parametrize(
        "impact,likelihood,expected_score,expected_band",
        [
            (1, 1, 1, "low"),
            (2, 2, 4, "low"),
            (1, 5, 5, "medium"),
            (3, 3, 9, "medium"),
            (2, 5, 10, "high"),
            (4, 4, 16, "high"),
            (5, 4, 20, "critical"),
            (5, 5, 25, "critical"),
        ],
    )
    def test_score_and_band(self, org_a, impact, likelihood, expected_score, expected_band):
        risk = _make_risk(org_a, impact=impact, likelihood=likelihood)
        assert risk.score == expected_score
        assert risk.risk_band == expected_band
        # Pure-function form must agree with the property.
        assert score_for(impact, likelihood) == expected_score
        assert band_for(expected_score) == expected_band

    def test_score_is_not_a_stored_column_it_is_always_recomputed(self, org_a):
        """
        Nothing (an AI response, a form submission, a direct DB write) can
        set a stale score: it does not exist as a column at all, only as a
        property computed from impact/likelihood on every access.
        """
        risk = _make_risk(org_a, impact=2, likelihood=2)
        assert risk.score == 4
        risk.impact = 5
        risk.likelihood = 5
        # No .save() needed - the property recomputes from the in-memory
        # field values, proving there is no cached/stored score to go stale.
        assert risk.score == 25
        assert risk.risk_band == "critical"

    def test_impact_out_of_range_rejected_by_full_clean(self, org_a):
        risk = _make_risk(org_a, impact=6)
        with pytest.raises(ValidationError):
            risk.full_clean()

    def test_likelihood_out_of_range_rejected_by_full_clean(self, org_a):
        risk = _make_risk(org_a, likelihood=0)
        with pytest.raises(ValidationError):
            risk.full_clean()


@pytest.mark.django_db
class TestRiskLifecycle:
    """PID §2, §21 -> AI draft cannot silently become confirmed."""

    def test_default_status_is_draft_ai_suggested(self, org_a):
        risk = _make_risk(org_a)
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED
        assert risk.confirmed_by_id is None
        assert risk.confirmed_at is None

    def test_manual_risk_can_be_created_confirmed_directly(self, org_a):
        """
        A manually-created risk is the customer's own direct assertion, not
        an AI suggestion awaiting review - mirrors key_assets' manual-asset
        convention.
        """
        risk = _make_risk(org_a, source=Risk.SOURCE_MANUAL, status=Risk.STATUS_CONFIRMED)
        assert risk.status == Risk.STATUS_CONFIRMED
        assert risk.source == Risk.SOURCE_MANUAL

    def test_status_enum_rejects_unsupported_value(self, org_a):
        # Built as an unsaved instance + full_clean(), not .objects.create():
        # an out-of-choices value for a CharField only fails at the Django
        # validation layer (full_clean), not necessarily at the DB layer.
        risk = Risk(
            organisation=org_a, title="t", threat="t", vulnerability="v",
            impact=3, likelihood=3, rationale="r", proposed_treatment="p",
            status="half_confirmed",
        )
        with pytest.raises(ValidationError):
            risk.full_clean()

    def test_source_enum_rejects_unsupported_value(self, org_a):
        risk = Risk(
            organisation=org_a, title="t", threat="t", vulnerability="v",
            impact=3, likelihood=3, rationale="r", proposed_treatment="p",
            source="other",
        )
        with pytest.raises(ValidationError):
            risk.full_clean()

    def test_ai_invocation_record_nullable_for_manual_risk(self, org_a):
        risk = _make_risk(org_a, source=Risk.SOURCE_MANUAL)
        assert risk.ai_invocation_record_id is None

    def test_key_asset_deletion_nulls_the_fk_not_the_risk(self, org_a):
        from key_assets.models import KeyAsset

        asset = KeyAsset.objects.create(
            organisation=org_a, name="Test asset", category="other", criticality="low"
        )
        risk = _make_risk(org_a, key_asset=asset)
        asset.delete()
        risk.refresh_from_db()
        assert risk.key_asset_id is None
        # The raw string reference survives even if the resolved FK doesn't.
        assert Risk.objects.filter(pk=risk.pk).exists()

    def test_grounding_refs_and_assumptions_round_trip_as_json_lists(self, org_a):
        risk = _make_risk(
            org_a,
            grounding_refs=["profile.endpoint_management", "asset:1234"],
            assumptions=["staff_count not confirmed"],
        )
        reloaded = Risk.objects.get(pk=risk.pk)
        assert reloaded.grounding_refs == ["profile.endpoint_management", "asset:1234"]
        assert reloaded.assumptions == ["staff_count not confirmed"]

    def test_str_includes_title_organisation_and_status(self, org_a):
        risk = _make_risk(org_a)
        text = str(risk)
        assert "Weak MFA on staff accounts" in text
        assert org_a.name in text
        assert Risk.STATUS_DRAFT_AI_SUGGESTED in text
