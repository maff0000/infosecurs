import json
import os

import pytest
from django.core.exceptions import ImproperlyConfigured

from ai_platform.contracts import GroundingPayload
from ai_platform.gateway import (
    DEFAULT_MODEL_ALIAS,
    GatewayAuthError,
    GatewayConnectionError,
    GatewayRateLimitError,
    InvalidResponseError,
    LiteLLMGateway,
)


def test_default_model_alias_is_trinity_core():
    # PID §9.1 / ARCHITECTURE.md: the generic, already-governed alias -
    # never an Infosecurs-specific one.
    assert DEFAULT_MODEL_ALIAS == "trinity-core"


# --- Lazy configuration (PID §9.2, §14) --------------------------------------

def test_generate_does_not_require_ai_env_vars_at_import_time(monkeypatch):
    # Importing the module / instantiating the gateway must never touch
    # config.env - only calling generate() does. Whether these vars happen
    # to be set in the ambient process environment (e.g. a developer's own
    # .env, which documents AI_RISK_MODEL_ALIAS with a non-blank default in
    # .env.example) is not this module's concern and not what this test
    # should assert on - PL integration note, 2026-09-23: the original
    # version of this test asserted the three vars were absent from
    # os.environ, which is true in CI (ci.yml sets none of them) but false
    # for any developer following .env.example locally, since docker
    # compose's env_file passes every .env entry into the container's real
    # process environment regardless of whether Django ever reads it. Force
    # a clean slate for *this test only* instead, so the assertion is about
    # the module's own behaviour, not about the surrounding shell's state.
    for name in ("AI_GATEWAY_BASE_URL", "AI_GATEWAY_API_KEY_FILE", "AI_RISK_MODEL_ALIAS"):
        monkeypatch.delenv(name, raising=False)
    LiteLLMGateway()  # must not raise


def test_generate_raises_loudly_when_base_url_missing(grounding):
    os.environ.pop("AI_GATEWAY_BASE_URL", None)
    os.environ.pop("AI_GATEWAY_API_KEY_FILE", None)
    gateway = LiteLLMGateway()
    with pytest.raises(ImproperlyConfigured):
        gateway.generate(grounding, "risk_generation_v1")


def test_generate_rejects_unknown_prompt_version(grounding, tmp_path, monkeypatch):
    key_file = tmp_path / "key"
    key_file.write_text("dummy-not-a-real-credential")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "http://example.invalid")
    monkeypatch.setenv("AI_GATEWAY_API_KEY_FILE", str(key_file))
    gateway = LiteLLMGateway()
    with pytest.raises(InvalidResponseError):
        gateway.generate(grounding, "some_other_prompt_version")


# --- Multi-version prompt resolution (M002 repair, 2026-09-23) --------------
#
# ai_platform.gateway used to hardcode the only prompt_version it could
# render to risk_generation_v1. That broke once risk_register/eval/harness.py
# and risk_register/services.py started requesting risk_generation_v2 (the
# repair for the PID §18 live-eval RED finding) - generate() would have
# rejected every v2 call as an "unknown prompt_version", even though v2 is
# a real, current version. These tests prove the fix: generate() now
# resolves *any* known version, not just v1, and still rejects a version
# that truly is not registered.

def test_generate_raises_loudly_when_base_url_missing_for_v2(grounding):
    # Mirrors test_generate_raises_loudly_when_base_url_missing above, but
    # for risk_generation_v2: proves the version check passes (we reach the
    # config lookup and get ImproperlyConfigured, not InvalidResponseError)
    # for v2 exactly as it already did for v1.
    os.environ.pop("AI_GATEWAY_BASE_URL", None)
    os.environ.pop("AI_GATEWAY_API_KEY_FILE", None)
    gateway = LiteLLMGateway()
    with pytest.raises(ImproperlyConfigured):
        gateway.generate(grounding, "risk_generation_v2")


def test_generate_still_rejects_a_version_that_is_not_registered_at_all(grounding, tmp_path, monkeypatch):
    key_file = tmp_path / "key"
    key_file.write_text("dummy-not-a-real-credential")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "http://example.invalid")
    monkeypatch.setenv("AI_GATEWAY_API_KEY_FILE", str(key_file))
    gateway = LiteLLMGateway()
    with pytest.raises(InvalidResponseError):
        gateway.generate(grounding, "risk_generation_v999_does_not_exist")


def test_build_messages_for_version_resolves_v1_and_v2_and_rejects_unknown():
    from ai_platform.prompts import KNOWN_PROMPT_VERSIONS, build_messages_for_version
    from ai_platform.prompts.risk_generation_v1 import build_messages as v1_build_messages
    from ai_platform.prompts.risk_generation_v2 import build_messages as v2_build_messages

    assert build_messages_for_version("risk_generation_v1") is v1_build_messages
    assert build_messages_for_version("risk_generation_v2") is v2_build_messages
    assert build_messages_for_version("not_a_real_version") is None
    assert set(KNOWN_PROMPT_VERSIONS) == {"risk_generation_v1", "risk_generation_v2"}


