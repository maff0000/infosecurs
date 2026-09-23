import json

import pytest
from django.core.exceptions import ImproperlyConfigured

from ai_platform.gateway import InvalidResponseError, LiteLLMGateway, PolicyGenerationGateway
from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS, PolicyGroundingPayload


def _grounding():
    return PolicyGroundingPayload(
        organisation_id="org-fixture",
        organisation_facts={"name": "Fixture Ltd", "staff_count": 5, "description": ""},
        workplace_facts=[],
        governance_facts={},
        baseline_facts={},
        security_state_facts={},
        open_risk_facts=[],
    )


def test_litellm_gateway_implements_policy_generation_gateway():
    assert isinstance(LiteLLMGateway(), PolicyGenerationGateway)


# --- Lazy configuration (PID §9.2, §14), same discipline as generate()/interpret() ------

def test_generate_policy_does_not_require_ai_env_vars_at_import_time(monkeypatch):
    for name in ("AI_GATEWAY_BASE_URL", "AI_GATEWAY_API_KEY_FILE", "AI_RISK_MODEL_ALIAS"):
        monkeypatch.delenv(name, raising=False)
    LiteLLMGateway()  # must not raise


def test_generate_policy_raises_loudly_when_base_url_missing(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_BASE_URL", raising=False)
    monkeypatch.delenv("AI_GATEWAY_API_KEY_FILE", raising=False)
    gateway = LiteLLMGateway()
    with pytest.raises(ImproperlyConfigured):
        gateway.generate_policy(_grounding(), "policy_generation_v1")


def test_generate_policy_rejects_unknown_prompt_version(tmp_path, monkeypatch):
    key_file = tmp_path / "key"
    key_file.write_text("dummy-not-a-real-credential")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "http://example.invalid")
    monkeypatch.setenv("AI_GATEWAY_API_KEY_FILE", str(key_file))
    gateway = LiteLLMGateway()
    with pytest.raises(InvalidResponseError):
        gateway.generate_policy(_grounding(), "some_other_prompt_version")


def test_generate_policy_rejects_a_generation_prompt_version_it_does_not_share_a_registry_with(
    tmp_path, monkeypatch
):
    # risk_generation_v1 is a real, known RISK-generation prompt version,
    # but generate_policy() must not resolve it - each task's prompt
    # registry is deliberately separate (ai_platform/prompts/__init__.py).
    key_file = tmp_path / "key"
    key_file.write_text("dummy-not-a-real-credential")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "http://example.invalid")
    monkeypatch.setenv("AI_GATEWAY_API_KEY_FILE", str(key_file))
    gateway = LiteLLMGateway()
    with pytest.raises(InvalidResponseError):
        gateway.generate_policy(_grounding(), "risk_generation_v1")


def test_build_policy_messages_for_version_resolves_v1_and_rejects_unknown():
    from ai_platform.prompts import (
        KNOWN_POLICY_PROMPT_VERSIONS,
        build_policy_messages_for_version,
    )
    from ai_platform.prompts.policy_generation_v1 import build_messages as v1_build_messages

    assert build_policy_messages_for_version("policy_generation_v1") is v1_build_messages
    assert build_policy_messages_for_version("not_a_real_version") is None
    assert set(KNOWN_POLICY_PROMPT_VERSIONS) == {"policy_generation_v1"}


# --- OpenAI-envelope parsing (policy-generation task) -------------------------

def _valid_structured_payload():
    return {
        "policy_title": "Fixture Ltd Information Security Policy",
        "sections": [{"section_key": ALLOWED_SECTION_KEYS[0], "content": "Purpose text."}],
        "review_warnings": [],
    }


def test_parse_openai_policy_response_valid():
    payload = {
        "model": "trinity/some-real-backend",
        "usage": {"prompt_tokens": 111, "completion_tokens": 22},
        "choices": [{"message": {"content": json.dumps(_valid_structured_payload())}}],
    }
    result = LiteLLMGateway._parse_openai_policy_response(payload, "policy_generation_v1")
    assert result.resolved_model == "trinity/some-real-backend"
    assert result.prompt_tokens == 111
    assert result.completion_tokens == 22
    assert len(result.sections) == 1
    assert result.policy_title == "Fixture Ltd Information Security Policy"


def test_parse_openai_policy_response_missing_choices_is_invalid_response():
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_policy_response({"choices": []}, "policy_generation_v1")


def test_parse_openai_policy_response_content_not_json_is_invalid_response():
    payload = {"choices": [{"message": {"content": "not json at all"}}]}
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_policy_response(payload, "policy_generation_v1")


def test_parse_openai_policy_response_unknown_section_key_is_invalid_response():
    structured = _valid_structured_payload()
    structured["sections"][0]["section_key"] = "not_a_real_section"
    payload = {"choices": [{"message": {"content": json.dumps(structured)}}]}
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_policy_response(payload, "policy_generation_v1")


def test_parse_openai_policy_response_duplicate_section_key_is_invalid_response():
    structured = _valid_structured_payload()
    structured["sections"].append(
        {"section_key": ALLOWED_SECTION_KEYS[0], "content": "a repeat"}
    )
    payload = {"choices": [{"message": {"content": json.dumps(structured)}}]}
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_policy_response(payload, "policy_generation_v1")
