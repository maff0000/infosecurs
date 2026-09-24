"""
Organisation Overview / journey-state derivation (M006 PID §6).

`build_overview(organisation)` is the single entry point: it returns one
dict per area listed in PID §6 (`Organisation setup`, `Security baseline`,
`Assets`, `Risks`, `Evidence`, `Remediation`, `Security state`,
`Governance / workplace`, `Policy`, `Questionnaire assurance`), each
carrying a deterministic `state` computed FRESH from real rows on every
call - never a second, independently editable status store (PID §6's core
invariant, "Overview is derived truth, not a second store").

This mirrors the "derive from real rows, never cache a verdict" discipline
`security_state.services.get_security_state` already applies to its own
projection (see that module's docstring) - `build_overview` is a thin
read-only aggregation over the SAME models that discipline already
protects, plus a handful of other domains' own models. It writes nothing
anywhere, ever.

Deliberately not every area reaches every one of the four states
(`Not started` / `Needs attention` / `In progress` / `Ready`) - PID §6
itself anticipates this ("Not every area needs to be capable of reaching
every state if that state genuinely doesn't make sense for that domain").
Each area function's own docstring explains which states it can reach and
why; the two areas PID's own dispatch instructions ask to be worked out in
full rigour first - Organisation setup and Policy - have the most detailed
reasoning, and every other area follows the same discipline at a shorter
length.

No maturity percentage, no numeric security grade, no compliance score
anywhere in this module (PID §6's other explicit non-goals) - every
`state` is one of the four named strings below and nothing else.
"""
from __future__ import annotations

import datetime

from django.urls import reverse

from evidence.models import EvidenceItem
from governance.models import GovernanceRoleAssignment
from key_assets.models import KeyAsset
from organisations.models import UNKNOWN, OrganisationProfile
from policy.models import PolicyVersion
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from remediation.models import RemediationAction
from risk_register.models import BAND_CRITICAL, BAND_HIGH, Risk
from security_baseline.catalogue import CATALOGUE
from security_baseline.models import ANSWER_UNKNOWN, BaselineAssessment
from security_state.services import (
    LABEL_EVIDENCE_CONFLICT,
    LABEL_EVIDENCE_STALE,
    LABEL_NOT_CONFIRMED,
    get_security_state,
)
from workplace.models import Workplace

# ---------------------------------------------------------------------------
# The four states PID §6 permits, and nothing else.
# ---------------------------------------------------------------------------
STATE_NOT_STARTED = "not_started"
STATE_NEEDS_ATTENTION = "needs_attention"
STATE_IN_PROGRESS = "in_progress"
STATE_READY = "ready"

STATE_LABELS = {
    STATE_NOT_STARTED: "Not started",
    STATE_NEEDS_ATTENTION: "Needs attention",
    STATE_IN_PROGRESS: "In progress",
    STATE_READY: "Ready",
}


def _area(
    *,
    key: str,
    title: str,
    state: str,
    detail: str,
    next_action_url_name: str,
    organisation_id,
    next_action_label: str,
    count: int | None = None,
) -> dict:
    """
    Shared shape every area function below returns: one dict with exactly
    these keys. `next_action_url` is resolved here (via `reverse`) so the
    Overview template never needs to know each area's own URL scheme -
    only the ONE clear next-action link PID §6 asks for ("Give the
    customer one clear next action where practical").
    """
    return {
        "key": key,
        "title": title,
        "state": state,
        "state_label": STATE_LABELS[state],
        "detail": detail,
        "count": count,
        "next_action_url": reverse(next_action_url_name, args=[organisation_id]),
        "next_action_label": next_action_label,
    }


