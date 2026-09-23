"""
Registry of known prompt/policy versions (M002 PID §9.4).

`ai_platform.gateway.LiteLLMGateway.generate()` must render whatever
`prompt_version` string its caller asks for - not just one hardcoded
version - since callers (`risk_register.services`, `risk_register.eval.
harness`) each pick a specific version to run. This module is the single
place that maps a `prompt_version` string to the versioned module that
knows how to render it, so the gateway never has to hardcode a version.

Kept as a plain dict, not a generic plugin/entry-point system: PID §25
reproducibility doctrine says a handful of known versions does not justify
more machinery than this. Adding a new version: create `risk_generation_vN.py`
(see `risk_generation_v1.py`'s docstring for why versions are never mutated
in place), then add its `PROMPT_VERSION -> module` entry to
`_PROMPT_MODULES_BY_VERSION` below.
"""
from __future__ import annotations

from typing import Callable, Optional

from ai_platform.prompts import (
    policy_generation_v1,
    risk_generation_v1,
    risk_generation_v2,
    risk_generation_v3,
    risk_interpretation_v1,
)

_PROMPT_MODULES_BY_VERSION = {
    risk_generation_v1.PROMPT_VERSION: risk_generation_v1,
    risk_generation_v2.PROMPT_VERSION: risk_generation_v2,
    risk_generation_v3.PROMPT_VERSION: risk_generation_v3,
}

# Exposed for error messages / diagnostics - never mutated at runtime.
KNOWN_PROMPT_VERSIONS = tuple(_PROMPT_MODULES_BY_VERSION)


def build_messages_for_version(prompt_version: str) -> Optional[Callable]:
    """Return the `build_messages(grounding)` callable that renders
    `prompt_version`, or `None` if `prompt_version` is not one this build
    knows how to render. Generation task only - see
    `build_interpretation_messages_for_version` for the interpretation
    task's own registry. Kept as two separate dicts/functions rather than
    one merged registry: the two tasks' `build_messages` callables take
    different argument types (`GroundingPayload` vs `InterpretationRequest`)
    and a single shared registry would erase that distinction at the type
    level, inviting a version string from one task to be resolved against
    the other task's renderer by mistake."""
    module = _PROMPT_MODULES_BY_VERSION.get(prompt_version)
    return module.build_messages if module is not None else None


# --- Interpretation task (M002-3c dispatch) - separate registry, see the
# docstring above for why this is not merged into the generation dict. ----
_INTERPRETATION_PROMPT_MODULES_BY_VERSION = {
    risk_interpretation_v1.PROMPT_VERSION: risk_interpretation_v1,
}

KNOWN_INTERPRETATION_PROMPT_VERSIONS = tuple(_INTERPRETATION_PROMPT_MODULES_BY_VERSION)


def build_interpretation_messages_for_version(prompt_version: str) -> Optional[Callable]:
    """Return the `build_messages(request)` callable that renders
    `prompt_version` for the interpretation task, or `None` if
    `prompt_version` is not one this build knows how to render."""
    module = _INTERPRETATION_PROMPT_MODULES_BY_VERSION.get(prompt_version)
    return module.build_messages if module is not None else None


# --- Policy-generation task (M004 m004-2a-policy-foundation dispatch) -
# separate registry, same reasoning as the interpretation registry above:
# this task's `build_messages` callable takes a `PolicyGroundingPayload`,
# a different argument type from either other task's. -----------------------
_POLICY_PROMPT_MODULES_BY_VERSION = {
    policy_generation_v1.PROMPT_VERSION: policy_generation_v1,
}

KNOWN_POLICY_PROMPT_VERSIONS = tuple(_POLICY_PROMPT_MODULES_BY_VERSION)


def build_policy_messages_for_version(prompt_version: str) -> Optional[Callable]:
    """Return the `build_messages(grounding)` callable that renders
    `prompt_version` for the policy-generation task, or `None` if
    `prompt_version` is not one this build knows how to render."""
    module = _POLICY_PROMPT_MODULES_BY_VERSION.get(prompt_version)
    return module.build_messages if module is not None else None
