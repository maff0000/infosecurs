"""
M008E-WI2-INCREMENT-2 one-shot data seeding for the disposable m008ewi2incr2
stack's Customer Zero organisation. Run ONCE (before either the "before" or
"after" capture pass) - idempotent via get_or_create/unique titles so a
second accidental run does not explode, but intended as a single setup
step. Not part of the application.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from evidence.models import EvidenceItem  # noqa: E402
from governance.models import GovernanceRoleAssignment  # noqa: E402
from governance.services import assign_role, ensure_account_holder_person  # noqa: E402
from key_assets.models import CATEGORY_BUSINESS_APPLICATION, CRITICALITY_HIGH, KeyAsset  # noqa: E402
from organisations.models import (  # noqa: E402
    SECTOR_PROFESSIONAL_CONSULTING,
    Organisation,
    OrganisationProfile,
)
from policy.models import PolicyDocument, PolicyVersion  # noqa: E402
from remediation.models import RemediationAction  # noqa: E402
from risk_register.models import Risk  # noqa: E402
from security_baseline.services import record_structured_baseline_answer  # noqa: E402
from security_baseline.structured_catalogue import STRUCTURED_OPTIONS  # noqa: E402
from workplace.models import Workplace  # noqa: E402

LONG_TEXT = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - East Wing Warehouse Annex 3 Backup Controller Unit"
)

User = get_user_model()
org = Organisation.objects.get(name="Infosecurs Limited")
user = User.objects.get(username="customerzero")
print(f"organisation id = {org.id}")

# --- Governance roles + profile + workplace (policy readiness gate) -------
person = ensure_account_holder_person(org, user)
for role in (
    GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
    GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
    GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
):
    assign_role(organisation=org, role=role, person=person, assigned_by=user)

OrganisationProfile.objects.update_or_create(
    organisation=org,
    defaults={
        "legal_trading_name": "Infosecurs Limited",
        "sector": SECTOR_PROFESSIONAL_CONSULTING,
    },
)
Workplace.objects.get_or_create(
    organisation=org, name="HQ", defaults={"type": Workplace.TYPE_DEDICATED_OFFICE}
)

# --- Structured baseline answers (drives security_state rows + policy
#     readiness's "all controls reviewed" condition) ------------------------
for control_key, options in STRUCTURED_OPTIONS.items():
    option_code = next(iter(options.keys()))
    record_structured_baseline_answer(org, control_key, option_code, actor=user)
print("baseline answers recorded for all structured controls")

# --- Policy: one draft version with sections (policy:detail/version_detail/
#     edit/approve all need this) ------------------------------------------
document, _ = PolicyDocument.objects.get_or_create(organisation=org)
version, created = PolicyVersion.objects.get_or_create(
    document=document,
    organisation=org,
    version_number=1,
    defaults={
        "status": PolicyVersion.STATUS_DRAFT,
        "title": "Infosecurs Limited Information Security Policy",
        "sections": [
            {"section_key": "purpose_and_scope", "content": "This policy sets out how Infosecurs Limited protects its information assets."},
            {"section_key": "access_and_authentication", "content": "Access to systems is granted on a least-privilege basis and reviewed regularly."},
        ],
        "review_warnings": [],
    },
)
print(f"policy version id = {version.id} (created={created})")

# --- Evidence: active + superseded + withdrawn, one long title ------------
def _make_evidence(title, status, kind=EvidenceItem.KIND_EXTERNAL_REFERENCE):
    item, _created = EvidenceItem.objects.get_or_create(
        organisation=org,
        title=title,
        defaults={
            "kind": kind,
            "status": status,
            "reference_url": "https://example.test/evidence",
            "recorded_by": user,
        },
    )
    return item


active_evidence = _make_evidence("Annual penetration test executive summary", EvidenceItem.STATUS_ACTIVE)
_make_evidence(LONG_TEXT, EvidenceItem.STATUS_SUPERSEDED)
_make_evidence("Old firewall configuration export", EvidenceItem.STATUS_WITHDRAWN)
print(f"evidence active item id = {active_evidence.id}")

# --- Key assets: suggested / confirmed / dismissed -------------------------
def _make_asset(name, status):
    asset, _created = KeyAsset.objects.get_or_create(
        organisation=org,
        name=name,
        defaults={
            "category": CATEGORY_BUSINESS_APPLICATION,
            "criticality": CRITICALITY_HIGH,
            "status": status,
            "description": "A representative business application asset used for M008E-WI2-INCREMENT-2 screenshot capture.",
        },
    )
    return asset


suggested_asset = _make_asset(LONG_TEXT, KeyAsset.STATUS_SUGGESTED)
_make_asset("CRM platform", KeyAsset.STATUS_CONFIRMED)
_make_asset("Decommissioned file server", KeyAsset.STATUS_DISMISSED)
print(f"suggested asset id = {suggested_asset.id}")

# --- Risks: draft / confirmed / dismissed ----------------------------------
def _make_risk(title, status, impact, likelihood):
    risk, _created = Risk.objects.get_or_create(
        organisation=org,
        title=title,
        defaults={
            "threat": "Synthetic threat text for M008E-WI2-INCREMENT-2 screenshot capture.",
            "vulnerability": "Synthetic vulnerability text.",
            "impact": impact,
            "likelihood": likelihood,
            "rationale": "Synthetic rationale.",
            "proposed_treatment": "Synthetic proposed treatment.",
            "status": status,
            "source": Risk.SOURCE_AI,
        },
    )
    return risk


_make_risk(LONG_TEXT, Risk.STATUS_DRAFT_AI_SUGGESTED, 3, 3)
confirmed_risk = _make_risk("Outdated firmware on network switches", Risk.STATUS_CONFIRMED, 5, 5)
_make_risk("Unused legacy VPN endpoint", Risk.STATUS_DISMISSED, 2, 2)
print(f"confirmed risk id = {confirmed_risk.id}")

# --- Remediation actions: open / in_progress / done / accepted ------------
def _make_action(title, status, priority=RemediationAction.PRIORITY_MEDIUM):
    action, _created = RemediationAction.objects.get_or_create(
        organisation=org,
        title=title,
        defaults={"status": status, "priority": priority},
    )
    return action


open_action = _make_action("Roll out MFA to all admin accounts", RemediationAction.STATUS_OPEN, RemediationAction.PRIORITY_HIGH)
_make_action("Patch public-facing web server", RemediationAction.STATUS_IN_PROGRESS)
_make_action("Rotate shared service account credentials", RemediationAction.STATUS_DONE)
_make_action("Accept residual risk on legacy EPOS terminal", RemediationAction.STATUS_ACCEPTED)
print(f"open action id = {open_action.id}")

print("SEED COMPLETE")
