"""
Policy-grounding construction (M004 PID §12 - m004-2a-policy-foundation
dispatch): the piece that ties organisation/workplace/governance/baseline/
security-state/risk facts together into the `PolicyGroundingPayload` an AI
policy-generation call sends outbound.

SAFETY-CRITICAL (mirrors `risk_register.grounding`'s own "the last item is
critical" framing - PID §16/§23): whatever `build_policy_grounding_payload`
returns becomes an outbound AI request payload. It must be structurally
impossible for it to read or include another organisation's data.

How that is enforced here, not just asserted - identical discipline to
`risk_register.grounding.build_grounding_payload`:

1. `build_policy_grounding_payload` takes a single `organisation` object -
   never an organisation id plus a separate lookup - so there is no code
   path where a caller-supplied id could diverge from the organisation
   whose facts are actually read.
2. Every DB access below is EITHER:
     - a reverse one-to-one/one-to-many traversal FROM that exact
       `organisation` object (`organisation.profile`,
       `organisation.baseline_assessment`), which Django resolves as a
       lookup keyed on that organisation's own primary key; or
     - an explicit `.filter(organisation=organisation, ...)`
       (`Workplace`, `GovernanceRoleAssignment`, `Risk`) - every one of
       these queries is organisation-scoped at the ORM call site, not
       filtered afterwards; or
     - a call to `security_state.services.get_security_state(organisation)`,
       which is itself built to the same discipline (see that function's
       own module docstring) - this module never re-derives security state
       itself, it only projects down the already tenant-scoped result.
   Nothing in this module ever calls `Model.objects.all()`,
   `Model.objects.get(pk=...)` without an organisation filter, or accepts a
   raw id from outside this function's own `organisation` argument.
3. Free text (organisation description, workplace location labels,
   governance names/titles, baseline notes, risk titles) is carried
   through as opaque string VALUES inside the returned dicts - never used
   to construct a query, never interpreted - so it cannot itself cause a
   cross-tenant read.
4. `security_state_facts` is deliberately a NARROW projection of
   `get_security_state`'s full result: only `area`, `answer`,
   `answer_label`, `assurance_label` and `open_remediation_count` per
   control. Everything else that function returns (evidence lists,
   evidence titles/descriptions/file references) is explicitly excluded -
   PID §12/§24: "Do not send evidence file bytes to AI. Do not send
   arbitrary evidence free text unless separately authorised."
5. `open_risk_facts` includes only `Risk.STATUS_CONFIRMED` rows - never a
   draft AI-suggested or dismissed risk - the same "only confirmed facts,
   never unreviewed/rejected data" discipline
   `risk_register.grounding._asset_facts` already applies to its own
   CONFIRMED-only asset filter.

This module decides which Organisation/Workplace/Governance/Baseline/
Security-state/Risk fields belong in the payload;
`ai_platform.policy_contracts.PolicyGroundingPayload` only guarantees
transport shape (see that module's docstring).
"""
from __future__ import annotations

from ai_platform.policy_contracts import PolicyGroundingPayload
from governance.models import GovernanceRoleAssignment
from organisations.models import OrganisationProfile
from risk_register.models import Risk
from security_baseline.models import BaselineAssessment
from security_state.services import get_security_state
from workplace.models import Workplace

# Only these keys are ever forwarded from get_security_state()'s per-control
# result - see module docstring point 4.
_SECURITY_STATE_PROJECTED_KEYS = (
    "area",
    "answer",
    "answer_label",
    "assurance_label",
    "open_remediation_count",
)


def _organisation_facts(organisation) -> dict:
    """`organisation.profile` is a reverse OneToOneField accessor - Django
    resolves it as a lookup scoped to `organisation`'s own primary key;
    there is no separate id parameter here that could be widened or
    mismatched. `{}`-profile-fields fall back to `None` if no
    `OrganisationProfile` exists yet, so the model still receives a
    consistent shape (name is always present; staff_count/description may
    be `None`)."""
    facts = {"name": organisation.name, "staff_count": None, "description": ""}
    try:
        profile = organisation.profile
    except OrganisationProfile.DoesNotExist:
        return facts
    facts["staff_count"] = profile.staff_count
    facts["description"] = profile.description
    return facts


def _workplace_facts(organisation) -> list:
    """This organisation's ACTIVE Workplace rows only - an inactive
    workplace is historical, not current context a policy should describe
    (PID §9.2's own "active workplace" framing). Explicitly filtered by
    `organisation=organisation` at the ORM call site."""
    workplaces = Workplace.objects.filter(organisation=organisation, is_active=True)
    return [
        {
            "name": w.name,
            "type": w.type,
            "location_label": w.location_label,
            "approx_people_count": w.approx_people_count,
        }
        for w in workplaces
    ]


def _governance_facts(organisation) -> dict:
    """This organisation's three governance-role assignments, keyed by
    role (PID §7-8). Explicitly filtered by `organisation=organisation` at
    the ORM call site, with the assigned `OrganisationPerson` reached only
    through that already-scoped row's own FK - never a separate,
    independently-filterable person query."""
    assignments = GovernanceRoleAssignment.objects.filter(
        organisation=organisation
    ).select_related("person")
    return {
        assignment.role: {
            "full_name": assignment.person.full_name,
            "job_title": assignment.person.job_title,
        }
        for assignment in assignments
    }


def _baseline_facts(organisation) -> dict:
    """This organisation's saved security-baseline answers, or {} if no
    assessment has been started yet - same shape and discipline as
    `risk_register.grounding._baseline_facts` (reverse OneToOneField
    traversal from this exact `organisation`, then a query scoped to that
    one assessment row's own FK)."""
    try:
        assessment = organisation.baseline_assessment
    except BaselineAssessment.DoesNotExist:
        return {}
    return {
        answer.question_key: {"answer": answer.answer, "note": answer.note}
        for answer in assessment.answers.all()
    }


def _security_state_facts(organisation) -> dict:
    """Project `security_state.services.get_security_state(organisation)`
    (already deterministic, already tenant-scoped) down to only the fields
    PID §12/§24 permit sending to AI - see module docstring point 4."""
    return {
        entry["control_key"]: {key: entry[key] for key in _SECURITY_STATE_PROJECTED_KEYS}
        for entry in get_security_state(organisation)
    }


def _open_risk_facts(organisation) -> list:
    """This organisation's CONFIRMED risks only - never draft/dismissed
    (module docstring point 5). Explicitly filtered by
    `organisation=organisation` at the ORM call site."""
    risks = Risk.objects.filter(organisation=organisation, status=Risk.STATUS_CONFIRMED)
    return [
        {"title": risk.title, "risk_band": risk.risk_band, "status": risk.status}
        for risk in risks
    ]


def build_policy_grounding_payload(organisation) -> PolicyGroundingPayload:
    """Assemble the current `organisation`'s `PolicyGroundingPayload` from
    its OrganisationProfile, active Workplace rows, governance-role
    assignments, canonical baseline answers, projected Current Security
    State, and CONFIRMED risks.

    Every fact group is read via a traversal or filter keyed on this exact
    `organisation` object - see module docstring for why that makes a
    cross-tenant leak structurally impossible here, not merely tested for.
    """
    return PolicyGroundingPayload(
        organisation_id=str(organisation.pk),
        organisation_facts=_organisation_facts(organisation),
        workplace_facts=_workplace_facts(organisation),
        governance_facts=_governance_facts(organisation),
        baseline_facts=_baseline_facts(organisation),
        security_state_facts=_security_state_facts(organisation),
        open_risk_facts=_open_risk_facts(organisation),
    )
