"""
Provider-neutral gateway abstraction for AI risk generation (M002 PID §9.1,
§9.2, §17, §24).

`RiskGenerationGateway` is the only interface the rest of the application -
and the later Risk-domain module - should depend on.

`LiteLLMGateway` is the real implementation. It talks to the existing
Trinity-governed LiteLLM-compatible gateway over its OpenAI-compatible
`/v1/chat/completions` endpoint, using the Python standard library only
(`urllib.request`/`json`) - no `requests`/`httpx`/new pip dependency (PID
§25: a single JSON POST with a bearer token and a timeout does not justify
a new governed dependency).

`FakeGateway` (the PID §17 test seam) lives in `ai_platform.testing`, not
here, so production code never imports test doubles.
"""
from __future__ import annotations

import abc
import json
import socket
import urllib.error
import urllib.request
from typing import Optional

from ai_platform.contracts import ContractValidationError, GenerationResult, GroundingPayload
from ai_platform.interpretation_contracts import InterpretationRequest, InterpretationResponse
from ai_platform.policy_contracts import PolicyGenerationResult, PolicyGroundingPayload

# Governed, generic Trinity alias (Central Architecture correction,
# 2026-09-22). Not Infosecurs-specific - see PID §9.1, ARCHITECTURE.md "AI".
DEFAULT_MODEL_ALIAS = "trinity-core"

DEFAULT_TIMEOUT_SECONDS = 30.0


class GatewayError(Exception):
    """Base class for all AI gateway failures. Never carries a credential
    value in its message (PID §9.8 / rule: never log the credential)."""


class RetryableGatewayError(GatewayError):
    """A failure `ai_platform.orchestration.generate_risks` may retry
    exactly once (PID §14). Transient/transport-shaped failures only."""


class GatewayTimeoutError(RetryableGatewayError):
    """The request did not complete within the configured timeout."""


class GatewayConnectionError(RetryableGatewayError):
    """A generic retryable network/transport/server failure (e.g. DNS,
    connection refused, 5xx)."""


class GatewayRateLimitError(RetryableGatewayError):
    """The gateway responded 429. Treated as retryable: PID §14 caps the
    total extra cost at exactly one bounded retry regardless of failure
    flavour, so this can never become an unbounded backoff/retry storm."""


class GatewayAuthError(GatewayError):
    """Credentials were rejected (401/403), or the credential file could
    not be read. Not retryable: an identical retry with the same
    credential will not succeed."""


class InvalidResponseError(GatewayError):
    """The gateway responded, but the payload failed structured validation
    (PID §9.3) or was not parseable at all. Not retryable - PID §14
    explicitly excludes schema/policy-invalid output from the one-retry
    allowance, since an identical retry is not more likely to produce
    valid JSON."""


class RiskGenerationGateway(abc.ABC):
    """Provider-neutral risk-generation boundary (PID §9.1)."""

    @abc.abstractmethod
    def generate(self, grounding: GroundingPayload, prompt_version: str) -> GenerationResult:
        """Run one generation call and return a validated `GenerationResult`.

        Raises a `GatewayError` subclass on any failure - never returns a
        partially-valid result.
        """
        raise NotImplementedError


class RiskInterpretationGateway(abc.ABC):
    """Provider-neutral risk-INTERPRETATION boundary (M002-3c dispatch,
    PID §0.6/§0.7/§9.1).

    Deliberately a separate ABC from `RiskGenerationGateway`, not a second
    abstract method bolted onto it: the retired generation task and this
    task have different request/response contracts
    (`GroundingPayload`/`GenerationResult` vs
    `InterpretationRequest`/`InterpretationResponse`), and every existing
    `RiskGenerationGateway` implementation/test-double (`LiteLLMGateway`,
    `ai_platform.testing.FakeGateway`) only ever needed to satisfy
    `generate()`. Adding `interpret()` as a second abstractmethod on the
    same ABC would have forced every existing `FakeGateway` construction
    site across the test suite to grow a meaningless `interpret()`
    implementation just to remain instantiable, for a method those tests
    have no reason to exercise. `LiteLLMGateway` below implements BOTH
    ABCs on the one concrete class - reusing its HTTP/retry/credential
    mechanics for both tasks - which is what PID's "don't duplicate the
    retry/timeout/credential mechanics" instruction actually requires;
    `ai_platform.testing.FakeInterpretationGateway` is this ABC's own,
    separate test double, mirroring `FakeGateway`'s mode-based pattern.
    """

    @abc.abstractmethod
    def interpret(
        self, request: InterpretationRequest, prompt_version: str
    ) -> InterpretationResponse:
        """Run one interpretation call over already-existing candidate
        summaries and return a validated `InterpretationResponse`.

        Raises a `GatewayError` subclass on any failure - never returns a
        partially-valid result, and never partially matches the request's
        indices (see `InterpretationResponse.from_response_dict`).
        """
        raise NotImplementedError


