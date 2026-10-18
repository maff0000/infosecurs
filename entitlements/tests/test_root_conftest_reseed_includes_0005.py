"""
Proves the root `conftest.py`'s `_wi6_ensure_entitlements_seed_data`
autouse fixture genuinely restores the M010A `tasks`/`irene` `ProductArea`
rows after the table is flushed to empty under a REUSED test database -
not merely "a fresh `--create-db` run happens to include them" (every
such run migrates from zero anyway, which is a weaker and different
claim - see `test_seed_data.py`'s own docstring for that proof).

Central Architecture's own 2026-10-18 integration-review finding asked
for this proof "with sequential tests using a reused database, not
merely avoided through fresh-database reruns". Relying on exactly when
Django/pytest-django's own `TransactionTestCase`-style teardown flush
happens relative to a separately-declared following test turned out, on
direct investigation, not to be a reliably observable thing across
pytest invocations against a reused `test_infosecurs` database - so this
test makes the flush itself explicit and deterministic instead of
depending on that implicit timing. A plain `ProductArea.objects.all().
delete()` is blocked by this table's own real `PROTECT` foreign keys
(`ProductArea.parent`, `FoundationRequirement.product_area`) - exactly
as it should be in ordinary application code - so this test uses a raw
`TRUNCATE ... CASCADE`, the same mechanism Django's own real flush
command (`manage.py flush`, and `TransactionTestCase._fixture_teardown`)
uses specifically because it bypasses ORM-level protection by design, to
genuinely and deterministically reproduce "the table was really
emptied" as its SOLE effect under `transaction=True` (so the truncate
commits for real, not rolled back the way an ordinary `django_db` test's
writes are).
"""
from __future__ import annotations

import pytest
from django.db import connection

from entitlements.models import FoundationRequirement, ProductArea


class TestRootConftestReseedIncludesMigration0005:
    @pytest.mark.django_db(transaction=True)
    def test_a_explicitly_truncates_product_area_to_simulate_a_real_flush(self):
        # Sanity: the autouse fixture has already ensured this table is
        # non-empty by the time this test's own body runs.
        assert ProductArea.objects.exists()

        with connection.cursor() as cursor:
            cursor.execute(
                f'TRUNCATE TABLE "{ProductArea._meta.db_table}", '
                f'"{FoundationRequirement._meta.db_table}" CASCADE;'
            )
        assert not ProductArea.objects.exists()

    @pytest.mark.django_db
    def test_b_the_next_test_still_sees_tasks_and_irene_rows(self):
        # Runs immediately after the test above (pytest's own default
        # same-class declaration-order execution - no randomisation
        # plugin is installed in this project, confirmed directly against
        # requirements-dev.txt/pytest.ini). The table was genuinely
        # truncated, for real, by that test's own explicit statement - so
        # whatever rows exist here were put there by THIS test's own
        # autouse fixture invocation, not merely left over from container
        # startup's real `migrate`.
        codes = set(ProductArea.objects.values_list("code", flat=True))
        assert {"tasks", "irene"} <= codes, (
            "the M010A tasks/irene ProductArea rows were not restored after "
            f"the table was flushed - full code set seen: {sorted(codes)}"
        )
        assert len(codes) == 18  # the original 16 + exactly these 2
