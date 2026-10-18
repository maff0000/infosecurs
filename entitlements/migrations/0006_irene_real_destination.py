# M010C (docs/pids/M010C-IRENE-MODAL-SKILLS-TOOLS.md §1, follow-on to
# 0005_seed_tasks_and_irene_product_areas.py's own prominently-flagged
# placeholder): the real IRENE workspace view now exists
# ("irene:workspace" - a dedicated, independently capability-gated
# direct-URL-enforcement route that redirects into Home with the modal
# forced open; see irene/views.py's own docstring for why there is no
# separate full-page template to maintain). This migration updates ONLY
# the `irene` ProductArea row's own `destination_view_name` field, from
# the temporary `organisations:detail` placeholder 0005 seeded it with,
# to the real route - mirroring EXACTLY how
# 0004_foundations_real_destination.py closed out the `foundations`
# row's own identical placeholder. Nothing else about the `irene` row
# (label, parent, tier, order, show_in_navigation) changes, no other row
# is touched, and 0002/0003/0004/0005 themselves are left completely
# unmodified.
#
# `show_in_navigation` stays `False` - unchanged by this migration. M010C
# wires its own, separate "Ask IRENE" trigger button directly into
# organisations/templates/organisations/detail.html (gated on the exact
# same `has_capability(request, "irene")` decision, via irene.views.
# build_modal_context), rather than relying on entitlements.navigation.
# build_navigation_tree's generic nav_tree loop - that generic loop has
# no mechanism to carry the "?irene=open" query string the trigger
# button's own link needs to force the modal open, and IRENE genuinely is
# a modal entry point rather than a distinct sidebar PAGE (0005's own
# documented reasoning for `show_in_navigation=False` still holds, now
# for a real reason rather than a placeholder one).
from django.db import migrations

IRENE_CODE = "irene"
OLD_DESTINATION = "organisations:detail"
NEW_DESTINATION = "irene:workspace"


def point_irene_at_its_real_workspace(apps, schema_editor):
    ProductArea = apps.get_model("entitlements", "ProductArea")
    ProductArea.objects.filter(code=IRENE_CODE).update(destination_view_name=NEW_DESTINATION)


def restore_irene_placeholder_destination(apps, schema_editor):
    """Reverse: restore the exact placeholder 0005 originally seeded, so
    a full rollback of this migration leaves the `irene` row
    byte-identical to how 0005 alone left it."""
    ProductArea = apps.get_model("entitlements", "ProductArea")
    ProductArea.objects.filter(code=IRENE_CODE).update(destination_view_name=OLD_DESTINATION)


class Migration(migrations.Migration):

    dependencies = [
        ("entitlements", "0005_seed_tasks_and_irene_product_areas"),
    ]

    operations = [
        migrations.RunPython(
            point_irene_at_its_real_workspace,
            restore_irene_placeholder_destination,
        ),
    ]
