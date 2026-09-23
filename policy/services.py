"""
Policy draft-generation service (M004 PID §14-15, §22 -
m004-2a-policy-foundation dispatch): the seam between the view layer and
`ai_platform`'s policy-generation contract/gateway/orchestration, mirroring
`risk_register.interpretation_service`'s shape for the equivalent seam on
the second AI task.

`generate_policy_draft` is the single entrypoint the view calls. It:

1. builds this organisation's `PolicyGroundingPayload`
   (`policy.grounding.build_policy_grounding_payload`);
2. calls `ai_platform.policy_orchestration.generate_policy` (one call, at
   most one bounded retry for a retryable failure only - the same
   discipline `ai_platform.orchestration.generate_risks` /
   `ai_platform.interpretation_orchestration.interpret_candidates` already
   use);
3. on success, creates (or continues) this organisation's
   `PolicyDocument`, and creates a NEW `PolicyVersion`
   (`status=draft`, `generation_source=ai`, ...) - never mutates an
   existing version, so this function alone can never violate the
   immutability guarantee `policy.models.PolicyVersion.save()` enforces;
4. emits exactly one `policy_draft_generated` `ActivityEvent` (PID §22),
   in the same transaction as the `PolicyDocument`/`PolicyVersion` writes,
   mirroring `workplace.services.create_workplace`'s single-writer-plus-
   same-transaction-event discipline;
5. on failure, raises `ai_platform.policy_orchestration.
   PolicyGenerationFailed` and creates nothing at all - no
   `PolicyDocument`, no `PolicyVersion`, no activity event. This holds
   structurally: `generate_policy` either returns a fully validated
   `PolicyGenerationResult`, or raises before this function ever reaches
   its persistence step (`_persist_draft` below), so there is no
   intermediate state a caller could observe.

The AI call itself (`generate_policy`) deliberately runs OUTSIDE any
`transaction.atomic()` block - it is an external HTTP call, and the
existing `ai_platform.policy_orchestration.generate_policy` already owns
its own `AIInvocationRecord` lifecycle/commits independently of whatever
this function does afterwards (identical pattern to
`risk_register.interpretation_service.interpret_draft_risks`, which does
not wrap its own call to `interpret_candidates` in `atomic()` either).
Only the persistence step that follows a successful call is wrapped, so a
`PolicyDocument`/`PolicyVersion`/`ActivityEvent` write can never partially
apply.
"""
from __future__ import annotations

import dataclasses
import datetime

from django.db import transaction
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_event
from ai_platform.gateway import LiteLLMGateway, PolicyGenerationGateway
from ai_platform.policy_contracts import PolicyGenerationResult
from ai_platform.policy_orchestration import generate_policy
from ai_platform.prompts.policy_generation_v1 import PROMPT_VERSION
from governance.models import GovernanceRoleAssignment

from policy.models import PolicyDocument, PolicyVersion
from policy.grounding import build_policy_grounding_payload


class PolicyLifecycleError(Exception):
    """
    Raised when a policy-lifecycle service function must refuse an
    operation - mirrors `governance.services.GovernanceServiceError` /
    `remediation.services.RemediationServiceError`: a defence-in-depth
    guard the service layer enforces for itself (who may approve, and how)
    rather than trusting the view layer alone (PID §17, ADR-0002 §4.1).
    """


# PID §18 "Default suggested review interval: 12 months". A plain
# calendar-day default (365 days from today), not exact calendar-month
# arithmetic - the dispatch instructions explicitly say this is fine
# ("a plain calendar-day default is fine, no need for exact calendar-month
# arithmetic"), and it keeps this function trivially deterministic with no
# extra calendar-math dependency.
DEFAULT_REVIEW_INTERVAL_DAYS = 365


def default_next_review_date() -> datetime.date:
    return datetime.date.today() + datetime.timedelta(days=DEFAULT_REVIEW_INTERVAL_DAYS)


