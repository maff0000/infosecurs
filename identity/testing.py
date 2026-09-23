"""
Deterministic, no-network fake seam for django-allauth's Google/Microsoft
OAuth2 login flow (M004-POLICY-FOUNDATION §5.4, §26 "fake/stub provider
sufficient for CI"; ADR-0002 §2.1).

WHAT THIS FAKES, AND WHAT IT DOES NOT
--------------------------------------
A real allauth OAuth2 login makes exactly two outbound network calls after
the browser comes back from the provider with an authorization `code`:

  1. the code -> access-token exchange
     (`allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token`,
     used identically by both the google and microsoft provider classes);
  2. a profile fetch, made through
     `allauth.socialaccount.adapter.DefaultSocialAccountAdapter.get_requests_session()`
     - for Microsoft this is always a Graph `/me` call
     (`MicrosoftGraphOAuth2Adapter.complete_login`); for Google it is a
     `/oauth2/v2/userinfo` call (`GoogleOAuth2Adapter._fetch_user_info`),
     reached because config/settings.py deliberately configures Google's
     scope as `["profile", "email"]` without `"openid"` - see the comment
     there for why (in short: with `"openid"`, Google returns a signed
     id_token instead, which allauth then JWT-decodes expecting a non-blank
     `aud`/client_id - something that can never be true with the blank
     client_id PID §28 requires normal CI/dev to run with, real Google or
     fake. Dropping `"openid"` makes both providers use the same plain
     REST-profile-fetch shape, which this fake seam mirrors).

`fake_provider_http()` monkeypatches exactly those two calls. Everything
else in the flow is real: the real allauth URLs
(`/identity/<provider>/login/`, `/identity/<provider>/login/callback/`),
real Django session/cookies, real OAuth2 `state` stashing/verification,
real CSRF handling, real `identity.adapters.CustomSocialAccountAdapter`
hooks, real `SocialAccount`/`User` creation. Nothing about *which* code
path runs is faked - only the two network legs a real Google/Microsoft
server would otherwise have to answer.

WHICH IDENTITY LOGS IN IS CHOSEN BY THE `code` VALUE ALONE
------------------------------------------------------------
There is no shared mutable state to correlate a login attempt back to a
persona: the synthetic `access_token` returned by the fake token exchange
*is* the same opaque `code` string the browser/test supplied at the start
(`fake_login_code(provider, persona_key)`), and the fake profile fetch
decodes the persona straight back out of the `Authorization: Bearer <...>`
header it receives, picking its response shape from the request URL
(Google userinfo vs. Microsoft Graph). This means the mechanism works
identically whether the HTTP requests driving it come from Django's test
client inside a single pytest process, or from a real browser
(Selenium/Playwright) driving a `pytest-django` `live_server` in the same
process - see `identity/tests/test_federated_login.py` for the pytest-level
usage, which is the fully-supported, tested route. See the "REAL-BROWSER
ACCEPTANCE" note at the bottom of this file for what is and is not covered.

HOW TO USE THIS
----------------
    from identity.testing import fake_login_code, fake_provider_http

    def test_something(client):
        start = client.get(reverse("google_login"))
        state = parse_qs(urlparse(start.url).query)["state"][0]
        with fake_provider_http():
            response = client.get(
                reverse("google_callback"),
                {"code": fake_login_code("google", "alice"), "state": state},
            )
        # response is now the real result of a real allauth login using the
        # synthetic "alice" persona below.

Available personas (`FAKE_PERSONAS`) are deliberately small and named for
what they exercise, not for narrative realism - add a new persona rather
than repurposing an existing one, so each key keeps meaning exactly one
thing across every test/acceptance run that references it.
"""
from __future__ import annotations

import contextlib
from unittest import mock
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Fixed, synthetic identities. Never real people, never real provider data.
# `uid` is deliberately provider-agnostic here - fake_login_code() namespaces
# it per provider when building the actual SocialAccount.uid, so the same
# persona key can be reused to log the "same person" in via google and via
# microsoft as two distinct, unrelated provider identities if a test wants
# that.
# ---------------------------------------------------------------------------
FAKE_PERSONAS = {
    "alice": dict(
        uid="alice-001",
        email="alice@example.test",
        email_verified=True,
        first_name="Alice",
        last_name="Adams",
    ),
    "alice-changed-email": dict(
        # Same underlying uid as "alice" - used to prove that an email
        # change at the provider does not create a duplicate identity.
        uid="alice-001",
        email="alice.new@example.test",
        email_verified=True,
        first_name="Alice",
        last_name="Adams",
    ),
    "bob": dict(
        uid="bob-002",
        email="bob@example.test",
        email_verified=True,
        first_name="Bob",
        last_name="Baker",
    ),
    "colliding-with-existing-user": dict(
        # A brand-new provider identity (a uid never seen before) whose
        # email is deliberately meant to match a *pre-existing* local User
        # a test creates directly (not via social login) - this is the
        # genuine ambiguous-linking scenario, see
        # identity/tests/test_unsafe_linking.py.
        uid="collider-003",
        email="shared@example.test",
        email_verified=True,
        first_name="Collides",
        last_name="Withsomeone",
    ),
}


def fake_login_code(provider: str, persona_key: str) -> str:
    """
    Build the value to pass as the `code` query parameter on the allauth
    callback URL (e.g. `reverse("google_callback")`), inside a
    `fake_provider_http()` block, to sign in as the named persona.
    """
    if persona_key not in FAKE_PERSONAS:
        raise KeyError(
            f"Unknown fake identity persona {persona_key!r}. "
            f"Known personas: {sorted(FAKE_PERSONAS)}"
        )
    if provider not in ("google", "microsoft"):
        raise ValueError(f"Unsupported fake provider {provider!r}")
    return f"{provider}:{persona_key}"


