import pytest

from ai_platform.contracts import ContractValidationError
from ai_platform.policy_contracts import (
    ALLOWED_SECTION_KEYS,
    MAX_TOTAL_CONTENT_CHARS,
    PolicyGenerationResult,
    PolicyGroundingPayload,
    PolicyReviewWarning,
    PolicySection,
)


def _grounding(**overrides):
    defaults = dict(
        organisation_id="org-1",
        organisation_facts={"name": "Fixture Ltd", "staff_count": 5, "description": ""},
        workplace_facts=[{"name": "HQ", "type": "dedicated_office"}],
        governance_facts={"policy_authoriser": {"full_name": "Ada", "job_title": "CEO"}},
        baseline_facts={"mfa_user_accounts": {"answer": "no", "note": ""}},
        security_state_facts={"mfa_user_accounts": {"area": "access", "answer": "no"}},
        open_risk_facts=[{"title": "Weak MFA", "risk_band": "high", "status": "confirmed"}],
    )
    defaults.update(overrides)
    return PolicyGroundingPayload(**defaults)


def _section(section_key=ALLOWED_SECTION_KEYS[0], content="Some concise policy content."):
    return PolicySection(section_key=section_key, content=content)


def _warning(subject="Backups", detail="Backup practice unknown."):
    return PolicyReviewWarning(subject=subject, detail=detail)


# --- PolicyGroundingPayload ---------------------------------------------------

def test_grounding_valid():
    grounding = _grounding()
    assert grounding.organisation_id == "org-1"


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("organisation_id", ""),
        ("organisation_facts", "not a dict"),
        ("workplace_facts", "not a list"),
        ("workplace_facts", [1, 2]),
        ("governance_facts", ["not", "a", "dict"]),
        ("baseline_facts", "not a dict"),
        ("security_state_facts", "not a dict"),
        ("open_risk_facts", "not a list"),
        ("open_risk_facts", ["not a dict"]),
    ],
)
def test_grounding_rejects_wrong_shape(field, bad_value):
    with pytest.raises(ContractValidationError):
        _grounding(**{field: bad_value})


# --- PolicySection -------------------------------------------------------------

def test_section_valid():
    section = _section()
    assert section.section_key in ALLOWED_SECTION_KEYS


def test_section_rejects_unknown_key():
    with pytest.raises(ContractValidationError):
        _section(section_key="not_a_real_section")


def test_section_rejects_blank_content():
    with pytest.raises(ContractValidationError):
        _section(content="")


def test_section_from_dict_missing_field_raises():
    with pytest.raises(ContractValidationError):
        PolicySection.from_dict({"section_key": ALLOWED_SECTION_KEYS[0]})


def test_section_from_dict_not_a_dict_raises():
    with pytest.raises(ContractValidationError):
        PolicySection.from_dict("not a dict")


# --- PolicyReviewWarning --------------------------------------------------------

def test_review_warning_valid():
    warning = _warning()
    assert warning.subject == "Backups"


def test_review_warning_rejects_blank_subject():
    with pytest.raises(ContractValidationError):
        _warning(subject="")


def test_review_warning_from_dict_missing_field_raises():
    with pytest.raises(ContractValidationError):
        PolicyReviewWarning.from_dict({"subject": "x"})


# --- PolicyGenerationResult ------------------------------------------------------

def test_result_valid_minimal():
    result = PolicyGenerationResult(policy_title="Fixture Ltd ISP", sections=[_section()])
    assert result.review_warnings == []


def test_result_rejects_empty_sections():
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult(policy_title="t", sections=[])


def test_result_rejects_blank_title():
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult(policy_title="", sections=[_section()])


def test_result_rejects_duplicate_section_key():
    with pytest.raises(ContractValidationError, match="duplicate"):
        PolicyGenerationResult(
            policy_title="t",
            sections=[
                _section(section_key=ALLOWED_SECTION_KEYS[0]),
                _section(section_key=ALLOWED_SECTION_KEYS[0], content="different content"),
            ],
        )


def test_result_rejects_over_cap_total_content_length():
    huge_content = "x" * (MAX_TOTAL_CONTENT_CHARS + 1)
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult(
            policy_title="t", sections=[_section(content=huge_content)]
        )


def test_result_accepts_exactly_at_cap():
    content = "x" * MAX_TOTAL_CONTENT_CHARS
    result = PolicyGenerationResult(policy_title="t", sections=[_section(content=content)])
    assert len(result.sections[0].content) == MAX_TOTAL_CONTENT_CHARS


# --- PolicyGenerationResult.from_response_dict: the single choke point -------

def _payload(sections, warnings=None):
    return {
        "policy_title": "Fixture Ltd Information Security Policy",
        "sections": sections,
        "review_warnings": warnings or [],
    }


def test_from_response_dict_valid():
    result = PolicyGenerationResult.from_response_dict(
        _payload([{"section_key": ALLOWED_SECTION_KEYS[0], "content": "Purpose text."}]),
        resolved_model="trinity/some-backend",
        prompt_version="policy_generation_v1",
        prompt_tokens=10,
        completion_tokens=20,
    )
    assert result.policy_title == "Fixture Ltd Information Security Policy"
    assert len(result.sections) == 1
    assert result.resolved_model == "trinity/some-backend"


def test_from_response_dict_rejects_unknown_section_key():
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult.from_response_dict(
            _payload([{"section_key": "not_a_real_section", "content": "x"}]),
            resolved_model="m",
            prompt_version="v1",
        )


def test_from_response_dict_rejects_duplicate_section_key():
    sections = [
        {"section_key": ALLOWED_SECTION_KEYS[0], "content": "a"},
        {"section_key": ALLOWED_SECTION_KEYS[0], "content": "b"},
    ]
    with pytest.raises(ContractValidationError, match="duplicate"):
        PolicyGenerationResult.from_response_dict(
            _payload(sections), resolved_model="m", prompt_version="v1"
        )


def test_from_response_dict_missing_sections_key_is_rejected():
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult.from_response_dict(
            {"policy_title": "t", "review_warnings": []},
            resolved_model="m",
            prompt_version="v1",
        )


def test_from_response_dict_missing_policy_title_is_rejected():
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult.from_response_dict(
            {"sections": [{"section_key": ALLOWED_SECTION_KEYS[0], "content": "x"}]},
            resolved_model="m",
            prompt_version="v1",
        )


def test_from_response_dict_review_warnings_default_to_empty():
    result = PolicyGenerationResult.from_response_dict(
        _payload([{"section_key": ALLOWED_SECTION_KEYS[0], "content": "x"}]),
        resolved_model="m",
        prompt_version="v1",
    )
    assert result.review_warnings == []


def test_from_response_dict_carries_review_warnings():
    result = PolicyGenerationResult.from_response_dict(
        _payload(
            [{"section_key": ALLOWED_SECTION_KEYS[0], "content": "x"}],
            warnings=[{"subject": "Backups", "detail": "Unknown."}],
        ),
        resolved_model="m",
        prompt_version="v1",
    )
    assert len(result.review_warnings) == 1
    assert result.review_warnings[0].subject == "Backups"


def test_from_response_dict_not_a_dict_is_rejected():
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult.from_response_dict(
            "not a dict", resolved_model="m", prompt_version="v1"
        )


def test_from_response_dict_enforces_total_content_cap():
    huge_content = "x" * (MAX_TOTAL_CONTENT_CHARS + 1)
    with pytest.raises(ContractValidationError):
        PolicyGenerationResult.from_response_dict(
            _payload([{"section_key": ALLOWED_SECTION_KEYS[0], "content": huge_content}]),
            resolved_model="m",
            prompt_version="v1",
        )