class PolicyGenerationGateway(abc.ABC):
    """Provider-neutral POLICY-generation boundary (M004 PID §13,
    m004-2a-policy-foundation dispatch).

    Deliberately a separate ABC from `RiskGenerationGateway`/
    `RiskInterpretationGateway`, not a third abstract method bolted onto
    either of them - same reasoning `RiskInterpretationGateway`'s own
    docstring already gives for why IT is a separate ABC from
    `RiskGenerationGateway`: this task has its own request/response
    contract (`PolicyGroundingPayload`/`PolicyGenerationResult`, from
    `ai_platform.policy_contracts`), and every existing
    `RiskGenerationGateway`/`RiskInterpretationGateway` implementation/test-
    double only ever needed to satisfy `generate()`/`interpret()`. Adding
    `generate_policy()` as a third abstractmethod on either existing ABC
    would force every existing gateway test double to grow a meaningless
    implementation of a method those tests have no reason to exercise.
    `LiteLLMGateway` below implements all THREE ABCs on the one concrete
    class - reusing its HTTP/retry/credential mechanics for all three tasks
    - which is exactly what the "don't duplicate the retry/timeout/
    credential mechanics" instruction requires; `ai_platform.testing.
    FakePolicyGateway` is this ABC's own, separate test double, mirroring
    `FakeGateway`/`FakeInterpretationGateway`'s mode-based pattern.
    """

    @abc.abstractmethod
    def generate_policy(
        self, grounding: PolicyGroundingPayload, prompt_version: str
    ) -> PolicyGenerationResult:
        """Run one policy-generation call and return a validated
        `PolicyGenerationResult`.

        Raises a `GatewayError` subclass on any failure - never returns a
        partially-valid result.
        """
        raise NotImplementedError