# ---------------------------------------------------------------------------
# Worked example 1 of 2 (dispatch instructions): Organisation setup.
# ---------------------------------------------------------------------------
# The load-bearing fact fields below are exactly the `OrganisationProfile`
# fields that (a) default to the explicit "unknown" tri-state/enum value
# (organisations/models.py's UNKNOWN discipline) AND (b) the customer
# actually confirms directly on the profile form. Two categories of field
# are deliberately EXCLUDED from this "must be confirmed to reach Ready"
# set, both judgment calls made explicit here rather than silently assumed:
#
#   - `working_model`: once any `workplace.Workplace` row exists it becomes
#     a derived, read-only summary (organisations.forms.
#     OrganisationProfileForm's own docstring/`save()`) - it is no longer
#     something the customer confirms on THIS page at all, so it cannot be
#     a load-bearing fact for Organisation setup specifically. Whether
#     workplaces have been recorded is the Governance/workplace area's job.
#   - `cyber_essentials_status` / `iso27001_status`: genuinely optional
#     assurance-context facts - an organisation may legitimately have no
#     certification and no plan to pursue one; leaving these "not
#     confirmed" is not a gap that should block Ready.
#   - `description` / `commercial_security_driver`: free text, optional at
#     the model layer itself (`blank=True`), never a tri-state/enum fact.
#
# `staff_count` is included even though it is a plain nullable integer
# (not a choices field with an "unknown" sentinel) - PID §6's own example
# for this area is headcount-shaped ("Organisation setup"), and a
# genuinely unset headcount is exactly the same kind of "not yet
# confirmed" gap as an unconfirmed enum field.
_ORGANISATION_SETUP_LOAD_BEARING_FIELDS = [
    "endpoint_management",
    "productivity_platform",
    "primary_cloud_provider",
    "develops_hosts_own_software",
    "handles_personal_data",
    "handles_confidential_business_data",
    "handles_payment_card_data",
    "handles_special_category_data",
    "receives_security_questionnaires",
]


def _organisation_setup_area(organisation) -> dict:
    """
    Not started: no `OrganisationProfile` row exists yet.
    In progress: a profile exists but at least one load-bearing fact above
        (or `staff_count`) is still unconfirmed.
    Ready: a profile exists and every load-bearing fact has been confirmed.

    `Needs attention` deliberately never applies to this area (this is the
    judgment call the dispatch instructions ask to be worked out
    explicitly): profile completeness is linear progress toward Ready,
    with no separate failure/warning condition a static setup form can
    surface on its own. A concerning FACT the profile records - e.g.
    "handles payment card data: yes" with no controls yet - is a reason
    for the Risk or Security state areas to show concern, not this one;
    Organisation setup only ever asks "has this been confirmed", never
    "is this concerning".
    """
    profile = OrganisationProfile.objects.filter(organisation=organisation).first()
    if profile is None:
        return _area(
            key="organisation_setup",
            title="Organisation setup",
            state=STATE_NOT_STARTED,
            detail="No organisation profile has been started yet.",
            next_action_url_name="organisations:profile",
            organisation_id=organisation.id,
            next_action_label="Start profile",
        )

    unconfirmed = [
        field_name
        for field_name in _ORGANISATION_SETUP_LOAD_BEARING_FIELDS
        if getattr(profile, field_name) == UNKNOWN
    ]
    if profile.staff_count is None:
        unconfirmed.append("staff_count")

    if unconfirmed:
        return _area(
            key="organisation_setup",
            title="Organisation setup",
            state=STATE_IN_PROGRESS,
            detail=f"{len(unconfirmed)} profile fact(s) still not confirmed.",
            next_action_url_name="organisations:profile",
            organisation_id=organisation.id,
            next_action_label="Finish profile",
            count=len(unconfirmed),
        )

    return _area(
        key="organisation_setup",
        title="Organisation setup",
        state=STATE_READY,
        detail="The organisation profile is complete.",
        next_action_url_name="organisations:profile",
        organisation_id=organisation.id,
        next_action_label="Review profile",
    )


