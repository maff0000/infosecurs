"""
IRENE's bounded, typed, allowlisted tool registry (M010C PID §3; docs/
architecture/M010-ADVISER-TOOLS-AND-SKILLS.md §3).

Every tool here is a THIN WRAPPER over a real, unmodified, already-existing
service function from `foundations_journey`, `security_tasks`,
`organisations` or `entitlements` - never a new, parallel data path, and
never a direct ORM query against a model this app does not own. This
module imports no AI/model code, and nothing in `ai_platform` imports this
module.

== AuthorizedContext and the "recheck on every call" rule (M010 threat
model §2) ==
`AuthorizedContext` carries the live Django `request` object alongside the
`organisation_id`/`user_id` it was built from. Every tool function's FIRST
action is `_revalidate(context, required_capability)`, which re-runs:

  1. `organisations.views.get_member_organisation_or_404` - a fresh,
     live membership query (never trusts that some EARLIER point in this
     same request, or an earlier turn of the same conversation, already
     proved membership).
  2. `entitlements.capabilities.has_capability(request, required_capability)`
     - a fresh, live package-tier decision.

This is deliberately the SAME two checks `entitlements.decorators.
require_capability`'s own view decorator already performs - reused, not
reimplemented - but run again, explicitly, inside the tool itself, so a
revoked membership or a downgraded tier between the Ask view's own
decorator running and this specific tool call executing (not possible
within a single synchronous Django request today, but exactly the
property M010 threat model §2's "snapshot is not a permanent grant"
requires this module to hold itself to regardless of today's call
topology - a future multi-step/background tool-execution path must not
silently inherit a stale grant) is caught here, independently, every time.

== Read tools (Class R) ==
`get_foundations_summary`, `get_next_structured_question`,
`get_security_tasks`, `get_task_detail`, `get_allowed_stage`,
`get_registered_route` - each returns typed, MINIMISED data (a handful of
named fields, never a full model `__dict__`/serializer dump) with source
IDs, never an unrestricted join the model could use to pull more than it
was offered.

== Constrained write tools (Class D then T) ==
`propose_task` (Class D - a PREVIEW only, writes one `AssistantAction` row
with `decision_state=PROPOSED`, never a `SecurityTask`) and
`confirm_task_creation` (Class T - requires the exact `action_id` the
matching `propose_task` call returned; calls `security_tasks.services.
create_task` - the SAME canonical write path every manual "New task" form
submission already uses, never a second write path). See each function's
own docstring for the full binding/expiry rule.

== Forbidden tools (M010 threat model §2/§5, M010-ADVISER-TOOLS-AND-
SKILLS.md §3) ==
No `execute_query`/`get_object`/`fetch_url`/`run_sql`/arbitrary-file-read/
shell-exec function exists ANYWHERE in this module, this app, or is
importable from it - "forbidden by construction, not only by policy
prose" (M010C PID scope). `irene/tests/test_adversarial.py` asserts this
module has no such attribute by name, for every name M010-ADVISER-TOOLS-
AND-SKILLS.md §3's own forbidden list enumerates.
"""
from __future__ import annotations

import dataclasses
import uuid as _uuid
from typing import Callable, Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import NoReverseMatch, reverse

from irene.exceptions import (
    ActionProposalExpiredError,
    ToolCapabilityDeniedError,
    UnregisteredToolError,
)
from irene.models import ActionDecisionState, AssistantAction, AssistantActionResultCategory
from irene.product_knowledge import get_concept


@dataclasses.dataclass(frozen=True)
class AuthorizedContext:
    """Server-created, per-request authorisation context (M010 threat
    model §2's `AuthorizedContext(user_id, organisation_id, role,
    capability_snapshot, request_id)` - this codebase's existing session/
    membership model has no explicit per-organisation "role" string beyond
    `OrganisationMembership.role` and no separate "capability_snapshot"
    beyond the live session tier, so this dataclass carries exactly the
    fields this codebase's real authorisation primitives need to be
    RE-CHECKED from, plus the live `request` those checks run against -
    never a boolean "is_authorised" flag computed once and trusted
    later).

    Constructed exactly once per request, by `irene.views`, from an
    already-`@require_capability()`-gated view - the same convention
    `security_tasks.views`/`foundations_journey.views` already use for
    their own first view-body action."""

    request: object
    organisation_id: str
    user_id: str
    request_id: str


