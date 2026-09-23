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

from ai_platform.prompts import risk_generation_v1, risk_generation_v2, risk_generation_v3

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
    knows how to render."""
    module = _PROMPT_MODULES_BY_VERSION.get(prompt_version)
    return module.build_messages if module is not None else None
