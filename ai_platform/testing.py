"""
Deterministic test double for `RiskGenerationGateway` (M002 PID §17 - "AI
test seam").

Mechanical tests must never require a live external LLM. `FakeGateway`
implements exactly the same interface as `LiteLLMGateway`, with fully
deterministic, constructor-selected behaviour. It is a test seam for the
application boundary - it must not become a second production AI
implementation, which is why it lives here (`ai_platform.testing`) rather
than in `ai_platform.gateway`, and contains no HTTP, no prompt rendering,
and no attempt at real NLP.

Kept inside the `ai_platform` app (not under `tests/`) so the later
Risk-domain module's own test suite can import it directly, the same way
this app's own tests do.
"""
from __future__ import annotations

from typing import Optional

from ai_platform.contracts import GenerationResult, GroundingPayload, RiskCandidate
from ai_platform.gateway import (
    GatewayAuthError,
    GatewayConnectionError,
    GatewayRateLimitError,
    GatewayTimeoutError,
    InvalidResponseError,
    RiskGenerationGateway,
    RiskInterpretationGateway,
)
from ai_platform.interpretation_contracts import InterpretationOutcome, InterpretationResponse


def default_valid_result(prompt_version: str = "risk_generation_v1") -> GenerationResult:
    """A minimal, valid `GenerationResult` - the default "happy path"
    fixture used by `FakeGateway(mode="valid")` when no explicit `result`
    is supplied."""
    return GenerationResult(
        candidates=[
            RiskCandidate(
                title="Weak endpoint protection on staff devices",
                asset_reference="asset:fixture-endpoint",
                threat="Malware/ransomware execution on an unmanaged endpoint",
                vulnerability="No confirmed endpoint anti-malware/EDR control",
                suggested_impact=4,
                suggested_likelihood=3,
                rationale=(
                    "The endpoint-management and endpoint-protection baseline facts "
                    "indicate a gap that a malware/ransomware threat could exploit."
                ),
                proposed_treatment="Deploy managed endpoint protection to all in-scope devices.",
                grounding_refs=["profile.endpoint_management", "baseline.endpoint_protection"],
                assumptions=[],
            ),
        ],
        clarification_questions=[],
        resolved_model="fixture-model/fake-v1",
        prompt_version=prompt_version,
        prompt_tokens=123,
        completion_tokens=45,
    )


class FakeGateway(RiskGenerationGateway):
    """Deterministic `RiskGenerationGateway` double.

    Construct with a `mode` selecting the behaviour a test needs:

    ``"valid"``
        returns ``result`` if supplied, else `default_valid_result()`.
    ``"invalid_schema"``
        raises `InvalidResponseError` (unparseable/invalid payload).
    ``"timeout"``
        raises `GatewayTimeoutError` on every call.
    ``"auth_error"``
        raises `GatewayAuthError` (not retryable).
    ``"rate_limit"``
        raises `GatewayRateLimitError` on every call.
    ``"retryable"``
        raises `GatewayConnectionError` on every call - a generic
        retryable failure distinct from timeout/rate-limit.
    ``"fail_then_succeed"``
        raises `GatewayConnectionError` on the first call only, then
        returns a valid result on the second - proves the orchestration's
        exactly-one-retry policy actually recovers.
    ``"always_fail_retryable"``
        always raises `GatewayConnectionError` - proves retry is bounded
        to exactly one (never an unbounded loop).

    `calls` records every `(grounding, prompt_version)` pair passed to
    `generate`, in order, so a test can assert on exactly what was sent -
    including proving that hostile/prompt-injection-shaped text in a
    `GroundingPayload` field is passed through completely unchanged, and
    that this fake's behaviour does not vary with the *content* of that
    text (only with its own constructor-selected `mode`). That is the
    proof PID §17 asks for: the fake needs no real NLP, it just has to
    show the adapter treats grounding text as inert data.
    """

    def __init__(self, mode: str = "valid", result: Optional[GenerationResult] = None):
        self.mode = mode
        self._result = result
        self.calls: list = []

    def generate(self, grounding: GroundingPayload, prompt_version: str) -> GenerationResult:
        self.calls.append((grounding, prompt_version))

        if self.mode == "valid":
            return self._result or default_valid_result(prompt_version)
        if self.mode == "invalid_schema":
            raise InvalidResponseError("fixture: gateway returned an unparseable/invalid payload")
        if self.mode == "timeout":
            raise GatewayTimeoutError("fixture: gateway timed out")
        if self.mode == "auth_error":
            raise GatewayAuthError("fixture: gateway rejected credentials")
        if self.mode == "rate_limit":
            raise GatewayRateLimitError("fixture: gateway rate limit exceeded")
        if self.mode == "retryable":
            raise GatewayConnectionError("fixture: retryable gateway/network failure")
        if self.mode == "fail_then_succeed":
            if len(self.calls) == 1:
                raise GatewayConnectionError("fixture: transient failure on first attempt")
            return self._result or default_valid_result(prompt_version)
        if self.mode == "always_fail_retryable":
            raise GatewayConnectionError("fixture: gateway/network failure (never recovers)")

        raise ValueError(f"FakeGateway: unknown mode {self.mode!r}")


