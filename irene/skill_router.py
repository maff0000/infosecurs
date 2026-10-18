"""
Controlled-intent skill router (M010C PID §3; docs/architecture/
M010-ADVISER-TOOLS-AND-SKILLS.md §4: "The skill router selects a small
relevant skill ... No arbitrary user-authored Markdown can become a
skill").

`select_skill` dispatches on a CONTROLLED `intent_code` (`irene.models.
IntentCode`) - never free-text matching against the customer's own typed
message. The customer's own words never choose which skill loads; `irene.
orchestration` is responsible for mapping whatever the UI/intent-selection
step determined into one of the fixed `IntentCode` values BEFORE calling
this router - this module has no access to, and does not need, the raw
message text at all.
"""
from __future__ import annotations

from typing import Optional

from irene.models import IntentCode
from irene.skill_loader import InvalidSkillManifestError, LoadedSkill, load_skill

_SKILL_BY_INTENT: dict[str, str] = {
    IntentCode.EXPLAIN_CONTROL: "foundations-guide",
    IntentCode.CLARIFY_OPTION: "foundations-guide",
    IntentCode.SUGGEST_FOLLOWUP: "foundations-guide",
    IntentCode.TASK_STATUS_HELP: "task-administration",
    IntentCode.TASK_NEXT_STEP_HELP: "task-administration",
    # IntentCode.UNCLEAR deliberately has no entry - see select_skill below.
}


def select_skill(intent_code: str) -> Optional[LoadedSkill]:
    """Returns the `LoadedSkill` registered for `intent_code`, or `None`
    for `IntentCode.UNCLEAR`, an unrecognised intent_code, or a skill that
    fails validation when loaded (fail-closed - never return a skill this
    package cannot prove is safe to use, even if the mapping above names
    one). `irene.orchestration` treats `None` as "use the safe fallback",
    exactly the same path taken when `IRENE_ADVISER_MODE_ENABLED` is off."""
    skill_name = _SKILL_BY_INTENT.get(intent_code)
    if skill_name is None:
        return None
    try:
        return load_skill(skill_name)
    except InvalidSkillManifestError:
        return None


__all__ = ["select_skill"]
