"""
M010A - Shared Security Task Spine: durable, tenant-isolated task
administration (docs/pids/M010A-TASK-SPINE.md, docs/architecture/
M010-DATA-WORKFLOW-CONTRACTS.md §1-§2, docs/architecture/
M010-MASTER-ARCHITECTURE.md §7).

Three models, exactly as the data contract names them:

  - `SecurityTask` - the organisation-shared work item.
  - `SecurityTaskDependency` - a directed "blocks" edge between two tasks
    in the SAME organisation (self-reference, cross-org edges, duplicate
    edges and cycles are all rejected - the DB-level `CheckConstraint`
    below catches self-reference; cross-org/duplicate/cycle rejection
    needs graph/cross-table logic a Postgres CHECK cannot express, so that
    lives in `security_tasks.services.link_task_dependency`, inside the
    same transaction as the write, with its own tests).
  - `SecurityTaskEvent` - an append-only audit trail, written in the same
    transaction as the task mutation it records (never a separate write).

Core invariant this file (and every function in `security_tasks.services`)
must never violate (M010-MASTER-ARCHITECTURE.md §6, M010-DATA-WORKFLOW-
CONTRACTS.md §2): marking a `SecurityTask` `done` is administrative state
only. This app never imports `security_baseline.models.BaselineAnswer`,
`policy.models.PolicyVersion`, `risk_register.models.Risk`, or
`entitlements.metrics` - task completion cannot, by construction, mutate
or even read any of those models' *write* paths. (`security_tasks.
source_registry` reads a handful of those apps' models, read-only, to
resolve a `source_locator` for display - never to establish or change
their state. See that module's own docstring.)

`occurrence_key` vs `idempotency_key` (M010 data contract §1): two
independent dedupe axes, deliberately not collapsed into one field -
  - `occurrence_key` is the deterministic, rules-engine-origin dedupe key
    (M010D's future scheduler derives it from
    source/rule/window-fingerprint); the partial unique constraint below
    enforces "at most one active occurrence per
    (organisation, source_origin, task_kind, occurrence_key)".
  - `idempotency_key` is the client-supplied retry token every
    `create_task` caller (human form submission or future IRENE/rules-
    engine caller) must pass, per M010 data contract §3's service
    signature - "manual_other idempotency uses a separate user-supplied
    idempotency token, not a hardcoded global title dedupe" (§1). The
    second partial unique constraint enforces "at most one row per
    (organisation, idempotency_key)", independent of occurrence_key.
Both are nullable `CharField`s (not blank-string sentinels) specifically
so Postgres's partial `UniqueConstraint(condition=Q(...isnull=False))`
only applies to rows that actually carry one - exactly the same technique
`entitlements.models.ProductArea`'s `parent` self-FK check and this
codebase's other partial-unique precedents use.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from organisations.models import Organisation

# ---------------------------------------------------------------------------
# Enums (M010 data contract §1) - plain TextChoices, never a free string a
# caller could invent. An unregistered/unknown value is rejected by the
# field's own `choices` at form/clean time and, more importantly, by
# `security_tasks.services`' own explicit validation before any write.
# ---------------------------------------------------------------------------


class TaskKind(models.TextChoices):
    FOUNDATION_CONFIRM = "foundation_confirm", "Foundations: confirm an answer"
    FOUNDATION_REMEDIATE = "foundation_remediate", "Foundations: remediate a control"
    RISK_REVIEW = "risk_review", "Risk review"
    REMEDIATION_FOLLOWUP = "remediation_followup", "Remediation follow-up"
    POLICY_REVIEW = "policy_review", "Policy review"
    EVIDENCE_REVIEW = "evidence_review", "Evidence review"
    SUPPLIER_REVIEW = "supplier_review", "Supplier review"
    ASSURANCE_FOLLOWUP = "assurance_followup", "Assurance follow-up"
    MANUAL_OTHER = "manual_other", "Other"


class TaskGroup(models.TextChoices):
    """Versioned, policy-controlled display grouping (M010-MASTER-
    ARCHITECTURE.md §7) - DERIVED from `task_kind` via `group_for_kind`
    below, deliberately never its own stored column, so a group can never
    silently drift out of sync with the kind that determines it (the same
    discipline `risk_register.Risk.score`/`.risk_band` already use for a
    derived, never-stored value)."""

    FOUNDATIONS = "foundations", "Foundations"
    RISKS_ACTIONS = "risks_actions", "Risks & Actions"
    POLICIES = "policies", "Policies"
    EVIDENCE_ASSURANCE = "evidence_assurance", "Evidence & Assurance"
    OTHER = "other", "Other"


TASK_GROUP_BY_KIND: dict[str, str] = {
    TaskKind.FOUNDATION_CONFIRM: TaskGroup.FOUNDATIONS,
    TaskKind.FOUNDATION_REMEDIATE: TaskGroup.FOUNDATIONS,
    TaskKind.RISK_REVIEW: TaskGroup.RISKS_ACTIONS,
    TaskKind.REMEDIATION_FOLLOWUP: TaskGroup.RISKS_ACTIONS,
    TaskKind.POLICY_REVIEW: TaskGroup.POLICIES,
    TaskKind.EVIDENCE_REVIEW: TaskGroup.EVIDENCE_ASSURANCE,
    TaskKind.SUPPLIER_REVIEW: TaskGroup.EVIDENCE_ASSURANCE,
    TaskKind.ASSURANCE_FOLLOWUP: TaskGroup.EVIDENCE_ASSURANCE,
    TaskKind.MANUAL_OTHER: TaskGroup.OTHER,
}


def group_for_kind(task_kind: str) -> str:
    """The one place a `task_kind` becomes a display group. Raises
    `ValueError` for an unregistered kind rather than silently defaulting
    to `OTHER` - a `task_kind` that reaches here without a group mapping
    is a programming error (every `TaskKind` member is mapped above), not
    a request-time condition to paper over."""
    try:
        return TASK_GROUP_BY_KIND[task_kind]
    except KeyError as exc:
        raise ValueError(
            f"Unregistered task_kind {task_kind!r} - no TASK_GROUP_BY_KIND mapping."
        ) from exc


class TaskStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    AWAITING_EXTERNAL = "awaiting_external", "Awaiting external"
    BLOCKED = "blocked", "Blocked"
    AWAITING_REVIEW = "awaiting_review", "Awaiting review"
    DONE = "done", "Done"
    CANCELLED = "cancelled", "Cancelled"


CLOSED_STATUSES = (TaskStatus.DONE, TaskStatus.CANCELLED)

# Exact transition table, M010 data contract §2. `done`/`cancelled` may
# only return to `open` via an explicit reopen/restore action - every
# `transition_task` call already requires a `reason`, so no separate
# "reopen requires extra confirmation" code path is needed: the mandatory
# reason IS that confirmation, recorded on the resulting SecurityTaskEvent.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    TaskStatus.OPEN: frozenset(
        {
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_EXTERNAL,
            TaskStatus.BLOCKED,
            TaskStatus.AWAITING_REVIEW,
            TaskStatus.CANCELLED,
            TaskStatus.DONE,
        }
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {
            TaskStatus.BLOCKED,
            TaskStatus.AWAITING_EXTERNAL,
            TaskStatus.AWAITING_REVIEW,
            TaskStatus.DONE,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.AWAITING_EXTERNAL: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.CANCELLED}
    ),
    TaskStatus.AWAITING_REVIEW: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.CANCELLED}
    ),
    TaskStatus.BLOCKED: frozenset({TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED}),
    TaskStatus.DONE: frozenset({TaskStatus.OPEN}),
    TaskStatus.CANCELLED: frozenset({TaskStatus.OPEN}),
}


class TaskPriority(models.TextChoices):
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class PriorityReason(models.TextChoices):
    """Provenance of the current `priority` value (M010 data contract §1
    - "from deterministic rules or authorised human choice; no LLM-set
    unvalidated urgency"). Not itself an urgency value - just where the
    current one came from."""

    DETERMINISTIC_RULE = "deterministic_rule", "Set by a deterministic rule"
    HUMAN_CHOICE = "human_choice", "Set by a person"
    DEFAULT = "default", "Default (not explicitly set)"


class SourceOrigin(models.TextChoices):
    HUMAN = "human", "Human"
    IRENE = "irene", "IRENE"
    RULES_ENGINE = "rules_engine", "Deterministic rules engine"
    EXISTING_DOMAIN = "existing_domain", "Existing domain record"


class StatusReason(models.TextChoices):
    WORK_STARTED = "work_started", "Work started"
    WAITING_ON_EXTERNAL_PARTY = "waiting_on_external_party", "Waiting on an external party"
    BLOCKED_BY_DEPENDENCY = "blocked_by_dependency", "Blocked by a dependency"
    READY_FOR_REVIEW = "ready_for_review", "Ready for review"
    ADMINISTRATIVE_WORK_COMPLETE = "administrative_work_complete", "Administrative work complete"
    LINKED_RECORD_UPDATED = "linked_record_updated", "Linked record updated elsewhere"
    NO_LONGER_RELEVANT = "no_longer_relevant", "No longer relevant"
    DUPLICATE = "duplicate", "Duplicate of another task"
    REOPENED_NEW_INFORMATION = "reopened_new_information", "Reopened - new information"
    RESTORED = "restored", "Restored from cancelled"
    OTHER = "other", "Other (see note)"


class ClosedReason(models.TextChoices):
    RESOLVED_ADMINISTRATIVELY = "resolved_administratively", "Resolved administratively"
    LINKED_RECORD_UPDATED = "linked_record_updated", "Linked record updated through its own service"
    SUPERSEDED_BY_NEW_OCCURRENCE = "superseded_by_new_occurrence", "Superseded by a new occurrence"
    NOT_APPLICABLE = "not_applicable", "Not applicable"
    DUPLICATE = "duplicate", "Duplicate"
    OTHER = "other", "Other"


class DependencyRelationType(models.TextChoices):
    BLOCKS = "blocks", "Blocks"


class TaskEventAction(models.TextChoices):
    CREATED = "created", "Created"
    STATUS_CHANGED = "status_changed", "Status changed"
    ASSIGNED = "assigned", "Assigned"
    DEPENDENCY_LINKED = "dependency_linked", "Dependency linked"


class ActorType(models.TextChoices):
    HUMAN = "human", "Human"
    IRENE = "irene", "IRENE"
    RULES_ENGINE = "rules_engine", "Deterministic rules engine"
    SYSTEM = "system", "System"


# Sentinel `source_kind`/`completion_evidence_source_kind` value meaning
# "no linked source" - defined here (not in `security_tasks.
# source_registry`) so this module has no import-time dependency on that
# module; `source_registry` imports this constant instead (one-directional,
# no cycle).
SOURCE_KIND_NONE = "none"


class SecurityTaskQuerySet(models.QuerySet):
    def for_organisation(self, organisation):
        return self.filter(organisation=organisation)

    def open_only(self):
        return self.exclude(status__in=CLOSED_STATUSES)


class SecurityTask(models.Model):
    """One organisation-shared work item (M010 data contract §1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="security_tasks"
    )

    task_kind = models.CharField(max_length=32, choices=TaskKind.choices)

    title = models.CharField(max_length=255)
    summary = models.TextField(
        blank=True,
        default="",
        help_text="Bounded, non-sensitive description. Rendered with normal Django auto-escaping - never marked safe.",
    )

    priority = models.CharField(max_length=16, choices=TaskPriority.choices, default=TaskPriority.NORMAL)
    priority_reason = models.CharField(
        max_length=32, choices=PriorityReason.choices, default=PriorityReason.DEFAULT
    )

    status = models.CharField(max_length=32, choices=TaskStatus.choices, default=TaskStatus.OPEN)
    status_reason = models.CharField(max_length=32, choices=StatusReason.choices, blank=True, default="")
    version = models.PositiveIntegerField(
        default=1, help_text="Optimistic-concurrency version. Incremented on every state-changing write."
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_security_tasks",
        help_text="Must be a current member of `organisation` - validated at assignment time, never trusted from a cached grant.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_security_tasks",
    )

    source_origin = models.CharField(max_length=20, choices=SourceOrigin.choices, default=SourceOrigin.HUMAN)
    source_kind = models.CharField(
        max_length=64,
        default=SOURCE_KIND_NONE,
        help_text="A key into security_tasks.source_registry.SOURCE_LOCATOR_REGISTRY, or SOURCE_KIND_NONE.",
    )
    source_object_id = models.CharField(max_length=64, null=True, blank=True)
    source_version = models.CharField(max_length=64, blank=True, default="")

    occurrence_key = models.CharField(max_length=160, null=True, blank=True)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)

    due_at = models.DateTimeField(null=True, blank=True)
    review_window_start_at = models.DateTimeField(null=True, blank=True)
    source_timezone = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="IANA timezone name, only set when due_at was derived from a local/business date.",
    )

    completed_at = models.DateTimeField(null=True, blank=True)
    # "Typed source locator" (M010 data contract §1) for the evidence a
    # completion was based on - same (kind, object_id) shape as the task's
    # own source_locator, resolved through the exact same allowlisted
    # registry, never a free-text/arbitrary reference.
    completion_evidence_source_kind = models.CharField(max_length=64, blank=True, default="")
    completion_evidence_source_object_id = models.CharField(max_length=64, null=True, blank=True)
    closed_reason = models.CharField(max_length=32, choices=ClosedReason.choices, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SecurityTaskQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "status", "due_at"]),
        ]
        constraints = [
            # M010 data contract §1: "unique per (organisation,
            # source_origin, task_kind, occurrence_key) where occurrence_key
            # non-null". Partial (condition=...isnull=False) so the many
            # tasks with no occurrence_key at all never collide with each
            # other.
            models.UniqueConstraint(
                fields=["organisation", "source_origin", "task_kind", "occurrence_key"],
                condition=models.Q(occurrence_key__isnull=False),
                name="securitytask_unique_occurrence_key",
            ),
            # Independent dedupe axis for the client-supplied idempotency
            # token every create_task call carries (see module docstring).
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="securitytask_unique_idempotency_key",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.organisation_id}) [{self.status}]"

    @property
    def task_group(self) -> str:
        return group_for_kind(self.task_kind)

    @property
    def is_closed(self) -> bool:
        return self.status in CLOSED_STATUSES


