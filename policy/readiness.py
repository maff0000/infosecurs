"""
M008D-WI4 — the policy readiness gate (docs/design/
M008D-POLICY-ARCHITECTURE.md §6).

`policy_readiness(organisation)` is the ONE place every condition §6
names is evaluated - mirroring `policy.views._approval_eligibility`'s own
"used by both the template (to decide what to show) and the view itself
(re-checked before accepting a POST, never trusted from the template/URL
alone)" shape. `policy.services._finalise_approval` is the final,
authoritative backstop (defence in depth) - the view-layer check below
exists only to give the customer an honest, specific reason BEFORE they
reach the confirmation step, not as the only enforcement point.

Conditions NOT implemented here, because they are already true by
construction or explicitly out of scope for this gate (§6 itself says so):

- NO/PARTIAL control states never block approval - this gate only checks
  that all 12 controls were DELIBERATELY REVIEWED (point 2 below), never
  what they were answered.
- UNKNOWN never blocks approval either - same point 2 only checks
  "reviewed", via `security_baseline.stage4.stage4_progress`'s own
  `reviewed` count, which counts an honest "Not sure" as reviewed. Any
  remaining UNKNOWN row is surfaced via `policy.implementation_status`
  instead (never hidden, never a gate).
- `entitlements.metrics.get_security_foundations_completion`'s 18-item
  percentage is explicitly NOT a condition here (§6 point 6) - see
  `policy/tests/test_readiness.py` for the regression test proving a
  policy can be approved while that metric is below 100%.
"""
from __future__ import annotations

import dataclasses

from organisations.models import SECTOR_NOT_SURE, OrganisationProfile
from organisations.overview import is_governance_complete, is_workplace_complete
from security_baseline.models import BaselineAssessment
from security_baseline.stage4 import stage4_progress


@dataclasses.dataclass(frozen=True)
class PolicyReadiness:
    """One named boolean per §6 condition this gate actually enforces,
    plus the derived `is_ready`/`blocking_reasons` every caller needs -
    never a bare `True`/`False`, so a caller can always say WHY approval
    is blocked, specifically (the same "name which conditions are/aren't
    met" shape `policy.views._approval_eligibility` already returns for
    its own, different question)."""

    legal_name_confirmed: bool
    sector_confirmed: bool
    has_active_workplace: bool
    governance_roles_complete: bool
    all_controls_reviewed: bool

    @property
    def is_ready(self) -> bool:
        return all(
            [
                self.legal_name_confirmed,
                self.sector_confirmed,
                self.has_active_workplace,
                self.governance_roles_complete,
                self.all_controls_reviewed,
            ]
        )

    @property
    def blocking_reasons(self) -> "list[str]":
        """Human-readable reasons, in a stable fixed order - empty when
        `is_ready`. Used by both the version-detail/approve templates (so
        a blocked customer sees exactly what is missing, not just
        "blocked") and this module's own tests."""
        reasons = []
        if not self.legal_name_confirmed:
            reasons.append("The organisation's legal/trading name has not been confirmed.")
        if not self.sector_confirmed:
            reasons.append("The organisation's sector has not been confirmed.")
        if not self.has_active_workplace:
            reasons.append("At least one active workplace must be recorded.")
        if not self.governance_roles_complete:
            reasons.append(
                "All three governance roles (Policy authoriser, Security "
                "responsible person, Senior leadership representative) "
                "must be assigned to an active person."
            )
        if not self.all_controls_reviewed:
            reasons.append(
                "All 12 security controls must be deliberately reviewed "
                '(including "Not sure") before this policy can be approved.'
            )
        return reasons


def policy_readiness(organisation) -> PolicyReadiness:
    """
    §6 conditions 1-2, evaluated fresh against `organisation`'s current
    canonical state - never cached, never persisted (same discipline as
    `policy.implementation_status`/`policy.services._approval_eligibility`
    - a readiness verdict from five minutes ago is not this organisation's
    readiness verdict right now).

    Condition 1 (legal name / sector / workplace / all three governance
    roles): `legal_name_confirmed`/`sector_confirmed` read
    `OrganisationProfile` directly (an organisation with no profile row at
    all has confirmed neither); `has_active_workplace` reuses
    `organisations.overview.is_workplace_complete` (PID §24 "prefer
    reusing the same underlying predicate" - already exactly "at least one
    active Workplace row"); `governance_roles_complete` reuses
    `organisations.overview.is_governance_complete` (already exactly "all
    three `GovernanceRoleAssignment.ROLE_CHOICES` roles assigned to an
    ACTIVE person" - the "at least one... per role" condition §6 asks for,
    not merely "at least one role assigned").

    Condition 2 (all 12 controls deliberately reviewed): reuses
    `security_baseline.stage4.stage4_progress` directly rather than
    re-deriving "reviewed" - `reviewed == 12` (never also requiring
    `still_need_confirmation == 0`, which would wrongly re-introduce
    "UNKNOWN blocks approval", exactly what §6 point 4 forbids).
    """
    profile = OrganisationProfile.objects.filter(organisation=organisation).first()
    legal_name_confirmed = bool(profile and profile.legal_trading_name.strip())
    sector_confirmed = bool(profile and profile.sector != SECTOR_NOT_SURE)

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    progress = stage4_progress(assessment)

    return PolicyReadiness(
        legal_name_confirmed=legal_name_confirmed,
        sector_confirmed=sector_confirmed,
        has_active_workplace=is_workplace_complete(organisation),
        governance_roles_complete=is_governance_complete(organisation),
        all_controls_reviewed=progress["reviewed"] == progress["total"],
    )


__all__ = ["PolicyReadiness", "policy_readiness"]
