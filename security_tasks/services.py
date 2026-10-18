"""
`SecurityTaskService` callable surface (M010 data contract §3): the ONE
transactional seam every view in this app - and, in a later work package,
IRENE/the deterministic rules engine - calls to read or mutate a
`SecurityTask`. Views stay thin; nothing here renders HTML or touches
`request`.

Core invariant (repeated from models.py's own docstring because it is the
single most important property of this whole app, M010-MASTER-
ARCHITECTURE.md §6, M010 data contract §2): marking a task `done` is
administrative state only. This module never imports `security_baseline.
models`, `policy.models`, `risk_register.models`, or `entitlements.metrics`
for a WRITE - `security_tasks.source_registry` reads a handful of those
models read-only, only to resolve a display locator, and this module calls
that registry the same way. There is no code path anywhere in this file
that calls `.save()`/`.update()`/`.delete()` on any model outside this
app's own three tables.

Tenant/permission boundary (M010 threat model §2): every function here
takes an already organisation-scoped, membership-checked `organisation`
object as its first argument - exactly the convention every other app in
this codebase already uses (`risk_register.services.generate_draft_risks
(organisation)`, `evidence.link_services.link_evidence_to_control
(organisation, ...)`). Callers (views, decorated with `@require_capability()`,
which itself re-validates live membership on every request - entitlements/
decorators.py) establish `organisation` fresh on every call; nothing here
caches or trusts a snapshot. Two checks this module DOES re-run itself,
independently of the caller, because they are object-scoped rather than
route-scoped and a caller could otherwise forge them in a POST body:
  - `assignee_id` must be a CURRENT `OrganisationMembership` of
    `organisation` (re-queried live, every call - never trusted from a
    stale session/cache).
  - A `source_kind`/`source_object_id` pair must resolve, through the
    allowlisted registry, to a real object OWNED BY `organisation` -
    before anything is persisted.

Concurrency (M010 data contract §4):
  - `create_task`: wrapped in `transaction.atomic()`; a genuine duplicate
    (two concurrent callers racing the same `occurrence_key` or the same
    `idempotency_key`) is caught as `IntegrityError` from the partial
    unique constraints on `SecurityTask` and resolved by re-fetching the
    existing row under the SAME organisation - never a second row, never
    a second event, never a newly-generated occurrence/idempotency key on
    retry.
  - `transition_task`/`assign_task`/`link_task_dependency`: each opens its
    own `transaction.atomic()` and takes `select_for_update()` on the
    task row(s) before comparing `expected_version` - a losing concurrent
    writer gets `ConcurrentModificationError`, never a silently-overwritten
    row. A transition request replaying an already-applied
    `idempotency_key` returns the task as it now stands, with no second
    `SecurityTaskEvent`.
"""
from __future__ import annotations

import dataclasses
from collections import defaultdict, deque

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from organisations.models import OrganisationMembership

from security_tasks.exceptions import (
    ConcurrentModificationError,
    DependencyBlockedError,
    DependencyCrossOrganisationError,
    DependencyCycleError,
    DependencySelfReferenceError,
    DuplicateDependencyError,
    ForeignAssigneeError,
    InvalidSourceLocatorError,
    InvalidTaskKindError,
    InvalidTransitionError,
)
from security_tasks.models import (
    ALLOWED_TRANSITIONS,
    CLOSED_STATUSES,
    ActorType,
    SOURCE_KIND_NONE,
    SecurityTask,
    SecurityTaskDependency,
    SecurityTaskEvent,
    SourceOrigin,
    TaskEventAction,
    TaskKind,
    TaskPriority,
    TaskStatus,
)
from security_tasks.source_registry import resolve_source_locator

# M010 data contract §5: "Starter warning windows 30 days, 7 days and
# overdue are configurable defaults requiring product approval at
# implementation". No such approval has been recorded for this package
# (M010A's own scope is the task spine, not the review-scheduling product
# decision - that is M010D's). A single, documented 7-day "due soon"
# default is used here ONLY for the Tasks page's own due-soon FILTER
# (never for creating or suppressing any task), with that limitation
# called out explicitly in this package's evidence document rather than
# silently presented as a ratified product value.
DUE_SOON_WINDOW_DAYS = 7

