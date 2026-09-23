"""
Grounding construction: the piece that ties M001 (OrganisationProfile) +
Security Baseline + Key Assets together into the `GroundingPayload` an AI
generation call sends outbound (M002 PID §10).

SAFETY-CRITICAL (PID §16, "the last item is critical"): whatever
`build_grounding_payload` returns becomes an outbound AI request payload.
It must be structurally impossible for it to read or include another
organisation's data.

How that is enforced here, not just asserted:

1. `build_grounding_payload` takes a single `organisation` object - never an
   organisation id plus a separate lookup - so there is no code path where a
   caller-supplied id could diverge from the organisation whose facts are
   actually read.
2. Every DB access below is EITHER:
     - a reverse one-to-one traversal FROM that exact `organisation` object
       (`organisation.profile`, `organisation.baseline_assessment`), which
       Django resolves as a lookup keyed on that organisation's own primary
       key - there is no query parameter here an attacker/bug could widen; or
     - an explicit `.filter(organisation=organisation, ...)` (KeyAsset) -
       every asset query is organisation-scoped at the ORM call site, not
       filtered afterwards.
   Nothing in this module ever calls `Model.objects.all()`,
   `Model.objects.get(pk=...)` without an organisation filter, or accepts a
   raw id from outside this function's own `organisation` argument.
3. Free text (profile description, commercial/security driver, baseline
   notes, asset descriptions) is carried through as opaque string VALUES
   inside the returned dicts - never used to construct a query, never
   interpreted - so it cannot itself cause a cross-tenant read.

This module decides which M001/Baseline/Assets fields belong in the
payload; `ai_platform.contracts.GroundingPayload` only guarantees transport
shape (see that module's docstring).
"""
from __future__ import annotations

from ai_platform.contracts import GroundingPayload
from key_assets.models import KeyAsset
from organisations.models import OrganisationProfile
from security_baseline.models import BaselineAssessment

# OrganisationProfile fields surfaced to the model, using the same
# "profile.<field>" naming PID §10 uses in its own grounding_refs examples.
# Deliberately excludes nothing structurally sensitive - every field here is
# already scoped to the single `organisation` passed in.
_PROFILE_FIELDS = [
    "legal_trading_name",
    "description",
    "staff_count",
    "working_model",
    "endpoint_management",
    "productivity_platform",
    "primary_cloud_provider",
    "develops_hosts_own_software",
    "handles_personal_data",
    "handles_confidential_business_data",
    "handles_payment_card_data",
    "handles_special_category_data",
    "receives_security_questionnaires",
    "cyber_essentials_status",
    "iso27001_status",
    "commercial_security_driver",
]


def _profile_facts(organisation) -> dict:
    """Current organisation's OrganisationProfile facts, or {} if the
    organisation has not completed a profile yet.

    `organisation.profile` is a reverse OneToOneField accessor
    (`OrganisationProfile.organisation`) - Django resolves it as a lookup
    scoped to `organisation`'s own primary key; there is no separate id
    parameter here that could be widened or mismatched.
    """
    try:
        profile = organisation.profile
    except OrganisationProfile.DoesNotExist:
        return {}
    return {field: getattr(profile, field) for field in _PROFILE_FIELDS}


def _baseline_facts(organisation) -> dict:
    """Current organisation's saved security-baseline answers, or {} if no
    assessment has been started yet.

    `organisation.baseline_assessment` is likewise a reverse OneToOneField
    accessor scoped to this exact organisation; `assessment.answers.all()`
    is then scoped to that one assessment row by its own FK - never a
    separate, independently-filterable query.
    """
    try:
        assessment = organisation.baseline_assessment
    except BaselineAssessment.DoesNotExist:
        return {}
    return {
        answer.question_key: {"answer": answer.answer, "note": answer.note}
        for answer in assessment.answers.all()
    }


def _asset_facts(organisation) -> list:
    """Current organisation's CONFIRMED key assets only (documented choice:
    a SUGGESTED asset has not been reviewed by the customer yet, and a
    DISMISSED one was explicitly rejected - grounding risk generation in
    either would let unreviewed/rejected data shape AI output as if it were
    established fact).

    Explicitly filtered by `organisation=organisation` at the ORM call site
    - never fetched unscoped and filtered afterwards.
    """
    assets = KeyAsset.objects.filter(
        organisation=organisation, status=KeyAsset.STATUS_CONFIRMED
    )
    return [
        {
            "id": str(asset.id),
            "name": asset.name,
            "category": asset.category,
            "criticality": asset.criticality,
            "description": asset.description,
        }
        for asset in assets
    ]


def build_grounding_payload(organisation) -> GroundingPayload:
    """Assemble the current `organisation`'s `GroundingPayload` from its
    OrganisationProfile (M001), BaselineAssessment/BaselineAnswers
    (security_baseline) and CONFIRMED KeyAssets (key_assets).

    Every fact group is read via a traversal or filter keyed on this exact
    `organisation` object - see module docstring for why that makes a
    cross-tenant leak structurally impossible here, not merely tested for.
    """
    return GroundingPayload(
        organisation_id=str(organisation.pk),
        profile_facts=_profile_facts(organisation),
        baseline_facts=_baseline_facts(organisation),
        asset_facts=_asset_facts(organisation),
    )
