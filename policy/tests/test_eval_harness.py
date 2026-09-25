"""
Tests for `policy.eval.harness` (PID §25 - m004-3-eval-harness dispatch).

Mechanics-only tests using `ai_platform.testing.FakePolicyGateway`, never a
live external LLM (forge-engineer.md rule 8; dispatch instructions "you
test the harness mechanics with --gateway=fake only"). Mirrors
`risk_register/tests/test_eval_harness.py`'s shape.
"""
import json

import pytest

from ai_platform.policy_contracts import MAX_TOTAL_CONTENT_CHARS
from ai_platform.testing import FakePolicyGateway

from policy.eval.golden_corpus import GOLDEN_CORPUS, ensure_case_organisation
from policy.eval.harness import (
    HUMAN_JUDGEMENT_PROPERTIES,
    INJECTION_CASE_KEY,
    _UUID_RE,
    _case_is_green,
    _certification_language_flag,
    _no_identifier_leak,
    _unsupported_implementation_language_flag,
    run_eval,
)


# ---------------------------------------------------------------------------
# Pure-function checks, in isolation
# ---------------------------------------------------------------------------

class TestNoIdentifierLeak:
    """Proves the UUID-shape regression check itself actually catches a
    violation - the exact non-vacuity discipline
    `risk_register/tests/test_eval_harness.py::TestNoIdentifierLeak`
    already demonstrates for the sibling AI task."""

    def test_true_when_no_uuid_shaped_text_present(self):
        sections = [{"section_key": "purpose_and_scope", "content": "A plain policy sentence."}]
        assert _no_identifier_leak("A Policy Title", sections, []) is True

    def test_false_when_title_contains_a_uuid(self):
        title = "Policy for 6747bc6a-843f-4744-b9f7-3757d875cf20"
        assert _no_identifier_leak(title, [], []) is False

    def test_false_when_section_content_contains_a_uuid(self):
        sections = [
            {"section_key": "purpose_and_scope", "content": "See record 6747bc6a-843f-4744-b9f7-3757d875cf20."}
        ]
        assert _no_identifier_leak("Title", sections, []) is False

    def test_false_when_review_warning_subject_or_detail_contains_a_uuid(self):
        warnings_subject = [{"subject": "Ref 6747bc6a-843f-4744-b9f7-3757d875cf20", "detail": "x"}]
        warnings_detail = [{"subject": "x", "detail": "Ref 6747bc6a-843f-4744-b9f7-3757d875cf20"}]
        assert _no_identifier_leak("Title", [], warnings_subject) is False
        assert _no_identifier_leak("Title", [], warnings_detail) is False

    def test_regex_matches_uuid_shape_case_insensitively(self):
        assert _UUID_RE.search("ID: 6747BC6A-843F-4744-B9F7-3757D875CF20") is not None


class TestCertificationLanguageFlag:
    def test_flags_a_known_certification_phrase(self):
        sections = [{"section_key": "purpose_and_scope", "content": "We are ISO 27001 certified."}]
        result = _certification_language_flag(sections)
        assert result["flagged"] is True
        assert result["matches"]

    def test_does_not_flag_ordinary_content(self):
        sections = [{"section_key": "purpose_and_scope", "content": "Staff must protect company devices."}]
        result = _certification_language_flag(sections)
        assert result["flagged"] is False
        assert result["matches"] == []


class TestUnsupportedImplementationLanguageFlag:
    def test_flags_current_implementation_phrase_for_an_unconfirmed_control_area(self):
        sections = [
            {
                "section_key": "information_handling_and_backup",
                "content": "The company performs daily encrypted backups.",
            }
        ]
        security_state_facts = {"backups": {"area": "Backups", "answer": "unknown"}}
        result = _unsupported_implementation_language_flag(sections, security_state_facts)
        assert result["flagged"] is True

    def test_does_not_flag_when_control_is_confirmed(self):
        sections = [
            {
                "section_key": "information_handling_and_backup",
                "content": "The company performs daily encrypted backups.",
            }
        ]
        security_state_facts = {"backups": {"area": "Backups", "answer": "yes"}}
        result = _unsupported_implementation_language_flag(sections, security_state_facts)
        assert result["flagged"] is False

    def test_does_not_flag_when_no_current_implementation_phrase_present(self):
        sections = [
            {
                "section_key": "information_handling_and_backup",
                "content": "Important business information must be backed up appropriately.",
            }
        ]
        security_state_facts = {"backups": {"area": "Backups", "answer": "unknown"}}
        result = _unsupported_implementation_language_flag(sections, security_state_facts)
        assert result["flagged"] is False


