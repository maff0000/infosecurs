"""
Tests for `questionnaire.eval.harness` (PID §28 - m005-3-eval-harness
dispatch).

Mechanics-only tests using fake gateways, never a live external LLM
(forge-engineer.md rule 8; dispatch instructions "you test the harness
mechanics with --gateway=fake only"). Mirrors `policy/tests/
test_eval_harness.py`'s shape.

`test_fake_mode_is_green_...` is the self-consistency proof described in
`questionnaire.eval.harness`'s own module docstring: if this is RED, the
corpus's tenant state does not actually cohere with its own claimed
`expected_outcome`, and the CORPUS must be fixed, not the harness.

`TestNegativeControl` proves the harness can actually produce RED, not just
praise success - a deliberately wrong local test-only case, run directly
through `_run_case`/`_case_is_green` without touching the real corpus.
"""
import json

import pytest

from ai_platform.questionnaire_drafting_contracts import QuestionnaireDraft
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation

from questionnaire.eval.golden_corpus import (
    GOLDEN_CORPUS,
    ensure_eval_actor_user,
)
from questionnaire.eval.harness import (
    HUMAN_JUDGEMENT_PROPERTIES,
    INJECTION_CASE_KEY,
    _UUID_RE,
    _alarming_language_flag,
    _case_is_green,
    _no_identifier_leak,
    _run_case,
    run_eval,
)


# ---------------------------------------------------------------------------
# Pure-function checks, in isolation
# ---------------------------------------------------------------------------

class TestNoIdentifierLeak:
    def test_true_when_no_uuid_shaped_text_present(self):
        assert _no_identifier_leak("A plain summary.", "A plain answer.", []) is True

    def test_false_when_summary_contains_a_uuid(self):
        summary = "See record 6747bc6a-843f-4744-b9f7-3757d875cf20"
        assert _no_identifier_leak(summary, "answer", []) is False

    def test_false_when_answer_text_contains_a_uuid(self):
        answer = "See record 6747bc6a-843f-4744-b9f7-3757d875cf20"
        assert _no_identifier_leak("summary", answer, []) is False

    def test_false_when_a_review_warning_contains_a_uuid(self):
        warnings = ["Ref 6747bc6a-843f-4744-b9f7-3757d875cf20"]
        assert _no_identifier_leak("summary", "answer", warnings) is False

    def test_regex_matches_uuid_shape_case_insensitively(self):
        assert _UUID_RE.search("ID: 6747BC6A-843F-4744-B9F7-3757D875CF20") is not None


class TestAlarmingLanguageFlag:
    def test_flags_a_known_alarming_phrase(self):
        result = _alarming_language_flag("This is a catastrophic failure of security.")
        assert result["flagged"] is True
        assert "catastrophic" in result["matches"]

    def test_does_not_flag_ordinary_content(self):
        result = _alarming_language_flag("Multi-factor authentication is enabled for all admins.")
        assert result["flagged"] is False
        assert result["matches"] == []


class TestCaseIsGreen:
    def _base_checks(self, **overrides):
        checks = {
            "generation_succeeded": True,
            "output_contract_valid": True,
            "interpretation_keys_valid": True,
            "intent_type_correct": True,
            "requirement_scope_correct": True,
            "evidence_explicitly_requested_correct": True,
            "outcome_exact": True,
            "no_drafting_outcome_upgrade": True,
            "no_identifier_leak": True,
            "cross_tenant_data_possible": False,
        }
        checks.update(overrides)
        return checks

    def test_green_when_every_check_passes(self):
        assert _case_is_green({"objective_checks": self._base_checks()}) is True

    def test_red_when_outcome_exact_is_false(self):
        assert _case_is_green({"objective_checks": self._base_checks(outcome_exact=False)}) is False

    def test_red_when_cross_tenant_data_possible_is_true(self):
        assert (
            _case_is_green({"objective_checks": self._base_checks(cross_tenant_data_possible=True)})
            is False
        )

    def test_none_values_do_not_count_as_failure(self):
        checks = self._base_checks(
            interpretation_keys_valid=None, intent_type_correct=None, requirement_scope_correct=None
        )
        assert _case_is_green({"objective_checks": checks}) is True

    def test_red_when_prompt_injection_resisted_present_and_false(self):
        checks = self._base_checks()
        checks["prompt_injection_resisted"] = False
        assert _case_is_green({"objective_checks": checks}) is False


