# M008A-WI1a: backfill a `CustomerZeroFixture` row for the Customer Zero
# organisation that may already exist on a live stack bootstrapped before
# this model existed (e.g. the dev stack at 192.168.11.10:8884). Every
# *future* `create_customer_zero` run creates its own fixture row directly
# (see organisations/management/commands/create_customer_zero.py) - this
# migration only needs to cover the one already-existing pre-this-change
# organisation.
#
# Reads `CUSTOMER_ZERO_ORGANISATION_NAME` straight from `os.environ`
# (never through `config.env.require_env`/`optional_env`): those helpers
# are the house convention for application code serving a request, but a
# data migration runs at `migrate` time, outside any request, where
# reading `os.environ` directly is the normal Django idiom.
#
# Three explicit cases, none of which silently guesses:
#   - Env var unset (or a fresh CI container that never sets it) -> skip.
#     Nothing to backfill, and on a genuinely fresh database no
#     Organisation rows exist yet anyway.
#   - Env var set but zero Organisation rows match it -> also skip, not an
#     error. This is the same "nothing to backfill yet" case as above -
#     bootstrap just hasn't run on this database yet.
#   - Env var set and exactly one Organisation row matches -> backfill its
#     fixture row. This is the live dev-stack's actual case.
#   - Env var set and MORE THAN ONE Organisation row matches -> genuinely
#     ambiguous. Raise loudly and fail the `migrate` run rather than guess
#     - `create_customer_zero`'s own `get_or_create(name=...)` would never
#     itself create two, but this migration must not assume that
#     invariant holds forever.
import os

from django.db import migrations

ENV_VAR = "CUSTOMER_ZERO_ORGANISATION_NAME"


def backfill_customer_zero_fixture(apps, schema_editor):
    organisation_name = os.environ.get(ENV_VAR)
    if not organisation_name:
        return  # unset at migration time - nothing to backfill

    Organisation = apps.get_model("organisations", "Organisation")
    CustomerZeroFixture = apps.get_model("organisations", "CustomerZeroFixture")

    matches = list(Organisation.objects.filter(name=organisation_name))

    if not matches:
        return  # env var set, but bootstrap hasn't created this org yet

    if len(matches) > 1:
        raise RuntimeError(
            f"{ENV_VAR}={organisation_name!r} matches {len(matches)} "
            "Organisation rows - ambiguous, refusing to guess which one is "
            "the trusted Customer Zero fixture. Resolve by hand (rename or "
            "merge the duplicates) before re-running migrate."
        )

    CustomerZeroFixture.objects.get_or_create(organisation=matches[0])


def remove_backfilled_customer_zero_fixture(apps, schema_editor):
    """Reverse: remove only the fixture row forward's own lookup would
    have created for the env-var-identified organisation - never a
    blanket table wipe, so this stays safe even if a later migration has
    added unrelated fixture rows. No-op if the env var is unset or no
    organisation matches it."""
    organisation_name = os.environ.get(ENV_VAR)
    if not organisation_name:
        return

    CustomerZeroFixture = apps.get_model("organisations", "CustomerZeroFixture")
    CustomerZeroFixture.objects.filter(organisation__name=organisation_name).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("organisations", "0002_customerzerofixture"),
    ]

    operations = [
        migrations.RunPython(
            backfill_customer_zero_fixture,
            remove_backfilled_customer_zero_fixture,
        ),
    ]
