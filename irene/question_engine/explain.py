"""
Generic, on-demand explanation interface (WO-IRENE-001 §2.2's "on-demand
explanation interface... extend irene/skill_router.py's existing
_SKILL_BY_INTENT wiring generically (keyed by intent code, not by
section)").

`irene.skill_router._SKILL_BY_INTENT` is ALREADY keyed purely by
`irene.models.IntentCode`, never by section (see that module's own
docstring: "The customer's own words never choose which skill loads").
This Increment reuses that existing mechanism exactly as-is - the Work
Order's own first-named option, "reusing EXPLAIN_CONTROL" - rather than
adding a second, parallel dispatch path or a new `IntentCode` member no
real skill yet answers. What IS new here is the generic, section-agnostic
ENTRY POINT a registered question's own declared `explain_intent_code`
goes through, proving dispatch depends solely on the intent code a
question declares, never on which section it belongs to -
`irene/tests/test_question_engine_presenter.py`'s
`TestExplanationInterfaceDispatchesByIntentCodeOnlyNeverBySection` proves
this directly: two different synthetic questions, from two different
synthetic sections, sharing the same `explain_intent_code`, resolve to
the identical skill.

Deliberately does NOT call `ai_platform.gateway.LiteLLMGateway.
ask_adviser` or build an `AdviserRequest` here - wiring the real,
minimised typed question context into an actual gateway call (Work Order
§1a R1) is a Stage 3 adapter concern for a future increment. This
module's job is bounded to "which skill would answer this question's
explanation", nothing more.
"""
from __future__ import annotations

from typing import Optional

from irene.question_engine.contract import QuestionDefinitionProtocol
from irene.skill_loader import LoadedSkill
from irene.skill_router import select_skill


def resolve_explanation_skill(question: QuestionDefinitionProtocol) -> Optional[LoadedSkill]:
    """Returns the `LoadedSkill` that would answer an on-demand
    explanation request for `question`, resolved EXCLUSIVELY from its
    own `explain_intent_code` - exactly the same `irene.skill_router.
    select_skill` call `irene.orchestration.ask_irene`'s own skill
    selection step already goes through for every other intent-code-
    driven request. Returns `None` under the exact same conditions
    `select_skill` already does (an unclear/unrecognised intent code, or
    a skill that fails its own manifest validation) - fail-closed, never
    a guessed fallback."""
    return select_skill(question.explain_intent_code)


__all__ = ["resolve_explanation_skill"]
