"""
`AssistantConversation`/`AssistantMessage` service layer (M010C PID §2;
M010-DATA-WORKFLOW-CONTRACTS.md §1). Same thin-service convention as
`security_tasks.services`/`foundations_journey.services`: views and
`irene.orchestration` call this module, never `AssistantConversation.
objects`/`AssistantMessage.objects` directly for a write.

Privacy (M010 threat model §4): every function here takes BOTH
`organisation` (already membership-checked by the caller) AND `user`, and
every query filters on `owner=user` as well as `organisation=organisation`
- a conversation belonging to another member of the SAME organisation is
exactly as inaccessible as one belonging to a different organisation
entirely (both resolve to "not found", never distinguished).
"""
from __future__ import annotations

import dataclasses

from django.db import transaction

from irene.exceptions import ConversationBoundsExceededError, ForeignConversationError
from irene.models import (
    AssistantConversation,
    AssistantMessage,
    ConversationState,
    MAX_MESSAGE_CONTENT_LENGTH,
    MAX_MESSAGES_PER_CONVERSATION,
    MessageClassification,
    MessageRole,
)
from organisations.models import OrganisationMembership


def _require_live_membership(organisation, user) -> None:
    """M010 threat model §3 'Member removed mid-conversation' ->
    'Recheck membership each message/tool call' -> 'Existing
    conversation becomes inaccessible, no stale-cache leakage'. A
    conversation row's own `(organisation, owner)` match is NOT enough on
    its own - this re-checks LIVE membership, every call, the same
    discipline `security_tasks.services._validate_assignee` already
    establishes for this codebase."""
    if not OrganisationMembership.objects.filter(organisation=organisation, user=user).exists():
        raise ForeignConversationError(
            f"{user!r} is no longer a member of {organisation!r} - this conversation is inaccessible."
        )


def get_or_create_active_conversation(organisation, user) -> AssistantConversation:
    """One active conversation per (organisation, user) - the product
    shape this package implements. Not DB-constrained to be unique
    (`AssistantConversation` carries no such `UniqueConstraint` - see that
    model's own docstring) because an older `ARCHIVED` row may coexist;
    this function always looks for the most recent `ACTIVE` row first and
    only creates a new one if none exists."""
    _require_live_membership(organisation, user)
    conversation = (
        AssistantConversation.objects.filter(
            organisation=organisation, owner=user, state=ConversationState.ACTIVE
        )
        .order_by("-updated_at")
        .first()
    )
    if conversation is not None:
        return conversation
    return AssistantConversation.objects.create(organisation=organisation, owner=user)


def _get_owned_conversation_or_raise(organisation, user, conversation_id) -> AssistantConversation:
    _require_live_membership(organisation, user)
    conversation = AssistantConversation.objects.filter(
        pk=conversation_id, organisation=organisation, owner=user
    ).first()
    if conversation is None:
        raise ForeignConversationError(
            f"Conversation {conversation_id!r} does not exist or is not owned by this user in this organisation."
        )
    return conversation


@dataclasses.dataclass(frozen=True)
class MessagePage:
    conversation: AssistantConversation
    messages: tuple


def list_messages(organisation, user, conversation_id) -> MessagePage:
    """Read-only. Raises `ForeignConversationError` for a conversation
    that does not exist, belongs to a different organisation, OR belongs
    to a different user in the SAME organisation - all three collapse to
    the identical failure, never disclosed apart (M010 threat model §4)."""
    conversation = _get_owned_conversation_or_raise(organisation, user, conversation_id)
    messages = tuple(conversation.messages.all())
    return MessagePage(conversation=conversation, messages=messages)


def append_message(
    organisation,
    user,
    conversation_id,
    *,
    role: str,
    content: str,
    classification: str = MessageClassification.NORMAL,
    source_concept_ids=None,
    provider_call_trace_id: str = "",
) -> AssistantMessage:
    """The ONE write path for a new message. Bounds length (M010-DATA-
    WORKFLOW-CONTRACTS.md §1 "content bounded") and total conversation
    length (`MAX_MESSAGES_PER_CONVERSATION` - a disclosed, conservative
    placeholder, see `irene.models`'s own comment) - raises
    `ConversationBoundsExceededError` rather than silently truncating or
    evicting history."""
    if role not in MessageRole.values:
        raise ValueError(f"Unregistered message role {role!r}.")

    content = (content or "")[:MAX_MESSAGE_CONTENT_LENGTH]
    _require_live_membership(organisation, user)

    with transaction.atomic():
        conversation = (
            AssistantConversation.objects.select_for_update()
            .filter(pk=conversation_id, organisation=organisation, owner=user)
            .first()
        )
        if conversation is None:
            raise ForeignConversationError(
                f"Conversation {conversation_id!r} does not exist or is not owned by this user in this organisation."
            )

        existing_count = conversation.messages.count()
        if existing_count >= MAX_MESSAGES_PER_CONVERSATION:
            raise ConversationBoundsExceededError(
                f"Conversation {conversation_id!r} has reached the maximum of "
                f"{MAX_MESSAGES_PER_CONVERSATION} messages."
            )

        next_sequence = existing_count + 1
        message = AssistantMessage.objects.create(
            conversation=conversation,
            sequence=next_sequence,
            role=role,
            content=content,
            classification=classification,
            source_concept_ids=list(source_concept_ids or []),
            provider_call_trace_id=provider_call_trace_id,
        )
        conversation.save(update_fields=["updated_at"])
        return message


__all__ = [
    "get_or_create_active_conversation",
    "list_messages",
    "append_message",
    "MessagePage",
]
