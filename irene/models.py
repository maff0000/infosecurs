"""
M010C - IRENE conversation + action-trace models (docs/pids/
M010C-IRENE-MODAL-SKILLS-TOOLS.md §2; docs/architecture/
M010-DATA-WORKFLOW-CONTRACTS.md §1 "AssistantConversation and
AssistantMessage" / "AssistantAction").

Three models, exactly as the data contract names them:

  - `AssistantConversation` - tenant FK AND owner-user FK (private to the
    owner, never organisation-wide - M010 threat model §4 "Default
    visibility private to originating user"). ONE active conversation per
    (organisation, owner) is the product shape this package implements
    (`irene.services.get_or_create_active_conversation`) - the model
    itself does not enforce a uniqueness constraint on that, deliberately,
    because `state=ARCHIVED` rows legitimately coexist with a newer
    active one for the same (organisation, owner): see that service's own
    docstring.
  - `AssistantMessage` - ordered by a monotonic `sequence` integer *within
    its conversation*, role-allowlisted, content bounded. Carries no
    direct `organisation` FK of its own (reached only via
    `conversation.organisation`) - the same "no direct FK, cascades via
    parent" treatment `security_baseline.BaselineAnswer`/
    `questionnaire.QuestionnaireImportQuestion` already use for an
    identical reason (see those models' own docstrings and
    `organisations.reset_service`'s own EXPECTED_DELETE comment for each).
  - `AssistantAction` - organisation+actor-scoped TRACE of a candidate
    tool invocation (constrained-write proposal/confirmation), never a
    second task ledger (M010 data contract §1: "All actual changes still
    recorded by domain activity events; AssistantAction is trace, not a
    second task ledger"). `requested_params_redacted` never carries a raw
    customer prose field - only the small, allowlisted, already-safe
    fields `irene.tools.propose_task`/`confirm_task_creation` themselves
    construct (see that module's own docstring).

Zero AI/LLM import anywhere in this module - purely structural models, like
every other app's `models.py` in this codebase.

JUDGEMENT CALL (recorded, not silently resolved): the data contract's own
"Consider reuse of existing activity framework instead of duplicate table
where viable" suggestion for `AssistantAction` was considered and NOT
taken. `activity.ActivityEvent` (see that app's own models.py) is itself a
fixed, append-only, *already-committed-fact* ledger for domain mutations
elsewhere in the product; `AssistantAction` needs a mutable `decision_state`
column (`proposed` -> `confirmed`/`rejected` -> `executed`/`failed`) that an
append-only activity row cannot honestly represent without either faking
immutability or growing a second, parallel update path onto a model several
OTHER apps also write to. A new, small, IRENE-owned table keeps that
lifecycle local to this app, exactly like `security_tasks.SecurityTaskEvent`
being its own table rather than reusing `activity.ActivityEvent` for task
events (M010A's own precedent - see `security_tasks/models.py`'s module
docstring, which raises and resolves the identical question the same way).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from organisations.models import Organisation


class ConversationState(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


# M010-ADVISER-TOOLS-AND-SKILLS.md §4/§8: controlled intent codes only -
# never free-text matching. `irene.skill_router` is the ONE place an
# `intent_code` selects a skill; this choice list is the full set this
# package implements (foundations-guide + task-administration's own
# allowed_intents, from each skill's own SKILL.md frontmatter).
class IntentCode(models.TextChoices):
    EXPLAIN_CONTROL = "explain_control", "Explain a Foundations control"
    CLARIFY_OPTION = "clarify_option", "Clarify an answer option"
    SUGGEST_FOLLOWUP = "suggest_followup", "Suggest a follow-up task"
    TASK_STATUS_HELP = "task_status_help", "Explain current task status"
    TASK_NEXT_STEP_HELP = "task_next_step_help", "Explain the next step for a task"
    UNCLEAR = "unclear", "Unclear / general"


MAX_MESSAGE_CONTENT_LENGTH = 4000
# M010 architecture doc §5: "bounded conversation length" - a placeholder,
# clearly-commented bound (see docs/evidence/M010C-IRENE-WORKSPACE-TOOLS.md
# for why this is disclosed as requiring separate product approval, same as
# every other numeric placeholder this package introduces).
MAX_MESSAGES_PER_CONVERSATION = 200


class AssistantConversation(models.Model):
    """One IRENE Ask-tab conversation thread, private to its owner
    (M010-DATA-WORKFLOW-CONTRACTS.md §1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="assistant_conversations"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_conversations",
        help_text="Private to this user - M010 threat model §4. No other member of the same organisation may read this conversation's messages.",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    state = models.CharField(max_length=16, choices=ConversationState.choices, default=ConversationState.ACTIVE)
    skill_version = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="The skill manifest version active when this conversation's most recent message was produced.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["organisation", "owner", "state"]),
        ]

    def __str__(self):
        return f"IRENE conversation {self.id} ({self.organisation_id}/{self.owner_id}) [{self.state}]"