def default_valid_interpretation_result(
    expected_indices, prompt_version: str = "risk_interpretation_v1"
) -> InterpretationResponse:
    """A minimal, valid `InterpretationResponse` covering exactly
    `expected_indices` - the default "happy path" fixture
    `FakeInterpretationGateway(mode="valid")` builds when no explicit
    `result` is supplied. Unlike generation's `default_valid_result()`
    (fixed content, any grounding), this one is index-shaped: it has to
    match whatever indices the specific request actually carried, or
    `InterpretationResponse.from_response_dict`'s own index-matching rule
    would reject a `FakeGateway`-produced "valid" fixture just as it would
    reject a real malformed model response - which would make `mode="valid"`
    a misleading name for what it actually exercises.
    """
    return InterpretationResponse(
        outcomes=[
            InterpretationOutcome(
                index=index,
                suggested_impact=3,
                suggested_likelihood=3,
                rationale=f"Fixture rationale for candidate {index}: starting assessment looks reasonable.",
                suggested_treatment=f"Fixture proposed treatment for candidate {index}.",
                clarification_questions=[],
                priority_note=None,
            )
            for index in sorted(expected_indices)
        ],
        additional_observations=[],
        resolved_model="fixture-model/fake-v1",
        prompt_version=prompt_version,
        prompt_tokens=123,
        completion_tokens=45,
    )


class FakeInterpretationGateway(RiskInterpretationGateway):
    """Deterministic `RiskInterpretationGateway` double (M002-3c dispatch),
    mirroring `FakeGateway`'s mode-based pattern exactly - see that class's
    own docstring for the shared rationale (PID §17: mechanical tests must
    never require a live external LLM).

    Modes:

    ``"valid"``
        returns ``result`` if supplied, else
        `default_valid_interpretation_result(request.expected_indices)` -
        built fresh per-call so it always matches whatever indices that
        specific call's request actually carried.
    ``"invalid_schema"``
        raises `InvalidResponseError` (unparseable/invalid payload).
    ``"index_mismatch"``
        raises `InvalidResponseError` - simulates a response that came
        back syntactically valid but with a missing/extra/duplicate index
        relative to what was sent (the exact failure mode
        `InterpretationResponse.from_response_dict`'s own validation
        exists to catch; this fixture doesn't need to replicate that
        validation logic itself to prove the orchestration layer treats it
        as a non-retryable invalid response like any other).
    ``"timeout"``
        raises `GatewayTimeoutError` on every call.
    ``"auth_error"``
        raises `GatewayAuthError` (not retryable).
    ``"rate_limit"``
        raises `GatewayRateLimitError` on every call.
    ``"retryable"``
        raises `GatewayConnectionError` on every call.
    ``"fail_then_succeed"``
        raises `GatewayConnectionError` on the first call only, then
        returns a valid result on the second - proves the orchestration's
        exactly-one-retry policy actually recovers.
    ``"always_fail_retryable"``
        always raises `GatewayConnectionError` - proves retry is bounded
        to exactly one (never an unbounded loop).

    `calls` records every `(request, prompt_version)` pair passed to
    `interpret`, in order, so a test can assert on exactly what was sent -
    including proving that hostile/prompt-injection-shaped text in a
    candidate's `notes` is passed through completely unchanged, and that
    this fake's behaviour does not vary with the *content* of that text
    (only with its own constructor-selected `mode`).
    """

    def __init__(self, mode: str = "valid", result: Optional[InterpretationResponse] = None):
        self.mode = mode
        self._result = result
        self.calls: list = []

    def interpret(self, request, prompt_version: str) -> InterpretationResponse:
        self.calls.append((request, prompt_version))

        if self.mode == "valid":
            return self._result or default_valid_interpretation_result(
                request.expected_indices, prompt_version
            )
        if self.mode in ("invalid_schema", "index_mismatch"):
            raise InvalidResponseError(
                f"fixture: gateway returned an unparseable/invalid payload ({self.mode})"
            )
        if self.mode == "timeout":
            raise GatewayTimeoutError("fixture: gateway timed out")
        if self.mode == "auth_error":
            raise GatewayAuthError("fixture: gateway rejected credentials")
        if self.mode == "rate_limit":
            raise GatewayRateLimitError("fixture: gateway rate limit exceeded")
        if self.mode == "retryable":
            raise GatewayConnectionError("fixture: retryable gateway/network failure")
        if self.mode == "fail_then_succeed":
            if len(self.calls) == 1:
                raise GatewayConnectionError("fixture: transient failure on first attempt")
            return self._result or default_valid_interpretation_result(
                request.expected_indices, prompt_version
            )
        if self.mode == "always_fail_retryable":
            raise GatewayConnectionError("fixture: gateway/network failure (never recovers)")

        raise ValueError(f"FakeInterpretationGateway: unknown mode {self.mode!r}")
