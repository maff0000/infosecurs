"""
M006 Round 6 (PID §15/§C, §22) - DEBUG=False static-file serving.

Round 2 identified, and this round closes, a real gap: plain
`manage.py runserver` only auto-serves STATICFILES_DIRS content when
DEBUG=True. Under the real DJANGO_ENV=production release-artifact proof,
every static asset (the one product stylesheet,
static/organisations/css/app.css, plus Django admin's own bundled static
files) was unreachable without WhiteNoise.

A second, genuinely-reproduced gap surfaced *while writing this fix*: the
`{% static %}` template tag resolves its URL via
`STORAGES["staticfiles"]["BACKEND"].url()`, independent of
`WHITENOISE_USE_FINDERS` (which only affects WhiteNoiseMiddleware's
request-time file lookup, never URL generation). Naively making the
manifest backend (`whitenoise.storage.CompressedManifestStaticFilesStorage`)
unconditional broke almost the entire test suite - it raises
`ValueError: Missing staticfiles manifest entry for '...'` for every
`{% static %}` use until a real `collectstatic` has populated STATIC_ROOT,
and DJANGO_ENV=test is already DEBUG=False (same as production - see
core/tests/test_error_pages.py's module docstring) but - correctly - never
runs collectstatic (neither CI nor a normal dev/test Docker stack does;
only docker-compose.release.yml's `web.command` does, deliberately, PID
§G). `config/settings.py` therefore makes `STORAGES["staticfiles"]["BACKEND"]`
itself conditional on `DJANGO_ENV == "production"`, not on `DEBUG` alone -
see its comment for the full reasoning. `test_reload_after_save_...` and
the rest of the previously-broken suite pass again with this fix in place;
see docs/evidence/M006-RELEASE.md for the full incident/fix narrative and
the real live proof against the release image.

Three tiers here:

1. Always-run: structural MIDDLEWARE wiring, plus the conditional-backend
   property itself for the CURRENT (test) process - the exact property
   whose absence caused the incident above, so it gets direct, permanent
   regression coverage.
2. Always-run: WhiteNoise's manifest storage class tested directly
   (`override_settings`, independent of whichever DJANGO_ENV this pytest
   process happens to be running under) - proves the class we ship for
   production genuinely produces a resolvable, content-hashed manifest
   entry for the real product stylesheet, without needing a full
   DJANGO_ENV=production process just to exercise it.
3. Skipped outside a real DJANGO_ENV=production run (mirrors
   core/tests/test_production_config.py's `_production_only`): a genuine
   HTTP request through the full middleware stack proving the asset is
   actually served over the wire under the real production configuration,
   not merely collectable. Requires `manage.py collectstatic --noinput` to
   have already been run in that same process's STATIC_ROOT before pytest
   starts (WhiteNoiseMiddleware scans STATIC_ROOT once, at middleware
   construction) - documented, not hidden, same accepted limitation
   test_production_config.py already carries for its own class.
"""
import tempfile
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.storage import storages
from django.core.management import call_command
from django.test import Client, override_settings

_production_only = pytest.mark.skipif(
    settings.DJANGO_ENV != "production",
    reason=(
        "Proves WhiteNoiseMiddleware genuinely serves a collected static "
        "asset over a real HTTP request under the real production "
        "STORAGES backend. Requires `manage.py collectstatic --noinput` to "
        "have already populated STATIC_ROOT before this process started "
        "(WhiteNoiseMiddleware scans STATIC_ROOT once, at middleware "
        "construction, not per-request) - run this file directly against a "
        "DJANGO_ENV=production process that has already run collectstatic, "
        "e.g. inside the release container. See this module's docstring "
        "and docs/evidence/M006-RELEASE.md, which carries the real "
        "live-stack proof for this exact gap."
    ),
)