def _persona_from_code(code: str):
    provider, _, persona_key = code.partition(":")
    return provider, FAKE_PERSONAS[persona_key]


class _FakeResponse:
    """Duck-types just enough of `requests.Response` for the two allauth
    adapters this harness stands in for (`.ok`, `.json()`, `.text`,
    `.headers`, `.status_code`)."""

    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200
        self.ok = True
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload

    @property
    def text(self):
        import json as _json

        return _json.dumps(self._payload)


class _FakeRequestsSession:
    """Stands in for `requests.Session` for the single HTTP call each
    provider adapter's `complete_login` makes after the token exchange.
    Never touches the network; decodes which persona to answer with from
    the bearer token, which *is* the `fake_login_code()` value (see module
    docstring), and shapes the response to match the URL being requested
    (Google's userinfo endpoint vs. Microsoft Graph `/me`)."""

    def get(self, url, params=None, headers=None, **kwargs):
        auth_header = (headers or {}).get("Authorization", "")
        code = auth_header.removeprefix("Bearer ").strip()
        provider, persona = _persona_from_code(code)

        # Exact-hostname match, not substring containment (a bare
        # "googleapis.com" in url check would also match an attacker-hosted
        # "googleapis.com.evil.test" or "evilgoogleapis.com" - CodeQL
        # "Incomplete URL substring sanitization"). `url` here only ever
        # comes from allauth's own GoogleOAuth2Adapter._fetch_user_info,
        # which requests exactly the default IDENTITY_URL,
        # "https://www.googleapis.com/oauth2/v2/userinfo" (this project
        # does not override SOCIALACCOUNT_PROVIDERS["google"]["IDENTITY_URL"]
        # - see config/settings.py) - so an exact hostname match is both
        # correct and precise, not a guess.
        hostname = urlparse(url).hostname or ""
        if hostname == "www.googleapis.com":
            # GoogleAccount's documented /v2/userinfo response shape.
            return _FakeResponse(
                {
                    "id": persona["uid"],
                    "email": persona["email"],
                    "verified_email": persona["email_verified"],
                    "given_name": persona["first_name"],
                    "family_name": persona["last_name"],
                    "name": f"{persona['first_name']} {persona['last_name']}",
                }
            )
        # Microsoft Graph /me response shape
        # (MicrosoftGraphOAuth2Adapter.user_properties).
        return _FakeResponse(
            {
                "id": persona["uid"],
                "mail": persona["email"],
                "userPrincipalName": persona["email"],
                "givenName": persona["first_name"],
                "surname": persona["last_name"],
                "displayName": f"{persona['first_name']} {persona['last_name']}",
            }
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _fake_get_access_token(self, code, pkce_code_verifier=None, extra_data=None):
    """Replaces `OAuth2Client.get_access_token` for the duration of a
    `fake_provider_http()` block. Signature matches the real method so it
    can be assigned directly as the class attribute (see below). Validates
    the persona exists (so a typo'd `code` fails fast here rather than
    surfacing as a confusing downstream allauth error) but otherwise just
    echoes `code` back as the access token - see module docstring."""
    _persona_from_code(code)  # raises KeyError early on an unknown persona
    return {
        "access_token": code,  # see module docstring: the token *is* the code
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@contextlib.contextmanager
def fake_provider_http():
    """
    Context manager. Inside it, any real allauth OAuth2 login/callback
    request (google or microsoft) that reaches the token-exchange/profile
    steps is answered deterministically from `FAKE_PERSONAS`, with zero
    real network access - see the module docstring for exactly what is and
    is not faked.
    """
    with mock.patch(
        "allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token",
        new=_fake_get_access_token,
    ), mock.patch(
        "allauth.socialaccount.adapter.DefaultSocialAccountAdapter.get_requests_session",
        new=lambda self: _FakeRequestsSession(),
    ):
        yield


# ---------------------------------------------------------------------------
# REAL-BROWSER ACCEPTANCE (PID §27 step 2) - read this before relying on it
# for out-of-process browser acceptance.
# ---------------------------------------------------------------------------
# `fake_provider_http()` is a Python-process-level monkeypatch. It works for
# ANY test running inside this pytest process - including a real
# Selenium/Playwright browser driving a `pytest-django` `live_server` (the
# live server runs in a background thread of the *same* process, so the
# patched attribute is shared). That combination - a real browser, a real
# running Django server, real HTTP, real cookies/redirects, only the two
# outbound provider network calls faked - is what this app's own tests use
# and is the supported, verified mechanism for "authenticate through a
# deterministic test/fake federated-auth seam" acceptance.
#
# It does NOT reach a *separately running* process - e.g. the
# `docker-compose.yml` `web` container serving real HTTP to an externally
# launched browser pointed at its port. A monkeypatch made in one Python
# process has no effect on another. If a fresh FORGE Auditor's real-browser
# acceptance run needs to drive the actual docker-compose `web` container
# rather than a pytest-django `live_server`, this fake seam does not cover
# that by itself - the Auditor/PL would need to decide how to activate an
# equivalent patch inside that server process (e.g. a dedicated,
# never-production settings flag that enters `fake_provider_http()` at
# process startup). That is not built here: half-building an unverified
# production-adjacent toggle seemed worse than flagging the gap plainly.
# The recommended, fully-supported route is a `live_server`-based
# Selenium/Playwright test using this module directly, exactly like
# identity/tests/test_federated_login.py.
