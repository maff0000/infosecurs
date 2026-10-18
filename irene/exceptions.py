"""Exceptions for the `irene` app - same shape as `security_tasks.
exceptions`/`foundations_journey.exceptions`: narrow, explicit, never a
bare `ValueError`/`Exception` for a condition a caller must branch on."""
from __future__ import annotations


class ConversationBoundsExceededError(Exception):
    """Raised by `irene.services.append_message` when the conversation
    has already reached `irene.models.MAX_MESSAGES_PER_CONVERSATION`."""


class ForeignConversationError(Exception):
    """Raised when a conversation_id does not resolve to a row owned by
    the (organisation, user) the caller is acting as - the same non-
    disclosing shape every other cross-tenant/cross-owner probe in this
    codebase uses (never distinguishing "does not exist" from "belongs to
    someone else")."""


class UnregisteredToolError(Exception):
    """Raised when something asks for a tool name that is not in
    `irene.tools.TOOL_REGISTRY` - default-deny, per M010 threat model §2."""


class ToolCapabilityDeniedError(Exception):
    """Raised when a live tenant/capability recheck fails for a tool
    invocation - independent of whatever `AuthorizedContext` snapshot the
    caller is holding (M010 threat model §2's "recheck actual live
    membership/entitlements at invocation")."""


class ActionProposalExpiredError(Exception):
    """Raised by `irene.tools.confirm_task_creation` when the
    `AssistantAction` proposal it was given has already been
    consumed/rejected, or does not belong to this (organisation, user)."""


class UnregisteredConceptError(Exception):
    """Raised by `irene.product_knowledge` resolution helpers for a
    `concept_id` that is not in the registry - fail loud at the point
    something tries to resolve a route for an unregistered concept."""


class InvalidSkillManifestError(Exception):
    """Raised by `irene.skill_loader` when a skill's manifest/frontmatter,
    references or declared capabilities/tools fail validation - a skill
    that fails this check is never loadable (M010 threat model §3's
    'malicious skill file or poison edit' negative test)."""
