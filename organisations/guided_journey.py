"""
M008-WI5 — "which stage of the guided Foundations journey should Home's
'Continue Security Foundations' CTA send this customer to right now?"
(docs/design/M008C-UX-FLOW-DESIGN.md §5).

`current_guided_stage(organisation)` is the ONE place this is decided.
`organisations.views.organisation_detail` calls it (non-paused branch
only) to build Home's new primary CTA context; nothing else in this
codebase should independently re-derive "which stage is next".

Deliberately a plain function over a real `organisation`, never a
caller-supplied id with its own lookup (this WI's tenant-isolation
discipline) - every caller already holds a tenant-scoped `organisation`
object (via `get_member_organisation_or_404`) before this is ever called.

No new model, no new migration: every completeness check below reads
existing canonical rows through this codebase's own existing, already-
tested predicates (`organisations.views.STAGE*_FIELDS` + `_count_confirmed`,
`organisations.overview.is_workplace_complete`/`is_governance_complete`,
`security_baseline.stage4.stage4_progress`, `policy.models.PolicyVersion`)
- never a second, independently re-derived definition of any of them.

Zero AI/LLM calls: this module imports nothing from `ai_platform` or
`risk_register.interpretation_service` - see
`organisations/tests/test_guided_journey.py`'s own import-statement-level
proof (same technique as `organisations/tests/
test_stage_forms_no_free_text_and_zero_ai.py`).

---------------------------------------------------------------------------
JUDGEMENT CALLS (M008-WI5 dispatch's own open design questions — recorded
here, not silently resolved elsewhere):

1. Stage 3 / Key Assets: chosen NOT to require "at least one confirmed
   Key Asset" for Stage 3 completion. Stage 3's own M008B catalogue
   questions (3.1-3.6, the ten `STAGE3_TECHNOLOGY_DATA_FIELDS`) are all
   `OrganisationProfile`-backed facts with a genuine "confirmed" state;
   Key Assets is an open-ended curation list with no natural "done" state
   of its own (`organisations.overview._assets_area`'s own docstring:
   reviewing the starter suggestions is a review step, not something that
   can be "complete" in the sense of having a final count) - gating Stage
   3's own "Continue" on it would import Stage 5's "no natural done state"
   problem one stage early. The simpler, defensible minimum (the ten
   profile fields alone) is used.

2. Stage 5 ("Your Risks & Actions"): NEVER a hard gate in this resolver.
   There is no persisted "visited this stage" fact to check (this WI adds
   no new model to create one), and risks can legitimately be regenerated
   forever as upstream facts change (the same reasoning
   `organisations.overview.is_risks_review_complete`'s own docstring gives
   for why the differently-scoped, older M007 "Risks review" milestone is
   framed the way it is) - there is no honest "done" state for a resolver
   like this one to detect. Once Stage 4 is complete, "Continue Security
   Foundations" moves straight to Stage 6; Stage 5 remains reachable via
   its own existing tile on the Foundations page exactly as before,
   completely untouched by this change.

3. Stage 6 ("Your Security Policy") terminal state: once at least one
   APPROVED `PolicyVersion` exists, there is nothing further for
   "Continue" to send the customer onward to - all 6 stages are done.
   Chosen treatment: keep the CTA, but mark it `is_complete=True` so the
   template can render different wording ("Review your Security Policy")
   rather than making the CTA disappear entirely - a disappearing CTA
   would remove the one obvious re-entry point back into the guided
   journey, and the design doc's own mockup never shows (or rules out)
   an "all done" treatment. Still links to `policy:detail` - the natural
   place to review the current approved policy, or start a new draft if
   policy needs to change again later.
---------------------------------------------------------------------------
"""
from __future__ import annotations

import dataclasses

from django.urls import reverse

from organisations.models import OrganisationProfile
from organisations.overview import is_governance_complete, is_workplace_complete
from policy.models import PolicyVersion
from security_baseline.models import BaselineAssessment
from security_baseline.stage4 import stage4_progress

TOTAL_STAGES = 6


