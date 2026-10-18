"""
IRENE four-tier capability matrix (M010E PID §1; docs/pids/
M010E-ENTITLEMENTS-CUSTOMER-ASSURANCE.md §1).

This module NEVER makes an authorization decision of its own and NEVER
introduces a second tier-comparison mechanism. Every row's real
authorization is, and remains, exactly whatever `entitlements.
capabilities.has_capability` already decides from the live `ProductArea.
min_package_tier` row for the `required_capability` each
`irene.tools.ToolSpec`/modal-feature route already carries - enforced
independently by `irene.tools._revalidate` (every tool, on every call) and
`entitlements.decorators.require_capability` (every modal-feature route).
What this module adds is a READ-ONLY reporting projection over those two
already-real sources (`irene.tools.TOOL_REGISTRY` and the live
`ProductArea` table) - for `docs/evidence/M010E-ASSURANCE-ENTITLEMENTS.md`'s
own capability-mapping table, and for a test to assert against - never a
hand-maintained third copy of "which tier does X need" that could silently
drift from the real gate.

`min_package_tier_code` is resolved via `entitlements.tiers.tier_code` -
the single canonical tier<->code mapping `entitlements.tiers` itself
already is ("nothing else in this codebase... should re-derive or
duplicate this mapping" - that module's own docstring). It is DISPLAY-ONLY
here, never compared against anything or used to make a decision - the
actual authorization check for every one of these rows is, and always
was, `has_capability`'s own `current_tier >= required_tier` integer
comparison. Using marketing-sounding tier names ("Foundational"/"Monthly"/
"PRO") anywhere in this module would be exactly the mistake M010E PID §1
warns against if they were hard-coded as the check itself - they are not:
this module never compares against a code string, only reports the one
`entitlements.tiers` already produces for an already-decided integer.
"""
from __future__ import annotations

import dataclasses

from entitlements.models import ProductArea
from entitlements.tiers import tier_code
from irene.tools import TOOL_REGISTRY, _tool_enabled

# Modal/view-level IRENE features that are not registered TOOL_REGISTRY
# entries but are still independently gated through `entitlements.
# decorators.require_capability` on their own URL - included so this
# matrix covers every IRENE-owned surface this campaign (Work Packages
# A-E) has built, not only its tool calls. A plain, code-reviewed dict -
# the SAME allowlist-dict discipline `irene.tools.TOOL_REGISTRY`/
# `security_tasks.source_registry.SOURCE_LOCATOR_REGISTRY`/
# `entitlements.capabilities.ROUTE_NAMESPACE_TO_CAPABILITY` already use,
# never database-configurable. name -> required_capability.
MODAL_FEATURE_CAPABILITIES: dict[str, str] = {
    "irene:workspace": "irene",
    "irene:ask": "irene",
    "irene:confirm_task": "irene",
    "irene:set_auto_open_preference": "irene",
    # M010E - the new Monthly/PRO-gated Customer Assurance status page
    # (irene.views.assurance_status) - explicitly NOT "irene" like every
    # row above: this is the one IRENE-owned route in this whole campaign
    # gated on a capability other than the base "irene"/"security"/
    # "tasks" ones every Work Package A-D surface uses.
    "irene:assurance_status": "customer_assurance",
}


@dataclasses.dataclass(frozen=True)
class CapabilityMatrixRow:
    name: str
    kind: str  # "tool" or "modal_feature"
    action_class: str  # ToolSpec.action_class for a tool; "-" for a modal_feature
    required_capability: str
    min_package_tier: "int | None"
    min_package_tier_code: "str | None"
    feature_flag_enabled: bool


def _tier_for_capability(capability_code: str):
    """Reads the REAL, live `ProductArea.min_package_tier` for
    `capability_code` - never a hand-maintained second copy. Returns
    `(None, None)` for a capability code with no active seeded row (never
    raises - this is a reporting helper, not an enforcement path; the
    enforcement path, `has_capability`, already treats a missing/inactive
    `ProductArea` as a deny on its own, independently of this module)."""
    try:
        area = ProductArea.objects.active().get(code=capability_code)
    except ProductArea.DoesNotExist:
        return None, None
    return area.min_package_tier, tier_code(area.min_package_tier)


def get_capability_matrix() -> list:
    """Returns one `CapabilityMatrixRow` per registered IRENE tool plus
    one per modal feature above, sorted by (kind, name) for a stable,
    diffable report. Read-only; queries the real `ProductArea` table
    currently in the database - the SAME table `has_capability` itself
    reads."""
    rows = []
    for spec in TOOL_REGISTRY.values():
        min_tier, min_tier_code = _tier_for_capability(spec.required_capability)
        rows.append(
            CapabilityMatrixRow(
                name=spec.name,
                kind="tool",
                action_class=spec.action_class,
                required_capability=spec.required_capability,
                min_package_tier=min_tier,
                min_package_tier_code=min_tier_code,
                feature_flag_enabled=_tool_enabled(spec),
            )
        )
    for name, capability_code in MODAL_FEATURE_CAPABILITIES.items():
        min_tier, min_tier_code = _tier_for_capability(capability_code)
        rows.append(
            CapabilityMatrixRow(
                name=name,
                kind="modal_feature",
                action_class="-",
                required_capability=capability_code,
                min_package_tier=min_tier,
                min_package_tier_code=min_tier_code,
                feature_flag_enabled=True,
            )
        )
    return sorted(rows, key=lambda row: (row.kind, row.name))


__all__ = ["CapabilityMatrixRow", "MODAL_FEATURE_CAPABILITIES", "get_capability_matrix"]
