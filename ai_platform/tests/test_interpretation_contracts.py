import pytest

from ai_platform.contracts import ClarificationQuestion, ContractValidationError
from ai_platform.interpretation_contracts import (
    MAX_INTERPRETATION_CANDIDATES,
    InterpretationCandidate,
    InterpretationOutcome,
    InterpretationRequest,
    InterpretationResponse,
)


def _candidate(index=1, **overrides):
    defaults = dict(
        index=index,
        title="Weak endpoint protection",
        exposure="The device runs everyday business software.",
        threat_event="Malware execution.",
        vulnerability="No confirmed endpoint protection.",
        consequence="Possible business disruption.",
        current_impact=3,
        current_likelihood=3,
        asset_category="endpoint",
        notes=[],
    )
    defaults.update(overrides)
    return InterpretationCandidate(**defaults)


def _outcome(index=1, **overrides):
    defaults = dict(
        index=index,
        suggested_impact=4,
        suggested_likelihood=3,
        rationale="Grounded rationale.",
        suggested_treatment="Deploy endpoint protection.",
        clarification_questions=[],
        priority_note=None,
    )
    defaults.update(overrides)
    return InterpretationOutcome(**defaults)


# --- InterpretationCandidate --------------------------------------------------

def test_candidate_valid_round_trips_to_wire_dict():
    c = _candidate(notes=["a customer note"])
    wire = c.to_wire_dict()
    assert wire["index"] == 1
    assert wire["notes"] == ["a customer note"]
    # No identifier-shaped field anywhere in the wire dict.
    assert "id" not in wire
    assert "risk_id" not in wire
    assert "key_asset" not in wire
    assert "scenario_id" not in wire


@pytest.mark.parametrize("bad_index", [0, -1, "1", 1.5, True])
def test_candidate_rejects_non_positive_int_index(bad_index):
    with pytest.raises(ContractValidationError):
        _candidate(index=bad_index)


def test_candidate_rejects_blank_required_string_field():
    with pytest.raises(ContractValidationError):
        _candidate(title="")


@pytest.mark.parametrize("field", ["current_impact", "current_likelihood"])
def test_candidate_rejects_out_of_range_ratings(field):
    with pytest.raises(ContractValidationError):
        _candidate(**{field: 6})


def test_candidate_notes_may_be_empty():
    c = _candidate(notes=[])
    assert c.notes == []


def test_candidate_notes_must_be_list_of_strings():
    with pytest.raises(ContractValidationError):
        _candidate(notes=["ok", 123])


# --- InterpretationRequest -----------------------------------------------------

def test_request_valid():
    req = InterpretationRequest(organisation_id="org-1", candidates=[_candidate(1), _candidate(2)])
    assert req.expected_indices == frozenset({1, 2})


def test_request_rejects_empty_candidates():
    with pytest.raises(ContractValidationError):
        InterpretationRequest(organisation_id="org-1", candidates=[])


def test_request_rejects_duplicate_indices():
    with pytest.raises(ContractValidationError):
        InterpretationRequest(organisation_id="org-1", candidates=[_candidate(1), _candidate(1)])


def test_request_rejects_non_sequential_indices():
    with pytest.raises(ContractValidationError):
        InterpretationRequest(organisation_id="org-1", candidates=[_candidate(1), _candidate(3)])


def test_request_rejects_indices_not_starting_at_one():
    with pytest.raises(ContractValidationError):
        InterpretationRequest(organisation_id="org-1", candidates=[_candidate(2), _candidate(3)])


def test_request_rejects_over_cap_candidate_count():
    candidates = [_candidate(i) for i in range(1, MAX_INTERPRETATION_CANDIDATES + 2)]
    with pytest.raises(ContractValidationError):
        InterpretationRequest(organisation_id="org-1", candidates=candidates)


def test_request_accepts_exactly_at_cap():
    candidates = [_candidate(i) for i in range(1, MAX_INTERPRETATION_CANDIDATES + 1)]
    req = InterpretationRequest(organisation_id="org-1", candidates=candidates)
    assert len(req.candidates) == MAX_INTERPRETATION_CANDIDATES


# --- InterpretationOutcome ------------------------------------------------------