def _security_baseline_area(organisation) -> dict:
    """
    Not started: no `BaselineAssessment` row exists.
    In progress: an assessment exists but not every catalogue question has
        been given a non-"unknown" answer yet.
    Ready: every catalogue question has an answer - a deliberate "no" or
        "not applicable" is a real, complete answer, not a gap.

    `Needs attention` does not apply here either, for the same reason as
    Organisation setup: a fully-answered baseline full of "no" answers is
    not a failure of THIS area - it is simply complete, honest input. Any
    consequence of a "no" answer belongs to Security state (assurance
    labels, below) and Risk, not to the completion step itself.
    """
    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    if assessment is None:
        return _area(
            key="security_baseline",
            title="Security baseline",
            state=STATE_NOT_STARTED,
            detail="The security baseline has not been started.",
            next_action_url_name="security_baseline:baseline",
            organisation_id=organisation.id,
            next_action_label="Start security baseline",
        )

    answers = {a.question_key: a.answer for a in assessment.answers.all()}
    total = len(CATALOGUE)
    answered = sum(
        1
        for item in CATALOGUE
        if answers.get(item["key"], ANSWER_UNKNOWN) != ANSWER_UNKNOWN
    )

    if answered < total:
        return _area(
            key="security_baseline",
            title="Security baseline",
            state=STATE_IN_PROGRESS,
            detail=f"{answered} of {total} baseline questions answered.",
            next_action_url_name="security_baseline:baseline",
            organisation_id=organisation.id,
            next_action_label="Continue security baseline",
            count=total - answered,
        )

    return _area(
        key="security_baseline",
        title="Security baseline",
        state=STATE_READY,
        detail=f"All {total} baseline questions have been answered.",
        next_action_url_name="security_baseline:baseline",
        organisation_id=organisation.id,
        next_action_label="Review security baseline",
    )


def _assets_area(organisation) -> dict:
    """
    Not started: no `KeyAsset` row exists.
    In progress: at least one deterministic starter suggestion is still
        awaiting the customer's confirm/edit/dismiss decision.
    Ready: no suggestions remain unreviewed (every row is confirmed or
        dismissed).

    `Needs attention` does not apply: an asset list with zero confirmed
    assets but all suggestions reviewed is still a real, complete customer
    decision ("none of these are key assets") - curating the starter list
    is a review step, not a step that can fail.
    """
    assets = list(KeyAsset.objects.filter(organisation=organisation))
    if not assets:
        return _area(
            key="assets",
            title="Assets",
            state=STATE_NOT_STARTED,
            detail="No key assets recorded yet.",
            next_action_url_name="key_assets:list",
            organisation_id=organisation.id,
            next_action_label="Open key assets",
        )

    pending = [a for a in assets if a.status == KeyAsset.STATUS_SUGGESTED]
    if pending:
        return _area(
            key="assets",
            title="Assets",
            state=STATE_IN_PROGRESS,
            detail=f"{len(pending)} suggested asset(s) awaiting review.",
            next_action_url_name="key_assets:list",
            organisation_id=organisation.id,
            next_action_label="Review suggested assets",
            count=len(pending),
        )

    confirmed_count = len([a for a in assets if a.status == KeyAsset.STATUS_CONFIRMED])
    return _area(
        key="assets",
        title="Assets",
        state=STATE_READY,
        detail=f"{confirmed_count} confirmed asset(s); no suggestions awaiting review.",
        next_action_url_name="key_assets:list",
        organisation_id=organisation.id,
        next_action_label="Open key assets",
        count=confirmed_count,
    )