# --- Credential handling (PID §9.2, never log the credential) ---------------

def test_read_credential_from_file(tmp_path):
    key_file = tmp_path / "key"
    key_file.write_text("  a-fixture-credential-value  \n")
    assert LiteLLMGateway._read_credential(str(key_file)) == "a-fixture-credential-value"


def test_read_credential_missing_file_raises_auth_error_without_leaking_path_contents(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(GatewayAuthError) as excinfo:
        LiteLLMGateway._read_credential(str(missing))
    # The path is safe to mention (it's configuration); there is nothing
    # else in the message because the file was never successfully read.
    assert str(missing) in str(excinfo.value)


def test_read_credential_empty_file_raises_auth_error(tmp_path):
    key_file = tmp_path / "key"
    key_file.write_text("   \n")
    with pytest.raises(GatewayAuthError):
        LiteLLMGateway._read_credential(str(key_file))


def test_credential_value_never_appears_in_any_raised_exception_message(tmp_path):
    secret_value = "sk-totally-secret-fixture-value-should-never-leak"
    key_file = tmp_path / "key"
    key_file.write_text(secret_value)
    # Exercise the status-based classifier with the credential in scope but
    # never passed to it - proves the classifier itself cannot echo it.
    with pytest.raises(GatewayAuthError) as excinfo:
        LiteLLMGateway._raise_for_status(401, b"{}")
    assert secret_value not in str(excinfo.value)


# --- HTTP status classification ---------------------------------------------

@pytest.mark.parametrize(
    "status,expected_exc",
    [
        (401, GatewayAuthError),
        (403, GatewayAuthError),
        (429, GatewayRateLimitError),
        (500, GatewayConnectionError),
        (503, GatewayConnectionError),
        (418, InvalidResponseError),  # unexpected status, not modelled -> invalid response
    ],
)
def test_raise_for_status_classifies_errors(status, expected_exc):
    with pytest.raises(expected_exc):
        LiteLLMGateway._raise_for_status(status, b"{}")


def test_raise_for_status_ok_for_2xx():
    LiteLLMGateway._raise_for_status(200, b"{}")  # must not raise


# --- OpenAI-envelope parsing --------------------------------------------------

def _valid_structured_payload():
    return {
        "risks": [
            {
                "title": "Weak MFA coverage",
                "asset_reference": "asset:fixture",
                "threat": "Account takeover",
                "vulnerability": "No MFA on ordinary user accounts",
                "suggested_impact": 3,
                "suggested_likelihood": 4,
                "rationale": "Baseline states MFA is not enabled.",
                "proposed_treatment": "Enable MFA.",
                "grounding_refs": ["baseline.mfa_user_accounts"],
                "assumptions": [],
            }
        ],
        "clarification_questions": [],
    }


def test_parse_openai_response_valid():
    payload = {
        "model": "trinity/some-real-backend",
        "usage": {"prompt_tokens": 111, "completion_tokens": 22},
        "choices": [{"message": {"content": json.dumps(_valid_structured_payload())}}],
    }
    result = LiteLLMGateway._parse_openai_response(payload, "risk_generation_v1")
    assert result.resolved_model == "trinity/some-real-backend"
    assert result.prompt_tokens == 111
    assert result.completion_tokens == 22
    assert len(result.candidates) == 1


def test_parse_openai_response_missing_choices_is_invalid_response():
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_response({"choices": []}, "risk_generation_v1")


def test_parse_openai_response_content_not_json_is_invalid_response():
    payload = {"choices": [{"message": {"content": "not json at all"}}]}
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_response(payload, "risk_generation_v1")


def test_parse_openai_response_content_fails_contract_validation_is_invalid_response():
    payload = {"choices": [{"message": {"content": json.dumps({"risks": "not-a-list"})}}]}
    with pytest.raises(InvalidResponseError):
        LiteLLMGateway._parse_openai_response(payload, "risk_generation_v1")


def test_parse_openai_response_over_max_candidates_is_not_rejected_here():
    # The cap is enforced by ai_platform.orchestration.generate_risks
    # (truncation), not by response parsing - parsing only validates shape.
    structured = _valid_structured_payload()
    structured["risks"] = structured["risks"] * 9  # 9 valid candidates
    payload = {"choices": [{"message": {"content": json.dumps(structured)}}]}
    result = LiteLLMGateway._parse_openai_response(payload, "risk_generation_v1")
    assert len(result.candidates) == 9
