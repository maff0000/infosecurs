"""
Structured contracts for the AI IRENE ADVISER task (M010C PID §3-§6; docs/
architecture/M010-ADVISER-TOOLS-AND-SKILLS.md §5 "Prompt, context and
response contracts").

Sibling module to `ai_platform.questionnaire_interpretation_contracts` /
`ai_platform.policy_contracts` / `ai_platform.interpretation_contracts` -
same pattern: a new, narrower request/response shape for a new task type,
reusing the generic `_require_*`/`ContractValidationError` helpers from
`ai_platform.contracts` rather than reimplementing them.

== What this module does NOT know about (layering, matches every sibling
contract module) ==
This module has no idea what a "security_tasks.SecurityTask" or a
"security_baseline control" is. It validates SHAPE and the small number of
SAFETY-CRITICAL allowlists that must never depend on product-specific
registries (`ALLOWED_PROPOSED_ACTION_TYPES` below - PID §5/§6's "no AI tools
for approve policy/accept risk/certify controls/..." - this allowlist is the
one place a forbidden action TYPE is rejected regardless of which registry
`irene.product_knowledge`/`irene.tools` happen to hold at any given moment).
Everything concept/route/tool-specific (does `concept_id` resolve to a real,
tenant-owned registry entry? does `source_links[].concept_id` correspond to
something this organisation may see?) is `irene.orchestration`'s job, AFTER
this contract has already validated the response is well-shaped - exactly
the same two-stage discipline `QuestionnaireInterpretation.from_response_dict`
already uses for `selected_keys` (shape+membership in THIS call's own
`available_keys` here; the product-specific "is this key real" lives in
`questionnaire.catalogue`, outside this module).

== Why `source_links` carries no URL at all ==
`docs/architecture/M010-ADVISER-TOOLS-AND-SKILLS.md` §2: "The model ...
never fabricates `/organisations/<other-tenant-id>/...`." The gateway
response is UNTRUSTED model output (M010 threat model §1.8). If this
contract accepted a `url` string from the model at all, a compromised or
merely confused model could emit any string - there would be no contract-
level way to prevent it leaking into rendered HTML as a real link. So the
contract only ever carries a `concept_id` (an opaque, bounded string) - never
a URL. `irene.orchestration` resolves the actual, safe URL itself, via
`irene.product_knowledge`'s registry + `security_tasks`/`foundations_journey`
services' own `get_registered_route`-style helpers, AFTER this contract has
already validated the response - and only for `concept_id` values that
resolve to something real; an unregistered/invented `concept_id` is silently
dropped from what is ultimately rendered, never followed or disclosed.

== Why `proposed_actions` carries no capacity to actually write anything ==
Every `ProposedAction` is a typed, bounded PREVIEW (`action_type` + a small
plain-string `preview` dict) - a description of what COULD be proposed, not
an instruction executed by this response's mere existence. `irene.
orchestration` never iterates `AdviserResponse.proposed_actions` and calls a
tool automatically; the UI renders the preview, and only an explicit,
separate, user-confirmed call to the real `irene.tools.propose_task`/
`confirm_task_creation` tool (going through `security_tasks.services.
create_task`, with its own independent tenant/capability recheck) can ever
cause a write. `ALLOWED_PROPOSED_ACTION_TYPES` is deliberately tiny and
read-only-in-spirit (every member names a DRAFT/PREVIEW action, M010 threat
model §5's Class D - never a Class H action) - a response naming any other
`action_type` fails this contract outright, so "the model invented an
approval/acceptance/certification action" is a `ContractValidationError`,
never something that reaches the UI layer at all.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from ai_platform.contracts import (
    ContractValidationError,
    _require_bool,
    _require_dict,
    _require_dict_list,
    _require_str,
    _require_str_allow_blank,
)

# M010 architecture doc §4/§6: "bounded prompts" - these are the Implementer-
# chosen, clearly-commented PLACEHOLDER bounds this package's own evidence
# document discloses as requiring separate numeric approval before
# IRENE_ADVISER_MODE_ENABLED is ever flipped on for real traffic (no such
# approval has been given to this campaign - PID §4/WO §2 WP-C). They are
# enforced here unconditionally (bounding is itself always safe), not only
# once "approved" - an unapproved placeholder that is too generous is a risk;
# one that is merely conservative is not.
MAX_USER_MESSAGE_LENGTH = 2000
MAX_ASSISTANT_MESSAGE_LENGTH = 4000
MAX_SOURCE_LINKS = 10
MAX_PROPOSED_ACTIONS = 3
MAX_FOLLOWUP_QUESTION_LENGTH = 500
MAX_TOOL_CALLS_PER_TURN = 1  # M010 threat model §3 "agent loops" bound.

# M010 architecture doc §5/§6, M010 threat model §5 - every member here is a
# Class D (draft/propose) action only. See module docstring.
PROPOSED_ACTION_TASK_PREVIEW = "propose_task_preview"
ALLOWED_PROPOSED_ACTION_TYPES = frozenset({PROPOSED_ACTION_TASK_PREVIEW})


@dataclasses.dataclass(frozen=True)
class TenantAdviserContext:
    """The MINIMAL, typed, server-assembled projection injected into one
    Ask-tab turn (M010-ADVISER-TOOLS-AND-SKILLS.md §5: "a compact, typed
    `TenantAdviserContext` ... minimal selected record projection ... never
    insert giant raw policy files or unfiltered conversation history").

    Every field is already-redacted/non-sensitive summary data - never a
    raw model instance, never free prose pulled from an uploaded document.
    `irene.orchestration` is the only place this is constructed; this
    dataclass itself has no DB access.
    """

    organisation_id: str
    current_question_key: Optional[str]
    checkpoint_state: str
    foundations_completion_percentage: int
    open_task_count: int

    def __post_init__(self):
        _require_str(self.organisation_id, "organisation_id")
        if self.current_question_key is not None:
            _require_str(self.current_question_key, "current_question_key")
        _require_str(self.checkpoint_state, "checkpoint_state")
        _require_int_range_inclusive(self.foundations_completion_percentage, "foundations_completion_percentage")
        if not isinstance(self.open_task_count, int) or self.open_task_count < 0:
            raise ContractValidationError("'open_task_count' must be a non-negative int")


def _require_int_range_inclusive(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 100):
        raise ContractValidationError(f"'{field}' must be an int between 0 and 100")
    return value


@dataclasses.dataclass(frozen=True)
class AdviserToolDescription:
    """A SAFE, short description of one already-registered, already-
    permitted tool (name + one-line description only - never the full
    schema/table list, M010-ADVISER-TOOLS-AND-SKILLS.md §2's "Model
    receives short safe descriptions of registered tools, not the full
    schema"). `irene.tools` builds this list from the real tool registry;
    this dataclass has no registry access of its own."""

    name: str
    description: str

    def __post_init__(self):
        _require_str(self.name, "name")
        _require_str(self.description, "description")


@dataclasses.dataclass(frozen=True)
class AdviserRequest:
    """What goes INTO one Ask-tab adviser call.

    `user_message` is untrusted external content (the customer's own typed
    text) - carried as a plain, length-bounded string, sent as inert JSON
    data in the prompt's user message, never concatenated into the system
    prompt (see `ai_platform.prompts.adviser_v1`) and NEVER treated as an
    instruction by this contract or by `irene.orchestration` (M010 threat
    model §1.6/§6).

    `intent_code` is a controlled, server/router-selected value - this
    contract only checks it is a short non-blank string; the actual
    allowlist of controlled intents a given skill may accept is `irene.
    skill_router`'s job (mirrors `QuestionnaireInterpretationRequest.
    available_keys`'s own "shape here, real allowlist in the product-
    specific caller" split).
    """

    organisation_id: str
    conversation_id: str
    intent_code: str
    user_message: str
    tenant_context: TenantAdviserContext
    available_tools: list  # list[AdviserToolDescription]
    skill_name: str
    skill_version: str
    skill_system_prompt: str

    def __post_init__(self):
        _require_str(self.organisation_id, "organisation_id")
        _require_str(self.conversation_id, "conversation_id")
        _require_str(self.intent_code, "intent_code")
        _require_str(self.user_message, "user_message")
        if len(self.user_message) > MAX_USER_MESSAGE_LENGTH:
            raise ContractValidationError(
                f"'user_message' exceeds the bounded maximum of {MAX_USER_MESSAGE_LENGTH} characters"
            )
        if not isinstance(self.tenant_context, TenantAdviserContext):
            raise ContractValidationError("'tenant_context' must be a TenantAdviserContext")
        if not isinstance(self.available_tools, list) or not all(
            isinstance(t, AdviserToolDescription) for t in self.available_tools
        ):
            raise ContractValidationError("'available_tools' must be a list of AdviserToolDescription")
        _require_str(self.skill_name, "skill_name")
        _require_str(self.skill_version, "skill_version")
        _require_str_allow_blank(self.skill_system_prompt, "skill_system_prompt")


@dataclasses.dataclass(frozen=True)
class SourceLink:
    """A reference to one registered Product Knowledge Map concept - see
    module docstring for why this carries no URL at all."""

    concept_id: str

    def __post_init__(self):
        _require_str(self.concept_id, "concept_id")


@dataclasses.dataclass(frozen=True)
class ProposedAction:
    """A typed, bounded DRAFT preview - see module docstring for why this
    can never itself cause a write."""

    action_type: str
    preview: dict  # bounded dict of plain strings only

    def __post_init__(self):
        if self.action_type not in ALLOWED_PROPOSED_ACTION_TYPES:
            raise ContractValidationError(
                f"'action_type' must be one of {sorted(ALLOWED_PROPOSED_ACTION_TYPES)!r}, "
                f"got {self.action_type!r}"
            )
        preview = _require_dict(self.preview, "preview")
        if len(preview) > 8:
            raise ContractValidationError("'preview' must not carry more than 8 fields")
        for key, value in preview.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ContractValidationError("'preview' must be a flat dict of str -> str")
            if len(value) > 255:
                raise ContractValidationError(f"'preview[{key!r}]' exceeds 255 characters")


@dataclasses.dataclass(frozen=True)
class AdviserResponse:
    """What comes OUT of one Ask-tab adviser call (M010-ADVISER-TOOLS-AND-
    SKILLS.md §5's exact field list): `message`, `intent_code`,
    `source_links[]`, `proposed_actions[]`, `followup_question` (optional),
    `uncertainty_flag`, `model_trace_id` (server generated - never taken
    from the gateway payload, see `from_response_dict`), `skill_version`.

    `message` is rendered by the template as plain escaped text (Django
    auto-escaping, no `mark_safe`, no raw HTML/Markdown interpretation) -
    see M010-ADVISER-TOOLS-AND-SKILLS.md §5 "Render generated prose as
    escaped text".
    """

    message: str
    intent_code: str
    source_links: list  # list[SourceLink]
    proposed_actions: list  # list[ProposedAction]
    followup_question: Optional[str]
    uncertainty_flag: bool
    model_trace_id: str
    skill_version: str
    resolved_model: Optional[str] = None
    prompt_version: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def __post_init__(self):
        _require_str(self.message, "message")
        if len(self.message) > MAX_ASSISTANT_MESSAGE_LENGTH:
            raise ContractValidationError(
                f"'message' exceeds the bounded maximum of {MAX_ASSISTANT_MESSAGE_LENGTH} characters"
            )
        _require_str(self.intent_code, "intent_code")
        if not isinstance(self.source_links, list) or not all(
            isinstance(s, SourceLink) for s in self.source_links
        ):
            raise ContractValidationError("'source_links' must be a list of SourceLink")
        if len(self.source_links) > MAX_SOURCE_LINKS:
            raise ContractValidationError(f"'source_links' exceeds the bounded maximum of {MAX_SOURCE_LINKS}")
        if not isinstance(self.proposed_actions, list) or not all(
            isinstance(a, ProposedAction) for a in self.proposed_actions
        ):
            raise ContractValidationError("'proposed_actions' must be a list of ProposedAction")
        if len(self.proposed_actions) > MAX_PROPOSED_ACTIONS:
            raise ContractValidationError(
                f"'proposed_actions' exceeds the bounded maximum of {MAX_PROPOSED_ACTIONS}"
            )
        if self.followup_question is not None:
            _require_str(self.followup_question, "followup_question")
            if len(self.followup_question) > MAX_FOLLOWUP_QUESTION_LENGTH:
                raise ContractValidationError(
                    f"'followup_question' exceeds the bounded maximum of {MAX_FOLLOWUP_QUESTION_LENGTH}"
                )
        _require_bool(self.uncertainty_flag, "uncertainty_flag")
        _require_str(self.model_trace_id, "model_trace_id")
        _require_str(self.skill_version, "skill_version")

    @classmethod
    def from_response_dict(
        cls,
        data: Any,
        *,
        model_trace_id: str,
        skill_version: str,
        resolved_model: Optional[str],
        prompt_version: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> "AdviserResponse":
        """Parse+validate a raw gateway JSON payload. `model_trace_id` and
        `skill_version` are ALWAYS server-supplied arguments, never read off
        `data` - the gateway/model has no authority to assert its own trace
        id or which skill version actually ran (M010-ADVISER-TOOLS-AND-
        SKILLS.md §5: "`model_trace_id` (server generated)")."""
        payload = _require_dict(data, "adviser response")

        try:
            message = payload["message"]
        except KeyError as exc:
            raise ContractValidationError("adviser response missing required field: 'message'") from exc

        intent_code = payload.get("intent_code", "") or ""
        raw_source_links = payload.get("source_links", []) or []
        raw_source_links = _require_dict_list(raw_source_links, "source_links")
        source_links = [SourceLink(concept_id=_require_str(e.get("concept_id", ""), "concept_id")) for e in raw_source_links]

        raw_actions = payload.get("proposed_actions", []) or []
        raw_actions = _require_dict_list(raw_actions, "proposed_actions")
        proposed_actions = [
            ProposedAction(action_type=e.get("action_type", ""), preview=e.get("preview", {}) or {})
            for e in raw_actions
        ]

        followup_question = payload.get("followup_question") or None
        uncertainty_flag = bool(payload.get("uncertainty_flag", False))

        return cls(
            message=message,
            intent_code=intent_code,
            source_links=source_links,
            proposed_actions=proposed_actions,
            followup_question=followup_question,
            uncertainty_flag=uncertainty_flag,
            model_trace_id=model_trace_id,
            skill_version=skill_version,
            resolved_model=resolved_model,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


SAFE_FALLBACK_MESSAGE = (
    "You can continue the questionnaire; free-form explanations are temporarily unavailable."
)


def safe_fallback_response(*, intent_code: str, model_trace_id: str, skill_version: str = "none") -> AdviserResponse:
    """The documented, exact-copy safe fallback (M010-UX-CUSTOMER-JOURNEYS.md
    §6) - used both when `IRENE_ADVISER_MODE_ENABLED` is off (the shipped
    default) and when a live/fake gateway call fails. Never fabricates a
    success, never attaches a source link or proposed action - just the
    one approved sentence."""
    return AdviserResponse(
        message=SAFE_FALLBACK_MESSAGE,
        intent_code=intent_code,
        source_links=[],
        proposed_actions=[],
        followup_question=None,
        uncertainty_flag=True,
        model_trace_id=model_trace_id,
        skill_version=skill_version,
    )