def _risks_area(organisation) -> dict:
    """
    Not started: no `Risk` row exists.
    In progress: at least one AI-suggested draft risk is awaiting review.
    Needs attention: no drafts are pending, but a customer-confirmed
        high/critical risk exists with no remediation action linked to it
        at all - a real, concrete "this needs a decision" signal, not an
        invented threshold.
    Ready: risks exist, no drafts are pending, and every confirmed
        high/critical risk has at least one linked remediation action
        (which may itself be `accepted` - PID's own "accepted risk !=
        requirement satisfied" distinction is Remediation's job to show,
        not this area's).
    """
    risks = list(Risk.objects.filter(organisation=organisation))
    if not risks:
        return _area(
            key="risks",
            title="Risks",
            state=STATE_NOT_STARTED,
            detail="No risks recorded yet.",
            next_action_url_name="risk_register:list",
            organisation_id=organisation.id,
            next_action_label="Open risk register",
        )

    pending = [r for r in risks if r.status == Risk.STATUS_DRAFT_AI_SUGGESTED]
    if pending:
        return _area(
            key="risks",
            title="Risks",
            state=STATE_IN_PROGRESS,
            detail=f"{len(pending)} AI-suggested risk(s) awaiting review.",
            next_action_url_name="risk_register:list",
            organisation_id=organisation.id,
            next_action_label="Review suggested risks",
            count=len(pending),
        )

    confirmed_high_or_critical = [
        r
        for r in risks
        if r.status == Risk.STATUS_CONFIRMED and r.risk_band in (BAND_HIGH, BAND_CRITICAL)
    ]
    addressed_ids = set(
        RemediationAction.objects.filter(
            organisation=organisation,
            risk_id__in=[r.id for r in confirmed_high_or_critical],
        ).values_list("risk_id", flat=True)
    )
    unaddressed = [r for r in confirmed_high_or_critical if r.id not in addressed_ids]
    if unaddressed:
        return _area(
            key="risks",
            title="Risks",
            state=STATE_NEEDS_ATTENTION,
            detail=(
                f"{len(unaddressed)} confirmed high/critical risk(s) with no "
                "remediation action linked."
            ),
            next_action_url_name="risk_register:list",
            organisation_id=organisation.id,
            next_action_label="Review high/critical risks",
            count=len(unaddressed),
        )

    return _area(
        key="risks",
        title="Risks",
        state=STATE_READY,
        detail="No suggested risks awaiting review; high/critical risks are tracked.",
        next_action_url_name="risk_register:list",
        organisation_id=organisation.id,
        next_action_label="Open risk register",
    )


def _evidence_area(organisation) -> dict:
    """
    Evidence is an ongoing area, not a milestone-shaped one: a customer can
    always add more evidence, and there is no point at which "no more
    evidence is needed" is a real, honest claim this module could make.
    As PID §6 itself anticipates ("not every area needs to be capable of
    reaching every state"), this area only ever reaches `Not started` or
    `In progress` - never `Ready` (no fabricated "evidence complete"
    milestone) and never `Needs attention` (a stale/conflicting evidence
    item is a property of a specific CONTROL, already surfaced by the
    Security state area below - restating it here would duplicate that
    signal rather than add a new one).
    """
    active_count = EvidenceItem.objects.filter(
        organisation=organisation, status=EvidenceItem.STATUS_ACTIVE
    ).count()
    if not EvidenceItem.objects.filter(organisation=organisation).exists():
        return _area(
            key="evidence",
            title="Evidence",
            state=STATE_NOT_STARTED,
            detail="No evidence has been added yet.",
            next_action_url_name="evidence:list",
            organisation_id=organisation.id,
            next_action_label="Add evidence",
        )

    return _area(
        key="evidence",
        title="Evidence",
        state=STATE_IN_PROGRESS,
        detail=f"{active_count} active evidence item(s).",
        next_action_url_name="evidence:list",
        organisation_id=organisation.id,
        next_action_label="Open evidence",
        count=active_count,
    )