def get_policy_authoriser(organisation):
    """
    The `governance.OrganisationPerson` currently assigned
    `GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER` for `organisation`,
    or `None` if no assignment exists yet. Explicitly filtered by
    `organisation=organisation` at the ORM call site (same tenant-scoping
    discipline `policy.grounding` already documents for every other
    cross-app read this app performs) - never a bare `.get(pk=...)` on a
    caller-supplied id.
    """
    assignment = (
        GovernanceRoleAssignment.objects.filter(
            organisation=organisation, role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        )
        .select_related("person", "person__user")
        .first()
    )
    return assignment.person if assignment is not None else None


def _next_version_number(document: PolicyDocument) -> int:
    """1 for a brand-new document, else one past this document's highest
    existing `version_number` (PID §15 "1, 2, 3... per document")."""
    latest = document.versions.order_by("-version_number").first()
    return (latest.version_number + 1) if latest is not None else 1


@transaction.atomic
def _persist_draft(organisation, result: PolicyGenerationResult, record, *, actor) -> PolicyVersion:
    document, _ = PolicyDocument.objects.get_or_create(organisation=organisation)
    version = PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=_next_version_number(document),
        status=PolicyVersion.STATUS_DRAFT,
        title=result.policy_title,
        sections=[dataclasses.asdict(section) for section in result.sections],
        review_warnings=[dataclasses.asdict(warning) for warning in result.review_warnings],
        generation_source=PolicyVersion.GENERATION_SOURCE_AI,
        prompt_version=result.prompt_version,
        ai_invocation_record=record,
        created_by=actor,
    )
    record_event(
        organisation,
        ActivityEvent.EVENT_POLICY_DRAFT_GENERATED,
        actor=actor,
        related_object_type="policy_version",
        related_object_id=str(version.id),
        metadata={"version_number": version.version_number},
    )
    return version


def generate_policy_draft(
    organisation, *, actor, gateway: PolicyGenerationGateway = None
) -> PolicyVersion:
    """Run one bounded AI policy-generation call for `organisation` and
    persist the result as a new draft `PolicyVersion`.

    Raises `ai_platform.policy_orchestration.PolicyGenerationFailed` on
    failure - see module docstring point 5: nothing is created in that
    case.

    `gateway` defaults to a real `LiteLLMGateway()` (constructed lazily
    inside this call, not at import time - PID §14: generation happens
    only on an explicit user action, mirroring `LiteLLMGateway`'s own lazy
    config-loading discipline, and `risk_register.interpretation_service.
    interpret_draft_risks`'s identical default). Tests pass
    `ai_platform.testing.FakePolicyGateway` explicitly.
    """
    grounding = build_policy_grounding_payload(organisation)
    gateway = gateway if gateway is not None else LiteLLMGateway()

    result, record = generate_policy(gateway, grounding, PROMPT_VERSION)

    return _persist_draft(organisation, result, record, actor=actor)


