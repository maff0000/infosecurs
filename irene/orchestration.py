"""
Ask-tab orchestration (M010C PID §4/§6; docs/architecture/
M010-ADVISER-TOOLS-AND-SKILLS.md §1/§5/§6).

`ask_irene` is the ONE function `irene.views`'s Ask-tab POST endpoint
calls. It is deliberately NOT an agentic tool-calling loop: tenant context
is pre-fetched, server-side, through the SAME bounded, capability-
rechecked READ tools `irene.tools` already exposes (a small, fixed,
enumerable set of calls - never model-selected, never more than one call
per registered context field) BEFORE the one gateway call is made. This
means `MAX_TOOL_CALLS_PER_TURN` (`ai_platform.adviser_contracts`) is
satisfied TRIVIALLY, by construction - there is no loop for a flood/
repeated-instruction adversarial prompt to exploit, because nothing in
`user_message`'s content can cause an extra tool call to happen at all
(see `irene/tests/test_adversarial.py`'s tool-call-flood case, which
asserts exactly this). `propose_task`/`confirm_task_creation` (the only
WRITE-capable tools) are never invoked from this function at all - only
from `irene.views`'s own separate, explicit, user-confirmed endpoints.

Two execution modes (M010-ADVISER-TOOLS-AND-SKILLS.md §1):

  - `settings.IRENE_ADVISER_MODE_ENABLED` is `False` (the SHIPPED
    DEFAULT): `ask_irene` returns the exact documented safe-fallback
    message immediately. No gateway is constructed. No network call is
    attempted, fake or real.
  - `True` (never enabled by this package itself - see docs/evidence/
    M010C-IRENE-WORKSPACE-TOOLS.md for the explicit disclosure that no
    numeric-budget/vendor-security approval exists for this campaign):
    selects a skill via the controlled intent router, builds a minimal
    `TenantAdviserContext`, and calls exactly one `AdviserGateway.
    ask_adviser` - via the real `ai_platform.gateway.LiteLLMGateway` if no
    `gateway` is explicitly passed, or the caller's own injected gateway
    (every test in this package injects `ai_platform.testing.
    FakeAdviserGateway` - this function never constructs a real gateway
    inside a test, because a test never leaves `gateway` unset while also
    setting the flag True without passing one explicitly).
"""
from __future__ import annotations

import logging
import uuid as _uuid

from django.conf import settings
from django.utils import timezone

from ai_platform.adviser_contracts import (
    AdviserRequest,
    AdviserResponse,
    AdviserToolDescription,
    TenantAdviserContext,
    safe_fallback_response,
)
from ai_platform.gateway import GatewayError
from irene import services as conversation_services
from irene import tools as irene_tools
from irene.models import IntentCode, MessageClassification, MessageRole
from irene.skill_router import select_skill

logger = logging.getLogger("irene.orchestration")

# M010 architecture doc §6 - PLACEHOLDER, conservative, clearly-disclosed
# numeric bounds (see docs/evidence/M010C-IRENE-WORKSPACE-TOOLS.md for the
# explicit "requires separate approval" disclosure). Enforced unconditionally
# whenever Adviser Mode is on - never only once "approved".
PER_USER_HOURLY_CALL_LIMIT = 20
PER_ORG_DAILY_CALL_LIMIT = 200


def _within_rate_limits(organisation, user) -> bool:
    from irene.models import AssistantConversation, AssistantMessage

    now = timezone.now()
    hourly_count = AssistantMessage.objects.filter(
        conversation__organisation=organisation,
        conversation__owner=user,
        role=MessageRole.ASSISTANT,
        classification=MessageClassification.NORMAL,
        created_at__gte=now - timezone.timedelta(hours=1),
    ).count()
    if hourly_count >= PER_USER_HOURLY_CALL_LIMIT:
        return False

    daily_count = AssistantMessage.objects.filter(
        conversation__organisation=organisation,
        role=MessageRole.ASSISTANT,
        classification=MessageClassification.NORMAL,
        created_at__gte=now - timezone.timedelta(days=1),
    ).count()
    if daily_count >= PER_ORG_DAILY_CALL_LIMIT:
        return False
    return True


def _build_tenant_context(context: "irene_tools.AuthorizedContext") -> TenantAdviserContext:
    """Pre-fetches the minimal projection - exactly two bounded, already-
    capability-rechecked read-tool calls, never more. Degrades gracefully
    (default values) if a sub-area is genuinely unavailable at this
    tenant's tier, rather than failing the whole Ask turn for a capability
    narrower than the `irene` capability the view itself already required."""
    from django.core.exceptions import PermissionDenied

    current_question_key = None
    checkpoint_state = "new"
    completion_percentage = 0
    try:
        summary = irene_tools.get_foundations_summary(context)
        current_question_key = summary["current_question_key"]
        checkpoint_state = summary["checkpoint_state"]
        completion_percentage = summary["completion_percentage"]
    except PermissionDenied:
        logger.info("irene.orchestration: foundations summary unavailable at this tier - degrading gracefully")

    open_task_count = 0
    try:
        open_task_count = len(irene_tools.get_security_tasks(context))
    except PermissionDenied:
        logger.info("irene.orchestration: tasks unavailable at this tier - degrading gracefully")

    return TenantAdviserContext(
        organisation_id=context.organisation_id,
        current_question_key=current_question_key,
        checkpoint_state=checkpoint_state,
        foundations_completion_percentage=completion_percentage,
        open_task_count=open_task_count,
    )


