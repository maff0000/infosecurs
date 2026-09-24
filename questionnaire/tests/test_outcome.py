"""
`questionnaire.outcome.derive_outcome` tests (M005 PID §12, §27 -
m005-1-foundation dispatch).

**These are the acceptance-criteria tests for the single most
safety-critical piece of M005.** Every one of PID §27's 18 required
assurance-derivation cases is proven below, by hand-constructing the
interpretation + grounding snapshot exactly as the dispatch instructions'
own algorithm walkthrough specifies for each case - this module does not
run the AI pipeline at all, only the pure `derive_outcome` function.
"""
import pytest

from ai_platform.questionnaire_drafting_contracts import (
    OUTCOME_CONFIRM,
    OUTCOME_GAP,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_SUPPORTED,
)
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretation
from questionnaire.outcome import derive_outcome

CONTROL_X = "control:mfa_privileged_accounts"
CONTROL_Y = "control:endpoint_protection"
POLICY_SECTION = "policy_section:access_and_authentication"
CERT_ISO = "org:certification_iso27001"


def _interp(
    *,
    intent_type="implementation",
    requirement_scope="all",
    selected_keys,
    evidence_explicitly_requested=False,
    ambiguous=False,
    ambiguity_note="",
):
    return QuestionnaireInterpretation(
        intent_type=intent_type,
        requirement_scope=requirement_scope,
        requirement_summary="fixture",
        selected_keys=selected_keys,
        evidence_explicitly_requested=evidence_explicitly_requested,
        ambiguous=ambiguous,
        ambiguity_note=ambiguity_note,
    )


# --- PID §27's 18 required cases, numbered to match the spec exactly ---------

