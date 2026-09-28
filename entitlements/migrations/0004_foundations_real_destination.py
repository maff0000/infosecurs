# M007-WI5 (PID §15, follow-on to 0002_seed_product_areas.py's own
# prominently-flagged judgement call): the real Foundations workspace view
# now exists (organisations:foundations) - this migration updates ONLY the
# `foundations` ProductArea row's own `destination_view_name` field, from
# the temporary `organisations:detail` placeholder 0002 seeded it with, to
# the real route. Nothing else about that row (label, parent, tier, order)
# changes, no other row is touched, and 0002/0003 themselves are left
# completely unmodified - this is a new, additive data migration, exactly
# as PID §22's "governed seed data" discipline requires.
from django.db import migrations

FOUNDATIONS_CODE = "foundations"
OLD_DESTINATION = "organisations:detail"
NEW_DESTINATION = "organisations:foundations"


def point_foundations_at_its_real_workspace(apps, schema_editor):
    ProductArea = apps.get_model("entitlements", "ProductArea")
    ProductArea.objects.filter(code=FOUNDATIONS_CODE).update(
        destination_view_name=NEW_DESTINATION
    )


def restore_foundations_placeholder_destination(apps, schema_editor):
    """Reverse: restore the exact placeholder 0002_seed_product_areas.py
    originally seeded, so a full rollback of this migration leaves the
    `foundations` row byte-identical to how 0002/0003 alone left it."""
    ProductArea = apps.get_model("entitlements", "ProductArea")
    ProductArea.objects.filter(code=FOUNDATIONS_CODE).update(
        destination_view_name=OLD_DESTINATION
    )


class Migration(migrations.Migration):

    dependencies = [
        ("entitlements", "0003_seed_foundation_requirements"),
    ]

    operations = [
        migrations.RunPython(
            point_foundations_at_its_real_workspace,
            restore_foundations_placeholder_destination,
        ),
    ]