def build_authorized_context(request, organisation) -> AuthorizedContext:
    return AuthorizedContext(
        request=request,
        organisation_id=str(organisation.id),
        user_id=str(request.user.pk),
        request_id=str(_uuid.uuid4()),
    )


def context_fingerprint(context: AuthorizedContext) -> str:
    """A non-secret fingerprint recorded on `AssistantAction` rows (M010
    data contract §1's "authorised context fingerprint (nonsecret)") -
    never a credential, never raw session content."""
    return f"org={context.organisation_id};user={context.user_id}"


def _revalidate(context: AuthorizedContext, required_capability: str):
    """See module docstring. Returns the live, membership-checked
    `Organisation`. Raises `Http404` (non-member - same non-disclosing
    convention as every other per-object fetch in this codebase) or
    `PermissionDenied` (member, insufficient tier) - never silently
    returns a usable organisation on any failure path."""
    from entitlements.capabilities import has_capability
    from organisations.views import get_member_organisation_or_404

    organisation = get_member_organisation_or_404(context.request.user, context.organisation_id)
    if not has_capability(context.request, required_capability):
        raise PermissionDenied(f"Session does not satisfy capability {required_capability!r}.")
    return organisation


@dataclasses.dataclass(frozen=True)
class ToolSpec:
    """One tool registry entry - the "stable name, version, typed input/
    output, timeout, max results, required capability, action class,
    redaction rules" row M010-ADVISER-TOOLS-AND-SKILLS.md §3 describes."""

    name: str
    version: str
    action_class: str  # "R" (read), "D" (draft/propose), "T" (task admin write)
    required_capability: str
    timeout_seconds: float
    max_results: int
    description: str  # the ONLY text ever exposed to the model about this tool
    func: Callable
    feature_flag: Optional[str] = None  # a settings.* attribute name; False disables this tool entirely


# ---------------------------------------------------------------------------
# Read tools (Class R)
# ---------------------------------------------------------------------------
def get_foundations_summary(context: AuthorizedContext) -> dict:
    from entitlements.metrics import get_security_foundations_completion
    from foundations_journey.services import get_journey_checkpoint

    organisation = _revalidate(context, "security")
    user = context.request.user
    checkpoint = get_journey_checkpoint(organisation, user)
    completion = get_security_foundations_completion(organisation)
    return {
        "current_question_key": checkpoint.current_question_key,
        "checkpoint_state": checkpoint.checkpoint_state,
        "completion_percentage": completion.percentage,
        "completion_completed_count": completion.completed_count,
        "completion_total_count": completion.total_count,
    }


def get_next_structured_question(context: AuthorizedContext) -> Optional[dict]:
    from foundations_journey.services import get_foundations_question, get_journey_checkpoint

    organisation = _revalidate(context, "security")
    user = context.request.user
    checkpoint = get_journey_checkpoint(organisation, user)
    if not checkpoint.current_question_key:
        return None
    view_model = get_foundations_question(organisation, user, checkpoint.current_question_key)
    return {
        "question_key": view_model.question_key,
        "title": view_model.title,
        "why_it_matters": view_model.why_it_matters,
        "option_labels": [label for _code, label in view_model.options],
        "saved_option_code": view_model.saved_option_code,
        "stage_progress_copy": view_model.stage_progress_copy,
    }


DEFAULT_TASK_TOOL_PAGE_SIZE = 5  # bounded (M010 threat model §2 "pagination")


def get_security_tasks(context: AuthorizedContext, *, status: Optional[str] = None) -> list:
    from security_tasks.models import TaskStatus
    from security_tasks.services import get_task_list

    organisation = _revalidate(context, "tasks")
    status = status if status in TaskStatus.values else None
    task_page = get_task_list(organisation, status=status, page_size=DEFAULT_TASK_TOOL_PAGE_SIZE)
    return [
        {
            "task_id": str(task.id),
            "title": task.title,
            "status": task.status,
            "task_group": task.task_group,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        }
        for task in task_page.items
    ]


