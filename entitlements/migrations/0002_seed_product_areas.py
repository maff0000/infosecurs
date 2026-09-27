# M007-WI1 (PID §4.3/§22): governed seed data, landed via a data migration
# so `migrate` alone deterministically produces these exact rows on a fresh
# database - never a runtime management command that could be skipped.
#
# The 16 rows below are the PID's own Appendix A illustrative seed table,
# taken verbatim for code/label/parent/min_package_tier, with one
# documented judgement call:
#
#   `foundations` (a top-level area) has no existing view to point at yet -
#   the Foundations workspace is explicitly WI5's own scope (PID §35), not
#   built in WI1. Rather than invent a URL name that does not exist (which
#   would fail this WI's own reverse()-resolution test, and would not be an
#   honest destination), this migration temporarily points `foundations` at
#   the existing organisation Overview page (`organisations:detail`) - the
#   same destination `home` uses today, before any Foundations-specific
#   page exists. This is flagged prominently in the WI1 report for PL/
#   Central Architecture confirmation: WI5 MUST land a follow-on data
#   migration updating this one row's `destination_view_name` once the real
#   Foundations workspace view exists. Every other row below reuses an
#   existing, already-reachable route exactly as PID §3.2 asks.
from django.db import migrations


# code -> (label, parent_code, destination_view_name, min_package_tier, display_order)
SEED_ROWS = [
    ("home", "Home", None, "organisations:detail", 0, 10),
    # JUDGEMENT CALL - see module docstring above: temporary placeholder
    # destination pending WI5's own Foundations workspace view.
    ("foundations", "Foundations", None, "organisations:detail", 1, 20),
    ("customer_assurance", "Customer Assurance", None, "questionnaire:list", 2, 30),
    ("security", "Security", None, "security_state:list", 1, 40),
    ("security_state", "Security State", "security", "security_state:list", 1, 41),
    ("baseline", "Baseline", "security", "security_baseline:baseline", 1, 42),
    ("assets", "Assets", "security", "key_assets:list", 1, 43),
    ("risks", "Risks", "security", "risk_register:list", 1, 44),
    ("evidence", "Evidence", "security", "evidence:list", 1, 45),
    ("remediation", "Remediation", "security", "remediation:list", 1, 46),
    ("policies", "Policies", None, "policy:detail", 1, 50),
    ("company", "Company", None, "organisations:organisation_hub", 1, 60),
    ("profile", "Profile", "company", "organisations:profile", 1, 61),
    ("governance", "Governance", "company", "governance:roles", 1, 62),
    ("workplace", "Workplace", "company", "workplace:list", 1, 63),
    ("activity", "Activity", "company", "activity:list", 1, 64),
]

SEED_CODES = [row[0] for row in SEED_ROWS]


def seed_product_areas(apps, schema_editor):
    ProductArea = apps.get_model("entitlements", "ProductArea")

    # Pass 1: create every row with no parent set yet - a child's parent
    # code may not have a row (and therefore no pk) until its own pass 1
    # insert has happened, so parenting is resolved entirely in pass 2 by
    # `code`, never by an assumed/guessed pk ordering.
    for code, label, _parent_code, destination_view_name, min_package_tier, display_order in SEED_ROWS:
        ProductArea.objects.create(
            code=code,
            label=label,
            parent=None,
            destination_view_name=destination_view_name,
            min_package_tier=min_package_tier,
            display_order=display_order,
            show_in_navigation=True,
            is_active=True,
        )

    # Pass 2: wire up parents by code.
    by_code = {area.code: area for area in ProductArea.objects.filter(code__in=SEED_CODES)}
    for code, _label, parent_code, *_ in SEED_ROWS:
        if parent_code is None:
            continue
        area = by_code[code]
        area.parent = by_code[parent_code]
        area.save(update_fields=["parent"])


def unseed_product_areas(apps, schema_editor):
    """Reverse: remove exactly the rows this migration created, identified
    by `code` - never a blanket table wipe, so this stays safe even if a
    later migration has added unrelated rows. Children are deleted before
    parents to respect the PROTECT FK."""
    ProductArea = apps.get_model("entitlements", "ProductArea")
    # Children first (non-null parent among the seeded set), then
    # top-level rows - a simple two-pass delete mirrors the two-pass
    # create above and avoids relying on PROTECT ordering.
    child_codes = [code for code, _label, parent_code, *_ in SEED_ROWS if parent_code is not None]
    top_codes = [code for code, _label, parent_code, *_ in SEED_ROWS if parent_code is None]
    ProductArea.objects.filter(code__in=child_codes).delete()
    ProductArea.objects.filter(code__in=top_codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("entitlements", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_product_areas, unseed_product_areas),
    ]