def test_whitenoise_middleware_present_and_correctly_positioned():
    """
    WhiteNoiseMiddleware must sit immediately after SecurityMiddleware
    (WhiteNoise's own documented placement requirement) - a regression here
    (removed, or moved) would silently reintroduce the DEBUG=False
    static-file gap without any other test failing (every other product
    test runs against Django's test Client, which bypasses static-file
    serving entirely).
    """
    middleware = settings.MIDDLEWARE
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in middleware
    security_index = middleware.index("django.middleware.security.SecurityMiddleware")
    whitenoise_index = middleware.index("whitenoise.middleware.WhiteNoiseMiddleware")
    assert whitenoise_index == security_index + 1


@pytest.mark.django_db
def test_staticfiles_backend_does_not_require_collectstatic_outside_production():
    """
    The exact property whose absence broke the suite while writing this
    fix (see module docstring): under any DJANGO_ENV other than
    "production" (this test's own process is DJANGO_ENV=test - see
    core/tests/test_error_pages.py), `{% static %}` must resolve without
    needing a prior `collectstatic` run - real proof, not just reading the
    settings.STORAGES dict: renders the real login page (extends
    templates/base.html, which uses `{% static %}` for the one product
    stylesheet) with a real Django test Client and confirms it renders
    (this exact request raised `ValueError: Missing staticfiles manifest
    entry` before this fix).
    """
    assert settings.DJANGO_ENV != "production", (
        "This test asserts the non-production behaviour and must run "
        "under a non-production DJANGO_ENV (normally 'test')."
    )
    assert (
        settings.STORAGES["staticfiles"]["BACKEND"]
        == "django.contrib.staticfiles.storage.StaticFilesStorage"
    )

    response = Client().get("/accounts/login/")

    assert response.status_code == 200
    assert b"organisations/css/app.css" in response.content


def test_collectstatic_with_the_whitenoise_manifest_backend_produces_a_real_hashed_entry():
    """
    Tests WhiteNoise's `CompressedManifestStaticFilesStorage` class
    directly, via `override_settings`, independent of whichever DJANGO_ENV
    this pytest process happens to be running under - this is the real
    backend `config/settings.py` selects for DJANGO_ENV=production (see its
    STORAGES comment), exercised here without needing a full second
    DJANGO_ENV=production process. Real `collectstatic` run (into a
    throwaway STATIC_ROOT, never the repository's own gitignored
    `staticfiles/`), then a real lookup through Django's storage registry -
    not an assertion that a config string merely exists. Fails if the
    WhiteNoise manifest backend stops producing a resolvable,
    content-hashed URL for the one real product stylesheet.
    """
    with tempfile.TemporaryDirectory() as tmp_static_root:
        with override_settings(
            STATIC_ROOT=tmp_static_root,
            STORAGES={
                **settings.STORAGES,
                "staticfiles": {
                    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
                },
            },
        ):
            call_command("collectstatic", "--noinput", verbosity=0)

            staticfiles_storage = storages["staticfiles"]
            url = staticfiles_storage.url("organisations/css/app.css")

            # Content-hashed filename (WhiteNoise/Django's manifest naming:
            # app.<12-hex-hash>.css), not the bare source filename - proves
            # the manifest backend actually ran, not merely a passthrough.
            assert url != "/static/organisations/css/app.css"
            assert url.startswith("/static/organisations/css/app.")
            assert url.endswith(".css")

            manifest_path = Path(tmp_static_root) / "staticfiles.json"
            assert manifest_path.exists()
            collected_css = Path(tmp_static_root) / "organisations" / "css" / "app.css"
            assert collected_css.exists()
            # Pre-compressed variant WhiteNoise's manifest storage produces
            # for text assets - real evidence collectstatic's
            # post-processing step actually ran, not just copied the file.
            assert collected_css.with_suffix(".css.gz").exists()


@_production_only
def test_static_asset_served_over_real_http_under_production_settings():
    assert settings.STORAGES["staticfiles"]["BACKEND"] == (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )
    client = Client()
    staticfiles_storage = storages["staticfiles"]
    url = staticfiles_storage.url("organisations/css/app.css")

    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/css")
