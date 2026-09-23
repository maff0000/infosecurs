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
)


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
