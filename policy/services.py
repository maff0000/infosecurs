"""
Policy draft-generation service (M004 PID §14-15, §22 -
m004-2a-policy-foundation dispatch): the seam between the view layer and
`ai_platform`'s policy-generation contract/gateway/orchestration, mirroring
`risk_register.interpretation_service`'s shape for the equivalent seam on
the second AI task.

`generate_policy_draft` is the single entrypoint the view calls. It:

1. builds this organisation's `PolicyGroundingPayload`
   (`policy.grounding.build_policy_grounding_payload`) - as of the G1
   correction (M006-AUDIT-0002), a bounded structured projection of
   canonical tenant state, not the organisation's own narrative - see that
   module's docstring;
2. calls `ai_platform.policy_orchestration.generate_policy` against
   `ai_platform.prompts.policy_generation_v2.PROMPT_VERSION` (one call, at
   most one bounded retry for a retryable failure only - the same
   discipline `ai_platform.orchestration.generate_risks` /
   `ai_platform.interpretation_orchestration.interpret_candidates` already
   use);
3. on success, creates (or continues) this organisation's
   `PolicyDocument`, and creates a NEW `PolicyVersion`
   (`status=draft`, `generation_source=ai`, ...) - never mutates an
   existing version, so this function alone can never violate the
   immutability guarantee `policy.models.PolicyVersion.save()` enforces.
   The persisted `review_warnings` are the AI's own `result.
   review_warnings` MERGED with a deterministic, application-owned set
   derived from the same canonical `security_state_facts` this call's
   grounding payload already computed (G1 correction §7 - see
   `_deterministic_review_warnings`/`_merge_review_warnings` below) - a
   material unknown/gap is therefore never silently unflagged purely
   because the model itself failed to mention it, which is exactly the gap
   M006-AUDIT-0002's G1 finding exploited (zero review-warning flag
   alongside the fabricated ISO 27001/MFA claim); each persisted entry is
   tagged `source=ai`/`source=deterministic` (H3 correction, M006-AUDIT-0003
   - see `_merge_and_tag_review_warnings`/`compute_current_review_warnings`
   below) so a later approval-time recompute can refresh only the
   deterministic subset against then-current canonical state without ever
   discarding a genuinely AI-authored warning;
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
from ai_platform.policy_contracts import PolicyGenerationResult, PolicyReviewWarning
from ai_platform.policy_orchestration import generate_policy
from ai_platform.prompts.policy_generation_v2 import PROMPT_VERSION
from governance.models import GovernanceRoleAssignment
from security_baseline.models import ANSWER_NO, ANSWER_PARTIAL, ANSWER_UNKNOWN
from security_state.services import LABEL_EVIDENCE_CONFLICT, LABEL_EVIDENCE_STALE

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


# G1 correction §7 (M006-AUDIT-0002): controls whose canonical state is not
# a confirmed "yes" get a deterministic, application-owned review warning -
# never left to depend solely on the model choosing to mention them. Not a
# second/parallel truth system: this reads the exact same
# `security_state_facts` projection `policy.grounding.
# build_policy_grounding_payload` already computed for the AI call itself -
# see that module's docstring for how `assurance_label`/`answer` are
# derived.
_WARNING_TRIGGER_ANSWERS = frozenset({ANSWER_UNKNOWN, ANSWER_PARTIAL, ANSWER_NO})
_WARNING_TRIGGER_ASSURANCE_LABELS = frozenset({LABEL_EVIDENCE_CONFLICT, LABEL_EVIDENCE_STALE})


def _deterministic_review_warnings(security_state_facts: dict) -> list:
    """One `PolicyReviewWarning` per control whose canonical `answer` is
    `unknown`/`partial`/`no`, OR whose `assurance_label` shows an evidence
    conflict/staleness (a materially untrustworthy "yes", even though the
    raw answer itself is confirmed) - deterministic, from already-canonical
    state, never re-deriving control truth itself (G1 correction §7: "Do
    not create a second control-truth system - this is a projection of
    existing canonical state").

    A `not_applicable`/confirmed-`yes`-with-no-conflict control never gets
    one here: `not_applicable` is a genuine customer assessment, not a gap,
    and a clean confirmed `yes` needs no review flag."""
    warnings = []
    for control_key, entry in security_state_facts.items():
        answer = entry.get("answer")
        assurance_label = entry.get("assurance_label")
        if answer not in _WARNING_TRIGGER_ANSWERS and assurance_label not in _WARNING_TRIGGER_ASSURANCE_LABELS:
            continue
        warnings.append(
            PolicyReviewWarning(
                subject=f"{entry.get('area')} - {control_key}",
                detail=(
                    f"Canonical current state: {entry.get('answer_label')} "
                    f"({assurance_label}). This control's implementation is not "
                    "fully confirmed - review before approving this policy."
                ),
            )
        )
    return warnings


# H3 correction (M006-AUDIT-0003, docs/evidence/M006-AUDIT-0003.md): each
# persisted `review_warnings` entry is tagged with WHERE it came from, so a
# later recompute (`compute_current_review_warnings` below - used both by
# the approval-confirmation GET preview and by `_finalise_approval`'s own
# freeze point) can cleanly REPLACE only the deterministic-sourced subset
# with a fresh one derived from CURRENT canonical state, while leaving any
# genuinely AI-authored entry alone. This is a persistence-layer tag only -
# it lives in the plain dict this app stores in `PolicyVersion.
# review_warnings` (a JSONField), not on `ai_platform.policy_contracts.
# PolicyReviewWarning` itself (that contract module is out of scope for
# this correction - see this dispatch's own hard constraints), so nothing
# about the AI response contract changes.
REVIEW_WARNING_SOURCE_AI = "ai"
REVIEW_WARNING_SOURCE_DETERMINISTIC = "deterministic"


def _merge_review_warnings(ai_warnings: list, security_state_facts: dict) -> list:
    """AI-supplied `review_warnings` (list[PolicyReviewWarning]) MERGED
    with the deterministic minimum `_deterministic_review_warnings` above
    computes, so a material unknown/gap is never silently unflagged purely
    because the model didn't mention it (G1 correction §7) - while avoiding
    an obviously duplicate/redundant warning for the same control.

    De-duplication approach (deliberately narrow and conservative, biased
    towards keeping a warning rather than dropping one that might matter -
    corrected after a live run of this exact mechanism, against the
    `several_unknown_baseline_controls` golden-corpus case, caught its own
    first version being too loose: matching against the AI's full warning
    DETAIL prose let one control's incidental phrasing - "...privileged
    access is not currently protected by MFA..." in the AI's
    `mfa_privileged_accounts` warning - falsely swallow the DIFFERENT,
    genuinely-uncovered `privileged_access_separation` control's own
    deterministic warning, purely because that control's `area` label
    ("Privileged access") happened to be a substring of that unrelated
    sentence. Exactly the "silently unflagged" failure class G1 exists to
    prevent - so this now matches ONLY against each AI warning's own short
    `subject` line, never its longer free-form `detail` prose. The
    `control_key` match is the one exception that still uses the AI's
    combined subject+detail text: an underscored slug like
    `device_encryption` is not the kind of phrase natural prose produces
    coincidentally, so it is safe to match wherever the AI wrote it. So: a
    deterministic warning for `control_key`/`area` is skipped only if
    that exact `control_key` appears anywhere in the AI's own combined
    warning text, OR `area` appears in some individual AI warning's own
    `subject` (never its `detail`). This still under-merges in some cases
    (an AI subject phrased very differently from the area label) but can
    no longer over-merge across two different controls whose area labels
    happen to share a common English phrase inside free-running prose."""
    deterministic = _deterministic_review_warnings(security_state_facts)
    ai_combined_text = " ".join(f"{w.subject} {w.detail}" for w in ai_warnings).lower()
    ai_subjects = [w.subject.lower() for w in ai_warnings]

    merged = list(ai_warnings)
    for warning in deterministic:
        area, _, control_key = warning.subject.partition(" - ")
        already_covered = control_key.lower() in ai_combined_text or any(
            area.lower() in subject for subject in ai_subjects
        )
        if already_covered:
            continue
        merged.append(warning)
    return merged


def _merge_and_tag_review_warnings(ai_warnings: list, security_state_facts: dict) -> list:
    """H3 correction: like `_merge_review_warnings` above (reused verbatim,
    not a second warning-truth system), but returns plain, PERSISTENCE-READY
    dicts (`{"subject", "detail", "source"}`) instead of
    `PolicyReviewWarning` instances - `source` is
    `REVIEW_WARNING_SOURCE_AI` for exactly the entries that came from
    `ai_warnings` (matched by `(subject, detail)` - robust to
    `_merge_review_warnings`'s own internal ordering, not merely "the first
    len(ai_warnings) entries"), `REVIEW_WARNING_SOURCE_DETERMINISTIC` for
    every other (i.e. deterministically-added) entry.

    This is the ONE place that decides provenance tagging - both
    `_persist_draft` (AI-generated drafts) and
    `create_new_draft_from_approved` (manual drafts, `ai_warnings=[]`) and
    `compute_current_review_warnings` (approval-time/preview recompute)
    call this, so the tagging rule can never drift between the three call
    sites."""
    merged = _merge_review_warnings(ai_warnings, security_state_facts)
    ai_keys = {(w.subject, w.detail) for w in ai_warnings}
    return [
        {
            "subject": w.subject,
            "detail": w.detail,
            "source": REVIEW_WARNING_SOURCE_AI
            if (w.subject, w.detail) in ai_keys
            else REVIEW_WARNING_SOURCE_DETERMINISTIC,
        }
        for w in merged
    ]


def compute_current_review_warnings(version: PolicyVersion) -> list:
    """H3 correction (M006-AUDIT-0003 finding H3): a pure, NON-MUTATING
    recompute of what `version.review_warnings` should read RIGHT NOW,
    against CURRENT canonical `security_state_facts` - never the stale
    snapshot from whenever this draft happened to be created/last
    generated.

    This is the ONE function both:
      - the approval-confirmation GET view uses to show the customer a
        live, un-persisted preview of current warnings BEFORE they confirm
        approval (Central Architecture's own "the customer must be able to
        see the current warnings before confirming approval" requirement -
        a derived-display approach, no DB write on a plain GET); and
      - `_finalise_approval` uses to compute the value it actually
        persists at the one authoritative freeze point - so what the
        customer previewed is exactly what gets frozen into the approved
        version, never a separately-computed value that could diverge.

    Design for the AI-vs-deterministic tension (see this dispatch's own
    report for the full reasoning): every entry in `version.review_warnings`
    that is NOT explicitly tagged `source=deterministic` is treated as
    "preserve" (a genuinely AI-authored entry, tagged `source=ai` by
    `_merge_and_tag_review_warnings` at draft-generation time - or, for a
    pre-H3 legacy row with no `source` key at all, preserved rather than
    silently discarded, since discarding an unlabelled entry of unknown
    provenance would risk exactly the "AI warnings silently discarded"
    regression this correction must avoid). Only entries explicitly tagged
    `source=deterministic` are dropped here and replaced wholesale by a
    freshly-recomputed deterministic set - this is what lets a
    since-resolved control's stale warning actually disappear (Case 2)
    while a still-open one, or a newly-opened one, is correctly present
    (Case 1 / Case 3), without ever discarding a real AI-authored warning
    (AI-generated-draft regression check)."""
    preserved_warnings = [
        PolicyReviewWarning(subject=w.get("subject", ""), detail=w.get("detail", ""))
        for w in version.review_warnings
        if w.get("source") != REVIEW_WARNING_SOURCE_DETERMINISTIC
    ]
    grounding = build_policy_grounding_payload(version.organisation)
    return _merge_and_tag_review_warnings(preserved_warnings, grounding.security_state_facts)


@transaction.atomic
def _persist_draft(
    organisation, result: PolicyGenerationResult, record, grounding, *, actor
) -> PolicyVersion:
    document, _ = PolicyDocument.objects.get_or_create(organisation=organisation)
    # H3: tagged (source=ai / source=deterministic) so a later approval-time
    # recompute (`compute_current_review_warnings`) can refresh only the
    # deterministic subset without discarding these AI-authored entries.
    review_warnings = _merge_and_tag_review_warnings(
        result.review_warnings, grounding.security_state_facts
    )
    version = PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=_next_version_number(document),
        status=PolicyVersion.STATUS_DRAFT,
        title=result.policy_title,
        sections=[dataclasses.asdict(section) for section in result.sections],
        review_warnings=review_warnings,
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

    return _persist_draft(organisation, result, record, grounding, actor=actor)


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

    H3 correction (M006-AUDIT-0003): this is the ONE authoritative freeze
    point for `review_warnings` too. Before this save persists
    `status=APPROVED`, `review_warnings` is recomputed via
    `compute_current_review_warnings` against CURRENT canonical
    `security_state_facts` - never the stale snapshot from whenever this
    draft happened to be created/generated - so a since-resolved control's
    warning cannot survive into the frozen approved record, a
    newly-appeared gap IS captured, and any genuinely AI-authored warning
    already on this draft is preserved (see that function's own docstring
    for the full reasoning). This write still runs while the row currently
    PERSISTED in the database is `status=draft` (this function's own
    defence-in-depth re-check above already guarantees that), so
    `review_warnings` - one of `PROTECTED_WHILE_APPROVED_FIELDS` - is not
    yet frozen by `PolicyVersion.save()`'s own guard at the moment this
    save runs; once this save completes, it is.
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
    version.review_warnings = compute_current_review_warnings(version)
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

    H3 correction (M006-AUDIT-0003 finding H3): `review_warnings` is NOT
    copied from `version` (the source approved row's own warnings may be
    stale - see this function's own module-level H3 discussion in
    `policy.services`) and is NOT left as `[]` either (the exact defect H3
    names - a customer could edit-and-reapprove a redrafted policy that
    ends up with zero review warnings even though real, unresolved gaps are
    unchanged). Instead a fresh `security_state_facts` projection is taken
    for this organisation RIGHT NOW and the deterministic warnings it
    implies are persisted immediately, tagged
    `source=deterministic` (`_merge_and_tag_review_warnings` with no
    AI-authored input - there is none for a manual copy) - so a customer
    looking at this brand-new draft before making any edits already sees
    an accurate warning set reflecting current canonical state, and
    `_finalise_approval` can later cleanly recompute/replace that
    deterministic subset again at the moment of approval if state has
    moved on since.

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
    grounding = build_policy_grounding_payload(version.organisation)
    new_version = PolicyVersion.objects.create(
        document=document,
        organisation=version.organisation,
        version_number=_next_version_number(document),
        status=PolicyVersion.STATUS_DRAFT,
        title=version.title,
        sections=[dict(section) for section in version.sections],
        review_warnings=_merge_and_tag_review_warnings([], grounding.security_state_facts),
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
    "compute_current_review_warnings",
    "REVIEW_WARNING_SOURCE_AI",
    "REVIEW_WARNING_SOURCE_DETERMINISTIC",
]
