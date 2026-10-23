"""
Additive Stage 3 "Explain this" orchestration entry point (WO-IRENE-001
Increment 2 browser-wiring; Central Architecture requirement 4: "send the
approved, minimised, typed question context through a versioned adviser
request/prompt and existing gateway").

This module is a NEW, SEPARATE orchestration path - deliberately built
to share ZERO code path with `irene.orchestration.ask_irene`'s own body
(Central Architecture requirement 5: the existing Ask-tab flow must
remain completely unchanged). Nothing here calls `ask_irene`, imports any
of its underscore-prefixed private helpers, or reads/writes
`irene.models.AssistantConversation`/`AssistantMessage` - a Stage 3
"Explain this" request is not an Ask-tab conversation turn, so there is
no conversation history for it to append to or read from.

It mirrors `ask_irene`'s exact disabled/rate-limit/failure -> fallback
SHAPE (same public constants/contracts/gateway/fallback helper, reused
AS-IS, never reinvented or modified - see the imports below), with its
own, independent, bounded Stage 3 rate-limit check reusing the SAME
public `AssistantMessage` table `ask_irene` writes to (a real, shared
LLM-call budget pool is more correct than inventing a second, parallel
one), but via its own independent query rather than importing any
private `irene.orchestration` function.

`ask_irene_stage3_explain`'s `user_message` is built purely from the
typed, minimised `irene.question_engine.adapters.stage3_technology_data.
Stage3QuestionExplanationContext` - never arbitrary customer-typed free
text (Stage 3's own "Explain this" control carries no free-text box at
all).

Called only by `irene.views`'s new, additive Stage 3 explain view - never
by anything in the existing Ask-tab path.
"""
from __future__ import annotations

import dataclasses
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
from irene.question_engine.adapters.stage3_technology_data import Stage3ExplanationDispatch

# Same PLACEHOLDER, conservative bounds `irene.orchestration` itself
# documents (that module's own `PER_USER_HOURLY_CALL_LIMIT`/
# `PER_ORG_DAILY_CALL_LIMIT` disclosure applies equally here - no numeric-
# budget/vendor-security approval exists for this campaign either).
# Deliberately duplicated as plain ints, rather than imported from
# `irene.orchestration`, so this module's own rate-limit query below is
# fully self-contained and provably shares no code path with that
# module's `ask_irene` body.
PER_USER_HOURLY_CALL_LIMIT = 20
PER_ORG_DAILY_CALL_LIMIT = 200


def _within_rate_limits(organisation, user) -> bool:
    """Reads the SAME `AssistantMessage` table `irene.orchestration.
    ask_irene` writes to (a real, shared LLM-call budget pool for the
    whole IRENE surface, Ask-tab included) via its own independent
    query - never calls into `ask_irene`/`irene.orchestration` at all.
    Stage 3 "Explain this" calls do not themselves write a row here (see
    module docstring), so this is a shared CEILING inherited from
    whatever Ask-tab usage has already happened this hour/day, not a
    Stage-3-specific counter of its own - an explicitly bounded, no-new-
    migration judgement call (see FORGE report)."""
    from irene.models import AssistantMessage, MessageClassification, MessageRole

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


def _build_user_message(context) -> str:
    """Builds the bounded, server-authored prompt content purely from the
    typed `Stage3QuestionExplanationContext` fields - no raw
    `OrganisationProfile` row, no free text of any kind (WO §1a R1: "never
    more than the specific question being explained needs")."""
    lines = [f"Question: {context.question_title}"]
    if context.field_code:
        lines.append(f"Sub-field: {context.field_code}")
    if context.permitted_answer_labels:
        lines.append("Permitted answers: " + ", ".join(context.permitted_answer_labels))
    lines.append(f"Current answer: {context.current_answer_label or 'Not confirmed'}")
    return "\n".join(lines)


def _foundations_completion_percentage(organisation) -> int:
    from entitlements.metrics import get_security_foundations_completion

    return get_security_foundations_completion(organisation).percentage


def _filter_response_against_registry(response: AdviserResponse) -> AdviserResponse:
    """Same defence-in-depth `irene.orchestration._filter_response_against_registry`
    applies - deliberately a separate, small, self-contained copy (never
    an import of that underscore-prefixed private helper) so this module
    shares no code path with `ask_irene`'s body. Drops any `source_links`
    entry whose `concept_id` is not a real, AVAILABLE Product Knowledge
    Map entry, and drops EVERY `proposed_actions` entry outright if
    `IRENE_TASK_TOOLS_ENABLED` is off."""
    from irene.product_knowledge import get_concept

    filtered_links = [link for link in response.source_links if get_concept(link.concept_id) is not None]
    proposed_actions = response.proposed_actions
    if not getattr(settings, "IRENE_TASK_TOOLS_ENABLED", False):
        proposed_actions = []
    return dataclasses.replace(response, source_links=filtered_links, proposed_actions=proposed_actions)


def ask_irene_stage3_explain(
    *,
    organisation,
    user,
    dispatch: Stage3ExplanationDispatch,
    gateway=None,
) -> AdviserResponse:
    """The ONE Stage 3 "Explain this" orchestration entrypoint (questions
    3.1-3.6 only - `dispatch` is built by `irene.question_engine.adapters.
    stage3_technology_data.resolve_stage3_explanation`, which already
    rejects 3.7/delegated_workflow). Mirrors `ask_irene`'s exact disabled
    -> rate-limit -> no-skill -> gateway-failure -> fallback sequence,
    reusing the same public contracts/gateway/fallback helper, but is a
    wholly separate function with its own independent rate-limit query
    and response filtering (see module docstring) - never calling
    `ask_irene` or any of its private helpers, and never writing to
    `AssistantConversation`/`AssistantMessage` itself.

    Returns the real `AdviserResponse` on success, or the exact
    documented `safe_fallback_response` under every one of: Adviser Mode
    disabled (requirement 6), rate limit exceeded, no skill resolved for
    this question's own `explain_intent_code`, or a `GatewayError` from
    the real/injected gateway - never an unhandled exception.
    """
    context = dispatch.context

    if not getattr(settings, "IRENE_ADVISER_MODE_ENABLED", False):
        return safe_fallback_response(intent_code=context.intent_code, model_trace_id=str(_uuid.uuid4()))

    if not _within_rate_limits(organisation, user):
        return safe_fallback_response(intent_code=context.intent_code, model_trace_id=str(_uuid.uuid4()))

    skill = dispatch.skill
    if skill is None:
        return safe_fallback_response(intent_code=context.intent_code, model_trace_id=str(_uuid.uuid4()))

    from irene import tools as irene_tools

    tenant_context = TenantAdviserContext(
        organisation_id=context.organisation_id,
        current_question_key=f"{context.section_code}:{context.question_code}",
        checkpoint_state="stage3_question_explain",
        foundations_completion_percentage=_foundations_completion_percentage(organisation),
        open_task_count=0,
    )
    available_tools = [
        AdviserToolDescription(name=t["name"], description=t["description"])
        for t in irene_tools.get_available_tool_descriptions()
        if t["name"] in skill.tools
    ]

    request = AdviserRequest(
        organisation_id=context.organisation_id,
        conversation_id=str(_uuid.uuid4()),
        intent_code=context.intent_code,
        user_message=_build_user_message(context),
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
    except GatewayError:
        return safe_fallback_response(intent_code=context.intent_code, model_trace_id=str(_uuid.uuid4()))

    return _filter_response_against_registry(response)


__all__ = ["ask_irene_stage3_explain"]