@transaction.atomic
def _finalise_approval(
    version: PolicyVersion, *, policy_authoriser, approval_mode, approved_by, next_review_date
) -> PolicyVersion:
    """
    Shared write path for BOTH `approve_policy_directly` and
    `record_external_policy_approval` (PID §17): everything about how an
    approval is persisted lives here exactly once, and the two callers only
    differ in HOW they establish who `policy_authoriser` is allowed to be
    relative to `approved_by` (that eligibility check is each caller's own
    job, not this function's - see each function's docstring).

    Re-confirms `version.status == draft` itself (defence in depth,
    matching `policy.models.PolicyVersion.save()`'s own "look up the
    currently-persisted row, do not trust the in-memory instance" instinct
    for the immutability guard - the analogous guard here is "you cannot
    approve something that is not currently a draft").

    Ordering matters for `PolicyVersion.save()`'s own immutability guard
    (see that method's docstring): this function's `version.save()` call
    below runs while `version`'s row currently PERSISTED in the database is
    still `status=draft` - so the guard does not block this specific
    draft-to-approved transition (confirmed directly against that method's
    logic, and already proven generically by
    `policy/tests/test_models.py::test_draft_to_approved_transition_itself_is_allowed`).
    The PREVIOUS approved version's own `.save()` below only changes
    `status`/`superseded_by` - neither is in
    `PolicyVersion.PROTECTED_WHILE_APPROVED_FIELDS`, so that save is
    allowed too (already proven generically by that same test module's
    `test_non_protected_field_can_still_change_after_approval`).

    Emits `EVENT_POLICY_SUPERSEDED` for the previous approved version (if
    one exists) THEN `EVENT_POLICY_APPROVED` for `version` itself, both
    inside this same transaction - a rolled-back approval attempt therefore
    never leaves an orphaned event of either kind behind.
    """
    if version.status != PolicyVersion.STATUS_DRAFT:
        raise PolicyLifecycleError(
            f"PolicyVersion {version.pk} is {version.status!r}, not 'draft' - only a draft "
            "policy version can be approved."
        )

    previous_approved = (
        version.document.versions.filter(status=PolicyVersion.STATUS_APPROVED)
        .exclude(pk=version.pk)
        .first()
    )

    version.status = PolicyVersion.STATUS_APPROVED
    version.policy_authoriser = policy_authoriser
    version.approval_mode = approval_mode
    version.approved_by = approved_by
    version.approved_at = timezone.now()
    version.next_review_date = next_review_date
    version.save()

    if previous_approved is not None:
        previous_approved.status = PolicyVersion.STATUS_SUPERSEDED
        previous_approved.superseded_by = version
        previous_approved.save()
        record_event(
            version.organisation,
            ActivityEvent.EVENT_POLICY_SUPERSEDED,
            actor=approved_by,
            related_object_type="policy_version",
            related_object_id=str(previous_approved.id),
            metadata={"superseded_by_version_number": version.version_number},
        )

    record_event(
        version.organisation,
        ActivityEvent.EVENT_POLICY_APPROVED,
        actor=approved_by,
        related_object_type="policy_version",
        related_object_id=str(version.id),
        metadata={"version_number": version.version_number, "approval_mode": approval_mode},
    )
    return version


def approve_policy_directly(version: PolicyVersion, *, actor, next_review_date) -> PolicyVersion:
    """
    PID §17.1 / ADR-0002 §4.1: the acting `User` IS the currently-assigned
    Policy Authoriser (`get_policy_authoriser(...).user == actor`).

    Raises `PolicyLifecycleError` - and writes nothing - if no Policy
    Authoriser is currently assigned, or if the assigned person's linked
    `user` is not `actor`. This is the service-layer half of the
    honesty distinction ADR-0002 §4.1 requires: it is structurally
    impossible for this function to record a "direct" approval for anyone
    other than the actual logged-in Policy Authoriser, regardless of what a
    view/caller passes.
    """
    person = get_policy_authoriser(version.organisation)
    if person is None:
        raise PolicyLifecycleError(
            "No Policy Authoriser is currently assigned for this organisation."
        )
    if person.user_id is None or person.user_id != actor.id:
        raise PolicyLifecycleError(
            "Direct approval requires the acting user to be the currently assigned "
            "Policy Authoriser."
        )
    return _finalise_approval(
        version,
        policy_authoriser=person,
        approval_mode=PolicyVersion.APPROVAL_MODE_DIRECT,
        approved_by=actor,
        next_review_date=next_review_date,
    )


