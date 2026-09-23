"""
Fixtures for the identity app's own tests.

Deliberately does NOT set GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET
/ MICROSOFT_OAUTH_CLIENT_ID / MICROSOFT_OAUTH_CLIENT_SECRET anywhere - the
root conftest.py doesn't set them either, so every test in this app already
runs the way normal CI/dev does: with optional_env() resolving all four to
"". identity/testing.py reads the client_id it needs live from settings
rather than assuming a value, precisely so this is true. See
test_federated_login.py::test_whole_suite_runs_without_live_provider_credentials
for the explicit assertion of this.
"""
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import Client
from django.urls import reverse

from identity.testing import fake_login_code, fake_provider_http


@pytest.fixture
def fake_login():
    """
    Drives a full, real allauth OAuth2 login through the real
    `/identity/<provider>/login/` -> `/identity/<provider>/login/callback/`
    URLs, using `identity.testing.fake_provider_http()` for the two
    outbound network legs. Returns the final HttpResponse from the callback
    (a redirect on success; a rendered error/rejection page otherwise).

    A fresh, independent `django.test.Client()` is used every call (not the
    shared pytest-django `client` fixture) - see organisations/tests/conftest.py
    `client_a`/`client_b` docstring for why a shared Client instance across
    fixtures is dangerous for auth-state tests.
    """

    def _fake_login(provider: str, persona_key: str, client: Client | None = None):
        client = client or Client()
        start = client.get(reverse(f"{provider}_login"))
        assert start.status_code == 302, (
            f"expected a redirect to {provider}'s authorize URL, got "
            f"{start.status_code}: {getattr(start, 'content', b'')[:500]!r}"
        )
        state = parse_qs(urlparse(start.url).query)["state"][0]
        with fake_provider_http():
            response = client.get(
                reverse(f"{provider}_callback"),
                {"code": fake_login_code(provider, persona_key), "state": state},
            )
        return client, response

    return _fake_login
