"""
M008C-WI3: `risk_register.scenario_engine.current_trigger_variant` /
`current_unconfirmed_control_keys` - the public, LIVE re-derivation helpers
Stage 5 "Your Risks & Actions" needs so it never trusts anything cached on
a `Risk` row (see that module's own docstrings for the full contract).
"""
import pytest

from key_assets.models import CATEGORY_CLOUD_SERVICE, CATEGORY_ENDPOINT, KeyAsset
from risk_register.methodology import VARIANT_NO, VARIANT_UNKNOWN
from risk_register.models import Risk
from risk_register.scenario_engine import (
    current_trigger_variant,
    current_unconfirmed_control_keys,
    instantiate_risks_for_organisation,
)
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


@pytest.mark.django_db
class TestCurrentTriggerVariant:
    def test_returns_no_for_a_confirmed_gap(self, org_a):
        _asset(org_a, CATEGORY_ENDPOINT)
        _set_answer(org_a, "device_encryption", "no")
        created = instantiate_risks_for_organisation(org_a)
        risk = next(r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft")

        assert current_trigger_variant(risk) == VARIANT_NO

    def test_returns_unknown_for_an_unanswered_control(self, org_a):
        _asset(org_a, CATEGORY_ENDPOINT)
        created = instantiate_risks_for_organisation(org_a)
        risk = next(r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft")

        assert current_trigger_variant(risk) == VARIANT_UNKNOWN
        assert current_unconfirmed_control_keys(risk) == ["device_encryption"]

    def test_returns_none_once_the_control_is_answered_yes(self, org_a):
        """Live re-derivation, never a stale snapshot: the risk row itself
        is untouched, but the organisation's facts have moved on."""
        _asset(org_a, CATEGORY_ENDPOINT)
        _set_answer(org_a, "device_encryption", "no")
        created = instantiate_risks_for_organisation(org_a)
        risk = next(r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft")
        assert current_trigger_variant(risk) == VARIANT_NO  # sanity, before the change

        _set_answer(org_a, "device_encryption", "yes")

        assert current_trigger_variant(risk) is None
        assert current_unconfirmed_control_keys(risk) == []

    def test_returns_none_for_a_scenario_id_that_does_not_resolve(self, org_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Manual risk", scenario_id="not_a_real_scenario_id",
            threat="t", vulnerability="v", impact=3, likelihood=3,
            rationale="r", proposed_treatment="p",
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_MANUAL,
        )
        assert current_trigger_variant(risk) is None
        assert current_unconfirmed_control_keys(risk) == []

    def test_multi_control_key_scenario_worst_variant_wins_but_the_other_stays_listed_unconfirmed(
        self, org_a
    ):
        """
        `cloud_service_admin_mfa_account_takeover` has two relevant
        control_keys. One answered 'no', the other left unanswered: the
        risk must be classified by the worst ('no') variant, while the
        still-genuinely-unconfirmed other control remains listed by
        `current_unconfirmed_control_keys` (PID's own "uncertainty must
        never be silently dropped" rule, re-applied live)."""
        _asset(org_a, CATEGORY_CLOUD_SERVICE)
        _set_answer(org_a, "mfa_privileged_accounts", "no")
        # privileged_access_separation left unanswered -> unknown.
        created = instantiate_risks_for_organisation(org_a)
        risk = next(
            r for r in created if r.scenario_id == "cloud_service_admin_mfa_account_takeover"
        )

        assert current_trigger_variant(risk) == VARIANT_NO
        assert current_unconfirmed_control_keys(risk) == ["privileged_access_separation"]
