"""
Which `security_baseline` control keys are relevant to a given `KeyAsset`
category (PID.md M002 §0.5's asset-specific protection/exposure
assessment).

Deliberately a pure function of `risk_register.methodology.CATALOGUE` - the
versioned common-security methodology catalogue - rather than a hand-
maintained second mapping (PID §0.5: "derive it from here ... don't hand-
maintain a second, potentially-drifting mapping"). Every methodology
scenario already declares its own `asset_category` and `control_keys`
(risk_register/methodology.py); this module only reads that catalogue and
groups it. It makes no database query and holds no tenant state.
"""
from __future__ import annotations

from typing import List

from risk_register.methodology import CATALOGUE as _METHODOLOGY_CATALOGUE


def relevant_control_keys_for_category(category: str) -> List[str]:
    """
    The `security_baseline` control keys relevant to `category`: the union
    of `control_keys` across every methodology scenario whose
    `asset_category` equals `category`.

    Order is deterministic and stable (first-seen, catalogue declaration
    order) rather than alphabetical, so a caller rendering these in order
    sees controls grouped the way the methodology itself groups them.
    Returns an empty list for a category no scenario currently targets
    (e.g. `other`) - that is a legitimate, expected result, not an error.
    """
    keys: List[str] = []
    seen = set()
    for scenario in _METHODOLOGY_CATALOGUE:
        if scenario.asset_category != category:
            continue
        for key in scenario.control_keys:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys
