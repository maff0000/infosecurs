"""
Root conftest. Provides safe, non-secret defaults for required environment
variables so the test suite can run without a hand-authored .env - real
environments (CI, docker-compose) set these for real and take precedence
because we only use setdefault().
"""
import os

os.environ.setdefault("DJANGO_ENV", "test")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production-use")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

os.environ.setdefault("POSTGRES_DB", "infosecurs_test")
os.environ.setdefault("POSTGRES_USER", "infosecurs")
os.environ.setdefault("POSTGRES_PASSWORD", "test-only-password-not-for-production")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")

os.environ.setdefault("CUSTOMER_ZERO_USERNAME", "customerzero")
os.environ.setdefault("CUSTOMER_ZERO_EMAIL", "customerzero@example.test")
os.environ.setdefault("CUSTOMER_ZERO_PASSWORD", "test-only-password-not-for-production")
os.environ.setdefault("CUSTOMER_ZERO_ORGANISATION_NAME", "Infosecurs Limited")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _wi6_ensure_entitlements_seed_data(request):
    """
    WI6 (real-browser acceptance capability) finding, not a product defect:
    `@pytest.mark.django_db(transaction=True)` - used only by this
    codebase's real-browser Playwright `live_server` tests (real HTTP needs
    real commits, not the ordinary savepoint-rollback plain `django_db`
    tests get) - flushes the whole test database between tests, including
    the `ProductArea`/`FoundationRequirement` rows `entitlements/
    migrations/0002_seed_product_areas.py`/`0003_seed_foundation_
    requirements.py` seed. This project's own pytest-django wiring
    (`pytest.ini`'s `--reuse-db`, no `serialized_rollback` anywhere) has no
    built-in mechanism to restore them afterward -
    `entitlements/tests/test_migration_0004_foundations_destination.py`'s
    own docstring already flagged this exact gap as a known, deferred risk
    ("no established pattern for restoring data-migration-seeded rows
    after a transaction=True-style test flushes the database"), believing
    it safe at the time because no `transaction=True` test yet depended on
    that seed data. `entitlements.decorators.require_capability` (WI3) now
    does, via `entitlements.capabilities.has_capability` -> `ProductArea`
    - so once more than one real-browser test runs in a single session,
    every test after the first genuinely lost its seed data and every
    capability-guarded route started returning a blanket 403, discovered
    only now that WI6 makes Playwright actually installable and these
    tests actually run instead of skip (see docs/evidence/
    M007-BROWSER-ACCEPTANCE.md for the full diagnosis).

    Idempotent and additive-only (never deletes/modifies an existing row;
    a fast `exists()` check is a no-op for every test that does not need
    it, including every non-`django_db` test, which this fixture returns
    from immediately without touching the database at all). Reseeds by
    calling the exact same functions the real migrations call, against the
    real live `django.apps.apps` registry - the identical, already-
    established technique `test_migration_0004_foundations_destination.py`
    uses to call these functions safely outside an actual migration run,
    in the correct dependency order (0002 before 0003 - `0003_seed_
    foundation_requirements.py`'s own `seed_foundation_requirements`
    requires `ProductArea` rows to already exist; 0004 last, so a reseed
    always lands on the CURRENT accepted state - the real Foundations
    workspace destination - not 0002's own original placeholder).
    """
    if request.node.get_closest_marker("django_db") is None:
        return

    request.getfixturevalue("db")

    from entitlements.models import ProductArea

    if ProductArea.objects.exists():
        return

    import importlib

    from django.apps import apps as live_apps

    seed_areas = importlib.import_module("entitlements.migrations.0002_seed_product_areas")
    seed_areas.seed_product_areas(live_apps, None)

    seed_requirements = importlib.import_module(
        "entitlements.migrations.0003_seed_foundation_requirements"
    )
    seed_requirements.seed_foundation_requirements(live_apps, None)

    repoint_foundations = importlib.import_module(
        "entitlements.migrations.0004_foundations_real_destination"
    )
    repoint_foundations.point_foundations_at_its_real_workspace(live_apps, None)

    # M010A/M010C: the same gap, now extended forward rather than
    # silently reopened. `0005_seed_tasks_and_irene_product_areas.py`
    # seeds the `tasks`/`irene` rows `security_tasks`/`irene`'s own
    # `require_capability()`-guarded routes depend on; `0006_irene_real_
    # destination.py` then repoints `irene` at its real workspace route,
    # exactly mirroring 0004's own repoint of `foundations` immediately
    # above. Without these two calls, `irene/tests/test_browser_
    # acceptance.py` (a `transaction=True` test) flushing the database
    # would silently strand every `irene`/`security_tasks` capability-
    # guarded test that happens to run afterward in the same session with
    # a blanket 403 - the exact same class of discovery this fixture's
    # own docstring already describes for WI6, now recurring for M010A/
    # M010C's own later-added seed rows.
    seed_tasks_and_irene = importlib.import_module(
        "entitlements.migrations.0005_seed_tasks_and_irene_product_areas"
    )
    seed_tasks_and_irene.seed_tasks_and_irene(live_apps, None)

    repoint_irene = importlib.import_module(
        "entitlements.migrations.0006_irene_real_destination"
    )
    repoint_irene.point_irene_at_its_real_workspace(live_apps, None)