@dataclasses.dataclass(frozen=True)
class GuidedStage:
    """One resolved "where should 'Continue' send this customer" result.

    `is_complete` is only ever True for the Stage 6 terminal state
    (judgement call 3 above) - every earlier stage this resolver returns
    is, by construction, the first INCOMPLETE stage in order 1-6."""

    number: int
    name: str
    url: str
    is_complete: bool = False


def current_guided_stage(organisation) -> GuidedStage:
    """
    Returns the first incomplete stage, in order 1 -> 6; if all are
    complete, the Stage 6 terminal state (judgement call 3 above).

    Lazy, in-function import of `organisations.views`' own
    `STAGE1_BUSINESS_FIELDS`/`STAGE2_PEOPLE_WORKPLACES_FIELDS`/
    `STAGE3_TECHNOLOGY_DATA_FIELDS`/`_count_confirmed`: `organisations.
    views` imports THIS module at module level (to wire Home's CTA), so
    importing it back at THIS module's own top level would be a circular
    import. Both modules are fully loaded by the time this function is
    actually called, so the import below always succeeds.

    This deliberately reuses `_count_confirmed`'s existing "confirmed"
    definition verbatim, bugs and all (e.g. `sector`/
    `commercial_security_driver` default to their own `*_NOT_SURE`
    sentinel, not the shared `UNKNOWN` sentinel `_count_confirmed` checks
    for - so a never-touched `sector`/`commercial_security_driver` field
    already reads as "confirmed" here, exactly as it already does on
    Stage 1's own "N of 5 confirmed so far" line). This WI's own dispatch
    is explicit: "mirror ... rather than re-deriving a new one" - changing
    that definition is a separate, out-of-scope change that would also
    change what Stage 1's own progress line shows, not something this
    resolver may silently correct on its own.
    """
    from organisations.views import (
        STAGE1_BUSINESS_FIELDS,
        STAGE2_PEOPLE_WORKPLACES_FIELDS,
        STAGE3_TECHNOLOGY_DATA_FIELDS,
        _count_confirmed,
    )

    profile = OrganisationProfile.objects.filter(organisation=organisation).first()

    if _count_confirmed(profile, STAGE1_BUSINESS_FIELDS) < len(STAGE1_BUSINESS_FIELDS):
        return GuidedStage(
            number=1,
            name="Your Business",
            url=reverse(
                "organisations:stage1_business", kwargs={"organisation_id": organisation.id}
            ),
        )

    stage2_fields_confirmed = _count_confirmed(
        profile, STAGE2_PEOPLE_WORKPLACES_FIELDS
    ) == len(STAGE2_PEOPLE_WORKPLACES_FIELDS)
    if not (
        stage2_fields_confirmed
        and is_workplace_complete(organisation)
        and is_governance_complete(organisation)
    ):
        return GuidedStage(
            number=2,
            name="Your People & Workplaces",
            url=reverse(
                "organisations:stage2_people_workplaces",
                kwargs={"organisation_id": organisation.id},
            ),
        )

    if _count_confirmed(profile, STAGE3_TECHNOLOGY_DATA_FIELDS) < len(
        STAGE3_TECHNOLOGY_DATA_FIELDS
    ):
        return GuidedStage(
            number=3,
            name="Your Technology & Data",
            url=reverse(
                "organisations:stage3_technology_data",
                kwargs={"organisation_id": organisation.id},
            ),
        )

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    if stage4_progress(assessment)["reviewed"] != 12:
        return GuidedStage(
            number=4,
            name="Your Security Foundations",
            url=reverse(
                "security_baseline:foundations_start",
                kwargs={"organisation_id": organisation.id},
            ),
        )

    # Stage 5 never gates "Continue" - judgement call 2 above. Once Stage 4
    # is complete, the CTA moves straight to Stage 6.
    policy_url = reverse("policy:detail", kwargs={"organisation_id": organisation.id})
    has_approved_policy = PolicyVersion.objects.filter(
        organisation=organisation, status=PolicyVersion.STATUS_APPROVED
    ).exists()
    if not has_approved_policy:
        return GuidedStage(number=6, name="Your Security Policy", url=policy_url)

    return GuidedStage(
        number=6, name="Your Security Policy", url=policy_url, is_complete=True
    )


__all__ = ["GuidedStage", "TOTAL_STAGES", "current_guided_stage"]
