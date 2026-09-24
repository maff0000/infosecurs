"""
M006 PID §12 — production-like configuration check.

`config/settings.py` only makes three settings conditional on
`DJANGO_ENV == "production"`: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
`SECURE_SSL_REDIRECT`. All three are read ONCE, at settings-module import
time, from the `DJANGO_ENV` environment variable — `override_settings()`
cannot retroactively fake them for a process that already imported
`config.settings` with a different `DJANGO_ENV` (which is exactly what the
normal test suite does: `conftest.py` sets `DJANGO_ENV=test`). So the
`TestProductionModeSecurityProperties` class below can only produce a real
result when the whole pytest process is started with `DJANGO_ENV=production`
already set in its environment, before Django ever imports settings — e.g.:

    DJANGO_ENV=production \\
    DJANGO_SECRET_KEY=<synthetic> \\
    DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \\
    DJANGO_CSRF_TRUSTED_ORIGINS=https://trusted.example.test \\
    POSTGRES_DB=... POSTGRES_USER=... POSTGRES_PASSWORD=... \\
    POSTGRES_HOST=... POSTGRES_PORT=... \\
        pytest core/tests/test_production_config.py -v

Everywhere else (the default CI/local `DJANGO_ENV=test` run) that class is
cleanly SKIPPED, not silently passed — a skip is visible in test output,
unlike a test that quietly asserts nothing. This was actually run, and
confirmed green, against a disposable `DJANGO_ENV=production` Docker stack
on dell-debian during the M006 Round 4 dispatch — see
`docs/evidence/M006-ROUND4-PRODCONFIG-HEALTH.md` for the full live-stack
proof (real `Set-Cookie` headers over the wire, `manage.py check --deploy`
output, and the reverse-proxy infinite-redirect-loop finding). This file
gives that same proof a permanent, re-runnable, mechanical form.

`CSRF_TRUSTED_ORIGINS` (PID §12 item 5) is NOT conditional on `DJANGO_ENV` -
`CsrfViewMiddleware` reads it at request time regardless of environment - so
`TestCSRFTrustedOriginBehaviour` below runs unconditionally, in the ordinary
suite, and contributes real durable regression coverage.
"""
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from core.tests.test_error_pages import _assert_no_leakage, _assert_no_unsupported_claims

_TEST_PASSWORD = "a-strong-test-password-123"

_production_only = pytest.mark.skipif(
    settings.DJANGO_ENV != "production",
    reason=(
        "Exercises DJANGO_ENV=production-conditional settings "
        "(SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE / SECURE_SSL_REDIRECT), "
        "which are read once at settings-module import time and cannot be "
        "faked with override_settings(). Run this file directly with "
        "DJANGO_ENV=production set in the process environment before pytest "
        "starts - see this module's docstring and "
        "docs/evidence/M006-ROUND4-PRODCONFIG-HEALTH.md."
    ),
)