def ask_irene(
    context: "irene_tools.AuthorizedContext",
    organisation,
    user,
    *,
    conversation_id,
    intent_code: str,
    user_message: str,
    gateway=None,
) -> AdviserResponse:
    """The ONE Ask-tab orchestration entrypoint. Always appends the
    user's message first (even when the flag is off - continuity of the
    conversation record is a deterministic, zero-AI write); the
    assistant's reply (safe fallback or real) is appended second, tagged
    with its `classification`."""
    conversation_services.append_message(
        organisation, user, conversation_id, role=MessageRole.USER, content=user_message
    )

    if intent_code not in IntentCode.values:
        intent_code = IntentCode.UNCLEAR

    if not getattr(settings, "IRENE_ADVISER_MODE_ENABLED", False):
        response = safe_fallback_response(intent_code=intent_code, model_trace_id=str(_uuid.uuid4()))
        _persist_assistant_response(organisation, user, conversation_id, response, MessageClassification.SAFE_FALLBACK)
        return response

    if not _within_rate_limits(organisation, user):
        response = safe_fallback_response(intent_code=intent_code, model_trace_id=str(_uuid.uuid4()))
        _persist_assistant_response(organisation, user, conversation_id, response, MessageClassification.SAFE_FALLBACK)
        return response

    skill = select_skill(intent_code)
    if skill is None:
        response = safe_fallback_response(intent_code=intent_code, model_trace_id=str(_uuid.uuid4()))
        _persist_assistant_response(organisation, user, conversation_id, response, MessageClassification.SAFE_FALLBACK)
        return response

    tenant_context = _build_tenant_context(context)
    available_tools = [
        AdviserToolDescription(name=t["name"], description=t["description"])
        for t in irene_tools.get_available_tool_descriptions()
        if t["name"] in skill.tools
    ]

    request = AdviserRequest(
        organisation_id=context.organisation_id,
        conversation_id=str(conversation_id),
        intent_code=intent_code,
        user_message=user_message,
        tenant_context=tenant_context,
        available_tools=available_tools,
        skill_name=skill.name,
        skill_version=skill.version,
        skill_system_prompt=skill.system_prompt,
    )

    if gateway is None:
        from ai_platform.gateway import LiteLLMGateway

        gateway = LiteLLMGateway()

    try:
        response = gateway.ask_adviser(request, prompt_version="adviser_v1")
    except GatewayError as exc:
        logger.info("irene.orchestration: adviser gateway call failed (%s) - safe fallback", type(exc).__name__)
        response = safe_fallback_response(intent_code=intent_code, model_trace_id=str(_uuid.uuid4()))
        _persist_assistant_response(organisation, user, conversation_id, response, MessageClassification.SAFE_FALLBACK)
        return response

    response = _filter_response_against_registry(response)
    _persist_assistant_response(organisation, user, conversation_id, response, MessageClassification.NORMAL)
    return response


def _filter_response_against_registry(response: AdviserResponse) -> AdviserResponse:
    """M010 threat model §1.5/§1.8: the provider response has zero grant
    authority. Drops any `source_links` entry whose `concept_id` is not a
    real, AVAILABLE Product Knowledge Map entry, and drops EVERY
    `proposed_actions` entry outright if `IRENE_TASK_TOOLS_ENABLED` is
    off - defence in depth on top of the contract's own `action_type`
    allowlist."""
    import dataclasses

    from irene.product_knowledge import get_concept

    filtered_links = [link for link in response.source_links if get_concept(link.concept_id) is not None]
    proposed_actions = response.proposed_actions
    if not getattr(settings, "IRENE_TASK_TOOLS_ENABLED", False):
        proposed_actions = []

    return dataclasses.replace(response, source_links=filtered_links, proposed_actions=proposed_actions)


def _persist_assistant_response(organisation, user, conversation_id, response: AdviserResponse, classification: str):
    conversation_services.append_message(
        organisation,
        user,
        conversation_id,
        role=MessageRole.ASSISTANT,
        content=response.message,
        classification=classification,
        source_concept_ids=[link.concept_id for link in response.source_links],
        provider_call_trace_id=response.model_trace_id,
    )


def materialize_proposed_actions(context: "irene_tools.AuthorizedContext", response: AdviserResponse) -> list:
    """Turns each contract-valid `propose_task_preview` the model
    returned into a REAL `AssistantAction` row (via `irene.tools.
    propose_task` - the exact same allowlist/length-bounding checks a
    directly-called `propose_task` tool invocation would apply), so the
    UI has a genuine `action_id` to bind its "Confirm" button to - never
    rendering the model's own unvalidated preview text as if it were
    already a safe, server-checked proposal. Returns `[]` outright if
    `IRENE_TASK_TOOLS_ENABLED` is off, or if `response.proposed_actions`
    was already empty (e.g. `_filter_response_against_registry` already
    cleared it for that same reason)."""
    from ai_platform.adviser_contracts import PROPOSED_ACTION_TASK_PREVIEW
    from security_tasks.models import TaskKind

    if not getattr(settings, "IRENE_TASK_TOOLS_ENABLED", False):
        return []

    materialized = []
    for action in response.proposed_actions:
        if action.action_type != PROPOSED_ACTION_TASK_PREVIEW:
            continue
        title = (action.preview.get("title") or "").strip() or "Untitled task"
        summary = action.preview.get("summary") or ""
        try:
            preview = irene_tools.propose_task(context, kind=TaskKind.MANUAL_OTHER, title=title, summary=summary)
        except ValueError:
            continue
        materialized.append(preview)
    return materialized


__all__ = ["ask_irene", "materialize_proposed_actions"]