def get_task_detail(context: AuthorizedContext, *, task_id) -> Optional[dict]:
    from security_tasks.services import get_task_detail as _get_task_detail

    organisation = _revalidate(context, "tasks")
    detail = _get_task_detail(organisation, task_id)
    if detail is None:
        return None
    task = detail.task
    return {
        "task_id": str(task.id),
        "title": task.title,
        "status": task.status,
        "task_group": task.task_group,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "source_unavailable": detail.source_unavailable,
    }


def get_allowed_stage(context: AuthorizedContext) -> dict:
    from organisations.guided_journey import current_guided_stage

    organisation = _revalidate(context, "security")
    stage = current_guided_stage(organisation)
    return {
        "number": stage.number,
        "name": stage.name,
        "url": stage.url,
        "is_complete": stage.is_complete,
    }


def get_registered_route(context: AuthorizedContext, *, concept_id: str, object_locator: Optional[dict] = None) -> Optional[str]:
    """Resolves a safe internal URL for a registered Product Knowledge Map
    concept - M010-ADVISER-TOOLS-AND-SKILLS.md §2's "the model can ask
    get_registered_route(...); route resolver builds a URL with server-
    verified tenant and current permissions. It never fabricates
    /organisations/<other-tenant-id>/...". `organisation_id` in the built
    URL is ALWAYS the live-revalidated organisation from THIS context,
    never anything the caller/model supplied - `object_locator` may only
    add the route's OWN additional kwargs (e.g. `question_key`/`task_id`),
    never an `organisation_id` key of its own (silently ignored if
    present, since the real value below always wins the dict merge)."""
    entry = get_concept(concept_id)
    if entry is None:
        return None
    organisation = _revalidate(context, entry.required_capability)
    kwargs = dict(object_locator or {})
    kwargs["organisation_id"] = organisation.id
    try:
        return reverse(entry.route_name, kwargs=kwargs)
    except NoReverseMatch:
        return None


def get_available_tool_descriptions() -> list:
    """Safe, short (name + one-line description only) descriptions of
    every tool that is both registered AND feature-flag-enabled -
    M010-ADVISER-TOOLS-AND-SKILLS.md §2's "Model receives short safe
    descriptions of registered tools, not the full schema". Used by
    `irene.orchestration` to build `AdviserRequest.available_tools`."""
    return [
        {"name": spec.name, "description": spec.description}
        for spec in TOOL_REGISTRY.values()
        if _tool_enabled(spec)
    ]


def _tool_enabled(spec: "ToolSpec") -> bool:
    if spec.feature_flag is None:
        return True
    return bool(getattr(settings, spec.feature_flag, False))


def call_tool(name: str, context: AuthorizedContext, **kwargs):
    """The ONE dispatch point `irene.orchestration`'s single bounded
    per-turn tool call goes through. Raises `UnregisteredToolError` for an
    unknown name (default-deny) and `ToolCapabilityDeniedError` if the
    tool exists but its feature flag is off - both are DENIED/RECORDED
    policy events (M010-ADVISER-TOOLS-AND-SKILLS.md §3's "A model
    proposing one is a denied/recorded policy event, not a request to
    create a new tool"), never a crash and never a silent no-op."""
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        raise UnregisteredToolError(f"{name!r} is not a registered tool.")
    if not _tool_enabled(spec):
        raise ToolCapabilityDeniedError(f"Tool {name!r} is disabled by feature flag {spec.feature_flag!r}.")
    return spec.func(context, **kwargs)


# ---------------------------------------------------------------------------
# Constrained write tools (Class D then T) - M010-ADVISER-TOOLS-AND-
# SKILLS.md §3's "propose_task (generates pending preview), confirm_task_
# creation (requires user's confirmed form/token)".
# ---------------------------------------------------------------------------
MAX_PROPOSAL_TITLE_LENGTH = 255
MAX_PROPOSAL_SUMMARY_LENGTH = 1000