def _remediation_area(organisation) -> dict:
    """
    Not started: no `RemediationAction` row exists.
    Needs attention: at least one open/in-progress action is past its
        `target_date`.
    In progress: at least one action is open/in-progress but none are
        overdue.
    Ready: actions exist, and none are currently open/in-progress (every
        one has reached `done` or `accepted`) - "the queue is clear right
        now", not "no action will ever be needed again".
    """
    actions = list(RemediationAction.objects.filter(organisation=organisation))
    if not actions:
        return _area(
            key="remediation",
            title="Remediation",
            state=STATE_NOT_STARTED,
            detail="No remediation actions yet.",
            next_action_url_name="remediation:list",
            organisation_id=organisation.id,
            next_action_label="Open actions",
        )

    active = [a for a in actions if a.status in RemediationAction.ACTIVE_STATUSES]
    today = datetime.date.today()
    overdue = [a for a in active if a.target_date is not None and a.target_date < today]

    if overdue:
        return _area(
            key="remediation",
            title="Remediation",
            state=STATE_NEEDS_ATTENTION,
            detail=f"{len(overdue)} action(s) overdue.",
            next_action_url_name="remediation:list",
            organisation_id=organisation.id,
            next_action_label="Review overdue actions",
            count=len(overdue),
        )

    if active:
        return _area(
            key="remediation",
            title="Remediation",
            state=STATE_IN_PROGRESS,
            detail=f"{len(active)} action(s) open or in progress.",
            next_action_url_name="remediation:list",
            organisation_id=organisation.id,
            next_action_label="Open actions",
            count=len(active),
        )

    return _area(
        key="remediation",
        title="Remediation",
        state=STATE_READY,
        detail="No outstanding remediation actions right now.",
        next_action_url_name="remediation:list",
        organisation_id=organisation.id,
        next_action_label="Open actions",
    )


def _security_state_area(organisation) -> dict:
    """
    Not started: the security baseline has not been started at all (every
        row would trivially be "Not confirmed").
    Needs attention: at least one control shows an active evidence
        conflict or stale supporting evidence (`security_state.services`'s
        own `LABEL_EVIDENCE_CONFLICT`/`LABEL_EVIDENCE_STALE` - reused
        directly, never re-derived, to protect the "one security truth"
        invariant that module's docstring describes).
    In progress: baseline started, no conflicts/stale evidence, but at
        least one control's canonical answer is still "Not confirmed".
    Ready: every control has a confirmed answer, with no conflicting or
        stale evidence outstanding.
    """
    if not BaselineAssessment.objects.filter(organisation=organisation).exists():
        return _area(
            key="security_state",
            title="Security state",
            state=STATE_NOT_STARTED,
            detail="Complete the security baseline to see current security state.",
            next_action_url_name="security_state:list",
            organisation_id=organisation.id,
            next_action_label="Open security state",
        )

    rows = get_security_state(organisation)
    concerning = [
        row
        for row in rows
        if row["assurance_label"] in (LABEL_EVIDENCE_CONFLICT, LABEL_EVIDENCE_STALE)
    ]
    if concerning:
        return _area(
            key="security_state",
            title="Security state",
            state=STATE_NEEDS_ATTENTION,
            detail=f"{len(concerning)} control(s) with conflicting or stale evidence.",
            next_action_url_name="security_state:list",
            organisation_id=organisation.id,
            next_action_label="Review security state",
            count=len(concerning),
        )

    not_confirmed = [row for row in rows if row["assurance_label"] == LABEL_NOT_CONFIRMED]
    if not_confirmed:
        return _area(
            key="security_state",
            title="Security state",
            state=STATE_IN_PROGRESS,
            detail=f"{len(not_confirmed)} control(s) not yet confirmed.",
            next_action_url_name="security_state:list",
            organisation_id=organisation.id,
            next_action_label="Continue security state",
            count=len(not_confirmed),
        )

    return _area(
        key="security_state",
        title="Security state",
        state=STATE_READY,
        detail="Every control has a confirmed answer, with no conflicting or stale evidence.",
        next_action_url_name="security_state:list",
        organisation_id=organisation.id,
        next_action_label="Open security state",
    )