def record_external_policy_approval(
    version: PolicyVersion, *, actor, next_review_date
) -> PolicyVersion:
    """
    PID §17.2 / ADR-0002 §4.1: the currently-assigned Policy Authoriser is a
    DIFFERENT named `governance.OrganisationPerson` - either with no login
    at all (`person.user is None`) or with a login that is not `actor`. The
    Account Holder (`actor`) is recording that approval was obtained
    outside Infosecurs; they are never recorded as having approved on the
    authoriser's behalf, and the authoriser is never recorded as having
    logged in.

    Raises `PolicyLifecycleError` - and writes nothing - if no Policy
    Authoriser is assigned, or if the assigned person IS `actor` (that case
    is `approve_policy_directly`'s job - this function refuses to silently
    fall back to recording an external approval when a direct one was the
    true case, per the dispatch's explicit instruction: "never silently
    fall back to recording an external approval when a direct one was
    attempted").
    """
    person = get_policy_authoriser(version.organisation)
    if person is None:
        raise PolicyLifecycleError(
            "No Policy Authoriser is currently assigned for this organisation."
        )
    if person.user_id is not None and person.user_id == actor.id:
        raise PolicyLifecycleError(
            "The assigned Policy Authoriser is the acting user - use direct approval instead "
            "of recording an external approval."
        )
    return _finalise_approval(
        version,
        policy_authoriser=person,
        approval_mode=PolicyVersion.APPROVAL_MODE_EXTERNAL_RECORDED,
        approved_by=actor,
        next_review_date=next_review_date,
    )


@transaction.atomic
def create_new_draft_from_approved(version: PolicyVersion, *, actor) -> PolicyVersion:
    """
    PID §15 "later create a new draft/version without overwriting the
    previously approved version" / PID §16's only path to changing an
    approved policy's content (there is no direct-edit-in-place path for a
    non-draft version - see `policy.views.policy_edit`'s draft-only gate).

    `version` (the source) must currently be `status=approved` - raises
    `PolicyLifecycleError` otherwise (e.g. refusing to "fork" a draft or a
    superseded version; a superseded version's own successor already
    exists via `superseded_by`, and forking a superseded version instead of
    the current approved one would silently orphan the real current
    policy).

    The new `PolicyVersion` is a PLAIN COPY of `version`'s `title`/
    `sections` - not a reference of any kind - `sections=list(...)` copies
    the outer list, and each element is itself a fresh dict, not the same
    object `version.sections` holds, so subsequent edits to the new draft
    (via `policy.views.policy_edit`) can never mutate `version`'s own
    persisted content; independently, `PolicyVersion.save()`'s own
    immutability guard would also reject any such mutation attempt against
    the source row directly.

    `generation_source=GENERATION_SOURCE_MANUAL`, no `ai_invocation_record`,
    no `prompt_version` carried over - this is deliberately NOT recorded as
    an AI-generated draft (see that constant's own docstring in
    `policy.models`). Emits `EVENT_POLICY_NEW_DRAFT_CREATED` (NOT
    `EVENT_POLICY_DRAFT_GENERATED` - see that event's docstring in
    `activity.models` for why the two are kept distinct).
    """
    if version.status != PolicyVersion.STATUS_APPROVED:
        raise PolicyLifecycleError(
            f"PolicyVersion {version.pk} is {version.status!r}, not 'approved' - a new draft "
            "can only be created from the currently approved policy version."
        )

    document = version.document
    new_version = PolicyVersion.objects.create(
        document=document,
        organisation=version.organisation,
        version_number=_next_version_number(document),
        status=PolicyVersion.STATUS_DRAFT,
        title=version.title,
        sections=[dict(section) for section in version.sections],
        review_warnings=[],
        generation_source=PolicyVersion.GENERATION_SOURCE_MANUAL,
        prompt_version="",
        created_by=actor,
    )
    record_event(
        version.organisation,
        ActivityEvent.EVENT_POLICY_NEW_DRAFT_CREATED,
        actor=actor,
        related_object_type="policy_version",
        related_object_id=str(new_version.id),
        metadata={
            "version_number": new_version.version_number,
            "source_version_number": version.version_number,
        },
    )
    return new_version


__all__ = [
    "generate_policy_draft",
    "PolicyLifecycleError",
    "DEFAULT_REVIEW_INTERVAL_DAYS",
    "default_next_review_date",
    "get_policy_authoriser",
    "approve_policy_directly",
    "record_external_policy_approval",
    "create_new_draft_from_approved",
]