DEFAULT_PAGE_SIZE = 25

DUE_FILTER_OVERDUE = "overdue"
DUE_FILTER_DUE_SOON = "due_soon"


@dataclasses.dataclass(frozen=True)
class TaskPage:
    items: tuple[SecurityTask, ...]
    total_count: int
    page: int
    page_size: int
    num_pages: int

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.num_pages


def get_task_list(
    organisation,
    *,
    group=None,
    status=None,
    assignee_id=None,
    due_filter=None,
    search=None,
    page=1,
    page_size=DEFAULT_PAGE_SIZE,
) -> TaskPage:
    """Stable-sorted, server-side-paginated, organisation-scoped task
    list (M010A PID §2/§3). `group`/`status`/`assignee_id`/`due_filter`/
    `search` are all optional AND-combined filters - never a free-text
    query string against the database, each is validated against its own
    known value set before being applied, and an unrecognised one is
    simply ignored (fails safe to "no extra filter" rather than raising,
    since this is a read path a hostile/forged query-string value must
    never be able to turn into a 500)."""
    queryset = SecurityTask.objects.for_organisation(organisation).select_related(
        "assigned_to", "created_by"
    )

    if status in TaskStatus.values:
        queryset = queryset.filter(status=status)
    if assignee_id:
        queryset = queryset.filter(assigned_to_id=assignee_id)
    if search:
        search = search.strip()
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(summary__icontains=search))

    now = timezone.now()
    if due_filter == DUE_FILTER_OVERDUE:
        queryset = queryset.exclude(status__in=CLOSED_STATUSES).filter(
            due_at__isnull=False, due_at__lt=now
        )
    elif due_filter == DUE_FILTER_DUE_SOON:
        soon = now + timezone.timedelta(days=DUE_SOON_WINDOW_DAYS)
        queryset = queryset.exclude(status__in=CLOSED_STATUSES).filter(
            due_at__isnull=False, due_at__gte=now, due_at__lte=soon
        )

    # `group` is derived (SecurityTask.task_group), not a stored column -
    # filter in Python against the kinds that map to the requested group,
    # keeping this one query bounded rather than an N+1 per-row re-check.
    if group:
        from security_tasks.models import TASK_GROUP_BY_KIND

        matching_kinds = [kind for kind, grp in TASK_GROUP_BY_KIND.items() if grp == group]
        if matching_kinds:
            queryset = queryset.filter(task_kind__in=matching_kinds)

    # Stable ordering (M010 data contract §3 "stable sorting/pagination"):
    # due date first (nulls last), then most recently created - never bare
    # unordered `created_at` alone, which is not unique enough to guarantee
    # a stable page boundary under ties.
    queryset = queryset.order_by("due_at", "-created_at", "id")

    total_count = queryset.count()
    page = max(int(page or 1), 1)
    page_size = max(int(page_size or DEFAULT_PAGE_SIZE), 1)
    num_pages = max((total_count + page_size - 1) // page_size, 1)
    page = min(page, num_pages)
    offset = (page - 1) * page_size
    items = tuple(queryset[offset : offset + page_size])

    return TaskPage(items=items, total_count=total_count, page=page, page_size=page_size, num_pages=num_pages)


@dataclasses.dataclass(frozen=True)
class TaskDetail:
    task: SecurityTask
    predecessor_dependencies: tuple[SecurityTaskDependency, ...]
    successor_dependencies: tuple[SecurityTaskDependency, ...]
    events: tuple[SecurityTaskEvent, ...]
    source_object: object | None
    source_unavailable: bool


def get_task_detail(organisation, task_id) -> TaskDetail | None:
    """Returns `None` for a task that does not exist OR does not belong
    to `organisation` - the view maps that to an ordinary 404, exactly
    like every other per-object fetch in this codebase (never
    distinguishing "does not exist" from "belongs to someone else")."""
    task = SecurityTask.objects.for_organisation(organisation).filter(pk=task_id).first()
    if task is None:
        return None

    source_object = None
    source_unavailable = False
    if task.source_kind != SOURCE_KIND_NONE and task.source_object_id:
        source_object = resolve_source_locator(
            organisation, task.source_kind, task.source_object_id, strict=False
        )
        source_unavailable = source_object is None

    predecessor_dependencies = tuple(
        task.predecessor_dependencies.select_related("predecessor_task").all()
    )
    successor_dependencies = tuple(task.successor_dependencies.select_related("successor_task").all())
    events = tuple(task.events.select_related("actor_user").all())

    return TaskDetail(
        task=task,
        predecessor_dependencies=predecessor_dependencies,
        successor_dependencies=successor_dependencies,
        events=events,
        source_object=source_object,
        source_unavailable=source_unavailable,
    )


def _validate_assignee(organisation, assignee_id):
    """Live membership re-check (M010 threat model §2) - raises
    `ForeignAssigneeError` for an assignee who is not CURRENTLY a member
    of `organisation`. `None` (unassigned) always passes."""
    if assignee_id is None:
        return
    if not OrganisationMembership.objects.filter(organisation=organisation, user_id=assignee_id).exists():
        raise ForeignAssigneeError(
            f"User {assignee_id!r} is not a current member of this organisation."
        )


def _validate_source_locator(organisation, source_kind, source_object_id):
    """Resolves and verifies ownership of a source locator BEFORE
    persistence (M010A PID §2). Raises `InvalidSourceLocatorError` for a
    `source_kind`/`source_object_id` pair that does not resolve to a real,
    same-organisation object. A `SOURCE_KIND_NONE` kind with no object id
    is always valid (no source linked)."""
    if source_kind == SOURCE_KIND_NONE:
        if source_object_id:
            raise InvalidSourceLocatorError("source_object_id must be blank when source_kind is 'none'.")
        return
    resolved = resolve_source_locator(organisation, source_kind, source_object_id, strict=True)
    if resolved is None:
        raise InvalidSourceLocatorError(
            f"source_kind={source_kind!r} source_object_id={source_object_id!r} does not resolve to "
            "an object owned by this organisation."
        )


def _find_existing_for_retry(organisation, *, occurrence_key, source_origin, task_kind, idempotency_key):
    """After an `IntegrityError` on create, re-fetch the row that already
    exists under this exact organisation - never create a second row, and
    never mint a new occurrence/idempotency key on retry (M010 data
    contract §4)."""
    if idempotency_key:
        existing = SecurityTask.objects.filter(organisation=organisation, idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing
    if occurrence_key:
        existing = SecurityTask.objects.filter(
            organisation=organisation,
            source_origin=source_origin,
            task_kind=task_kind,
            occurrence_key=occurrence_key,
        ).first()
        if existing is not None:
            return existing
    return None


def create_task(
    organisation,
    *,
    actor,
    kind,
    title,
    idempotency_key,
    summary="",
    source_origin=SourceOrigin.HUMAN,
    source_kind=SOURCE_KIND_NONE,
    source_object_id=None,
    occurrence_key=None,
    due_at=None,
    assignee_id=None,
    priority=None,
    priority_reason=None,
) -> SecurityTask:
    """Create a new `SecurityTask`, exactly-once per `idempotency_key`
    (and, independently, per `occurrence_key` within the same
    `(organisation, source_origin, task_kind)`), with its `created` event
    in the same transaction (M010 data contract §3/§4).

    `idempotency_key` is REQUIRED (matches the data contract's own
    `create_task` signature exactly) - every caller, including a plain
    human web-form submission, must supply one. See `security_tasks.
    forms`/`views` for how the "create task" page generates and
    round-trips one through a hidden field so a double-click/browser
    retry reuses the same token (a documented design decision - the data
    contract names the parameter but does not prescribe how a human-
    facing form obtains it)."""
    if not idempotency_key:
        raise ValueError("create_task requires a non-empty idempotency_key.")
    if kind not in TaskKind.values:
        raise InvalidTaskKindError(f"Unregistered task_kind {kind!r}.")

    title = (title or "").strip()
    if not title:
        raise ValueError("title must not be empty.")
    title = title[:255]

    _validate_assignee(organisation, assignee_id)
    _validate_source_locator(organisation, source_kind, source_object_id)

    resolved_priority = priority if priority in TaskPriority.values else TaskPriority.NORMAL
    resolved_priority_reason = priority_reason or (
        "human_choice" if priority else "default"
    )

    try:
        with transaction.atomic():
            task = SecurityTask.objects.create(
                organisation=organisation,
                task_kind=kind,
                title=title,
                summary=summary or "",
                priority=resolved_priority,
                priority_reason=resolved_priority_reason,
                status=TaskStatus.OPEN,
                version=1,
                assigned_to_id=assignee_id,
                created_by=actor if getattr(actor, "pk", None) else None,
                source_origin=source_origin,
                source_kind=source_kind,
                source_object_id=source_object_id,
                occurrence_key=occurrence_key,
                idempotency_key=idempotency_key,
                due_at=due_at,
            )
            SecurityTaskEvent.objects.create(
                organisation=organisation,
                task=task,
                action=TaskEventAction.CREATED,
                actor_type=_actor_type_for(source_origin),
                actor_user=actor if getattr(actor, "pk", None) else None,
                previous_status="",
                new_status=TaskStatus.OPEN,
                revision=1,
                request_id=idempotency_key,
                metadata={"task_kind": kind, "source_origin": source_origin},
            )
            return task
    except IntegrityError:
        existing = _find_existing_for_retry(
            organisation,
            occurrence_key=occurrence_key,
            source_origin=source_origin,
            task_kind=kind,
            idempotency_key=idempotency_key,
        )
        if existing is None:
            raise
        return existing


def _actor_type_for(source_origin: str) -> str:
    return {
        SourceOrigin.HUMAN: ActorType.HUMAN,
        SourceOrigin.IRENE: ActorType.IRENE,
        SourceOrigin.RULES_ENGINE: ActorType.RULES_ENGINE,
        SourceOrigin.EXISTING_DOMAIN: ActorType.SYSTEM,
    }.get(source_origin, ActorType.HUMAN)


def _unresolved_blocking_predecessors(task):
    """Predecessor ("blocks") tasks that are not yet done/cancelled - the
    set that must be empty (or explicitly overridden) before `task` may
    move to `done`/`awaiting_review` (M010 data contract §2)."""
    return list(
        SecurityTask.objects.filter(
            successor_dependencies__successor_task=task,
            successor_dependencies__relation_type="blocks",
        ).exclude(status__in=CLOSED_STATUSES)
    )


def transition_task(
    organisation,
    *,
    actor,
    task_id,
    expected_version,
    next_status,
    reason,
    idempotency_key=None,
    completion_source_kind=None,
    completion_source_object_id=None,
    override_blocked=False,
) -> SecurityTask:
    """Transition a task's `status`, with its event, inside one
    transaction, under `select_for_update()` (M010 data contract §4).

    Idempotent replay: if `idempotency_key` matches an existing
    `SecurityTaskEvent.request_id` already recorded for this task, returns
    the task AS IT CURRENTLY STANDS without applying the transition again
    and without creating a second event - a repeated request with the same
    token is a no-op, never a duplicate (M010A PID §4).

    Concurrency: raises `ConcurrentModificationError` if `expected_version`
    does not match the task's current `version` under the row lock - the
    losing writer never silently overwrites the winner.
    """
    with transaction.atomic():
        task = SecurityTask.objects.select_for_update().filter(pk=task_id, organisation=organisation).first()
        if task is None:
            raise SecurityTask.DoesNotExist(f"No task {task_id!r} in this organisation.")

        if idempotency_key:
            already_applied = SecurityTaskEvent.objects.filter(task=task, request_id=idempotency_key).exists()
            if already_applied:
                return task

        if task.version != expected_version:
            raise ConcurrentModificationError(
                f"Task {task_id!r} is at version {task.version}, expected {expected_version}."
            )

        if next_status not in TaskStatus.values:
            raise InvalidTransitionError(f"Unregistered status {next_status!r}.")
        allowed = ALLOWED_TRANSITIONS.get(task.status, frozenset())
        if next_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition task {task_id!r} from {task.status!r} to {next_status!r}."
            )

        if next_status in (TaskStatus.DONE, TaskStatus.AWAITING_REVIEW):
            blocking = _unresolved_blocking_predecessors(task)
            if blocking and not override_blocked:
                raise DependencyBlockedError(
                    f"Task {task_id!r} is blocked by {len(blocking)} unresolved predecessor task(s)."
                )

        if completion_source_kind or completion_source_object_id:
            _validate_source_locator(organisation, completion_source_kind or SOURCE_KIND_NONE, completion_source_object_id)

        previous_status = task.status
        task.status = next_status
        task.status_reason = reason or ""
        task.version = task.version + 1
        update_fields = ["status", "status_reason", "version", "updated_at"]

        if next_status in CLOSED_STATUSES:
            task.completed_at = timezone.now()
            if completion_source_kind:
                task.completion_evidence_source_kind = completion_source_kind
                task.completion_evidence_source_object_id = completion_source_object_id
                update_fields += ["completion_evidence_source_kind", "completion_evidence_source_object_id"]
            update_fields.append("completed_at")
        elif previous_status in CLOSED_STATUSES and next_status not in CLOSED_STATUSES:
            # Explicit reopen/restore (M010 data contract §2) - clear the
            # terminal markers rather than leaving a stale completed_at on
            # an active task.
            task.completed_at = None
            task.closed_reason = ""
            update_fields += ["completed_at", "closed_reason"]

        task.save(update_fields=update_fields)

        SecurityTaskEvent.objects.create(
            organisation=organisation,
            task=task,
            action=TaskEventAction.STATUS_CHANGED,
            actor_type=ActorType.HUMAN if getattr(actor, "pk", None) else ActorType.SYSTEM,
            actor_user=actor if getattr(actor, "pk", None) else None,
            previous_status=previous_status,
            new_status=next_status,
            revision=task.version,
            request_id=idempotency_key or "",
            metadata={"reason": reason or "", "override_blocked": bool(override_blocked)},
        )
        return task


def assign_task(organisation, *, actor, task_id, expected_version, assignee_id) -> SecurityTask:
    """Reassign (or unassign, `assignee_id=None`) a task. Same
    select_for_update/expected_version discipline as `transition_task`.
    `assignee_id`'s membership is re-verified live, inside this same
    transaction, never trusted from whatever a caller's form widget
    happened to list (M010 threat model §2's "forged/stale" scenario)."""
    with transaction.atomic():
        task = SecurityTask.objects.select_for_update().filter(pk=task_id, organisation=organisation).first()
        if task is None:
            raise SecurityTask.DoesNotExist(f"No task {task_id!r} in this organisation.")
        if task.version != expected_version:
            raise ConcurrentModificationError(
                f"Task {task_id!r} is at version {task.version}, expected {expected_version}."
            )

        _validate_assignee(organisation, assignee_id)

        task.assigned_to_id = assignee_id
        task.version = task.version + 1
        task.save(update_fields=["assigned_to", "version", "updated_at"])

        SecurityTaskEvent.objects.create(
            organisation=organisation,
            task=task,
            action=TaskEventAction.ASSIGNED,
            actor_type=ActorType.HUMAN if getattr(actor, "pk", None) else ActorType.SYSTEM,
            actor_user=actor if getattr(actor, "pk", None) else None,
            previous_status=task.status,
            new_status=task.status,
            revision=task.version,
            metadata={"assignee_id": str(assignee_id) if assignee_id else None},
        )
        return task


def _reachable(graph: dict, start, target) -> bool:
    """Plain BFS: is `target` reachable from `start` following
    `graph`'s directed edges?"""
    if start == target:
        return True
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbour in graph.get(node, ()):
            if neighbour == target:
                return True
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return False


def link_task_dependency(
    organisation, *, actor, predecessor_id, successor_id, relation_type="blocks"
) -> SecurityTaskDependency:
    """Create a `predecessor_task -> successor_task` dependency edge,
    rejecting self-reference, cross-organisation joins, duplicate edges
    and cycles - ALL inside the same transaction as the write (M010 data
    contract §1/§2), not as a later/best-effort check.

    Cross-org rejection: both task ids are looked up scoped to
    `organisation` in one query; if either id does not resolve to a row
    in THIS organisation (wrong org, or does not exist at all), this
    raises `DependencyCrossOrganisationError` without ever disclosing
    which of the two ids was the problem (non-disclosing, matching this
    codebase's established convention).

    Cycle rejection: every existing dependency edge for this organisation
    is locked (`select_for_update()`) and loaded into an adjacency list;
    adding `predecessor -> successor` would close a cycle exactly when
    `predecessor` is already reachable FROM `successor` in the current
    graph - checked before the new row is inserted. Locking the full
    existing-edge set for the organisation (not just the two endpoint
    tasks) serialises concurrent dependency-graph mutations for the same
    organisation, so two requests that would TOGETHER create a cycle
    cannot both succeed (see test_dependencies.py's concurrency case).
    """
    with transaction.atomic():
        if predecessor_id == successor_id:
            raise DependencySelfReferenceError("A task cannot depend on itself.")

        ordered_ids = sorted([str(predecessor_id), str(successor_id)])
        tasks = {
            str(t.pk): t
            for t in SecurityTask.objects.select_for_update()
            .filter(pk__in=ordered_ids, organisation=organisation)
        }
        if str(predecessor_id) not in tasks or str(successor_id) not in tasks:
            raise DependencyCrossOrganisationError(
                "Both tasks must exist and belong to this organisation."
            )

        existing_edges = list(
            SecurityTaskDependency.objects.select_for_update().filter(organisation=organisation)
        )
        for edge in existing_edges:
            if (
                str(edge.predecessor_task_id) == str(predecessor_id)
                and str(edge.successor_task_id) == str(successor_id)
                and edge.relation_type == relation_type
            ):
                raise DuplicateDependencyError("This dependency edge already exists.")

        graph = defaultdict(list)
        for edge in existing_edges:
            graph[str(edge.predecessor_task_id)].append(str(edge.successor_task_id))

        # Adding predecessor -> successor closes a cycle iff predecessor is
        # already reachable FROM successor in the existing graph.
        if _reachable(graph, str(successor_id), str(predecessor_id)):
            raise DependencyCycleError(
                "This dependency would create a cycle in the task dependency graph."
            )

        dependency = SecurityTaskDependency.objects.create(
            organisation=organisation,
            predecessor_task=tasks[str(predecessor_id)],
            successor_task=tasks[str(successor_id)],
            relation_type=relation_type,
            created_by=actor if getattr(actor, "pk", None) else None,
        )

        for task in (tasks[str(predecessor_id)], tasks[str(successor_id)]):
            SecurityTaskEvent.objects.create(
                organisation=organisation,
                task=task,
                action=TaskEventAction.DEPENDENCY_LINKED,
                actor_type=ActorType.HUMAN if getattr(actor, "pk", None) else ActorType.SYSTEM,
                actor_user=actor if getattr(actor, "pk", None) else None,
                previous_status=task.status,
                new_status=task.status,
                revision=task.version,
                metadata={
                    "predecessor_task_id": str(predecessor_id),
                    "successor_task_id": str(successor_id),
                    "relation_type": relation_type,
                },
            )
        return dependency


__all__ = [
    "DUE_SOON_WINDOW_DAYS",
    "DEFAULT_PAGE_SIZE",
    "DUE_FILTER_OVERDUE",
    "DUE_FILTER_DUE_SOON",
    "TaskPage",
    "TaskDetail",
    "get_task_list",
    "get_task_detail",
    "create_task",
    "transition_task",
    "assign_task",
    "link_task_dependency",
]
