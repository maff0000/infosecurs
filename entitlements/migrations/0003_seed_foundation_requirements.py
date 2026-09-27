# M007-WI1 (PID §10/§22): governed seed data for the requirement/
# methodology registry - 12 BASELINE_CONTROL rows (one per
# security_baseline.catalogue key, §11.4's weight table verbatim) + 6
# DERIVED_MILESTONE rows (§12.3's remaining Foundations items), landed via
# a data migration for the same reason as 0002: `migrate` alone must
# deterministically produce these exact 18 rows on a fresh database.
#
# `source_key` for the 12 baseline rows is the exact
# `security_baseline.catalogue.CATALOGUE_KEYS` string (per this dispatch's
# PL recon notes) - this migration intentionally does NOT import that
# catalogue module (a data migration must not depend on application code
# that can change shape later; it hard-codes the *current* keys as of this
# methodology version, which is exactly what "the metric result should
# retain its methodology version" (PID §10.3) is protecting against
# silently drifting).
from django.db import migrations


FOUNDATION_METRIC_VERSION = "2026-09-v1"

BASELINE_CONTROL = "BASELINE_CONTROL"
DERIVED_MILESTONE = "DERIVED_MILESTONE"

# (code, title, source_key, security_weight, display_order)
# security_weight per PID §11.4's table verbatim. product_area is "baseline"
# (Security > Baseline) for all 12 - not repeated per row below, applied as
# a constant in seed_foundation_requirements().
BASELINE_PRODUCT_AREA_CODE = "baseline"
BASELINE_ROWS = [
    ("baseline_mfa_user_accounts", "Multi-factor authentication (staff)", "mfa_user_accounts", 3, 1),
    ("baseline_mfa_privileged_accounts", "Multi-factor authentication (admin)", "mfa_privileged_accounts", 5, 2),
    ("baseline_endpoint_protection", "Endpoint protection", "endpoint_protection", 3, 3),
    ("baseline_patching", "Patching", "patching", 5, 4),
    ("baseline_device_encryption", "Device encryption", "device_encryption", 3, 5),
    ("baseline_backups", "Backups", "backups", 5, 6),
    ("baseline_joiner_mover_leaver", "Access removal", "joiner_mover_leaver", 3, 7),
    ("baseline_privileged_access_separation", "Privileged access", "privileged_access_separation", 3, 8),
    ("baseline_security_awareness_training", "Staff awareness", "security_awareness_training", 1, 9),
    ("baseline_incident_reporting_route", "Incident reporting", "incident_reporting_route", 1, 10),
    ("baseline_email_phishing_protection", "Email/phishing protection", "email_phishing_protection", 3, 11),
    ("baseline_remote_access_control", "Remote access", "remote_access_control", 3, 12),
]

# (code, title, product_area_code, source_key, display_order) - PID §12.3's
# remaining 6 completion items. security_weight is not meaningful for these
# (they never participate in posture, v1 - PID §11.2/§12.1) so left at the
# model default of 0; counts_toward_posture=False for all six.
MILESTONE_ROWS = [
    ("milestone_organisation_profile", "Organisation profile", "profile", "organisation_profile", 13),
    ("milestone_governance_roles", "Governance roles assigned", "governance", "governance_roles", 14),
    ("milestone_workplace", "At least one active workplace recorded", "workplace", "workplace", 15),
    ("milestone_assets_review", "Asset review complete", "assets", "assets_review", 16),
    ("milestone_risks_review", "Risk review complete", "risks", "risks_review", 17),
    ("milestone_policy_approved", "Information Security Policy approved", "policies", "policy_approved", 18),
]

BASELINE_CODES = [row[0] for row in BASELINE_ROWS]
MILESTONE_CODES = [row[0] for row in MILESTONE_ROWS]


def seed_foundation_requirements(apps, schema_editor):
    ProductArea = apps.get_model("entitlements", "ProductArea")
    FoundationRequirement = apps.get_model("entitlements", "FoundationRequirement")

    area_by_code = {area.code: area for area in ProductArea.objects.all()}
    baseline_area = area_by_code[BASELINE_PRODUCT_AREA_CODE]

    for code, title, source_key, security_weight, display_order in BASELINE_ROWS:
        FoundationRequirement.objects.create(
            code=code,
            title=title,
            product_area=baseline_area,
            methodology_version=FOUNDATION_METRIC_VERSION,
            requirement_kind=BASELINE_CONTROL,
            source_key=source_key,
            min_package_tier=baseline_area.min_package_tier,
            counts_toward_posture=True,
            counts_toward_completion=True,
            security_weight=security_weight,
            display_order=display_order,
            is_active=True,
        )

    for code, title, product_area_code, source_key, display_order in MILESTONE_ROWS:
        FoundationRequirement.objects.create(
            code=code,
            title=title,
            product_area=area_by_code[product_area_code],
            methodology_version=FOUNDATION_METRIC_VERSION,
            requirement_kind=DERIVED_MILESTONE,
            source_key=source_key,
            min_package_tier=area_by_code[product_area_code].min_package_tier,
            counts_toward_posture=False,
            counts_toward_completion=True,
            security_weight=0,
            display_order=display_order,
            is_active=True,
        )


def unseed_foundation_requirements(apps, schema_editor):
    FoundationRequirement = apps.get_model("entitlements", "FoundationRequirement")
    FoundationRequirement.objects.filter(code__in=BASELINE_CODES + MILESTONE_CODES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("entitlements", "0002_seed_product_areas"),
    ]

    operations = [
        migrations.RunPython(seed_foundation_requirements, unseed_foundation_requirements),
    ]
