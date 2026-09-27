"""
Wires the current Django/allauth Beta authentication into the
`SessionContextIssuer` (PID §6.6):

    current Django Beta login ─┐
                               ├─> SessionContextIssuer ─> infosecurs_context
    future external account ───┘

Both Django's own `LoginView` (config/urls.py's "login"/"account_login")
and allauth's social-login flow ultimately call
`django.contrib.auth.login()`, which sends `user_logged_in` - so connecting
here (see `entitlements/apps.py`'s `ready()`) covers every real login path
this Beta has *without* touching either login view's own code, and without
building the WI3-scoped dev/test fixture-switching route. Domain/dashboard
code consumes `infosecurs_context` via `entitlements.session`, never
assumptions about which auth mechanism ran.

--------------------------------------------------------------------------
JUDGEMENT CALL - flagged prominently for PL/Central Architecture (PID §6.6
does not resolve this itself beyond "current Django Beta login ->
SessionContextIssuer -> infosecurs_context"):
--------------------------------------------------------------------------

There is no real commercial/billing system yet (PID §2.2/§6.6 explicitly
defer it), so there is no other authoritative source for a real login's
package tier in this Beta. Every real login today issues at
`TIER_PRO` - the most permissive of the four tiers, deliberately, since
every real user of this Beta is an internal Customer-Zero-style tester who
needs to reach every product area, not a production customer being under-
or over-entitled by a guess. This is a temporary Beta adapter default, not
a commercial decision, and it is trivially replaced (a one-line change
here) once a real package/billing source of truth exists. WI3's fixed
PAUSED/FOUNDATION/MONTHLY/PRO test fixtures bypass this default entirely by
calling `entitlements.session.issue_context` directly with an explicit
tier - they never go through this signal handler.
"""
from __future__ import annotations

from entitlements.session import issue_context
from entitlements.tiers import TIER_PRO

#: The real-login default tier judgement call above, pulled out as a named
#: constant so it is one obvious line to change, not a buried literal.
REAL_LOGIN_DEFAULT_TIER = TIER_PRO

#: Recorded in every issued context's `auth_source` (PID §6.2's own example
#: value) so a later external-account adapter can be distinguished from
#: this one without inspecting anything else.
AUTH_SOURCE = "django_beta"


def issue_context_on_login(sender, request, user, **kwargs):
    """`django.contrib.auth.signals.user_logged_in` receiver - see this
    module's docstring for the full reasoning, including the default-tier
    judgement call."""
    issue_context(
        request,
        user,
        package_tier=REAL_LOGIN_DEFAULT_TIER,
        auth_source=AUTH_SOURCE,
    )