def test_case_1_yes_clean_current_state_is_supported():
    interp = _interp(selected_keys=[CONTROL_X])
    snapshot = {
        CONTROL_X: {
            "answer": "yes",
            "assurance_label": "Supporting evidence attached",
            "active_supporting_evidence_count": 1,
            "active_contradicting_evidence_count": 0,
            "relevant_remediation": [],
        }
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_SUPPORTED


def test_case_2_evidence_explicitly_requested_no_active_support_is_confirm():
    interp = _interp(selected_keys=[CONTROL_X], evidence_explicitly_requested=True)
    snapshot = {
        CONTROL_X: {
            "answer": "yes",
            "assurance_label": "Not confirmed",
            "active_supporting_evidence_count": 0,
            "relevant_remediation": [],
        }
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_2b_evidence_explicitly_requested_customer_stated_zero_evidence_is_confirm():
    """Regression test for the 2026-09-24 spec correction: the ORIGINAL
    (literal-to-the-dispatch-text) branch only checked
    `assurance_label in ("Evidence stale", "Not confirmed")`, which misses
    this case entirely - "Customer stated" is the REAL, reachable
    `security_state.services` label for "answer=yes, zero evidence ever
    attached" (unlike "Not confirmed", which can never co-occur with
    answer="yes" in a real get_security_state() row). Case 2's own test
    above intentionally keeps the "Not confirmed" construction to prove the
    literal branch still matches the dispatch text; this test proves the
    real-world gap PID §12.1/§H actually require closed is now closed too.
    """
    interp = _interp(selected_keys=[CONTROL_X], evidence_explicitly_requested=True)
    snapshot = {
        CONTROL_X: {
            "answer": "yes",
            "assurance_label": "Customer stated",
            "active_supporting_evidence_count": 0,
            "relevant_remediation": [],
        }
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_3_unknown_is_confirm():
    interp = _interp(selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "unknown", "assurance_label": "Not confirmed"}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_4_evidence_conflict_is_confirm():
    interp = _interp(selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "yes", "assurance_label": "Evidence conflict"}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_5_stale_only_evidence_requested_is_confirm():
    interp = _interp(selected_keys=[CONTROL_X], evidence_explicitly_requested=True)
    snapshot = {
        CONTROL_X: {
            "answer": "yes",
            "assurance_label": "Evidence stale",
            "active_supporting_evidence_count": 0,
            "relevant_remediation": [],
        }
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_6_no_is_gap():
    interp = _interp(selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "no"}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_GAP


def test_case_7_partial_scope_all_is_gap():
    interp = _interp(selected_keys=[CONTROL_X], requirement_scope="all")
    snapshot = {CONTROL_X: {"answer": "partial", "relevant_remediation": []}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_GAP


def test_case_8_partial_with_managed_exception_still_gap():
    interp = _interp(selected_keys=[CONTROL_X], requirement_scope="all")
    snapshot = {
        CONTROL_X: {
            "answer": "partial",
            "relevant_remediation": [
                {
                    "status": "open",
                    "owner": "Ada Holder",
                    "target_date": "2026-12-01",
                    "treatment_summary": "Enable MFA on the rest.",
                }
            ],
        }
    }
    outcome, warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_GAP
    assert any("Ada Holder" in w for w in warnings)


def test_case_9_policy_requires_plus_implementation_partial_implementation_question_is_gap():
    interp = _interp(
        intent_type="implementation",
        requirement_scope="all",
        selected_keys=[CONTROL_X, POLICY_SECTION],
    )
    snapshot = {
        CONTROL_X: {"answer": "partial", "relevant_remediation": []},
        POLICY_SECTION: {"policy_exists": True, "approved_version_number": 1, "section_present": True, "section_content": "MFA required."},
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_GAP


def test_case_10_policy_requirement_question_approved_clause_exists_is_supported():
    interp = _interp(intent_type="policy_requirement", selected_keys=[POLICY_SECTION])
    snapshot = {
        POLICY_SECTION: {
            "policy_exists": True,
            "approved_version_number": 1,
            "section_present": True,
            "section_content": "MFA required.",
        }
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_SUPPORTED


def test_case_11_artefact_existence_approved_policy_exists_is_supported():
    interp = _interp(intent_type="artefact_existence", selected_keys=[POLICY_SECTION])
    snapshot = {
        POLICY_SECTION: {
            "policy_exists": True,
            "approved_version_number": 1,
            "section_present": False,
            "section_content": None,
        }
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_SUPPORTED


def test_case_12_certification_certified_is_supported():
    interp = _interp(intent_type="certification", selected_keys=[CERT_ISO])
    snapshot = {CERT_ISO: {"value": "certified"}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_SUPPORTED


def test_case_13_certification_unknown_is_confirm():
    interp = _interp(intent_type="certification", selected_keys=[CERT_ISO])
    snapshot = {CERT_ISO: {"value": "unknown"}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_14_explicit_canonical_na_single_control_is_not_applicable():
    interp = _interp(intent_type="implementation", requirement_scope="not_applicable_test", selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "not_applicable"}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_NOT_APPLICABLE


def test_case_15_plausible_but_non_explicit_na_is_confirm():
    interp = _interp(intent_type="implementation", requirement_scope="not_applicable_test", selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "partial", "relevant_remediation": []}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_16_multi_fact_with_one_gap_is_gap():
    interp = _interp(selected_keys=[CONTROL_X, CONTROL_Y])
    snapshot = {
        CONTROL_X: {"answer": "yes", "assurance_label": "Supporting evidence attached", "active_supporting_evidence_count": 1},
        CONTROL_Y: {"answer": "no"},
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_GAP


def test_case_17_multi_fact_no_gap_one_confirm_is_confirm():
    interp = _interp(selected_keys=[CONTROL_X, CONTROL_Y])
    snapshot = {
        CONTROL_X: {"answer": "yes", "assurance_label": "Supporting evidence attached", "active_supporting_evidence_count": 1},
        CONTROL_Y: {"answer": "unknown", "assurance_label": "Not confirmed"},
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_case_18_materially_ambiguous_scope_partial_is_confirm():
    interp = _interp(requirement_scope="unspecified", selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "partial", "relevant_remediation": []}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


# --- Additional coverage beyond the 18 numbered cases -------------------------

def test_unclear_intent_short_circuits_to_confirm_even_with_selected_keys():
    interp = _interp(intent_type="unclear", selected_keys=[CONTROL_X], ambiguous=True, ambiguity_note="Too vague.")
    snapshot = {CONTROL_X: {"answer": "yes", "assurance_label": "Customer stated"}}
    outcome, warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM
    assert "Too vague." in warnings


def test_empty_selected_keys_is_confirm():
    interp = _interp(selected_keys=[])
    outcome, warnings = derive_outcome(interp, {})
    assert outcome == OUTCOME_CONFIRM
    assert warnings


def test_partial_scope_some_is_supported():
    interp = _interp(requirement_scope="some", selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "partial", "relevant_remediation": []}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_SUPPORTED


def test_partial_scope_existence_is_supported():
    interp = _interp(requirement_scope="existence", selected_keys=[CONTROL_X])
    snapshot = {CONTROL_X: {"answer": "partial", "relevant_remediation": []}}
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_SUPPORTED


def test_not_applicable_with_multiple_control_keys_never_forces_overall_na():
    """PID §12.4: a not_applicable control amid OTHER selected control keys
    must not, by itself, force the whole answer to NOT_APPLICABLE."""
    interp = _interp(selected_keys=[CONTROL_X, CONTROL_Y])
    snapshot = {
        CONTROL_X: {"answer": "not_applicable"},
        CONTROL_Y: {"answer": "yes", "assurance_label": "Customer stated", "active_supporting_evidence_count": 0},
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_SUPPORTED


def test_all_control_keys_not_applicable_with_multiple_selected_does_not_silently_support():
    """Defensive safety net (see questionnaire.outcome module docstring):
    every selected control folds to 'irrelevant' when count > 1 and all are
    canonically not_applicable - must never silently become SUPPORTED."""
    interp = _interp(selected_keys=[CONTROL_X, CONTROL_Y])
    snapshot = {
        CONTROL_X: {"answer": "not_applicable"},
        CONTROL_Y: {"answer": "not_applicable"},
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_CONFIRM


def test_gap_always_wins_over_supported_policy_signal():
    """PID §14's MFA worked example: the policy signal must never
    independently short-circuit to SUPPORTED before aggregation runs."""
    interp = _interp(intent_type="mixed", requirement_scope="all", selected_keys=[CONTROL_X, POLICY_SECTION])
    snapshot = {
        CONTROL_X: {"answer": "no"},
        POLICY_SECTION: {"policy_exists": True, "approved_version_number": 1, "section_present": True, "section_content": "x"},
    }
    outcome, _warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_GAP


def test_review_warnings_never_invent_owner_or_date():
    interp = _interp(requirement_scope="all", selected_keys=[CONTROL_X])
    snapshot = {
        CONTROL_X: {
            "answer": "partial",
            "relevant_remediation": [
                {"status": "open", "owner": None, "target_date": None, "treatment_summary": "Do the thing."}
            ],
        }
    }
    outcome, warnings = derive_outcome(interp, snapshot)
    assert outcome == OUTCOME_GAP
    combined = " ".join(warnings)
    assert "not yet assigned" in combined
    assert "not yet set" in combined