@_production_only
class TestProductionModeSecurityProperties:
    def test_session_and_csrf_cookies_are_secure(self, db):
        """PID §12 items 1-2: secure session cookie, secure CSRF cookie."""
        host = settings.ALLOWED_HOSTS[0]
        User = get_user_model()
        user = User.objects.create_user(username="prodconfig-cookie-check", password=_TEST_PASSWORD)

        client = Client(enforce_csrf_checks=True, SERVER_NAME=host)
        get_response = client.get(reverse("login"), secure=True)
        assert get_response.status_code == 200
        csrf_cookie = get_response.cookies.get("csrftoken")
        assert csrf_cookie is not None
        assert csrf_cookie["secure"]

        token = client.cookies["csrftoken"].value
        post_response = client.post(
            reverse("login"),
            {"username": user.username, "password": _TEST_PASSWORD, "csrfmiddlewaretoken": token},
            secure=True,
            HTTP_REFERER=f"https://{host}/",
        )
        assert post_response.status_code == 302  # successful login redirect
        session_cookie = post_response.cookies.get("sessionid")
        assert session_cookie is not None
        assert session_cookie["secure"]
        assert session_cookie["httponly"]

    def test_plain_http_request_redirects_to_https(self, db):
        """
        PID §12 item 3: a plain HTTP request (Django's test client defaults
        to secure=False) must redirect to an https:// URL, given
        SECURE_SSL_REDIRECT=True.
        """
        host = settings.ALLOWED_HOSTS[0]
        client = Client(SERVER_NAME=host)
        response = client.get(reverse("login"), secure=False)
        assert response.status_code in (301, 302)
        assert response.url.startswith("https://")

    def test_disallowed_host_returns_safe_400(self):
        """
        PID §12 item 4: ALLOWED_HOSTS enforcement, re-proven under
        DJANGO_ENV=production this time (mirrors
        core/tests/test_error_pages.py's DisallowedHost test, which only
        ever runs under DJANGO_ENV=test). Confirmed live (both via this
        mechanism and by curl against the real disposable stack) that
        DisallowedHost is raised while SecurityMiddleware itself is still
        building the HTTPS-redirect Location header - i.e. the host check
        wins before SECURE_SSL_REDIRECT ever gets a chance to redirect
        anywhere, so no redirect loop is possible for this specific path.
        """
        client = Client()
        response = client.get("/", HTTP_HOST="not-an-allowed-host.invalid.example")
        assert response.status_code == 400
        assert b"couldn't process that request" in response.content
        _assert_no_leakage(response.content)
        _assert_no_unsupported_claims(response.content)

    def test_404_no_debug_disclosure(self):
        """PID §12 item 6, re-proven under DJANGO_ENV=production (not just DJANGO_ENV=test)."""
        host = settings.ALLOWED_HOSTS[0]
        client = Client(SERVER_NAME=host)
        response = client.get("/this-path-does-not-exist-anywhere/", secure=True)
        assert response.status_code == 404
        assert b"Page not found" in response.content
        _assert_no_leakage(response.content)
        _assert_no_unsupported_claims(response.content)

    def test_403_csrf_failure_no_debug_disclosure(self):
        """PID §12 item 6, re-proven under DJANGO_ENV=production (not just DJANGO_ENV=test)."""
        host = settings.ALLOWED_HOSTS[0]
        client = Client(enforce_csrf_checks=True, SERVER_NAME=host)
        response = client.post(
            reverse("login"), {"username": "someone", "password": "wrong"}, secure=True
        )
        assert response.status_code == 403
        assert b"session expired" in response.content
        _assert_no_leakage(response.content)
        _assert_no_unsupported_claims(response.content)

    @override_settings(ROOT_URLCONF="core.tests._deliberate_500_fixture_urls")
    def test_500_no_debug_disclosure(self):
        """PID §12 item 6, re-proven under DJANGO_ENV=production (not just DJANGO_ENV=test)."""
        host = settings.ALLOWED_HOSTS[0]
        client = Client(raise_request_exception=False, SERVER_NAME=host)
        response = client.get("/__test-only-deliberate-500__/", secure=True)
        assert response.status_code == 500
        assert b"Something went wrong" in response.content
        assert b"Please try again" in response.content
        assert b"check the relevant page before repeating the action" in response.content
        _assert_no_leakage(response.content)
        _assert_no_unsupported_claims(response.content)


class TestCSRFTrustedOriginBehaviour:
    """
    PID §12 item 5. `django.middleware.csrf.CsrfViewMiddleware`, whenever a
    request carries an `Origin` header (as any real cross-origin browser
    POST does), verifies that Origin against `CSRF_TRUSTED_ORIGINS` (or the
    request's own origin) BEFORE ever falling back to Referer checking -
    this is real Django CSRF-origin-verification behaviour, not a
    hand-rolled stand-in, and it is independent of DJANGO_ENV/secure-request
    state, so it runs in the ordinary suite. Confirmed identically under a
    live DJANGO_ENV=production stack - see
    docs/evidence/M006-ROUND4-PRODCONFIG-HEALTH.md.
    """

    @override_settings(CSRF_TRUSTED_ORIGINS=["https://trusted.example.test"])
    def test_trusted_origin_accepted_for_cross_origin_styled_post(self, db):
        # secure=True + settings.ALLOWED_HOSTS[0] as SERVER_NAME so this
        # also works unmodified when DJANGO_ENV=production is the real
        # process env (SECURE_SSL_REDIRECT=True there would otherwise
        # redirect a plain insecure GET before any cookie is ever set -
        # that is PID §12 item 3's own property, not something to work
        # around, so this test simply issues a secure request instead of
        # depending on DJANGO_ENV being test).
        host = settings.ALLOWED_HOSTS[0]
        User = get_user_model()
        user = User.objects.create_user(username="csrf-trusted-origin-check", password=_TEST_PASSWORD)
        client = Client(enforce_csrf_checks=True, SERVER_NAME=host)
        client.get(reverse("login"), secure=True)
        token = client.cookies["csrftoken"].value

        response = client.post(
            reverse("login"),
            {"username": user.username, "password": _TEST_PASSWORD, "csrfmiddlewaretoken": token},
            secure=True,
            HTTP_ORIGIN="https://trusted.example.test",
        )
        assert response.status_code == 302

    @override_settings(CSRF_TRUSTED_ORIGINS=["https://trusted.example.test"])
    def test_untrusted_origin_rejected_for_cross_origin_styled_post(self, db):
        host = settings.ALLOWED_HOSTS[0]
        client = Client(enforce_csrf_checks=True, SERVER_NAME=host)
        client.get(reverse("login"), secure=True)
        token = client.cookies["csrftoken"].value

        response = client.post(
            reverse("login"),
            {"username": "irrelevant", "password": "irrelevant", "csrfmiddlewaretoken": token},
            secure=True,
            HTTP_ORIGIN="https://untrusted.example.test",
        )
        assert response.status_code == 403