# ---------------------------------------------------------------------------
# run_eval, end to end, against fresh per-case fake gateways
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRunEvalMechanics:
    def test_runs_all_fourteen_corpus_cases(self):
        report = run_eval("fake")
        assert report["case_count"] == 14
        assert len(report["cases"]) == 14
        assert {c["key"] for c in report["cases"]} == {c["key"] for c in GOLDEN_CORPUS}

    def test_report_is_json_serialisable(self):
        report = run_eval("fake")
        json.dumps(report)  # must not raise

    def test_fake_mode_is_green_proving_corpus_self_consistency(self):
        """THE self-consistency proof (see module docstring): if this is
        RED, fix the corpus, not the harness."""
        report = run_eval("fake")
        assert report["overall_verdict"] == "green", json.dumps(report, indent=2, default=str)

    def test_invalid_gateway_mode_raises_value_error(self):
        with pytest.raises(ValueError):
            run_eval("bogus")

    def test_injection_case_reports_prompt_injection_resisted(self):
        report = run_eval("fake")
        case = next(c for c in report["cases"] if c["key"] == INJECTION_CASE_KEY)
        assert case["objective_checks"]["prompt_injection_resisted"] is True

    def test_prompt_injection_resisted_only_reported_for_the_injection_case(self):
        report = run_eval("fake")
        for case in report["cases"]:
            if case["key"] == INJECTION_CASE_KEY:
                continue
            assert "prompt_injection_resisted" not in case["objective_checks"]

    def test_ambiguous_case_has_interpretation_grading_switched_off(self):
        report = run_eval("fake")
        case = next(c for c in report["cases"] if c["key"] == "ambiguous_compound_question")
        assert case["objective_checks"]["interpretation_keys_valid"] is None
        assert case["objective_checks"]["intent_type_correct"] is None
        assert case["objective_checks"]["requirement_scope_correct"] is None
        # outcome_exact and evidence_explicitly_requested_correct are still
        # graded even though interpretation grading is off.
        assert case["objective_checks"]["outcome_exact"] is True
        assert case["objective_checks"]["evidence_explicitly_requested_correct"] is True

    def test_policy_artefact_existence_requires_at_least_one_policy_section_key(self):
        report = run_eval("fake")
        case = next(c for c in report["cases"] if c["key"] == "policy_artefact_existence")
        assert case["objective_checks"]["interpretation_keys_valid"] is True
        assert any(
            key.startswith("policy_section:") for key in case["actual_interpretation"]["selected_keys"]
        )

    def test_policy_requires_mfa_case_has_intent_type_grading_switched_off_only(self):
        """Post-live-eval-run-1 refinement (docs/evidence/
        M005-LIVE-EVALUATION.md): only intent_type_correct is opted out for
        this case - interpretation_keys_valid/requirement_scope_correct
        remain fully graded."""
        report = run_eval("fake")
        case = next(
            c for c in report["cases"] if c["key"] == "policy_requires_mfa_implementation_partial"
        )
        assert case["objective_checks"]["intent_type_correct"] is None
        assert case["objective_checks"]["interpretation_keys_valid"] is True
        assert case["objective_checks"]["requirement_scope_correct"] is True
        assert case["objective_checks"]["outcome_exact"] is True

    def test_genuine_not_applicable_case_has_requirement_scope_grading_switched_off_only(self):
        """Post-live-eval-run-1 refinement (docs/evidence/
        M005-LIVE-EVALUATION.md): only requirement_scope_correct is opted
        out for this case - interpretation_keys_valid/intent_type_correct
        remain fully graded."""
        report = run_eval("fake")
        case = next(c for c in report["cases"] if c["key"] == "genuine_not_applicable")
        assert case["objective_checks"]["requirement_scope_correct"] is None
        assert case["objective_checks"]["interpretation_keys_valid"] is True
        assert case["objective_checks"]["intent_type_correct"] is True
        assert case["objective_checks"]["outcome_exact"] is True

    def test_certification_question_case_has_requirement_scope_grading_switched_off_only(self):
        """M006 Round 7 correction (PR #42 §A): the live harness returned
        RED on both Round 7 runs solely because
        certification_question's requirement_scope_correct == false -
        requirement_scope is genuinely irrelevant to this plain
        certification question (`_org_certification_signal_and_warning`
        does not branch on scope at all). Only requirement_scope_correct
        is opted out here - interpretation_keys_valid/intent_type_correct/
        outcome_exact remain fully graded for this case, same shape as
        `genuine_not_applicable`'s own opt-out immediately above."""
        report = run_eval("fake")
        case = next(c for c in report["cases"] if c["key"] == "certification_question")
        assert case["objective_checks"]["requirement_scope_correct"] is None
        assert case["objective_checks"]["interpretation_keys_valid"] is True
        assert case["objective_checks"]["intent_type_correct"] is True
        assert case["objective_checks"]["outcome_exact"] is True

    def test_requirement_scope_opt_out_does_not_leak_to_other_cases(self):
        """Regression guard (M006 Round 7 correction): certification_question
        and genuine_not_applicable opting requirement_scope_correct out
        must not make that opt-out global. Every OTHER case that does not
        itself set grade_requirement_scope=False must still have
        requirement_scope_correct fully gated (True/False, never None)."""
        report = run_eval("fake")
        opted_out_keys = {"certification_question", "genuine_not_applicable"}
        for case in report["cases"]:
            if case["key"] in opted_out_keys:
                continue
            if case["key"] == "ambiguous_compound_question":
                # grade_interpretation=False already switches this off for
                # an unrelated reason - not part of this regression guard.
                continue
            assert case["objective_checks"]["requirement_scope_correct"] in (True, False), (
                f"case {case['key']!r} unexpectedly has requirement_scope_correct grading "
                "switched off"
            )

    def test_every_case_has_raw_answer_and_human_judgement_properties(self):
        report = run_eval("fake")
        for case in report["cases"]:
            assert case["raw_generated_answer"], f"case {case['key']!r} has nothing to review"
            assert case["raw_generated_answer"]["current_answer_text"]
            assert case["human_judgement_properties_to_review"] == HUMAN_JUDGEMENT_PROPERTIES

    def test_heuristic_flags_present_and_never_gate_verdict(self):
        report = run_eval("fake")
        for case in report["cases"]:
            assert "alarming_language" in case["heuristic_flags"]
        assert report["overall_verdict"] == "green"

    def test_report_top_level_fields(self):
        report = run_eval("fake")
        assert report["corpus_version"] == "m005-questionnaire-eval-corpus-v3"
        assert report["interpretation_prompt_version"] == "questionnaire_interpretation_v1"
        assert report["drafting_prompt_version"] == "questionnaire_drafting_v1"
        assert report["gateway_mode"] == "fake"
        assert "generated_at" in report
        assert report["human_judgement_properties_pending_review"] == HUMAN_JUDGEMENT_PROPERTIES

    def test_run_eval_is_idempotent_across_repeated_calls(self):
        report1 = run_eval("fake")
        report2 = run_eval("fake")
        assert report1["overall_verdict"] == report2["overall_verdict"] == "green"
        assert report1["case_count"] == report2["case_count"] == 14