# ---------------------------------------------------------------------------
# run_eval, end to end, against the fake gateway
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRunEvalMechanics:
    def test_runs_all_eight_corpus_cases(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        assert report["case_count"] == 8
        assert len(report["cases"]) == 8
        assert {c["key"] for c in report["cases"]} == {c["key"] for c in GOLDEN_CORPUS}

    def test_report_is_json_serialisable(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        json.dumps(report)  # must not raise

    def test_overall_verdict_green_when_every_case_mechanically_passes(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        assert report["overall_verdict"] == "green"
        for case in report["cases"]:
            checks = case["objective_checks"]
            assert checks["generation_succeeded"] is True
            assert checks["output_contract_valid"] is True
            assert checks["section_keys_all_recognised"] is True
            assert checks["no_identifier_leak"] is True
            assert checks["total_content_length_within_bound"] is True
            assert checks["cross_tenant_data_possible"] is False
            assert case["harness_defect"] is False

    def test_every_case_has_raw_content_and_human_judgement_properties(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        for case in report["cases"]:
            assert case["raw_generated_sections"], f"case {case['key']!r} has nothing to review"
            assert case["raw_generated_sections"]["sections"]
            assert case["human_judgement_properties_to_review"] == HUMAN_JUDGEMENT_PROPERTIES

    def test_injection_case_reports_prompt_injection_resisted(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        case = next(c for c in report["cases"] if c["key"] == INJECTION_CASE_KEY)
        assert case["objective_checks"]["prompt_injection_resisted"] is True

    def test_prompt_injection_resisted_only_reported_for_the_injection_case(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        for case in report["cases"]:
            if case["key"] == INJECTION_CASE_KEY:
                continue
            assert "prompt_injection_resisted" not in case["objective_checks"]

    def test_total_content_chars_reported_and_within_bound(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        for case in report["cases"]:
            assert case["total_content_chars"] is not None
            assert case["total_content_chars"] <= MAX_TOTAL_CONTENT_CHARS
            assert case["max_total_content_chars"] == MAX_TOTAL_CONTENT_CHARS

    def test_heuristic_flags_present_and_never_gate_verdict(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        for case in report["cases"]:
            assert "certification_or_compliance_language" in case["heuristic_flags"]
            assert "unsupported_current_implementation_language" in case["heuristic_flags"]
        # The fake gateway's fixture content contains no certification
        # phrases and no current-implementation phrases paired with an
        # unconfirmed control - but even if it did, _case_is_green only
        # reads objective_checks, never heuristic_flags (see that
        # function's own source).
        assert report["overall_verdict"] == "green"

    def test_a_failing_gateway_produces_a_red_verdict_and_no_crash(self):
        gw = FakePolicyGateway(mode="auth_error")
        report = run_eval(gw)
        assert report["overall_verdict"] == "red"
        for case in report["cases"]:
            assert case["objective_checks"]["generation_succeeded"] is False
            assert case["harness_defect"] is False
            assert case["error"]
            assert case["raw_generated_sections"] is None

    def test_case_is_green_ignores_heuristic_flags(self):
        case_result = {
            "objective_checks": {
                "generation_succeeded": True,
                "output_contract_valid": True,
                "section_keys_all_recognised": True,
                "no_identifier_leak": True,
                "total_content_length_within_bound": True,
                "cross_tenant_data_possible": False,
            },
            "heuristic_flags": {
                "certification_or_compliance_language": {"flagged": True, "matches": [{"x": "y"}]},
            },
            "harness_defect": False,
        }
        assert _case_is_green(case_result) is True

    def test_case_is_green_false_on_harness_defect(self):
        case_result = {
            "objective_checks": {
                "generation_succeeded": True,
                "output_contract_valid": True,
                "section_keys_all_recognised": True,
                "no_identifier_leak": True,
                "total_content_length_within_bound": True,
                "cross_tenant_data_possible": False,
            },
            "heuristic_flags": {},
            "harness_defect": True,
        }
        assert _case_is_green(case_result) is False

    def test_token_totals_are_summed_across_all_cases(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        # ai_platform.testing.default_valid_policy_result() fixture reports
        # prompt_tokens=234, completion_tokens=98 PER CASE CALL - one call
        # per case, all eight succeed under mode="valid".
        assert report["token_totals"]["prompt_tokens"] == 234 * 8
        assert report["token_totals"]["completion_tokens"] == 98 * 8

    def test_corpus_and_prompt_version_recorded_in_report(self):
        gw = FakePolicyGateway(mode="valid")
        report = run_eval(gw)
        assert report["corpus_version"] == "m004-policy-eval-corpus-v1"
        assert report["prompt_version"] == "policy_generation_v2"
        assert "generated_at" in report
        assert report["configured_model_alias"] == "trinity-core"

    def test_run_eval_is_idempotent_across_repeated_calls(self):
        """Running the whole eval twice must not fail on duplicate
        synthetic tenant state (golden_corpus.ensure_case_organisation is
        update_or_create-based), and each case's second call must create a
        NEW draft version, not fail or mutate the first."""
        gw1 = FakePolicyGateway(mode="valid")
        report1 = run_eval(gw1)

        gw2 = FakePolicyGateway(mode="valid")
        report2 = run_eval(gw2)

        assert report1["overall_verdict"] == report2["overall_verdict"] == "green"
        assert report1["case_count"] == report2["case_count"] == 8


class TestGoldenCorpusStableIds:
    """Pins the deterministic-id property `golden_corpus.
    ensure_case_organisation` relies on for idempotency - mirrors
    `risk_register/tests/test_eval_harness.py::TestGoldenCorpusStableIds`."""

    def test_case_organisation_id_is_stable_across_calls(self):
        from policy.eval.golden_corpus import _stable_id

        first = _stable_id("organisation", "some_case_key")
        second = _stable_id("organisation", "some_case_key")
        assert first == second

    def test_different_case_keys_produce_different_ids(self):
        from policy.eval.golden_corpus import _stable_id

        assert _stable_id("organisation", "case_one") != _stable_id("organisation", "case_two")

    def test_all_case_keys_are_unique(self):
        keys = [case["key"] for case in GOLDEN_CORPUS]
        assert len(keys) == len(set(keys))


@pytest.mark.django_db
class TestGoldenCorpusCoverage:
    """Proves each PID §25 case actually builds the tenant state its own
    description promises - not just that `ensure_case_organisation` runs
    without raising."""

    def test_four_person_fully_remote_company(self):
        from workplace.models import Workplace

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "four_person_fully_remote")
        organisation = ensure_case_organisation(case)
        workplaces = list(Workplace.objects.filter(organisation=organisation, is_active=True))
        assert len(workplaces) == 1
        assert workplaces[0].type == Workplace.TYPE_DISTRIBUTED_HOME
        assert workplaces[0].approx_people_count == 4

    def test_six_person_shared_office_woking(self):
        from workplace.models import Workplace

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "six_person_shared_office_woking")
        organisation = ensure_case_organisation(case)
        workplaces = list(Workplace.objects.filter(organisation=organisation, is_active=True))
        assert len(workplaces) == 1
        assert workplaces[0].type == Workplace.TYPE_SHARED_OFFICE
        assert workplaces[0].location_label == "Woking, Surrey"
        assert workplaces[0].approx_people_count == 6

    def test_twenty_person_london_hq_plus_remote(self):
        from workplace.models import Workplace

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "twenty_person_london_hq_plus_remote")
        organisation = ensure_case_organisation(case)
        workplaces = list(Workplace.objects.filter(organisation=organisation, is_active=True))
        assert len(workplaces) == 2
        office = next(w for w in workplaces if w.type == Workplace.TYPE_DEDICATED_OFFICE)
        home = next(w for w in workplaces if w.type == Workplace.TYPE_DISTRIBUTED_HOME)
        assert office.location_label == "London"
        assert office.approx_people_count == 15
        assert home.approx_people_count == 5

    def test_several_unknown_baseline_controls(self):
        from security_baseline.catalogue import CATALOGUE_KEYS
        from security_state.services import get_security_state, LABEL_NOT_CONFIRMED

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "several_unknown_baseline_controls")
        organisation = ensure_case_organisation(case)
        state = get_security_state(organisation)
        not_confirmed = [entry for entry in state if entry["assurance_label"] == LABEL_NOT_CONFIRMED]
        # 3 omitted rows + 2 explicit "unknown" rows = 5 of the 12
        # catalogue controls not confirmed (PID §25 case 4).
        assert len(not_confirmed) == 5
        assert len(state) == len(CATALOGUE_KEYS)

    def test_strong_evidence_backed_security_state_actually_produces_supporting_evidence_label(self):
        """Verifies - does not merely assume - that this case's
        EvidenceItem + ControlEvidenceLink(relationship=SUPPORTS) rows
        make `security_state.services.get_security_state` report
        "Supporting evidence attached" for the linked controls (dispatch
        instructions: "verify this actually happens by calling
        get_security_state yourself while building the case")."""
        from security_state.services import LABEL_SUPPORTING_EVIDENCE, get_security_state

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "strong_evidence_backed_security_state")
        organisation = ensure_case_organisation(case)
        state = get_security_state(organisation)
        state_by_key = {entry["control_key"]: entry for entry in state}

        linked_controls = {entry["control_key"] for entry in case["evidence_links"]}
        assert linked_controls  # sanity: the case actually declares some
        for control_key in linked_controls:
            assert state_by_key[control_key]["assurance_label"] == LABEL_SUPPORTING_EVIDENCE, (
                f"{control_key!r} did not get 'Supporting evidence attached' - "
                f"got {state_by_key[control_key]['assurance_label']!r} instead"
            )

    def test_explicit_control_gaps_open_remediation(self):
        from remediation.models import RemediationAction
        from risk_register.models import Risk

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "explicit_control_gaps_open_remediation")
        organisation = ensure_case_organisation(case)
        open_actions = RemediationAction.objects.filter(
            organisation=organisation, status=RemediationAction.STATUS_OPEN
        )
        assert open_actions.count() == 4
        confirmed_risks = Risk.objects.filter(organisation=organisation, status=Risk.STATUS_CONFIRMED)
        assert confirmed_risks.count() == 1

    def test_different_named_policy_authoriser(self):
        from governance.models import GovernanceRoleAssignment

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "different_named_policy_authoriser")
        organisation = ensure_case_organisation(case)
        authoriser_assignment = GovernanceRoleAssignment.objects.get(
            organisation=organisation, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        other_roles = GovernanceRoleAssignment.objects.filter(organisation=organisation).exclude(
            role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        assert authoriser_assignment.person.user is None
        assert authoriser_assignment.person.full_name == "Jordan Reyes"
        for assignment in other_roles:
            assert assignment.person.user is not None
            assert assignment.person.full_name == "Sam Whitfield"
        # Different actual person for the authoriser role, confirming
        # this is not accidentally the same OrganisationPerson.
        assert authoriser_assignment.person_id != other_roles.first().person_id

    def test_adversarial_prompt_injection_note_is_present_upstream(self):
        from security_baseline.models import BaselineAnswer

        case = next(
            c for c in GOLDEN_CORPUS if c["key"] == "adversarial_prompt_injection_in_baseline_note"
        )
        organisation = ensure_case_organisation(case)
        answer = BaselineAnswer.objects.get(
            assessment__organisation=organisation, question_key="backups"
        )
        assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in answer.note
