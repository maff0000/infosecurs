"""
Policy-grounding construction (M004 PID §12 - m004-2a-policy-foundation
dispatch; STRUCTURED-FIRST re-architecture - M006-AUDIT-0002 finding G1,
`policy_generation_v2`): the piece that ties organisation/workplace/
governance/baseline/security-state/risk facts together into the
`PolicyGroundingPayload` an AI policy-generation call sends outbound.

== G1 correction (read before touching this module) ==========================
A fresh independent Auditor (`docs/evidence/M006-AUDIT-0002.md`) proved that
planting hostile prose (a behavioural-injection instruction plus a
fabricated "ISO 27001 certified / MFA fully implemented" claim) in a
`BaselineAnswer.note` field caused the policy-generation AI surface to adopt
the fabricated claim into an approved, downloadable policy PDF. Central
Architecture's ruling (recorded in `PID.md` §10 "AI doctrine"): prompt-only
defences against hostile customer prose have now failed on this exact
pattern, here and previously against `risk_interpretation` (M006-AUDIT-0001
F3). The correction is DATA MINIMISATION AT THE SOURCE, not a third
paragraph of prompt wording -

    Structured first. Prose by exception. AI clarifies. Customer confirms.
    Application owns truth.

This module now builds a STRUCTURED PROJECTION of canonical tenant state,
not a carrier for the tenant's own free-text narrative. Every helper below
that used to pass an organisation-authored string straight through (an
organisation description, a workplace name/location label, a governance
person's full name/job title, a baseline answer's note, a risk's own
customer-influenced title) has been rewritten to emit only: short
identifying labels that are NOT the excluded prose class (see each helper's
own docstring for why its specific fields are not on that list), controlled
enum values, bounded numeric/date values, and deterministic
application/methodology-owned keys. No helper in this module sends the
model a sentence a customer wrote.

SAFETY-CRITICAL (mirrors `risk_register.grounding`'s own "the last item is
critical" framing - PID §16/§23): whatever `build_policy_grounding_payload`
returns becomes an outbound AI request payload. It must be structurally
impossible for it to read or include another organisation's data.

How that is enforced here, not just asserted - identical discipline to
`risk_register.grounding.build_grounding_payload`, UNCHANGED by the G1
correction (G1 is about WHICH fields travel, not about weakening this
tenant-scoping discipline in any way):

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
3. The organisation-authored free text this module still deliberately
   EXCLUDES (organisation description, workplace name/location labels,
   governance names/titles, baseline notes, risk titles) is simply never
   read into the returned payload at all any more - not carried through as
   an opaque value, not sent anywhere. It has no opportunity to reach a
   query or an outbound request, because it is never touched by this
   module in the first place (a stronger guarantee than the pre-G1 "carried
   through as an inert value" discipline this docstring used to describe).
4. `security_state_facts` is deliberately a NARROW projection of
   `get_security_state`'s full result: only `area`, `answer`,
   `answer_label`, `assurance_label` and `open_remediation_count` per
   control. Everything else that function returns (evidence lists,
   evidence titles/descriptions/file references) is explicitly excluded -
   PID §12/§24: "Do not send evidence file bytes to AI. Do not send
   arbitrary evidence free text unless separately authorised." This
   projection was already G1-compliant before the correction (no free
   text) - left unchanged.
5. `open_risk_facts` includes only `Risk.STATUS_CONFIRMED` rows - never a
   draft AI-suggested or dismissed risk - the same "only confirmed facts,
   never unreviewed/rejected data" discipline
   `risk_register.grounding._asset_facts` already applies to its own
   CONFIRMED-only asset filter.

This module decides which Organisation/Workplace/Governance/Baseline/
Security-state/Risk fields belong in the payload;
`ai_platform.policy_contracts.PolicyGroundingPayload` only guarantees
transport shape (plain dicts/lists per fact group) - it does not mandate
what those dicts/lists contain, so this G1 restructuring changes this
module's own return values without needing any change to that contract
module (see its own docstring).
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

# G1: assignment status only - never a governance person's own name/title.
# See `_governance_facts`'s own docstring for the full reasoning, and
# `ai_platform.prompts.policy_generation_v2`'s module docstring for how the
# generated policy text still refers to each role sensibly without ever
# being given a name to write.
GOVERNANCE_ASSIGNED = "assigned"
GOVERNANCE_NOT_ASSIGNED = "not_assigned"

# The fixed governance-role set (PID §7-8) this projection always reports on
# - every role, whether or not it currently has an assignment - so an
# UNASSIGNED role is itself a structured, positive fact the model (and any
# deterministic review-warning logic built on the same projection) can see,
# rather than merely a key that happens to be absent from the dict.
_GOVERNANCE_ROLES = (
    GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
    GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
    GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
)

# G1: a CONFIRMED risk with no traceable catalogue scenario (e.g. a manually
# created risk - `risk_register.models.Risk.scenario_id` is blank/default
# for those) still needs a non-prose, deterministic label rather than
# either leaking `Risk.title` (customer-influenced - see PID §0.7) or
# silently disappearing from the projection.
_MANUALLY_ADDED_RISK_SCENARIO_LABEL = "manually_added"


def _organisation_facts(organisation) -> dict:
    """`organisation.profile` is a reverse OneToOneField accessor - Django
    resolves it as a lookup scoped to `organisation`'s own primary key;
    there is no separate id parameter here that could be widened or
    mismatched.

    G1: `description` (organisation-authored free text) is EXCLUDED - it is
    exactly the prose class Central Architecture's correction names
    explicitly. `name` and `staff_count` remain: `name` is a short
    identifying label, not the prose class being excluded (the same
    distinction Central Architecture's own correction draws - "a short
    identifying string, not the prose class being excluded here"), and it
    is also needed so the application/PDF renderer can put the
    organisation's real name in `policy_title`/prose deterministically;
    `staff_count` is already a bounded numeric value."""
    facts = {"name": organisation.name, "staff_count": None}
    try:
        profile = organisation.profile
    except OrganisationProfile.DoesNotExist:
        return facts
    facts["staff_count"] = profile.staff_count
    return facts


def _workplace_facts(organisation) -> list:
    """This organisation's ACTIVE Workplace rows only - an inactive
    workplace is historical, not current context a policy should describe
    (PID §9.2's own "active workplace" framing). Explicitly filtered by
    `organisation=organisation` at the ORM call site.

    G1: `name` and `location_label` (both organisation-authored free text -
    e.g. "Woking shared office" / "Woking, Surrey") are EXCLUDED. `type` is
    a fixed, controlled enum (`workplace.models.Workplace.TYPE_CHOICES`) and
    `approx_people_count` is a bounded numeric value - both match Central
    Architecture's own worked example verbatim (`workplace_types`/
    `workplace_people`). Kept as one dict per active Workplace row (rather
    than the two separate parallel arrays Central Architecture's example
    shows) so a case with several distinctly-typed workplaces still keeps
    each workplace's own type paired with its own people count without
    relying on two lists staying index-aligned - the same information,
    expressed as ordinary JSON objects rather than parallel arrays."""
    workplaces = Workplace.objects.filter(organisation=organisation, is_active=True)
    return [
        {"type": w.type, "approx_people_count": w.approx_people_count} for w in workplaces
    ]


def _governance_facts(organisation) -> dict:
    """This organisation's governance-role ASSIGNMENT STATUS, keyed by the
    three fixed roles (PID §7-8) - `GOVERNANCE_ASSIGNED` if a
    `GovernanceRoleAssignment` currently exists for that role,
    `GOVERNANCE_NOT_ASSIGNED` otherwise. Explicitly filtered by
    `organisation=organisation` at the ORM call site.

    G1: a governance person's `full_name`/`job_title` are BOTH
    organisation-authored free text and are excluded entirely - the model
    is never given a name to reason over, write into policy prose, or be
    misled by (see `ai_platform.prompts.policy_generation_v2`'s module
    docstring for the resulting prompt-design decision: the model refers to
    each role generically, e.g. "the person assigned as Security
    Responsible", never by name). This mirrors Central Architecture's own
    worked example exactly (`governance: {policy_authoriser: assigned,
    security_responsible: assigned, senior_leadership: assigned}`).

    Every one of the three fixed roles is always present in the returned
    dict, whether or not it currently has an assignment - an unassigned
    role is itself a structured fact, not an absent key (see
    `_GOVERNANCE_ROLES` module constant)."""
    assigned_roles = set(
        GovernanceRoleAssignment.objects.filter(
            organisation=organisation, role__in=_GOVERNANCE_ROLES
        ).values_list("role", flat=True)
    )
    return {
        role: (GOVERNANCE_ASSIGNED if role in assigned_roles else GOVERNANCE_NOT_ASSIGNED)
        for role in _GOVERNANCE_ROLES
    }


def _baseline_facts(organisation) -> dict:
    """This organisation's saved security-baseline ANSWERS ONLY, or {} if
    no assessment has been started yet - same reverse OneToOneField
    traversal from this exact `organisation`, then a query scoped to that
    one assessment row's own FK, `risk_register.grounding._baseline_facts`
    already establishes.

    G1: `note` (organisation-authored free text - the exact field
    M006-AUDIT-0002's G1 finding planted its hostile prose in) is EXCLUDED.
    `answer` is a fixed, controlled enum
    (`security_baseline.models.ANSWER_CHOICES`) and is kept unchanged."""
    try:
        assessment = organisation.baseline_assessment
    except BaselineAssessment.DoesNotExist:
        return {}
    return {answer.question_key: {"answer": answer.answer} for answer in assessment.answers.all()}


def _security_state_facts(organisation) -> dict:
    """Project `security_state.services.get_security_state(organisation)`
    (already deterministic, already tenant-scoped) down to only the fields
    PID §12/§24 permit sending to AI - see module docstring point 4. This
    projection carried no organisation-authored free text before G1 either
    - unchanged here."""
    return {
        entry["control_key"]: {key: entry[key] for key in _SECURITY_STATE_PROJECTED_KEYS}
        for entry in get_security_state(organisation)
    }


def _open_risk_facts(organisation) -> list:
    """This organisation's CONFIRMED risks only - never draft/dismissed
    (module docstring point 5). Explicitly filtered by
    `organisation=organisation` at the ORM call site.

    G1: `Risk.title` is EXCLUDED - `risk_register.scenario_engine.
    _build_title` (and a manually-created risk's own customer-supplied
    title) embeds the customer's own asset name, exactly the prose class
    Central Architecture's correction names ("Risk title containing
    customer asset names"). `Risk.scenario_id` replaces it: a stable,
    deterministic, non-prose methodology-catalogue key (e.g.
    "identity_mfa_privileged_account_takeover" -
    `risk_register.methodology.CATALOGUE_BY_ID`) that traces back to the
    scenario that produced the risk, matching Central Architecture's own
    "canonical methodology/scenario class where useful" guidance. A
    manually-created risk has no catalogue scenario
    (`Risk.scenario_id == ""` by model default) - reported as the fixed,
    non-prose `_MANUALLY_ADDED_RISK_SCENARIO_LABEL` rather than either an
    empty string or (worse) silently falling back to the excluded `title`.
    `risk_band` (a deterministic property computed from `impact`/
    `likelihood`, never AI- or customer-supplied - see `Risk.risk_band`'s
    own docstring) and `status` are both already non-prose and unchanged."""
    risks = Risk.objects.filter(organisation=organisation, status=Risk.STATUS_CONFIRMED)
    return [
        {
            "scenario_id": risk.scenario_id or _MANUALLY_ADDED_RISK_SCENARIO_LABEL,
            "risk_band": risk.risk_band,
            "status": risk.status,
        }
        for risk in risks
    ]


def build_policy_grounding_payload(organisation) -> PolicyGroundingPayload:
    """Assemble the current `organisation`'s `PolicyGroundingPayload` - a
    STRUCTURED PROJECTION of canonical tenant state (G1 correction - see
    module docstring), never the organisation's own narrative - from its
    OrganisationProfile, active Workplace rows, governance-role assignment
    STATUS, canonical baseline ANSWERS, projected Current Security State,
    and CONFIRMED risks' methodology scenario/band/status.

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
