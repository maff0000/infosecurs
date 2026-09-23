"""
Tests for risk_register.eval.harness (PID §18).

These are mechanics tests only - `--gateway=fake`, never a live external
LLM (forge-engineer.md rule 8; dispatch instructions "You test this
command's mechanics with --gateway=fake only").
"""
import dataclasses

import pytest

from ai_platform.contracts import GenerationResult, GroundingPayload, RiskCandidate
from ai_platform.testing import FakeGateway, default_valid_result

from risk_register.eval.golden_corpus import GOLDEN_CORPUS
from risk_register.eval.harness import HUMAN_JUDGEMENT_PROPERTIES, _grounding_refs_are_subset, run_eval


class TestGroundingRefsSubsetCheck:
    """
    Proves the check itself actually catches a violation, independent of
    the golden corpus's content - the corpus is deliberately built so a
    generic FakeGateway fixture passes it (see golden_corpus.py docstring),
    so this test exercises the check function directly instead.
    """

    def _grounding(self, **profile_facts):
        return GroundingPayload(
            organisation_id="00000000-0000-0000-0000-000000000000",
            profile_facts=profile_facts,
            baseline_facts={"mfa_user_accounts": {"answer": "no", "note": ""}},
            asset_facts=[{"id": "11111111-1111-1111-1111-111111111111"}],
        )

    def _candidate(self, grounding_refs):
        return RiskCandidate(
            title="t", asset_reference="a", threat="t", vulnerability="v",
            suggested_impact=3, suggested_likelihood=3, rationale="r",
            proposed_treatment="p", grounding_refs=grounding_refs,
        )

    def test_true_when_every_ref_was_actually_supplied(self):
        grounding = self._grounding(endpoint_management="byod")
        candidate = self._candidate(
            ["profile.endpoint_management", "baseline.mfa_user_accounts",
             "asset:11111111-1111-1111-1111-111111111111"]
        )
        assert _grounding_refs_are_subset([candidate], grounding) is True

    def test_false_when_a_ref_was_never_supplied_fabricated(self):
        grounding = self._grounding(endpoint_management="byod")
        candidate = self._candidate(["profile.iso27001_status"])  # never in profile_facts
        assert _grounding_refs_are_subset([candidate], grounding) is False

    def test_false_when_asset_ref_points_at_an_asset_id_not_supplied(self):
        grounding = self._grounding(endpoint_management="byod")
        candidate = self._candidate(["asset:99999999-9999-9999-9999-999999999999"])
        assert _grounding_refs_are_subset([candidate], grounding) is False

    def test_one_bad_candidate_among_good_ones_fails_the_whole_check(self):
        grounding = self._grounding(endpoint_management="byod")
        good = self._candidate(["profile.endpoint_management"])
        bad = self._candidate(["profile.this_was_never_supplied"])
        assert _grounding_refs_are_subset([good, bad], grounding) is False


@pytest.mark.django_db
class TestRunEvalMechanics:
    def test_runs_all_eight_corpus_cases(self):
        gw = FakeGateway(mode="valid")
        report = run_eval(gw)
        assert report["case_count"] == 8
        assert len(report["cases"]) == 8
        assert {c["key"] for c in report["cases"]} == {c["key"] for c in GOLDEN_CORPUS}

    def test_report_is_json_serialisable(self):
        import json

        gw = FakeGateway(mode="valid")
        report = run_eval(gw)
        json.dumps(report)  # must not raise

    def test_every_case_carries_raw_candidates_for_human_review(self):
        gw = FakeGateway(mode="valid")
        report = run_eval(gw)
        for case in report["cases"]:
            assert case["raw_candidates"], f"case {case['key']} has no raw candidates to review"
            assert case["human_judgement_properties_to_review"] == HUMAN_JUDGEMENT_PROPERTIES

    def test_overall_verdict_green_when_every_case_mechanically_passes(self):
        gw = FakeGateway(mode="valid")
        report = run_eval(gw)
        assert report["overall_verdict"] == "green"
        for case in report["cases"]:
            assert case["generation_succeeded"] is True
            assert case["objective_checks"]["grounding_refs_subset_of_supplied_facts"] is True
            assert case["objective_checks"]["impact_likelihood_within_bounds"] is True
            assert case["objective_checks"]["cross_tenant_data_possible"] is False

    def test_a_failing_gateway_produces_a_red_verdict_and_no_crash(self):
        gw = FakeGateway(mode="invalid_schema")
        report = run_eval(gw)
        assert report["overall_verdict"] == "red"
        for case in report["cases"]:
            assert case["generation_succeeded"] is False
            assert case["error"]

    def test_a_fabricated_grounding_ref_is_caught_and_turns_the_verdict_red(self):
        """
        Belt-and-braces at the run_eval level: force one case's result to
        contain a grounding_ref never supplied in that case's own payload,
        and prove the harness's overall_verdict correctly goes red rather
        than silently passing it through.
        """
        case = GOLDEN_CORPUS[0]
        base = default_valid_result()
        fabricated = dataclasses.replace(
            base.candidates[0], grounding_refs=["profile.this_fact_was_never_supplied"]
        )
        bad_result = dataclasses.replace(base, candidates=[fabricated])
        gw = FakeGateway(mode="valid", result=bad_result)

        report = run_eval(gw, corpus=[case])
        assert report["overall_verdict"] == "red"
        assert report["cases"][0]["objective_checks"]["grounding_refs_subset_of_supplied_facts"] is False

    def test_token_totals_are_summed_across_successful_cases(self):
        gw = FakeGateway(mode="valid")
        report = run_eval(gw)
        # default_valid_result() fixture reports prompt_tokens=123, completion_tokens=45.
        assert report["token_totals"]["prompt_tokens"] == 123 * 8
        assert report["token_totals"]["completion_tokens"] == 45 * 8

    def test_corpus_and_prompt_version_recorded_in_report(self):
        gw = FakeGateway(mode="valid")
        report = run_eval(gw)
        assert report["corpus_version"] == "m002-golden-corpus-v1"
        assert report["prompt_version"] == "risk_generation_v1"
        assert "generated_at" in report
