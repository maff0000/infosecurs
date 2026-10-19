# M010A PID §2 ("Add ProductArea capability for Tasks / IRENE using
# existing seed/migration and route enforcement doctrine... Existing 16
# ProductArea rows must not be silently changed or repurposed").
#
# Strictly additive: this migration INSERTS exactly two new rows (`tasks`,
# `irene`) and touches nothing else. It never updates, deletes, or
# reorders any of the 16 rows 0002_seed_product_areas.py seeded (verified
# directly - see docs/evidence/M010A-TASK-SPINE.md's migration-diff proof
# and entitlements/tests/test_seed_data.py's own pre-existing 16-row
# count assertion, left completely unmodified by this package).
#
# Two rows, two judgement calls, both documented here rather than guessed
# at silently:
#
#   - `tasks`: a REAL, top-level navigation entry for the Tasks sidebar
#     page this package builds (security_tasks:list), min_package_tier=1
#     (Foundational tier and above - M010-MASTER-ARCHITECTURE.md §9's
#     "Foundational: ...safe task management..."), display_order=25 -
#     placed between `foundations` (20) and `customer_assurance` (30),
#     matching M010-MASTER-ARCHITECTURE.md §1's explicit ordering: "The
#     sidebar retains Dashboard, Foundations and Tasks".
#
#   - `irene`: the PLACEHOLDER M010A PID §2 itself asks for ("a placeholder
#     for the future IRENE modal entry point") - M010C (a LATER work
#     package in this same campaign) owns the real IRENE modal/view; no
#     such view exists yet in this package's scope. This row is seeded
#     `is_active=True` (so `has_capability(request, "irene")` is already
#     callable and correct once M010C wires a real check onto it) but
#     `show_in_navigation=False` (IRENE is a modal entry point, not a
#     sidebar page - M010-MASTER-ARCHITECTURE.md §8's "AI Adviser is a
#     central entry, not a corner widget" never describes it as a nav
#     list item - unlike `foundations`'s original 0002 placeholder, which
#     WAS a real, intended nav item simply missing its final view, showing
#     a sidebar link here that only ever redirects to Home would be
#     actively misleading). `destination_view_name` reuses
#     `organisations:detail` - the exact same "point at an existing, real
#     route rather than invent one that does not exist" discipline
#     0002_seed_product_areas.py's own docstring establishes for
#     `foundations`'s original placeholder. M010C must land its own
#     follow-on migration updating ONLY this row's `destination_view_name`
#     (and, if a real modal needs no destination route at all, that is
#     M010C's own documented call to make) - mirroring exactly how
#     0004_foundations_real_destination.py closed out `foundations`'s
#     placeholder.
from django.db import migrations

NEW_SEED_ROWS = [
    # code, label, parent_code, destination_view_name, min_package_tier,
    # display_order, show_in_navigation
    ("tasks", "Tasks", None, "security_tasks:list", 1, 25, True),
    ("irene", "IRENE", None, "organisations:detail", 1, 9999, False),
]

NEW_SEED_CODES = [row[0] for row in NEW_SEED_ROWS]


def seed_tasks_and_irene(apps, schema_editor):
    ProductArea = apps.get_model("entitlements", "ProductArea")
    for code, label, parent_code, destination_view_name, min_package_tier, display_order, show_in_navigation in NEW_SEED_ROWS:
        ProductArea.objects.create(
            code=code,
            label=label,
            parent=None,
            destination_view_name=destination_view_name,
            min_package_tier=min_package_tier,
            display_order=display_order,
            show_in_navigation=show_in_navigation,
            is_active=True,
        )
        if parent_code is not None:
            area = ProductArea.objects.get(code=code)
            area.parent = ProductArea.objects.get(code=parent_code)
            area.save(update_fields=["parent"])


def unseed_tasks_and_irene(apps, schema_editor):
    """Reverse: remove exactly the two rows this migration created,
    identified by code - never a blanket delete, so any OTHER row added
    by a later migration is left untouched."""
    ProductArea = apps.get_model("entitlements", "ProductArea")
    ProductArea.objects.filter(code__in=NEW_SEED_CODES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("entitlements", "0004_foundations_real_destination"),
    ]

    operations = [
        migrations.RunPython(seed_tasks_and_irene, unseed_tasks_and_irene),
    ]