def _governance_workplace_area(organisation) -> dict:
    """
    Not started: no `GovernanceRoleAssignment` and no `Workplace` row
        exists at all. In the normal product flow this is effectively
        unreachable - `organisations.views.organisation_create` defaults
        all three governance roles to the Account Holder atomically at
        creation time (`governance.services.ensure_account_holder_person`)
        - but a directly-constructed `Organisation` (e.g. a test fixture
        that skips that flow) genuinely has neither, so this state stays
        meaningful rather than dead code.
    Needs attention: a currently-assigned role's person has since been
        marked inactive (`GovernanceRoleAssignment.assignee_is_inactive` -
        reused directly from governance.models, never re-derived).
    Ready: all three governance roles are assigned to active people, and
        at least one active workplace is recorded.
    In progress: anything short of Ready that isn't Not started/Needs
        attention - e.g. roles assigned but no workplace recorded yet, or
        vice versa.
    """
    assignments = list(
        GovernanceRoleAssignment.objects.filter(organisation=organisation).select_related(
            "person"
        )
    )
    active_workplace_count = Workplace.objects.filter(
        organisation=organisation, is_active=True
    ).count()

    if not assignments and active_workplace_count == 0:
        return _area(
            key="governance_workplace",
            title="Governance / workplace",
            state=STATE_NOT_STARTED,
            detail="No governance roles or workplaces recorded yet.",
            next_action_url_name="organisations:organisation_hub",
            organisation_id=organisation.id,
            next_action_label="Set up governance and workplace",
        )

    inactive_assignees = [a for a in assignments if a.assignee_is_inactive]
    if inactive_assignees:
        return _area(
            key="governance_workplace",
            title="Governance / workplace",
            state=STATE_NEEDS_ATTENTION,
            detail=(
                f"{len(inactive_assignees)} governance role(s) assigned to an "
                "inactive person."
            ),
            next_action_url_name="governance:roles",
            organisation_id=organisation.id,
            next_action_label="Review governance roles",
            count=len(inactive_assignees),
        )

    all_roles_assigned = len(assignments) == len(GovernanceRoleAssignment.ROLE_CHOICES)
    if all_roles_assigned and active_workplace_count > 0:
        return _area(
            key="governance_workplace",
            title="Governance / workplace",
            state=STATE_READY,
            detail="All governance roles are assigned; at least one active workplace is recorded.",
            next_action_url_name="organisations:organisation_hub",
            organisation_id=organisation.id,
            next_action_label="Open governance and workplace",
        )

    return _area(
        key="governance_workplace",
        title="Governance / workplace",
        state=STATE_IN_PROGRESS,
        detail=(
            f"{len(assignments)} of {len(GovernanceRoleAssignment.ROLE_CHOICES)} governance "
            f"role(s) assigned; {active_workplace_count} active workplace(s)."
        ),
        next_action_url_name="organisations:organisation_hub",
        organisation_id=organisation.id,
        next_action_label="Continue governance and workplace",
    )


