import pytest

from ai_platform.contracts import (
    ClarificationQuestion,
    ContractValidationError,
    GenerationResult,
    GroundingPayload,
    RiskCandidate,
)


# --- GroundingPayload -------------------------------------------------------

def test_grounding_payload_accepts_generic_dicts():
    gp = GroundingPayload(
        organisation_id="org-1",
        profile_facts={"any": "profile field the Risk domain decides to pass"},
        baseline_facts={"any": "baseline field"},
        asset_facts=[{"any": "asset field"}],
    )
    assert gp.organisation_id == "org-1"
    assert gp.asset_facts == [{"any": "asset field"}]


def test_grounding_payload_allows_empty_fact_dicts_and_lists():
    # Not every M001 fact will be known/supplied - the transport layer must
    # not force facts to exist, only be well-typed if present.
    gp = GroundingPayload(organisation_id="org-1", profile_facts={}, baseline_facts={}, asset_facts=[])
    assert gp.profile_facts == {}
    assert gp.asset_facts == []


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(organisation_id="", profile_facts={}, baseline_facts={}, asset_facts=[]),
        dict(organisation_id="org-1", profile_facts="not-a-dict", baseline_facts={}, asset_facts=[]),
        dict(organisation_id="org-1", profile_facts={}, baseline_facts=[], asset_facts=[]),
        dict(organisation_id="org-1", profile_facts={}, baseline_facts={}, asset_facts=["not-a-dict"]),
        dict(organisation_id="org-1", profile_facts={}, baseline_facts={}, asset_facts={"not": "a list"}),
    ],
)
def test_grounding_payload_rejects_malformed_input(kwargs):
    with pytest.raises(ContractValidationError):
        GroundingPayload(**kwargs)


# --- RiskCandidate -----------------------------------------------------------

def _valid_candidate_kwargs(**overrides):
    kwargs = dict(
        title="Weak MFA coverage",
        asset_reference="asset:fixture",
        threat="Account takeover",
        vulnerability="No MFA on ordinary user accounts",
        suggested_impact=3,
        suggested_likelihood=4,
        rationale="Baseline states MFA is not enabled for ordinary accounts.",
        proposed_treatment="Enable MFA for all productivity accounts.",
        grounding_refs=["baseline.mfa_user_accounts"],
        assumptions=[],
    )
    kwargs.update(overrides)
    return kwargs


def test_risk_candidate_accepts_valid_fields():
    candidate = RiskCandidate(**_valid_candidate_kwargs())
    assert candidate.suggested_impact == 3
    assert candidate.grounding_refs == ["baseline.mfa_user_accounts"]


@pytest.mark.parametrize(
    "overrides",
    [
        dict(title=""),
        dict(title=123),
        dict(suggested_impact=0),
        dict(suggested_impact=6),
        dict(suggested_impact="3"),
        dict(suggested_impact=True),  # bool is a subclass of int - must be rejected
        dict(suggested_likelihood=0),
        dict(suggested_likelihood=6),
        dict(grounding_refs=[]),
        dict(grounding_refs=["ok", 123]),
        dict(grounding_refs="not-a-list"),
        dict(assumptions="not-a-list"),
        dict(assumptions=[1, 2]),
    ],
)
def test_risk_candidate_rejects_invalid_fields(overrides):
    with pytest.raises(ContractValidationError):
        RiskCandidate(**_valid_candidate_kwargs(**overrides))


def test_risk_candidate_assumptions_may_be_empty():
    candidate = RiskCandidate(**_valid_candidate_kwargs(assumptions=[]))
    assert candidate.assumptions == []


def test_risk_candidate_from_dict_valid():
    data = _valid_candidate_kwargs()
    candidate = RiskCandidate.from_dict(data)
    assert candidate.title == "Weak MFA coverage"


def test_risk_candidate_from_dict_defaults_assumptions_to_empty_list():
    data = _valid_candidate_kwargs()
    del data["assumptions"]
    candidate = RiskCandidate.from_dict(data)
    assert candidate.assumptions == []


@pytest.mark.parametrize("missing_field", ["title", "grounding_refs", "suggested_impact"])
def test_risk_candidate_from_dict_rejects_missing_required_field(missing_field):
    data = _valid_candidate_kwargs()
    del data[missing_field]
    with pytest.raises(ContractValidationError):
        RiskCandidate.from_dict(data)


def test_risk_candidate_from_dict_rejects_non_object():
    with pytest.raises(ContractValidationError):
        RiskCandidate.from_dict(["not", "an", "object"])


# --- ClarificationQuestion ----------------------------------------------------

def test_clarification_question_valid():
    q = ClarificationQuestion.from_dict(
        {
            "missing_fact": "Whether backups are in place",
            "why_it_matters": "Cannot assess ransomware impact without this",
            "affects": "Backups risk candidate",
        }
    )
    assert q.missing_fact == "Whether backups are in place"


def test_clarification_question_rejects_missing_field():
    with pytest.raises(ContractValidationError):
        ClarificationQuestion.from_dict({"missing_fact": "x", "why_it_matters": "y"})


# --- GenerationResult / from_response_dict -----------------------------------

def _valid_response_dict():
    return {
        "risks": [_valid_candidate_kwargs()],
        "clarification_questions": [
            {
                "missing_fact": "Backup status",
                "why_it_matters": "Cannot rate ransomware impact",
                "affects": "Backups risk",
            }
        ],
    }


def test_generation_result_from_response_dict_valid():
    result = GenerationResult.from_response_dict(
        _valid_response_dict(),
        resolved_model="provider/model-x",
        prompt_version="risk_generation_v1",
        prompt_tokens=10,
        completion_tokens=20,
    )
    assert len(result.candidates) == 1
    assert len(result.clarification_questions) == 1
    assert result.resolved_model == "provider/model-x"
    assert result.prompt_version == "risk_generation_v1"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20


def test_generation_result_from_response_dict_clarification_questions_optional():
    data = _valid_response_dict()
    del data["clarification_questions"]
    result = GenerationResult.from_response_dict(
        data, resolved_model=None, prompt_version="risk_generation_v1"
    )
    assert result.clarification_questions == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("risks"),
        lambda d: d.__setitem__("risks", "not-a-list"),
        lambda d: d.__setitem__("risks", [{"title": "missing everything else"}]),
        lambda d: d.__setitem__("clarification_questions", "not-a-list"),
        lambda d: d.__setitem__("risks", [123]),
    ],
)
def test_generation_result_from_response_dict_rejects_invalid_shapes(mutate):
    data = _valid_response_dict()
    mutate(data)
    with pytest.raises(ContractValidationError):
        GenerationResult.from_response_dict(data, resolved_model=None, prompt_version="risk_generation_v1")


def test_generation_result_from_response_dict_rejects_non_object_payload():
    with pytest.raises(ContractValidationError):
        GenerationResult.from_response_dict("not a dict", resolved_model=None, prompt_version="v1")


def test_generation_result_from_response_dict_rejects_unparseable_top_level_none():
    with pytest.raises(ContractValidationError):
        GenerationResult.from_response_dict(None, resolved_model=None, prompt_version="v1")


def test_generation_result_construction_rejects_non_candidate_list():
    with pytest.raises(ContractValidationError):
        GenerationResult(candidates=["not-a-candidate"])


def test_generation_result_default_clarification_questions_is_empty_list():
    result = GenerationResult(candidates=[])
    assert result.clarification_questions == []