class MessageRole(models.TextChoices):
    """Allowlisted roles only (M010-DATA-WORKFLOW-CONTRACTS.md §1 "role
    allowlist") - `tool` carries a tool RESULT, rendered as inert data to
    the next model turn, never as an instruction (M010 threat model §1.8/
    irrevocable STOPs)."""

    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    TOOL = "tool", "Tool result"
    SYSTEM = "system", "System"


class MessageClassification(models.TextChoices):
    """Small, allowlisted metadata only - never a free string (M010
    threat model §2's general "no arbitrary filters/values" discipline,
    applied here to message bookkeeping)."""

    NORMAL = "normal", "Normal"
    SAFE_FALLBACK = "safe_fallback", "Safe fallback (adviser mode off or gateway failure)"
    POLICY_DENIED = "policy_denied", "A forbidden/unregistered action was requested and denied"


class AssistantMessage(models.Model):
    """One message in an `AssistantConversation`, ordered by `sequence`
    (monotonic, unique within its conversation - M010-DATA-WORKFLOW-
    CONTRACTS.md §1 "Message ordered by monotonic sequence")."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation, on_delete=models.CASCADE, related_name="messages"
    )
    sequence = models.PositiveIntegerField()
    role = models.CharField(max_length=16, choices=MessageRole.choices)
    content = models.TextField(
        help_text=(
            f"Bounded to {MAX_MESSAGE_CONTENT_LENGTH} characters at the service layer "
            "(irene.services.append_message). Rendered with normal Django "
            "auto-escaping - never marked safe, never interpreted as HTML/Markdown."
        ),
    )
    classification = models.CharField(
        max_length=20, choices=MessageClassification.choices, default=MessageClassification.NORMAL
    )
    source_concept_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="Small list of registered Product Knowledge Map concept_ids this message referenced - never raw DB identifiers.",
    )
    provider_call_trace_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "sequence"], name="assistantmessage_unique_sequence_per_conversation"
            )
        ]
        indexes = [models.Index(fields=["conversation", "sequence"])]

    def __str__(self):
        return f"[{self.role}] message {self.sequence} in conversation {self.conversation_id}"


class ActionDecisionState(models.TextChoices):
    PROPOSED = "proposed", "Proposed (preview only, nothing written)"
    CONFIRMED = "confirmed", "Confirmed by the user"
    REJECTED = "rejected", "Rejected / expired"
    EXECUTED = "executed", "Executed (real write committed)"
    FAILED = "failed", "Failed"


class AssistantActionResultCategory(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    DENIED_POLICY = "denied_policy", "Denied - forbidden/unregistered action"
    DENIED_TENANT = "denied_tenant", "Denied - tenant/membership recheck failed"
    DENIED_EXPIRED = "denied_expired", "Denied - proposal expired or already consumed"
    ERROR = "error", "Error"


class AssistantAction(models.Model):
    """Immutable-in-spirit trace of one candidate tool invocation
    (M010-DATA-WORKFLOW-CONTRACTS.md §1 "AssistantAction"). Only
    `irene.tools.propose_task`/`confirm_task_creation` ever write this
    model - see that module's own docstring for the exact lifecycle
    (`PROPOSED` -> `CONFIRMED`/`REJECTED` -> `EXECUTED`/`FAILED`)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="assistant_actions"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistant_actions",
    )
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    tool_name = models.CharField(max_length=64)
    tool_version = models.CharField(max_length=32)
    context_fingerprint = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="A non-secret fingerprint of the AuthorizedContext this proposal was made under (e.g. a hash of organisation_id+user_id+capability_snapshot) - never a credential, never raw session data.",
    )
    requested_params_redacted = models.JSONField(
        default=dict,
        blank=True,
        help_text="Small, allowlisted structured detail only - constructed exclusively by irene.tools itself, never raw prose from the model or the customer.",
    )
    decision_state = models.CharField(
        max_length=16, choices=ActionDecisionState.choices, default=ActionDecisionState.PROPOSED
    )
    canonical_target_id = models.CharField(max_length=64, blank=True, default="")
    result_category = models.CharField(
        max_length=20, choices=AssistantActionResultCategory.choices, default=AssistantActionResultCategory.PENDING
    )
    trace_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "created_at"]),
            models.Index(fields=["organisation", "decision_state"]),
        ]

    def __str__(self):
        return f"{self.tool_name}@{self.tool_version} [{self.decision_state}] ({self.organisation_id})"
