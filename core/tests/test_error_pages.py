"""
Customer-facing 400/403/404/500 pages (M006 PID §10).

Run with `DJANGO_ENV=test`, which is already `DEBUG=False`
(`config/settings.py`: `DEBUG = DJANGO_ENV == "development"`) - exactly the
"production-like" mode PID §10 asks these pages to be proven under, with no
extra settings override needed.

Each assertion checks BOTH that the branded, plain-language page rendered
(not Django's bare built-in default) AND that nothing unsafe leaked -
no stack trace, no Python exception class/message, no secret value, no
filesystem/source path, no SQL.
"""
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse

_UNSAFE_MARKERS = [
    b"Traceback",
    b"Exception",
    b"RuntimeError",
    settings.SECRET_KEY.encode(),
    b"/srv/",
    b"/app/",
    b"File \"",
    b"django.db",
    b"SELECT ",
    b"Django Version",
]


def _assert_no_leakage(content: bytes):
    for marker in _UNSAFE_MARKERS:
        assert marker not in content, f"unsafe marker leaked into error page: {marker!r}"


def test_404_renders_safe_customer_facing_page(client):
    response = client.get("/this-path-does-not-exist-anywhere/")
    assert response.status_code == 404
    assert b"Page not found" in response.content
    _assert_no_leakage(response.content)


def test_400_renders_safe_customer_facing_page_on_disallowed_host():
    # DisallowedHost (a SuspiciousOperation subclass) is Django's own real,
    # organic 400 path - a request whose Host header isn't in
    # ALLOWED_HOSTS (conftest.py sets it to "localhost,127.0.0.1,testserver"
    # only). No need to hand-craft a fake malformed-request view for this
    # one; it is already a genuine product code path (CommonMiddleware).
    client = Client()
    response = client.get("/", HTTP_HOST="not-an-allowed-host.invalid")
    assert response.status_code == 400
    assert b"couldn't process that request" in response.content
    _assert_no_leakage(response.content)


def test_403_csrf_failure_renders_safe_customer_facing_page():
    # A real, organic 403 path: this codebase raises no application-level
    # PermissionDenied/HttpResponseForbidden anywhere (grep across every
    # views.py confirms it - cross-tenant/unauthorised access is
    # deliberately a 404, never a 403, per the "never reveal a foreign
    # object exists" discipline already established by every
    # `get_member_organisation_or_404`/`get_object_or_404` call site). The
    # only genuine 403 in the whole app is a CSRF verification failure,
    # which `django.middleware.csrf.CsrfViewMiddleware` raises before any
    # view code runs - so a real POST with `enforce_csrf_checks=True` and
    # no token is enough, no test-only view needed.
    client = Client(enforce_csrf_checks=True)
    response = client.post(reverse("login"), {"username": "someone", "password": "wrong"})
    assert response.status_code == 403
    assert b"session expired" in response.content
    _assert_no_leakage(response.content)


@override_settings(ROOT_URLCONF="core.tests._deliberate_500_fixture_urls")
def test_500_renders_safe_customer_facing_page():
    # The one place this dispatch adds a view that raises on purpose - it
    # lives only in `core/tests/_deliberate_500_fixture_urls.py`, is swapped
    # in only for this single test via ROOT_URLCONF override, and is never
    # reachable through the product's real urlconf (`config.urls`).
    client = Client(raise_request_exception=False)
    response = client.get("/__test-only-deliberate-500__/")
    assert response.status_code == 500
    assert b"Something went wrong" in response.content
    _assert_no_leakage(response.content)