# ---------------------------------------------------------------------------
# Worked example 2 of 2 (dispatch instructions): Policy.
# ---------------------------------------------------------------------------
def _policy_area(organisation) -> dict:
    """
    Not started: no `PolicyVersion` exists at all.
    In progress: at least one draft `PolicyVersion` exists, but none has
        ever been approved.
    Ready: an approved `PolicyVersion` exists. This holds even if a NEWER
        draft also exists alongside it (M004's "create a new draft from an
        approved version" flow, PID §15) - a currently-approved version is
        a real, valid policy right now regardless of what happens to it
        next; a fresh unreviewed draft sitting next to it is not itself a
        problem with the CURRENT approved policy.
    Needs attention: an approved version exists, but its own
        `next_review_date` has passed. This is the deliberately simple
        choice named in the dispatch instructions: reuse the field M004
        already has for exactly this purpose, rather than inventing a new
        staleness threshold PID does not ask for.
    """
    versions = list(PolicyVersion.objects.filter(organisation=organisation))
    if not versions:
        return _area(
            key="policy",
            title="Policy",
            state=STATE_NOT_STARTED,
            detail="No Information Security Policy has been generated yet.",
            next_action_url_name="policy:detail",
            organisation_id=organisation.id,
            next_action_label="Generate policy",
        )

    approved = [v for v in versions if v.status == PolicyVersion.STATUS_APPROVED]
    if not approved:
        return _area(
            key="policy",
            title="Policy",
            state=STATE_IN_PROGRESS,
            detail="A draft policy exists; none has been approved yet.",
            next_action_url_name="policy:detail",
            organisation_id=organisation.id,
            next_action_label="Review draft policy",
        )

    latest_approved = max(approved, key=lambda v: v.version_number)
    today = datetime.date.today()
    if latest_approved.next_review_date is not None and latest_approved.next_review_date < today:
        return _area(
            key="policy",
            title="Policy",
            state=STATE_NEEDS_ATTENTION,
            detail=f"Approved policy v{latest_approved.version_number}'s scheduled review date has passed.",
            next_action_url_name="policy:detail",
            organisation_id=organisation.id,
            next_action_label="Review policy",
        )

    return _area(
        key="policy",
        title="Policy",
        state=STATE_READY,
        detail=f"Approved policy v{latest_approved.version_number} is current.",
        next_action_url_name="policy:detail",
        organisation_id=organisation.id,
        next_action_label="Open policy",
    )


def _questionnaire_area(organisation) -> dict:
    """
    Also an ongoing area, like Evidence: new questionnaire questions can
    arrive at any time, so there is no "permanently done" milestone and
    this area never reaches `Ready`. Unlike Evidence, `Needs attention` IS
    a real, concrete signal here: a draft response is one the customer has
    not yet reviewed/accepted (`questionnaire.models.QuestionnaireResponse.
    STATUS_DRAFT`) - exactly the "this needs a decision" case the state
    exists for.
    """
    if not QuestionnaireQuestion.objects.filter(organisation=organisation).exists():
        return _area(
            key="questionnaire",
            title="Questionnaire assurance",
            state=STATE_NOT_STARTED,
            detail="No questionnaire question has been pasted yet.",
            next_action_url_name="questionnaire:list",
            organisation_id=organisation.id,
            next_action_label="Open questionnaire assurance",
        )

    pending_drafts = QuestionnaireResponse.objects.filter(
        organisation=organisation, status=QuestionnaireResponse.STATUS_DRAFT
    ).count()
    if pending_drafts:
        return _area(
            key="questionnaire",
            title="Questionnaire assurance",
            state=STATE_NEEDS_ATTENTION,
            detail=f"{pending_drafts} draft response(s) awaiting review.",
            next_action_url_name="questionnaire:list",
            organisation_id=organisation.id,
            next_action_label="Review draft responses",
            count=pending_drafts,
        )

    return _area(
        key="questionnaire",
        title="Questionnaire assurance",
        state=STATE_IN_PROGRESS,
        detail="All responses so far have been reviewed.",
        next_action_url_name="questionnaire:list",
        organisation_id=organisation.id,
        next_action_label="Open questionnaire assurance",
    )


def build_overview(organisation) -> list[dict]:
    """
    Return one dict per PID §6 area, in the order PID §6 lists them,
    for `organisation`. Every call recomputes every area from real rows -
    there is nothing to invalidate, nothing that can go stale, and no
    write path anywhere in this module.
    """
    return [
        _organisation_setup_area(organisation),
        _security_baseline_area(organisation),
        _assets_area(organisation),
        _risks_area(organisation),
        _evidence_area(organisation),
        _remediation_area(organisation),
        _security_state_area(organisation),
        _governance_workplace_area(organisation),
        _policy_area(organisation),
        _questionnaire_area(organisation),
    ]


__all__ = ["build_overview", "STATE_LABELS"]