class SecurityTaskDependency(models.Model):
    """A directed `predecessor_task` -> `successor_task` "blocks" edge
    (M010 data contract §1). Both tasks must belong to the SAME
    organisation - enforced in `security_tasks.services.
    link_task_dependency`, inside the same transaction as the insert (a
    Postgres CHECK constraint cannot reference another row's column, so
    cross-org rejection cannot live here - see that service's docstring).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="security_task_dependencies"
    )
    predecessor_task = models.ForeignKey(
        SecurityTask, on_delete=models.CASCADE, related_name="successor_dependencies"
    )
    successor_task = models.ForeignKey(
        SecurityTask, on_delete=models.CASCADE, related_name="predecessor_dependencies"
    )
    relation_type = models.CharField(
        max_length=16, choices=DependencyRelationType.choices, default=DependencyRelationType.BLOCKS
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_security_task_dependencies",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["predecessor_task", "successor_task", "relation_type"],
                name="securitytaskdependency_unique_edge",
            ),
            # DB-level self-reference guard, mirroring entitlements.models.
            # ProductArea's own "cannot parent itself" CheckConstraint
            # precedent exactly - a backstop against a raw INSERT/future
            # admin surface, not the primary enforcement (the service
            # layer rejects this first, with a clear error).
            models.CheckConstraint(
                condition=~models.Q(predecessor_task=models.F("successor_task")),
                name="securitytaskdependency_no_self_reference",
            ),
        ]

    def __str__(self):
        return f"{self.predecessor_task_id} blocks {self.successor_task_id} ({self.organisation_id})"


class SecurityTaskEvent(models.Model):
    """Append-only audit trail (M010 data contract §1/§6). Written in the
    same transaction as the task mutation it records - see `security_tasks.
    services` for every write path. No `update`/`delete` entrypoint is
    exposed anywhere in this app's service layer or admin registration;
    this is a code-level convention (same as `activity.ActivityEvent`'s own
    "history, not a second source of current truth"), not a DB-level
    immutability trigger."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="security_task_events"
    )
    task = models.ForeignKey(SecurityTask, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=32, choices=TaskEventAction.choices)
    actor_type = models.CharField(max_length=16, choices=ActorType.choices, default=ActorType.HUMAN)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_task_events",
    )
    previous_status = models.CharField(max_length=32, blank=True, default="")
    new_status = models.CharField(max_length=32, blank=True, default="")
    revision = models.PositiveIntegerField(help_text="The task's `version` immediately after this event.")
    request_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="The idempotency key of the request that produced this event, if any.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Small, allowlisted structured detail only - never secrets, raw prose, or provider payloads.",
    )
    event_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_time"]
        indexes = [models.Index(fields=["organisation", "task", "event_time"])]

    def __str__(self):
        return f"{self.action} on {self.task_id} @ {self.event_time}"