class LiteLLMGateway(RiskGenerationGateway, RiskInterpretationGateway, PolicyGenerationGateway):
    """Real implementation - the existing Trinity LiteLLM-compatible
    gateway (PID §9.1, §9.2, §24).

    Configuration (`AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY_FILE`,
    `AI_RISK_MODEL_ALIAS`) is read lazily, inside `generate()`, not at
    Django import/startup - PID §14: generation happens only on an explicit
    user action, so the rest of the application (baseline, assets, etc.)
    must keep working in dev/CI without AI config present.
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self._timeout = timeout

    def generate(self, grounding: GroundingPayload, prompt_version: str) -> GenerationResult:
        # Local imports: keep config/prompt loading lazy, and keep this
        # module importable without Django settings configured (e.g. from
        # a plain script or a non-Django test).
        from config.env import optional_env, require_env

        from ai_platform.prompts import KNOWN_PROMPT_VERSIONS, build_messages_for_version

        build_messages = build_messages_for_version(prompt_version)
        if build_messages is None:
            raise InvalidResponseError(
                f"requested prompt_version {prompt_version!r} is not one of the prompt "
                f"versions this gateway build knows how to render {KNOWN_PROMPT_VERSIONS!r}"
            )

        base_url = require_env("AI_GATEWAY_BASE_URL").rstrip("/")
        key_file = require_env("AI_GATEWAY_API_KEY_FILE")
        model_alias = optional_env("AI_RISK_MODEL_ALIAS", DEFAULT_MODEL_ALIAS)

        api_key = self._read_credential(key_file)

        request_body = json.dumps(
            {
                "model": model_alias,
                "messages": build_messages(grounding),
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url=f"{base_url}/v1/chat/completions",
            data=request_body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        status, raw_body = self._send(request)
        self._raise_for_status(status, raw_body)

        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidResponseError("AI gateway response was not valid JSON") from exc

        return self._parse_openai_response(payload, prompt_version)

    def interpret(
        self, request: InterpretationRequest, prompt_version: str
    ) -> InterpretationResponse:
        """`RiskInterpretationGateway.interpret` (M002-3c dispatch). Reuses
        this class's own `_send`/`_read_credential`/`_raise_for_status`/
        `_extract_structured_content` exactly as `generate()` does above -
        same HTTP client, same lazy config loading, same error taxonomy,
        same credential handling - only the built request messages and the
        response contract parser differ.
        """
        # Local imports: keep config/prompt loading lazy, and keep this
        # module importable without Django settings configured - same
        # reasoning as generate() above.
        from config.env import optional_env, require_env

        from ai_platform.prompts import (
            KNOWN_INTERPRETATION_PROMPT_VERSIONS,
            build_interpretation_messages_for_version,
        )

        build_messages = build_interpretation_messages_for_version(prompt_version)
        if build_messages is None:
            raise InvalidResponseError(
                f"requested prompt_version {prompt_version!r} is not one of the "
                f"interpretation prompt versions this gateway build knows how to "
                f"render {KNOWN_INTERPRETATION_PROMPT_VERSIONS!r}"
            )

        base_url = require_env("AI_GATEWAY_BASE_URL").rstrip("/")
        key_file = require_env("AI_GATEWAY_API_KEY_FILE")
        model_alias = optional_env("AI_RISK_MODEL_ALIAS", DEFAULT_MODEL_ALIAS)

        api_key = self._read_credential(key_file)

        request_body = json.dumps(
            {
                "model": model_alias,
                "messages": build_messages(request),
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        http_request = urllib.request.Request(
            url=f"{base_url}/v1/chat/completions",
            data=request_body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        status, raw_body = self._send(http_request)
        self._raise_for_status(status, raw_body)

        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidResponseError("AI gateway response was not valid JSON") from exc

        return self._parse_openai_interpretation_response(
            payload, prompt_version, request.expected_indices
        )

    def generate_policy(
        self, grounding: PolicyGroundingPayload, prompt_version: str
    ) -> PolicyGenerationResult:
        """`PolicyGenerationGateway.generate_policy` (M004
        m004-2a-policy-foundation dispatch). Reuses this class's own
        `_send`/`_read_credential`/`_raise_for_status`/
        `_extract_structured_content` exactly as `generate()`/`interpret()`
        do above - same HTTP client, same lazy config loading, same error
        taxonomy, same credential handling - only the built request
        messages and the response contract parser differ.

        Model alias: reuses `AI_RISK_MODEL_ALIAS` (PID §13 names the same
        governed `trinity-core` alias for policy generation as for risk
        generation - there is no separate policy-specific model-alias env
        var to invent).
        """
        # Local imports: keep config/prompt loading lazy, and keep this
        # module importable without Django settings configured - same
        # reasoning as generate()/interpret() above.
        from config.env import optional_env, require_env

        from ai_platform.prompts import (
            KNOWN_POLICY_PROMPT_VERSIONS,
            build_policy_messages_for_version,
        )

        build_messages = build_policy_messages_for_version(prompt_version)
        if build_messages is None:
            raise InvalidResponseError(
                f"requested prompt_version {prompt_version!r} is not one of the "
                f"policy-generation prompt versions this gateway build knows how "
                f"to render {KNOWN_POLICY_PROMPT_VERSIONS!r}"
            )

        base_url = require_env("AI_GATEWAY_BASE_URL").rstrip("/")
        key_file = require_env("AI_GATEWAY_API_KEY_FILE")
        model_alias = optional_env("AI_RISK_MODEL_ALIAS", DEFAULT_MODEL_ALIAS)

        api_key = self._read_credential(key_file)

        request_body = json.dumps(
            {
                "model": model_alias,
                "messages": build_messages(grounding),
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        http_request = urllib.request.Request(
            url=f"{base_url}/v1/chat/completions",
            data=request_body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        status, raw_body = self._send(http_request)
        self._raise_for_status(status, raw_body)

        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidResponseError("AI gateway response was not valid JSON") from exc

        return self._parse_openai_policy_response(payload, prompt_version)

    def _send(self, request: urllib.request.Request):
        """Perform the HTTP call, translating transport failures into typed
        gateway exceptions. Never logs/echoes the Authorization header."""
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            # A non-2xx response - the server did respond, so surface its
            # body/status through the normal status-based classification.
            return exc.code, exc.read()
        except socket.timeout as exc:
            raise GatewayTimeoutError("AI gateway request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise GatewayTimeoutError("AI gateway request timed out") from exc
            raise GatewayConnectionError(f"AI gateway connection failed: {exc.reason}") from exc

    @staticmethod
    def _read_credential(key_file: str) -> str:
        """Read the bearer credential from its mounted file (PID §9.2). The
        credential VALUE is never logged, never placed in an exception
        message, never stored on `self`/an `AIInvocationRecord`. The file
        PATH is ordinary configuration and is safe to name in errors."""
        try:
            with open(key_file, "r", encoding="utf-8") as fh:
                value = fh.read().strip()
        except OSError as exc:
            raise GatewayAuthError(
                f"could not read AI gateway credential file {key_file!r}"
            ) from exc
        if not value:
            raise GatewayAuthError(f"AI gateway credential file {key_file!r} is empty")
        return value

    @staticmethod
    def _raise_for_status(status: int, raw_body: bytes) -> None:
        if 200 <= status < 300:
            return
        if status in (401, 403):
            raise GatewayAuthError(f"AI gateway rejected credentials (HTTP {status})")
        if status == 429:
            raise GatewayRateLimitError("AI gateway rate limit exceeded")
        if 500 <= status < 600:
            raise GatewayConnectionError(f"AI gateway server error (HTTP {status})")
        raise InvalidResponseError(f"AI gateway returned unexpected HTTP {status}")

    @staticmethod
    def _extract_structured_content(payload: dict):
        """Unwrap the OpenAI-compatible envelope shared by BOTH the
        generation and interpretation tasks - `choices[0].message.content`
        is the model's own JSON, `model`/`usage` are the same envelope
        metadata either way. Shared by `_parse_openai_response` and
        `_parse_openai_interpretation_response` below so this unwrap step
        exists exactly once; only each task's OWN response-contract parser
        (`GenerationResult.from_response_dict` /
        `InterpretationResponse.from_response_dict`) differs after this
        point. Extracted as part of the M002-3c dispatch reusing
        `LiteLLMGateway`'s mechanics for the new task without duplicating
        them - behaviour of the pre-existing `_parse_openai_response` is
        unchanged by this extraction (see `ai_platform/tests/test_gateway.py`,
        which exercises it directly and is unmodified by this dispatch).

        Returns `(structured, resolved_model, prompt_tokens,
        completion_tokens)`. Raises `InvalidResponseError` if the envelope
        itself is missing or its content is not valid JSON.
        """
        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InvalidResponseError(
                "AI gateway response missing choices[0].message.content"
            ) from exc

        try:
            structured = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvalidResponseError("AI gateway message content was not valid JSON") from exc

        resolved_model: Optional[str] = payload.get("model")
        usage = payload.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        return structured, resolved_model, prompt_tokens, completion_tokens

    @staticmethod
    def _parse_openai_response(payload: dict, prompt_version: str) -> GenerationResult:
        """Unwrap the OpenAI-compatible envelope, then hand the model's own
        JSON content to the strict contract parser."""
        structured, resolved_model, prompt_tokens, completion_tokens = (
            LiteLLMGateway._extract_structured_content(payload)
        )

        try:
            return GenerationResult.from_response_dict(
                structured,
                resolved_model=resolved_model,
                prompt_version=prompt_version,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except ContractValidationError as exc:
            raise InvalidResponseError(str(exc)) from exc

    @staticmethod
    def _parse_openai_interpretation_response(
        payload: dict, prompt_version: str, expected_indices
    ) -> InterpretationResponse:
        """Interpretation-task counterpart to `_parse_openai_response` -
        same envelope unwrap (`_extract_structured_content`), different
        response-contract parser. `expected_indices` is threaded through to
        `InterpretationResponse.from_response_dict`, which is where the
        index-matching validation the M002-3c dispatch requires actually
        happens (see that method's own docstring)."""
        structured, resolved_model, prompt_tokens, completion_tokens = (
            LiteLLMGateway._extract_structured_content(payload)
        )

        try:
            return InterpretationResponse.from_response_dict(
                structured,
                expected_indices=expected_indices,
                resolved_model=resolved_model,
                prompt_version=prompt_version,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except ContractValidationError as exc:
            raise InvalidResponseError(str(exc)) from exc

    @staticmethod
    def _parse_openai_policy_response(
        payload: dict, prompt_version: str
    ) -> PolicyGenerationResult:
        """Policy-generation-task counterpart to `_parse_openai_response`/
        `_parse_openai_interpretation_response` - same envelope unwrap
        (`_extract_structured_content`), different response-contract
        parser (`PolicyGenerationResult.from_response_dict`)."""
        structured, resolved_model, prompt_tokens, completion_tokens = (
            LiteLLMGateway._extract_structured_content(payload)
        )

        try:
            return PolicyGenerationResult.from_response_dict(
                structured,
                resolved_model=resolved_model,
                prompt_version=prompt_version,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except ContractValidationError as exc:
            raise InvalidResponseError(str(exc)) from exc