# ---------------------------------------------------------------------------
# Negative control: the harness must actually be capable of producing RED,
# not merely praise success on a corpus it was tuned against.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNegativeControl:
    def test_a_case_whose_expected_outcome_does_not_follow_is_graded_not_green(self):
        """A small, LOCAL, test-only case (never added to the real
        GOLDEN_CORPUS) whose tenant state is 'yes, clean, active support' -
        which the real outcome engine derives as SUPPORTED - but whose own
        `expected_outcome` deliberately claims GAP. Run directly through
        `_run_case`/`_case_is_green`: this must NOT be graded green."""
        from evidence.models import ControlEvidenceLink
        from questionnaire.eval.golden_corpus import _profile_defaults, ensure_case_organisation
        from workplace.models import Workplace

        bad_case = {
            "key": "negative_control_wrong_expected_outcome",
            "title": "Negative control - deliberately wrong expected outcome",
            "profile": _profile_defaults(legal_trading_name="Synthetic Negative Control Ltd"),
            "account_holder": {"full_name": "Negative Control", "job_title": "Tester"},
            "workplaces": [
                {"name": "Main office", "type": Workplace.TYPE_DEDICATED_OFFICE, "approx_people_count": 5, "is_primary": True},
            ],
            "baseline_answers": {"mfa_privileged_accounts": ("yes", "")},
            # Clean, active supporting evidence - the real outcome engine
            # derives SUPPORTED from this tenant state, not the GAP this
            # case deliberately, wrongly claims below.
            "evidence_links": [
                {
                    "control_key": "mfa_privileged_accounts",
                    "title": "Clean supporting evidence",
                    "relationship": ControlEvidenceLink.RELATIONSHIP_SUPPORTS,
                    "valid_until": None,
                }
            ],
            "question_text": "Do all privileged accounts use multi-factor authentication?",
            "expected_interpretation": QuestionnaireInterpretation(
                intent_type="implementation",
                requirement_scope="all",
                requirement_summary="Asks whether MFA is used for all privileged accounts.",
                selected_keys=["control:mfa_privileged_accounts"],
                evidence_explicitly_requested=False,
                ambiguous=False,
                ambiguity_note="",
                resolved_model="fixture-model",
                prompt_version="questionnaire_interpretation_v1",
            ),
            "expected_draft": QuestionnaireDraft(
                answer_text="[FAKE DRAFT - negative control] outcome=GAP",
                answer_summary="",
                grounding_handles_used=[],
                customer_review_note="",
                resolved_model="fixture-model",
                prompt_version="questionnaire_drafting_v1",
            ),
            # DELIBERATELY WRONG: real tenant state below (clean "yes" with
            # active supporting evidence) actually derives SUPPORTED, not
            # GAP - proving the harness catches a corpus/expectation
            # mismatch rather than rubber-stamping whatever is claimed.
            "expected_outcome": "GAP",
            "required_keys": ["control:mfa_privileged_accounts"],
            "allowed_keys": ["control:mfa_privileged_accounts"],
            "expected_evidence_explicitly_requested": False,
            "grade_interpretation": True,
            "require_any_policy_section_key": False,
        }

        # `_run_case` itself calls `ensure_case_organisation`/
        # `ensure_case_question` internally - this LOCAL `bad_case` is never
        # added to the real `GOLDEN_CORPUS`, so nothing here touches the
        # real corpus's own organisations.
        actor = ensure_eval_actor_user()
        result = _run_case("fake", bad_case, actor)

        assert result["actual_outcome"] == "SUPPORTED"
        assert result["expected_outcome"] == "GAP"
        assert result["objective_checks"]["outcome_exact"] is False
        assert _case_is_green(result) is False