def test_outcome_valid_with_clarification_and_priority_note():
    outcome = _outcome(
        clarification_questions=[
            ClarificationQuestion(missing_fact="x", why_it_matters="y", affects="z")
        ],
        priority_note="Looks like a duplicate of index 2.",
    )
    assert outcome.priority_note == "Looks like a duplicate of index 2."


def test_outcome_from_dict_defaults_missing_optional_fields():
    outcome = InterpretationOutcome.from_dict(
        {
            "index": 1,
            "suggested_impact": 3,
            "suggested_likelihood": 3,
            "rationale": "r",
            "suggested_treatment": "t",
        }
    )
    assert outcome.clarification_questions == []
    assert outcome.priority_note is None


def test_outcome_from_dict_missing_required_field_raises():
    with pytest.raises(ContractValidationError):
        InterpretationOutcome.from_dict({"index": 1, "suggested_impact": 3})


def test_outcome_from_dict_not_a_dict_raises():
    with pytest.raises(ContractValidationError):
        InterpretationOutcome.from_dict("not a dict")


# --- InterpretationResponse.from_response_dict: the index-matching rule -------
# This is the specific validation the M002-3c dispatch requires: every
# input index has exactly one matching output index; reject on mismatch,
# never silently drop or guess.

def _outcomes_payload(indices):
    return {
        "interpretations": [
            {
                "index": i,
                "suggested_impact": 3,
                "suggested_likelihood": 3,
                "rationale": f"r{i}",
                "suggested_treatment": f"t{i}",
            }
            for i in indices
        ],
        "additional_observations": [],
    }


def test_response_exact_match_is_valid():
    response = InterpretationResponse.from_response_dict(
        _outcomes_payload([1, 2, 3]),
        expected_indices={1, 2, 3},
        resolved_model="m",
        prompt_version="v1",
    )
    assert {o.index for o in response.outcomes} == {1, 2, 3}
    assert response.outcome_for_index(2).rationale == "r2"


def test_response_missing_index_is_rejected():
    with pytest.raises(ContractValidationError, match="missing"):
        InterpretationResponse.from_response_dict(
            _outcomes_payload([1, 2]),
            expected_indices={1, 2, 3},
            resolved_model="m",
            prompt_version="v1",
        )


def test_response_extra_unknown_index_is_rejected():
    with pytest.raises(ContractValidationError, match="not sent"):
        InterpretationResponse.from_response_dict(
            _outcomes_payload([1, 2, 3, 4]),
            expected_indices={1, 2, 3},
            resolved_model="m",
            prompt_version="v1",
        )


def test_response_duplicate_index_is_rejected():
    payload = _outcomes_payload([1, 2, 2])
    with pytest.raises(ContractValidationError, match="duplicate"):
        InterpretationResponse.from_response_dict(
            payload,
            expected_indices={1, 2},
            resolved_model="m",
            prompt_version="v1",
        )


def test_response_missing_interpretations_key_is_rejected():
    with pytest.raises(ContractValidationError):
        InterpretationResponse.from_response_dict(
            {"additional_observations": []},
            expected_indices={1},
            resolved_model="m",
            prompt_version="v1",
        )


def test_response_carries_additional_observations_separately_from_outcomes():
    payload = _outcomes_payload([1])
    payload["additional_observations"] = ["Consider a supplier-risk scenario too."]
    response = InterpretationResponse.from_response_dict(
        payload, expected_indices={1}, resolved_model="m", prompt_version="v1"
    )
    assert response.additional_observations == ["Consider a supplier-risk scenario too."]
    # Never attached to an outcome/index.
    assert not hasattr(response.outcomes[0], "additional_observations")


def test_response_additional_observations_must_be_list_of_strings():
    payload = _outcomes_payload([1])
    payload["additional_observations"] = [{"not": "a string"}]
    with pytest.raises(ContractValidationError):
        InterpretationResponse.from_response_dict(
            payload, expected_indices={1}, resolved_model="m", prompt_version="v1"
        )


def test_response_not_a_dict_is_rejected():
    with pytest.raises(ContractValidationError):
        InterpretationResponse.from_response_dict(
            "not a dict", expected_indices={1}, resolved_model="m", prompt_version="v1"
        )