def propose_task(
    context: AuthorizedContext,
    *,
    kind: str,
    title: str,
    summary: str = "",
    source_kind: Optional[str] = None,
    source_object_id: Optional[str] = None,
    conversation_id=None,
) -> dict:
    """Class D - writes ONLY an `AssistantAction` row (`decision_state=
    PROPOSED`); never a `SecurityTask`. The returned `action_id` is the
    single token `confirm_task_creation` accepts - there is no separate
    "confirmation token" string to leak or forge, because the token IS a
    tenant+owner-scoped database row this function itself just created and
    `confirm_task_creation` re-validates belongs to the exact same
    (organisation, user) before ever calling `security_tasks.services.
    create_task` (see that function's own docstring)."""
    from security_tasks.models import TaskKind
    from security_tasks.source_registry import SOURCE_KIND_NONE

    organisation = _revalidate(context, "tasks")

    if kind not in TaskKind.values:
        raise ValueError(f"Unregistered task_kind {kind!r}.")
    title = (title or "").strip()[:MAX_PROPOSAL_TITLE_LENGTH]
    if not title:
        raise ValueError("title must not be empty.")
    summary = (summary or "").strip()[:MAX_PROPOSAL_SUMMARY_LENGTH]
    source_kind = source_kind or SOURCE_KIND_NONE

    action = AssistantAction.objects.create(
        organisation=organisation,
        actor=context.request.user,
        conversation_id=conversation_id,
        tool_name="propose_task",
        tool_version="1.0.0",
        context_fingerprint=context_fingerprint(context),
        requested_params_redacted={
            "kind": kind,
            "title": title,
            "summary": summary,
            "source_kind": source_kind,
            "source_object_id": str(source_object_id) if source_object_id else None,
        },
        decision_state=ActionDecisionState.PROPOSED,
        result_category=AssistantActionResultCategory.PENDING,
        trace_id=context.request_id,
    )
    return {
        "action_id": str(action.id),
        "kind": kind,
        "title": title,
        "summary": summary,
        "source_kind": source_kind,
        "changes_security_truth": False,
    }


