"""
M010D - Deterministic Security Review Scheduler: the rule registry
(docs/pids/M010D-REVIEW-RULES-SCHEDULER.md §1-§2, docs/architecture/
M010-DATA-WORKFLOW-CONTRACTS.md §5, M010-MASTER-ARCHITECTURE.md §7).

This module is PURE candidate computation only. No model is ever written
here, no `SecurityTask` is created here, and no organisation other than
the one a caller passes in is ever queried (every rule function takes an
already-resolved `organisation` object and filters every queryset by it
explicitly - never a cross-tenant query). Task emission, dedupe and
reconciliation live in `security_tasks.review_scheduler`, which is the
only module that calls `security_tasks.services.create_task`/
`transition_task` with these candidates.

Inventory (PID §1 "inventory live domain fields and services before
code", re-verified directly against the real models in this repository,
not assumed from any prior summary):

  - ENABLED `policy_review` - `policy.models.PolicyVersion.next_review_date`
    (`DateField`, nullable). A genuine, real review-date field.
  - ENABLED `remediation_followup` - `remediation.models.RemediationAction.
    target_date` (`DateField`, nullable). A genuine, real deadline field.
  - ENABLED `evidence_review` - `evidence.models.EvidenceItem.valid_until`
    (`DateField`, nullable). A genuine, real expiry field.
  - DISABLED `risk_review` - `risk_register.models.Risk` has NO review-
    date-shaped field at all: only `confirmed_at`/`dismissed_at`/
    `created_at`/`updated_at` (all `DateTimeField`s recording when
    something already happened, none a future due date). This package
    does NOT invent a review cadence (e.g. "N months after
    confirmed_at") - no such cadence is authorised by the PID. See
    `REGISTERED_RULES["risk_review"].disabled_reason` and
    `docs/evidence/M010D-REVIEW-SCHEDULER.md`.
  - DISABLED `supplier_review` - no supplier/vendor-management Django app
    exists anywhere in this repository (confirmed directly: no
    `supplier*` top-level app directory, no model named anything
    supplier-shaped). PID §1's own condition ("only if supplier module
    exists and offers a canonical date") is not met.
  - DISABLED `foundations_recurrence` - no Foundations re-confirmation
    due-date field exists either. `security_baseline.models` has no field
    representing a future "re-confirm this control by" date (checked
    directly: only `created_at`/`updated_at`/`recorded_at`, all
    DateTimeFields recording the past, never a future due date), and
    `entitlements.models` has no date field at all. No rule is registered
    for this at all (not merely disabled) - there is nothing to point a
    disabled rule at.

Warning-window numbers (M010 data contract §5: "Starter warning windows
30 days, 7 days and overdue are configurable defaults requiring product
approval at implementation, not a statement that every domain currently
has a due date"): used here as the working default, exactly as that
sentence licenses, but NO product approval has been recorded for this
package - this is the same disclosed-placeholder discipline Work Package
C already used for its own AI-budget placeholders. See the evidence
document.

Business timezone (M010 data contract §5: "business dates interpreted in
organisation-configured IANA timezone or configured Europe/London default
if explicitly confirmed"): `organisations.models.Organisation` has no
timezone field at all (checked directly), so no per-organisation IANA
timezone can be read. `Europe/London` is used as a single, global working
default below - again disclosed, not "explicitly confirmed" by product,
exactly like the warning-window numbers.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from zoneinfo import ZoneInfo

from security_tasks.models import TaskKind
from security_tasks.source_registry import (
    SOURCE_KIND_EVIDENCE_ITEM,
    SOURCE_KIND_POLICY_VERSION,
    SOURCE_KIND_REMEDIATION_ACTION,
)

# --- Disclosed, unapproved placeholders (see module docstring) -------------
BUSINESS_TIMEZONE = ZoneInfo("Europe/London")

WARNING_WINDOW_30_DAYS = 30
WARNING_WINDOW_7_DAYS = 7

WINDOW_OVERDUE = "overdue"
WINDOW_DUE_7D = "due_7d"
WINDOW_DUE_30D = "due_30d"
WINDOW_FUTURE = "future"

RULE_ID_POLICY_REVIEW = "policy_review"
RULE_ID_REMEDIATION_FOLLOWUP = "remediation_followup"
RULE_ID_EVIDENCE_REVIEW = "evidence_review"
RULE_ID_RISK_REVIEW = "risk_review"
RULE_ID_SUPPLIER_REVIEW = "supplier_review"


@dataclasses.dataclass(frozen=True)
class ReviewCandidate:
    """One due-candidate for one source object in one organisation. Never
    persisted directly - `security_tasks.review_scheduler` turns this into
    a `create_task` call."""

    rule_id: str
    rule_version: int
    organisation_id: object
    task_kind: str
    source_kind: str
    source_object_id: str
    due_at: dt.datetime  # UTC-aware
    due_occurrence: str  # the source DateField's own ISO date string
    window: str
    title: str
    owner_user_id: object | None  # candidate owner - NOT yet membership-verified


def due_at_from_local_date(local_date: dt.date) -> dt.datetime:
    """Midnight, `BUSINESS_TIMEZONE`, on `local_date`, converted to a
    UTC-aware `datetime` (M010 data contract §5: "DST fold/gap rules must
    be tested, not guessed" - see `security_tasks/tests/
    test_review_rules.py`'s explicit spring-forward/autumn-back/UTC-
    midnight cases). `fold=0` (the default) is used deliberately and
    explicitly - this is never ambiguous for a UK business-midnight
    instant in practice (both UK DST transitions happen at 01:00 local,
    never at midnight), but the explicit, tested conversion through
    `zoneinfo` (never naive UTC arithmetic on the date alone) is what
    makes that true by construction rather than by luck."""
    local_midnight = dt.datetime(
        local_date.year, local_date.month, local_date.day, 0, 0, 0, tzinfo=BUSINESS_TIMEZONE, fold=0
    )
    return local_midnight.astimezone(dt.timezone.utc)


def warning_window_for(due_at: dt.datetime, *, now: dt.datetime) -> str:
    """Bucket `due_at` relative to `now` - both UTC-aware `datetime`s, so
    the arithmetic is exact elapsed wall-clock time regardless of any DST
    transition the [now, due_at] interval happens to cross (never a naive
    calendar-day subtraction)."""
    if due_at < now:
        return WINDOW_OVERDUE
    if due_at <= now + dt.timedelta(days=WARNING_WINDOW_7_DAYS):
        return WINDOW_DUE_7D
    if due_at <= now + dt.timedelta(days=WARNING_WINDOW_30_DAYS):
        return WINDOW_DUE_30D
    return WINDOW_FUTURE


def _candidate_from_date(
    *,
    rule_id,
    rule_version,
    organisation_id,
    task_kind,
    source_kind,
    source_object_id,
    local_date: dt.date | None,
    now: dt.datetime,
    title: str,
    owner_user_id,
) -> ReviewCandidate | None:
    """Shared candidate-building step. Returns `None` - never a fabricated
    date - when `local_date` is falsy (M010D non-negotiable constraint:
    "Never fabricate a due date... simply skipped by that rule for that
    object")."""
    if local_date is None:
        return None
    due_at = due_at_from_local_date(local_date)
    return ReviewCandidate(
        rule_id=rule_id,
        rule_version=rule_version,
        organisation_id=organisation_id,
        task_kind=task_kind,
        source_kind=source_kind,
        source_object_id=str(source_object_id),
        due_at=due_at,
        due_occurrence=local_date.isoformat(),
        window=warning_window_for(due_at, now=now),
        title=title,
        owner_user_id=owner_user_id,
    )


def rule_policy_review(organisation, *, now: dt.datetime, rule_version: int = 1) -> list[ReviewCandidate]:
    """`policy.models.PolicyVersion.next_review_date` - only the current,
    APPROVED version of a document is eligible (PID required scenario
    "superseded-policy-version" must be SKIPPED, never re-reviewed; a
    `draft` version has not yet been confirmed into force either, so it
    is excluded too - only `approved` represents the policy currently in
    effect for this organisation).

    Owner: deliberately left `None` (unassigned queue) for every
    candidate. `PolicyVersion.policy_authoriser` is a `governance.
    OrganisationPerson` record, not necessarily a logged-in
    `AUTH_USER_MODEL` account with current organisation membership - this
    package does not guess a mapping between the two that the PID never
    specified, applying the exact same "do not invent" discipline to
    ownership that §1 mandates for due dates."""
    from policy.models import PolicyVersion

    candidates = []
    queryset = PolicyVersion.objects.filter(
        organisation=organisation,
        status=PolicyVersion.STATUS_APPROVED,
        next_review_date__isnull=False,
    ).select_related("document")
    for version in queryset:
        candidate = _candidate_from_date(
            rule_id=RULE_ID_POLICY_REVIEW,
            rule_version=rule_version,
            organisation_id=organisation.id,
            task_kind=TaskKind.POLICY_REVIEW,
            source_kind=SOURCE_KIND_POLICY_VERSION,
            source_object_id=version.id,
            local_date=version.next_review_date,
            now=now,
            title=f"Review policy: {version.title}",
            owner_user_id=None,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def rule_remediation_followup(organisation, *, now: dt.datetime, rule_version: int = 1) -> list[ReviewCandidate]:
    """`remediation.models.RemediationAction.target_date` - only actions
    still in `ACTIVE_STATUSES` (`open`/`in_progress`) are eligible (PID
    required scenario "already-completed-source" must be SKIPPED: a
    `done`/`accepted` action needs no follow-up task).

    Owner: `RemediationAction.assigned_to_id`, if set - the ONE field in
    this package's three source models that genuinely means "the person
    already working this" (M010-DATA-WORKFLOW-CONTRACTS.md §5 "Task owner
    assigned from existing source owner only if authorised member;
    otherwise unassigned queue"). Live-membership re-verification happens
    in `review_scheduler`, not here - this module only reports the
    candidate owner it found on the source row."""
    from remediation.models import RemediationAction

    candidates = []
    queryset = RemediationAction.objects.filter(
        organisation=organisation,
        status__in=RemediationAction.ACTIVE_STATUSES,
        target_date__isnull=False,
    )
    for action in queryset:
        candidate = _candidate_from_date(
            rule_id=RULE_ID_REMEDIATION_FOLLOWUP,
            rule_version=rule_version,
            organisation_id=organisation.id,
            task_kind=TaskKind.REMEDIATION_FOLLOWUP,
            source_kind=SOURCE_KIND_REMEDIATION_ACTION,
            source_object_id=action.id,
            local_date=action.target_date,
            now=now,
            title=f"Follow up remediation action: {action.title}",
            owner_user_id=action.assigned_to_id,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def rule_evidence_review(organisation, *, now: dt.datetime, rule_version: int = 1) -> list[ReviewCandidate]:
    """`evidence.models.EvidenceItem.valid_until` - only `status=active`
    items are eligible (a `superseded`/`withdrawn` item is no longer the
    organisation's current evidence for anything; reviewing its expiry is
    moot, the same "already-completed-source"-shaped skip
    `rule_remediation_followup` applies for its own status field).

    Owner: deliberately left `None` (unassigned queue). `EvidenceItem.
    recorded_by` records who HISTORICALLY uploaded/recorded the item, not
    who is responsible for renewing it going forward - treating it as an
    "owner" would be a guess the PID never authorised, so (matching
    `rule_policy_review`'s identical reasoning) this rule does not make
    that guess."""
    from evidence.models import EvidenceItem

    candidates = []
    queryset = EvidenceItem.objects.filter(
        organisation=organisation,
        status=EvidenceItem.STATUS_ACTIVE,
        valid_until__isnull=False,
    )
    for item in queryset:
        candidate = _candidate_from_date(
            rule_id=RULE_ID_EVIDENCE_REVIEW,
            rule_version=rule_version,
            organisation_id=organisation.id,
            task_kind=TaskKind.EVIDENCE_REVIEW,
            source_kind=SOURCE_KIND_EVIDENCE_ITEM,
            source_object_id=item.id,
            local_date=item.valid_until,
            now=now,
            title=f"Review evidence before it expires: {item.title}",
            owner_user_id=None,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


@dataclasses.dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    task_kind: str | None
    enabled: bool
    function: object | None  # Callable[[organisation, now, rule_version], list[ReviewCandidate]] | None
    disabled_reason: str = ""


REGISTERED_RULES: dict[str, RuleSpec] = {
    RULE_ID_POLICY_REVIEW: RuleSpec(
        rule_id=RULE_ID_POLICY_REVIEW,
        task_kind=TaskKind.POLICY_REVIEW,
        enabled=True,
        function=rule_policy_review,
    ),
    RULE_ID_REMEDIATION_FOLLOWUP: RuleSpec(
        rule_id=RULE_ID_REMEDIATION_FOLLOWUP,
        task_kind=TaskKind.REMEDIATION_FOLLOWUP,
        enabled=True,
        function=rule_remediation_followup,
    ),
    RULE_ID_EVIDENCE_REVIEW: RuleSpec(
        rule_id=RULE_ID_EVIDENCE_REVIEW,
        task_kind=TaskKind.EVIDENCE_REVIEW,
        enabled=True,
        function=rule_evidence_review,
    ),
    RULE_ID_RISK_REVIEW: RuleSpec(
        rule_id=RULE_ID_RISK_REVIEW,
        task_kind=TaskKind.RISK_REVIEW,
        enabled=False,
        function=None,
        disabled_reason=(
            "risk_register.models.Risk has no review-date-shaped field at all - only "
            "confirmed_at/dismissed_at/created_at/updated_at (all DateTimeFields recording "
            "when something already happened, none a future due date). No review cadence "
            "(e.g. 'N months after confirmed_at') is invented - the PID never authorised one."
        ),
    ),
    RULE_ID_SUPPLIER_REVIEW: RuleSpec(
        rule_id=RULE_ID_SUPPLIER_REVIEW,
        task_kind=TaskKind.SUPPLIER_REVIEW,
        enabled=False,
        function=None,
        disabled_reason=(
            "No supplier/vendor-management Django app exists anywhere in this repository "
            "(confirmed directly - no 'supplier*' top-level app directory). PID §1's own "
            "condition ('only if supplier module exists and offers a canonical date') is not met."
        ),
    ),
    # No foundations_recurrence entry: there is no Foundations re-confirmation
    # due-date field anywhere to point a rule at (security_baseline.models has
    # only created_at/updated_at/recorded_at; entitlements.models has no date
    # field at all) - and no SecurityTask.TaskKind member exists for it
    # either, so there is nothing to even register as disabled. See module
    # docstring and docs/evidence/M010D-REVIEW-SCHEDULER.md.
}


def evaluate_organisation(organisation, *, now: dt.datetime | None = None) -> list[ReviewCandidate]:
    """Run every ENABLED rule for exactly one organisation and return the
    combined candidate list. Never queries any other organisation - every
    rule function above filters by `organisation=organisation` explicitly
    (M010D PID §5 "no cross-tenant aggregation into one query")."""
    if now is None:
        from django.utils import timezone as django_timezone

        now = django_timezone.now()
    candidates: list[ReviewCandidate] = []
    for spec in REGISTERED_RULES.values():
        if not spec.enabled or spec.function is None:
            continue
        candidates.extend(spec.function(organisation, now=now))
    return candidates


__all__ = [
    "BUSINESS_TIMEZONE",
    "WARNING_WINDOW_30_DAYS",
    "WARNING_WINDOW_7_DAYS",
    "WINDOW_OVERDUE",
    "WINDOW_DUE_7D",
    "WINDOW_DUE_30D",
    "WINDOW_FUTURE",
    "RULE_ID_POLICY_REVIEW",
    "RULE_ID_REMEDIATION_FOLLOWUP",
    "RULE_ID_EVIDENCE_REVIEW",
    "RULE_ID_RISK_REVIEW",
    "RULE_ID_SUPPLIER_REVIEW",
    "ReviewCandidate",
    "RuleSpec",
    "REGISTERED_RULES",
    "due_at_from_local_date",
    "warning_window_for",
    "rule_policy_review",
    "rule_remediation_followup",
    "rule_evidence_review",
    "evaluate_organisation",
]
