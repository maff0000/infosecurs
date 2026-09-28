"""
M007-WI5 mechanical reversibility test for entitlements/migrations/
0004_foundations_real_destination.py (PID §22's "rollback behaviour
understood/documented" requirement).

Deliberately does NOT use Django's `MigrationExecutor` to physically flip
migration/schema state back and forth. Migrations 0002-0004 in this app are
pure `RunPython` data migrations (no schema change at all), and this
project's own pytest-django wiring (`pytest.ini`'s `--reuse-db`, no
`serialized_rollback` anywhere) has no established pattern for restoring
data-migration-seeded rows after a `transaction=True`/`TransactionTestCase`
-style test flushes the database - the only `transaction=True` usage
anywhere in this codebase is real-browser Playwright `live_server` tests
(e.g. `core/tests/test_responsive_text_regression.py`), none of which touch
migration state at all. Physically un-/re-applying 0004 via
`MigrationExecutor` under a flushing fixture would risk silently wiping
every OTHER test's seeded `ProductArea`/`FoundationRequirement` rows for the
rest of the pytest session, with no mechanism to reseed them afterward
(Django's `post_migrate` signal never re-runs a data migration's
`RunPython`).

Calling this migration's own `point_foundations_at_its_real_workspace`/
`restore_foundations_placeholder_destination` functions directly instead -
passing the real, live `django.apps.apps` registry (the exact same concrete
`ProductArea` model those functions already operate on via
`apps.get_model(...)`) - proves the exact same forward/reverse behaviour
Django's migration runner performs when it calls them, safely, under this
codebase's ordinary transaction-rollback `db` fixture (each test's writes
roll back automatically at test end - no flush, no risk to any other test).
"""
from __future__ import annotations

import importlib

import pytest
from django.apps import apps as live_apps

from entitlements.models import ProductArea

pytestmark = pytest.mark.django_db

_migration_0004 = importlib.import_module(
    "entitlements.migrations.0004_foundations_real_destination"
)

PLACEHOLDER_DESTINATION = "organisations:detail"  # 0002_seed_product_areas.py's original seed
REAL_DESTINATION = "organisations:foundations"


class TestForward:
    def test_updates_only_the_foundations_row_to_the_real_destination(self):
        ProductArea.objects.filter(code="foundations").update(
            destination_view_name=PLACEHOLDER_DESTINATION
        )
        other_rows_before = {
            area.code: area.destination_view_name
            for area in ProductArea.objects.exclude(code="foundations")
        }

        _migration_0004.point_foundations_at_its_real_workspace(live_apps, None)

        assert (
            ProductArea.objects.get(code="foundations").destination_view_name
            == REAL_DESTINATION
        )
        other_rows_after = {
            area.code: area.destination_view_name
            for area in ProductArea.objects.exclude(code="foundations")
        }
        assert other_rows_after == other_rows_before  # no other row touched


class TestReverse:
    def test_restores_the_exact_original_placeholder_destination(self):
        ProductArea.objects.filter(code="foundations").update(
            destination_view_name=REAL_DESTINATION
        )

        _migration_0004.restore_foundations_placeholder_destination(live_apps, None)

        assert (
            ProductArea.objects.get(code="foundations").destination_view_name
            == PLACEHOLDER_DESTINATION
        )


class TestRoundTrip:
    def test_apply_then_unapply_returns_to_the_exact_starting_value(self):
        ProductArea.objects.filter(code="foundations").update(
            destination_view_name=PLACEHOLDER_DESTINATION
        )

        _migration_0004.point_foundations_at_its_real_workspace(live_apps, None)
        assert (
            ProductArea.objects.get(code="foundations").destination_view_name
            == REAL_DESTINATION
        )

        _migration_0004.restore_foundations_placeholder_destination(live_apps, None)
        assert (
            ProductArea.objects.get(code="foundations").destination_view_name
            == PLACEHOLDER_DESTINATION
        )
