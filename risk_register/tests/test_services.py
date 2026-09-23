"""
Tests for risk_register.services.generate_draft_risks - the seam between
the view and risk_register.scenario_engine.instantiate_risks_for_organisation
(PID §0.6/§0.7, §15; M002-3b dispatch).

REWRITTEN by the M002-3b dispatch: the retired shape of this file drove a
FakeGateway/RiskCandidate-based AI generation flow that no longer exists.
Every test below only ever creates ordinary KeyAsset/BaselineAnswer rows
and calls generate_draft_risks(organisation) directly - no AI call, no
gateway, no ai_platform import anywhere in this file.
"""
import pytest

from key_assets.models import KeyAsset
from risk_register.methodology import CATALOGUE_BY_ID
from risk_register.models import Risk
from risk_register.services import generate_draft_risks
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _confirmed_asset(org, *, category="endpoint", name="Fixture asset"):
    return KeyAsset.objects.create(
        organisation=org,
        name=name,
        category=category,
        criticality="medium",
        status=KeyAsset.STATUS_CONFIRMED,
    )


def _answer(org, question_key, value):
    assessment, _created = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=question_key, defaults={"answer": value}
    )
    return assessment


@pytest.mark.django_db
class TestGenerateDraftRisksHappyPath:
    def test_persists_a_risk_for_a_no_answer_endpoint_scenario(self, org_a):
        asset = _confirmed_asset(org_a)
        _answer(org_a, "device_encryption", "no")

        created = generate_draft_risks(org_a)

        matching = [r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft"]
        assert len(matching) == 1
        risk = matching[0]
        assert risk.organisation_id == org_a.pk
        assert risk.key_asset_id == asset.id
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED
        assert risk.source == Risk.SOURCE_AI
        assert risk.ai_invocation_record_id is None
        assert "is not enabled" in risk.vulnerability
        assert risk.impact == 3
        assert risk.likelihood == 3
        assert risk.grounding_refs == ["baseline.device_encryption", f"asset:{asset.id}"]
        assert risk.assumptions == []
        assert Risk.objects.filter(organisation=org_a).count() == len(created)

    def test_missing_baseline_answer_is_treated_as_unknown_not_as_no_risk(self, org_a):
        """
        Dispatch instruction, verbatim rule: "If the organisation has no
        BaselineAnswer at all for a given question_key ... treat that
        control as unknown for applicability purposes, not as 'yes'/not-
        applicable." No BaselineAssessment is created at all here.
        """
        asset = _confirmed_asset(org_a)

        created = generate_draft_risks(org_a)

        matching = [r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft"]
        assert len(matching) == 1
        risk = matching[0]
        assert "not confirmed" in risk.vulnerability
        assert "is not enabled" not in risk.vulnerability
        assert risk.assumptions == ["baseline.device_encryption: control state not confirmed"]
        assert risk.grounding_refs == ["baseline.device_encryption", f"asset:{asset.id}"]

    def test_yes_answers_never_instantiate_a_scenario(self, org_a):
        _confirmed_asset(org_a)
        _answer(org_a, "device_encryption", "yes")
        _answer(org_a, "endpoint_protection", "yes")
        _answer(org_a, "patching", "yes")

        created = generate_draft_risks(org_a)
        assert created == []
        assert Risk.objects.filter(organisation=org_a).count() == 0

    def test_no_confirmed_assets_produces_no_risks(self, org_a):
        KeyAsset.objects.create(
            organisation=org_a,
            name="Suggested only - not yet reviewed",
            category="endpoint",
            criticality="low",
            status=KeyAsset.STATUS_SUGGESTED,
        )
        created = generate_draft_risks(org_a)
        assert created == []

    def test_only_scenarios_matching_the_assets_category_are_considered(self, org_a):
        _confirmed_asset(org_a, category="people", name="Staff")
        created = generate_draft_risks(org_a)
        assert created  # sanity: 'unknown' defaulting means something is generated
        for risk in created:
            assert CATALOGUE_BY_ID[risk.scenario_id].asset_category == "people"

    def test_no_organisation_wide_facts_leak_between_unrelated_asset_categories(self, org_a):
        """A confirmed 'people' asset must never produce an 'endpoint'
        scenario, even though both exist on the same organisation."""
        _confirmed_asset(org_a, category="people", name="Staff")
        created = generate_draft_risks(org_a)
        endpoint_scenario_ids = {
            sid for sid, s in CATALOGUE_BY_ID.items() if s.asset_category == "endpoint"
        }
        assert not any(r.scenario_id in endpoint_scenario_ids for r in created)


@pytest.mark.django_db
class TestMultiControlKeyResolution:
    """
    This dispatch's required, documented, testable rule for a scenario
    whose `control_keys` names more than one canonical baseline question
    (`cloud_service_admin_mfa_account_takeover`: mfa_privileged_accounts +
    privileged_access_separation). Rule (see scenario_engine.py module
    docstring): applies if ANY relevant control is a trigger state; the
    WORST applicable variant wins - 'no' beats 'unknown'.
    """

    SCENARIO_ID = "cloud_service_admin_mfa_account_takeover"

    def _risk(self, created):
        return next(r for r in created if r.scenario_id == self.SCENARIO_ID)

    def test_no_on_one_relevant_control_beats_unknown_on_the_other(self, org_a):
        _confirmed_asset(org_a, category="cloud_service", name="Azure")
        _answer(org_a, "mfa_privileged_accounts", "no")
        _answer(org_a, "privileged_access_separation", "unknown")

        risk = self._risk(generate_draft_risks(org_a))
        assert "is not protected by MFA" in risk.vulnerability  # the 'no' wording won
        assert risk.assumptions == [
            "baseline.privileged_access_separation: control state not confirmed"
        ]

    def test_both_relevant_controls_unknown_resolves_to_the_unknown_variant(self, org_a):
        _confirmed_asset(org_a, category="cloud_service", name="Azure")
        _answer(org_a, "mfa_privileged_accounts", "unknown")
        _answer(org_a, "privileged_access_separation", "partial")

        risk = self._risk(generate_draft_risks(org_a))
        assert "not confirmed whether" in risk.vulnerability
        assert "is not protected by MFA" not in risk.vulnerability

    def test_scenario_does_not_apply_when_every_relevant_control_is_yes(self, org_a):
        _confirmed_asset(org_a, category="cloud_service", name="Azure")
        _answer(org_a, "mfa_privileged_accounts", "yes")
        _answer(org_a, "privileged_access_separation", "yes")

        created = generate_draft_risks(org_a)
        assert self.SCENARIO_ID not in {r.scenario_id for r in created}

    def test_grounding_refs_cover_every_relevant_control_key_not_only_the_winning_one(self, org_a):
        asset = _confirmed_asset(org_a, category="cloud_service", name="Azure")
        _answer(org_a, "mfa_privileged_accounts", "no")
        _answer(org_a, "privileged_access_separation", "unknown")

        risk = self._risk(generate_draft_risks(org_a))
        assert risk.grounding_refs == [
            "baseline.mfa_privileged_accounts",
            "baseline.privileged_access_separation",
            f"asset:{asset.id}",
        ]


@pytest.mark.django_db
class TestRegenerationDedup:
    """
    PID §15, and this dispatch's §1: "this is your regeneration/dedup
    mechanism, and it must be exact - re-running instantiation must never
    create a duplicate Risk for a combination already represented (draft,
    confirmed, or dismissed), and must never touch/overwrite an existing
    one, regardless of its current status."
    """

    def test_running_twice_with_no_new_facts_creates_no_duplicates(self, org_a):
        _confirmed_asset(org_a)
        first = generate_draft_risks(org_a)
        assert first  # sanity: something was created the first time

        second = generate_draft_risks(org_a)

        assert second == []
        assert Risk.objects.filter(organisation=org_a).count() == len(first)

    def test_confirmed_risk_survives_a_second_run_byte_for_byte(self, org_a):
        _confirmed_asset(org_a)
        first = generate_draft_risks(org_a)
        target = first[0]
        target.status = Risk.STATUS_CONFIRMED
        target.title = "Customer-edited title"
        target.impact = 5
        target.likelihood = 5
        target.save()
        before = Risk.objects.get(pk=target.pk)

        generate_draft_risks(org_a)

        after = Risk.objects.get(pk=target.pk)
        assert after.title == before.title == "Customer-edited title"
        assert after.status == Risk.STATUS_CONFIRMED
        assert after.impact == 5
        assert after.likelihood == 5
        assert after.updated_at == before.updated_at

    def test_confirmed_risk_survives_a_second_run_when_title_is_unchanged(self, org_a):
        """
        Companion to the byte-for-byte test above, deliberately WITHOUT
        editing anything first: the second run's candidate for this exact
        (organisation, scenario_id, key_asset) tuple would be byte-
        identical to the confirmed row, which is exactly the shape a
        title/content-keyed "upsert" regression would silently overwrite
        while the edited-first variant above would not catch - see the
        dispatch report's revert-and-rerun evidence.
        """
        _confirmed_asset(org_a)
        first = generate_draft_risks(org_a)
        target = first[0]
        original_title = target.title
        target.status = Risk.STATUS_CONFIRMED
        target.save()

        generate_draft_risks(org_a)

        target.refresh_from_db()
        assert target.title == original_title
        assert target.status == Risk.STATUS_CONFIRMED
        assert Risk.objects.filter(organisation=org_a).count() == len(first)

    def test_dismissed_risk_also_survives_a_second_run(self, org_a):
        _confirmed_asset(org_a)
        first = generate_draft_risks(org_a)
        target = first[0]
        target.status = Risk.STATUS_DISMISSED
        target.save()

        generate_draft_risks(org_a)

        target.refresh_from_db()
        assert target.status == Risk.STATUS_DISMISSED

    def test_a_newly_confirmed_second_asset_still_generates_its_own_new_risks(self, org_a):
        """Dedup is scoped per (scenario_id, key_asset) - a genuinely new
        confirmed asset must still produce its own candidates on the next
        run, without disturbing the first asset's existing rows."""
        _confirmed_asset(org_a, name="First asset")
        first = generate_draft_risks(org_a)

        second_asset = _confirmed_asset(org_a, name="Second asset")
        second = generate_draft_risks(org_a)

        assert second
        assert all(r.key_asset_id == second_asset.id for r in second)
        assert Risk.objects.filter(organisation=org_a).count() == len(first) + len(second)

    def test_editing_a_baseline_answer_after_first_run_does_not_recreate_an_existing_row(
        self, org_a
    ):
        """The dedup key is (organisation, scenario_id, key_asset) only -
        it must not be reopened by a later baseline-answer edit; a changed
        answer influences only NEW candidates on a later run, never an
        already-persisted row for the same tuple."""
        _confirmed_asset(org_a)
        _answer(org_a, "device_encryption", "unknown")
        first = generate_draft_risks(org_a)
        target = next(r for r in first if r.scenario_id == "endpoint_device_encryption_loss_theft")
        original_vulnerability = target.vulnerability

        _answer(org_a, "device_encryption", "no")
        generate_draft_risks(org_a)

        target.refresh_from_db()
        assert target.vulnerability == original_vulnerability
