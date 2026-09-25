import json

import pytest
from django.core.exceptions import ImproperlyConfigured

from ai_platform.gateway import InvalidResponseError, LiteLLMGateway
from ai_platform.interpretation_contracts import InterpretationCandidate, InterpretationRequest


def _candidate(index=1):
    return InterpretationCandidate(
        index=index,
        title="Weak MFA coverage",
        exposure="The account signs in over the internet.",
        threat_event="Credential theft or phishing.",
        vulnerability="No confirmed MFA on ordinary user accounts.",
        consequence="Possible unauthorised access.",
        current_impact=3,
        current_likelihood=3,
        asset_category="identity_or_productivity",
        notes=[],
    )


@pytest.fixture
def interpretation_request():
    return InterpretationRequest(organisation_id="org-fixture", candidates=[_candidate(1)])


# --- Lazy configuration (PID §9.2, §14), same discipline as generate() ------

def test_interpret_does_not_require_ai_env_vars_at_import_time(monkeypatch):
    for name in ("AI_GATEWAY_BASE_URL", "AI_GATEWAY_API_KEY_FILE", "AI_RISK_MODEL_ALIAS"):
        monkeypatch.delenv(name, raising=False)
    LiteLLMGateway()  # must not raise


def test_interpret_raises_loudly_when_base_url_missing(interpretation_request, monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_BASE_URL", raising=False)
    monkeypatch.delenv("AI_GATEWAY_API_KEY_FILE", raising=False)
    gateway = LiteLLMGateway()
    with pytest.raises(ImproperlyConfigured):
        gateway.interpret(interpretation_request, "risk_interpretation_v1")


def test_interpret_rejects_unknown_prompt_version(interpretation_request, tmp_path, monkeypatch):
    key_file = tmp_path / "key"
    key_file.write_text("dummy-not-a-real-credential")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "http://example.invalid")
    monkeypatch.setenv("AI_GATEWAY_API_KEY_FILE", str(key_file))
    gateway = LiteLLMGateway()
    with pytest.raises(InvalidResponseError):
        gateway.interpret(interpretation_request, "some_other_prompt_version")


def test_interpret_rejects_a_generation_prompt_version_it_does_not_share_a_registry_with(
    interpretation_request, tmp_path, monkeypatch
):
    # risk_generation_v1 is a real, known GENERATION prompt version, but
    # interpret() must not resolve it - the two tasks' prompt registries are
    # deliberately separate (ai_platform/prompts/__init__.py).
    key_file = tmp_path / "key"
    key_file.write_text("dummy-not-a-real-credential")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "http://example.invalid")
    monkeypatch.setenv("AI_GATEWAY_API_KEY_FILE", str(key_file))
    gateway = LiteLLMGateway()
    with pytest.raises(InvalidResponseError):
        gateway.interpret(interpretation_request, "risk_generation_v1")


def test_build_interpretation_messages_for_version_resolves_v1_and_v2_and_v3_and_rejects_unknown():
    """F3 (M006-AUDIT-0001) added risk_interpretation_v3 to the registry -
    exact precedent: test_gateway.py's own
    test_build_messages_for_version_resolves_v1_and_v2_and_v3_and_rejects_unknown
    for the sibling risk_generation registry."""
    from ai_platform.prompts import (
        KNOWN_INTERPRETATION_PROMPT_VERSIONS,
        build_interpretation_messages_for_version,
    )
    from ai_platform.prompts.risk_interpretation_v1 import build_messages as v1_build_messages
    from ai_platform.prompts.risk_interpretation_v2 import build_messages as v2_build_messages
    from ai_platform.prompts.risk_interpretation_v3 import build_messages as v3_build_messages

    assert build_interpretation_messages_for_version("risk_interpretation_v1") is v1_build_messages
    assert build_interpretation_messages_for_version("risk_interpretation_v2") is v2_build_messages
    assert build_interpretation_messages_for_version("risk_interpretation_v3") is v3_build_messages
    assert build_interpretation_messages_for_version("not_a_real_version") is None
    assert set(KNOWN_INTERPRETATION_PROMPT_VERSIONS) == {
        "risk_interpretation_v1",
        "risk_interpretation_v2",
        "risk_interpretation_v3",
    }


# --- OpenAI-envelope parsing (interpretation task) ---------------------------

def _valid_structured_payload():
    return {
        "interpretations": [
            {
                "index": 1,
                "suggested_impact": 4,
                "suggested_likelihood": 3,
                "rationale": "Baseline states MFA is not enabled.",
                "suggested_treatment": "Enable MFA.",
                "clarification_questions": [],
            }
        ],
        "additional_observations": [],
    }


def test_parse_openai_interpretation_response_valid():
    payload = {
        "model": "trinity/some-real-backend",
        "usage": {"prompt_tokens": 111, "completion_tokens": 22},
        "choices": [{"message": {"content": json.dumps(_valid_structured_payload())}}],
    }
    result = LiteLLMGateway._parse_openai_interpretation_response(
        payload, "risk_interpretation_v1", expected_indices={1}
    )
    assert result.resolved_model == "trinity/some-real-backend"
    assert result.prompt_tokens == 111
    assert result.completion_tokens == 22
    assert len(result.outcomes) == 1
    assert result.outcomes[0].index == 1


def test_parse_openai_interpretation_response_missing_choices_is_invalid_response():
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_interpretation_response(
            {"choices": []}, "risk_interpretation_v1", expected_indices={1}
        )


def test_parse_openai_interpretation_response_content_not_json_is_invalid_response():
    payload = {"choices": [{"message": {"content": "not json at all"}}]}
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_interpretation_response(
            payload, "risk_interpretation_v1", expected_indices={1}
        )


def test_parse_openai_interpretation_response_index_mismatch_is_invalid_response():
    payload = {"choices": [{"message": {"content": json.dumps(_valid_structured_payload())}}]}
    # expected_indices says {1, 2} but the payload only interprets index 1.
    with pytest.raises(InvalidResponseError, match="missing"):
        LiteLLMGateway._parse_openai_interpretation_response(
            payload, "risk_interpretation_v1", expected_indices={1, 2}
        )


def test_parse_openai_interpretation_response_unknown_index_is_invalid_response():
    payload = {"choices": [{"message": {"content": json.dumps(_valid_structured_payload())}}]}
    # expected_indices says {2} but the payload interprets index 1.
    with pytest.raises(InvalidResponseError, match="not sent"):
        LiteLLMGateway._parse_openai_interpretation_response(
            payload, "risk_interpretation_v1", expected_indices={2}
        )
