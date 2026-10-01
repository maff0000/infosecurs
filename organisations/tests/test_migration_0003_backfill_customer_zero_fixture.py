"""
M008A-WI1a mechanical proof for organisations/migrations/
0003_backfill_customer_zero_fixture.py's three explicit backfill cases
(PID-style "rollback behaviour understood/documented" discipline, same
approach as entitlements/tests/test_migration_0004_foundations_destination.py).

Deliberately does NOT use Django's `MigrationExecutor` to physically flip
migration/schema state - see that file's own module docstring for why
(this project's `--reuse-db`/no-`serialized_rollback` pytest-django wiring
has no established pattern for restoring other data-migration-seeded rows
after a flushing `transaction=True` test). Calling
`backfill_customer_zero_fixture`/`remove_backfilled_customer_zero_fixture`
directly - passing the real, live `django.apps.apps` registry, the exact
same concrete `Organisation`/`CustomerZeroFixture` models those functions
already operate on via `apps.get_model(...)` - proves the exact same
forward/reverse behaviour Django's migration runner performs when it calls
them, safely, under this codebase's ordinary transaction-rollback `db`
fixture.
"""
from __future__ import annotations

import importlib

import pytest
from django.apps import apps as live_apps

from organisations.models import CustomerZeroFixture, Organisation

pytestmark = pytest.mark.django_db

_migration_0003 = importlib.import_module(
    "organisations.migrations.0003_backfill_customer_zero_fixture"
)

ENV_VAR = "CUSTOMER_ZERO_ORGANISATION_NAME"


class TestEnvVarUnset:
    def test_unset_env_var_is_a_no_op_not_an_error(self, monkeypatch, org_a):
        monkeypatch.delenv(ENV_VAR, raising=False)

        _migration_0003.backfill_customer_zero_fixture(live_apps, None)

        assert CustomerZeroFixture.objects.count() == 0


class TestEnvVarSetNoMatch:
    def test_env_var_set_but_zero_matching_organisations_is_a_no_op(self, monkeypatch, org_a):
        """`org_a`'s name does not match - this is the "fresh bootstrap
        hasn't run yet" case, not an error."""
        monkeypatch.setenv(ENV_VAR, "No Such Organisation Exists Yet Ltd")

        _migration_0003.backfill_customer_zero_fixture(live_apps, None)

        assert CustomerZeroFixture.objects.count() == 0


class TestEnvVarSetExactlyOneMatch:
    def test_backfills_the_one_matching_organisation(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "The Real Customer Zero Org")
        organisation = Organisation.objects.create(name="The Real Customer Zero Org")

        _migration_0003.backfill_customer_zero_fixture(live_apps, None)

        assert CustomerZeroFixture.objects.filter(organisation=organisation).count() == 1

    def test_is_idempotent_if_run_again(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "The Real Customer Zero Org")
        organisation = Organisation.objects.create(name="The Real Customer Zero Org")

        _migration_0003.backfill_customer_zero_fixture(live_apps, None)
        _migration_0003.backfill_customer_zero_fixture(live_apps, None)

        assert CustomerZeroFixture.objects.filter(organisation=organisation).count() == 1

    def test_does_not_touch_an_unrelated_organisation(self, monkeypatch, org_a):
        monkeypatch.setenv(ENV_VAR, "The Real Customer Zero Org")
        organisation = Organisation.objects.create(name="The Real Customer Zero Org")

        _migration_0003.backfill_customer_zero_fixture(live_apps, None)

        assert CustomerZeroFixture.objects.filter(organisation=organisation).count() == 1
        assert not CustomerZeroFixture.objects.filter(organisation=org_a).exists()


class TestEnvVarSetMultipleMatches:
    def test_raises_loudly_instead_of_guessing(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "Ambiguous Duplicate Org")
        Organisation.objects.create(name="Ambiguous Duplicate Org")
        Organisation.objects.create(name="Ambiguous Duplicate Org")

        with pytest.raises(RuntimeError):
            _migration_0003.backfill_customer_zero_fixture(live_apps, None)

        # Refused to guess - no fixture row created for either candidate.
        assert CustomerZeroFixture.objects.count() == 0


class TestReverse:
    def test_removes_only_the_backfilled_organisations_fixture_row(self, monkeypatch, org_a):
        monkeypatch.setenv(ENV_VAR, "The Real Customer Zero Org")
        organisation = Organisation.objects.create(name="The Real Customer Zero Org")
        CustomerZeroFixture.objects.create(organisation=organisation)
        # An unrelated fixture row (e.g. one created directly by
        # create_customer_zero for a differently-named org) must survive.
        CustomerZeroFixture.objects.create(organisation=org_a)

        _migration_0003.remove_backfilled_customer_zero_fixture(live_apps, None)

        assert not CustomerZeroFixture.objects.filter(organisation=organisation).exists()
        assert CustomerZeroFixture.objects.filter(organisation=org_a).exists()

    def test_reverse_with_env_var_unset_is_a_no_op(self, monkeypatch, org_a):
        monkeypatch.setenv(ENV_VAR, "The Real Customer Zero Org")
        organisation = Organisation.objects.create(name="The Real Customer Zero Org")
        CustomerZeroFixture.objects.create(organisation=organisation)

        monkeypatch.delenv(ENV_VAR, raising=False)
        _migration_0003.remove_backfilled_customer_zero_fixture(live_apps, None)

        assert CustomerZeroFixture.objects.filter(organisation=organisation).exists()


class TestRoundTrip:
    def test_apply_then_unapply_returns_to_zero_fixture_rows(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "The Real Customer Zero Org")
        organisation = Organisation.objects.create(name="The Real Customer Zero Org")

        _migration_0003.backfill_customer_zero_fixture(live_apps, None)
        assert CustomerZeroFixture.objects.filter(organisation=organisation).count() == 1

        _migration_0003.remove_backfilled_customer_zero_fixture(live_apps, None)
        assert not CustomerZeroFixture.objects.filter(organisation=organisation).exists()
