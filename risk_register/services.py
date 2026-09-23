"""
Generation service: the seam between the Risk-domain view layer and the
deterministic scenario-instantiation engine
(`risk_register.scenario_engine`) that replaced the retired AI-open-
generation path (PID §0.6/§0.7, M002-3b dispatch).

`generate_draft_risks` is the single entrypoint the view calls. It performs
NO AI CALL - it never imports or touches `ai_platform` - and is a thin,
tenant-scoped wrapper around
`scenario_engine.instantiate_risks_for_organisation`. It is kept as its
own function (rather than inlining the engine call directly into the view)
so the pre-existing view/service boundary is preserved, and so a later,
separate Phase 3c AI-interpretation dispatch has an obvious, narrow seam to
extend without touching `risk_register.views` again.

Regeneration safety (PID §15): every `Risk` row this function can possibly
create is a plain `.objects.create(...)` inside
`instantiate_risks_for_organisation`, gated by that function's own
`(organisation, scenario_id, key_asset)` dedup check (PID §0's "must be
exact" requirement - see `scenario_engine`'s module docstring). This
function itself never queries for, updates, or deletes an existing `Risk`
row. Calling it again after risks already exist therefore cannot overwrite
or mutate a confirmed (or dismissed) risk, by construction - not merely by
convention.
"""
from __future__ import annotations

from risk_register.models import Risk
from risk_register.scenario_engine import instantiate_risks_for_organisation


def generate_draft_risks(organisation) -> list[Risk]:
    """Deterministically instantiate `organisation`'s candidate risks from
    its confirmed key assets, canonical baseline answers and the
    methodology catalogue (`risk_register.methodology.CATALOGUE`), and
    persist each new candidate as a draft `Risk` row.

    Returns the list of newly-created `Risk` rows (may be empty - e.g. no
    confirmed assets yet, or every applicable candidate already exists).
    Never touches an existing `Risk` row - see `scenario_engine`'s dedup
    rule.
    """
    return instantiate_risks_for_organisation(organisation)


__all__ = ["generate_draft_risks"]