def confirm_task_creation(context: AuthorizedContext, *, action_id) -> dict:
    """Class T - the ONE place this module ever calls `security_tasks.
    services.create_task` (the exact canonical write path a manual "New
    task" form submission already uses). Requires:

      1. `action_id` resolves to an `AssistantAction` owned by THIS
         (organisation, actor) - re-checked live, under
         `select_for_update()`, same non-disclosing 404-shaped failure as
         every other cross-tenant/cross-owner probe in this codebase
         (`ActionProposalExpiredError` here, mapped to a generic denial
         by the caller - never "found but not yours").
      2. `decision_state == PROPOSED` - a proposal can be confirmed
         EXACTLY ONCE; replaying the same `action_id` after it has
         already moved to `EXECUTED`/`REJECTED`/`FAILED` raises
         `ActionProposalExpiredError` rather than creating a second task
         (the explicit "user gesture and confirmation token bind exact
         ... organisation" discipline M010-ADVISER-TOOLS-AND-SKILLS.md §3
         asks for - the "token" IS this exact proposal row, single-use,
         row-locked for the duration of this call).

    The `idempotency_key` passed to `security_tasks.services.create_task`
    is DERIVED from `action_id` itself (`f"irene-action-{action_id}"`),
    never caller-supplied - so even a genuine concurrent double-submit of
    the same confirmation (two requests racing past the `select_for_update`
    lock boundary before either commits) still only ever produces ONE
    `SecurityTask`, via `create_task`'s own existing idempotency-key
    uniqueness constraint - the second writer's `IntegrityError` re-fetch
    path returns the SAME task, never a duplicate.
    """
    from django.db import transaction

    from security_tasks.services import create_task

    organisation = _revalidate(context, "tasks")

    with transaction.atomic():
        action = (
            AssistantAction.objects.select_for_update()
            .filter(pk=action_id, organisation=organisation, actor_id=context.request.user.pk)
            .first()
        )
        if action is None:
            raise ActionProposalExpiredError("This proposal does not exist or does not belong to you.")
        if action.decision_state != ActionDecisionState.PROPOSED:
            raise ActionProposalExpiredError(
                f"This proposal is already {action.decision_state!r} and cannot be confirmed again."
            )

        params = action.requested_params_redacted
        idempotency_key = f"irene-action-{action.id}"
        try:
            task = create_task(
                organisation,
                actor=context.request.user,
                kind=params["kind"],
                title=params["title"],
                summary=params.get("summary", ""),
                idempotency_key=idempotency_key,
                source_kind=params.get("source_kind") or "none",
                source_object_id=params.get("source_object_id"),
            )
        except Exception:
            action.decision_state = ActionDecisionState.FAILED
            action.result_category = AssistantActionResultCategory.ERROR
            action.save(update_fields=["decision_state", "result_category", "updated_at"])
            raise

        action.decision_state = ActionDecisionState.EXECUTED
        action.canonical_target_id = str(task.id)
        action.result_category = AssistantActionResultCategory.SUCCESS
        action.save(update_fields=["decision_state", "canonical_target_id", "result_category", "updated_at"])

        return {"task_id": str(task.id), "title": task.title, "status": task.status}


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "get_foundations_summary": ToolSpec(
        name="get_foundations_summary",
        version="1.0.0",
        action_class="R",
        required_capability="security",
        timeout_seconds=5.0,
        max_results=1,
        description="Get a short summary of this organisation's current Foundations progress.",
        func=get_foundations_summary,
    ),
    "get_next_structured_question": ToolSpec(
        name="get_next_structured_question",
        version="1.0.0",
        action_class="R",
        required_capability="security",
        timeout_seconds=5.0,
        max_results=1,
        description="Get the current guided Foundations question for this organisation, if any.",
        func=get_next_structured_question,
    ),
    "get_security_tasks": ToolSpec(
        name="get_security_tasks",
        version="1.0.0",
        action_class="R",
        required_capability="tasks",
        timeout_seconds=5.0,
        max_results=DEFAULT_TASK_TOOL_PAGE_SIZE,
        description="Get a short, bounded list of this organisation's current security tasks.",
        func=get_security_tasks,
    ),
    "get_task_detail": ToolSpec(
        name="get_task_detail",
        version="1.0.0",
        action_class="R",
        required_capability="tasks",
        timeout_seconds=5.0,
        max_results=1,
        description="Get detail for one specific task this organisation owns.",
        func=get_task_detail,
    ),
    "get_allowed_stage": ToolSpec(
        name="get_allowed_stage",
        version="1.0.0",
        action_class="R",
        required_capability="security",
        timeout_seconds=5.0,
        max_results=1,
        description="Get which of the 6 guided Foundations stages this organisation should continue to next.",
        func=get_allowed_stage,
    ),
    "get_registered_route": ToolSpec(
        name="get_registered_route",
        version="1.0.0",
        action_class="R",
        required_capability="irene",
        timeout_seconds=5.0,
        max_results=1,
        description="Resolve a safe internal link for a registered Product Knowledge Map concept.",
        func=get_registered_route,
    ),
    "propose_task": ToolSpec(
        name="propose_task",
        version="1.0.0",
        action_class="D",
        required_capability="tasks",
        timeout_seconds=5.0,
        max_results=1,
        description="Propose (preview only - nothing is written yet) a new administrative task.",
        func=propose_task,
        feature_flag="IRENE_TASK_TOOLS_ENABLED",
    ),
    "confirm_task_creation": ToolSpec(
        name="confirm_task_creation",
        version="1.0.0",
        action_class="T",
        required_capability="tasks",
        timeout_seconds=5.0,
        max_results=1,
        description="Create the previously-proposed task, only after the user has explicitly confirmed it.",
        func=confirm_task_creation,
        feature_flag="IRENE_TASK_TOOLS_ENABLED",
    ),
}


__all__ = [
    "AuthorizedContext",
    "build_authorized_context",
    "context_fingerprint",
    "ToolSpec",
    "TOOL_REGISTRY",
    "call_tool",
    "get_available_tool_descriptions",
    "get_foundations_summary",
    "get_next_structured_question",
    "get_security_tasks",
    "get_task_detail",
    "get_allowed_stage",
    "get_registered_route",
    "propose_task",
    "confirm_task_creation",
]
