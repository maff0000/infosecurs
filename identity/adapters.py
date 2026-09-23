"""
Custom django-allauth social-account adapter.

ADR-0002 §2.2 / M004-POLICY-FOUNDATION §5.2, §24: stable external identity
is keyed by (provider, subject) - allauth's own `SocialAccount` already
enforces this as a `unique_together` natural key - and a federated login
must never be silently linked to an existing local `User` merely because an
email address happens to match.

allauth's own library defaults already produce a safe outcome for that
scenario without any code here:

  - `ACCOUNT_UNIQUE_EMAIL` (default True) makes a colliding email a real
    conflict rather than being ignored;
  - `ACCOUNT_PREVENT_ENUMERATION` (default True, and not "strict") makes
    `allauth.account.internal.flows.manage_email.assess_unique_email`
    return `False` (not `None`) for that conflict, i.e. "reject", not
    "silently pretend to sign up" (`allauth/account/internal/flows/manage_email.py`);
  - `SOCIALACCOUNT_AUTO_SIGNUP` (default True) is what makes that `False`
    actually stop the auto-signup instead of falling through;
  - `SOCIALACCOUNT_EMAIL_AUTHENTICATION` (default False) is the setting
    that would otherwise let a *verified* colliding email log straight into
    the existing account without ever creating/linking a SocialAccount at
    all - its docstring in allauth itself names this exact risk. It must
    stay False.

Those four settings are made explicit (not left as implicit defaults) in
the settings.py block this app's PID dispatch report hands to the PL.

This adapter adds one deliberate, explicit, independently-testable guard on
top of that library behaviour: `pre_social_login` refuses outright (before
allauth's own signup/link machinery even runs) whenever a *brand new*
provider identity (i.e. no existing SocialAccount for this exact
(provider, uid) pair - see `sociallogin.is_existing`) presents an email
address that already belongs to a local `User`. This does not replace
allauth's login pipeline; it intervenes at the one hook point allauth
documents for exactly this purpose, so the rejection is owned by this app's
code (and covered by this app's own test - see
identity/tests/test_unsafe_linking.py) rather than depending solely on the
continued interaction of several library defaults across future allauth
versions.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpRequest
from django.template.response import TemplateResponse

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        if sociallogin.is_existing:
            # Returning identity: allauth already resolved this exact
            # (provider, uid) pair to an existing SocialAccount/User via its
            # natural-key lookup (SocialLogin.lookup(), called just before
            # this hook fires). That is the safe, expected "same person,
            # same provider identity, signing in again" case - nothing for
            # this app to intervene on; allauth's normal flow logs them
            # straight into the same local User it already found.
            return
        self._reject_unsafe_email_collision(request, sociallogin)

    def _reject_unsafe_email_collision(
        self, request: HttpRequest, sociallogin: SocialLogin
    ) -> None:
        candidate_emails = {
            address.email.strip().lower()
            for address in sociallogin.email_addresses
            if address.email
        }
        if not candidate_emails:
            return

        User = get_user_model()
        email_match = Q()
        for email in candidate_emails:
            email_match |= Q(email__iexact=email)

        if User.objects.filter(email_match).exists():
            # A local User already owns this email address, but this
            # (provider, uid) pair has never signed in before. Do not
            # create a new User, do not create/link a SocialAccount, do
            # not authenticate the request - just stop, honestly, here.
            raise ImmediateHttpResponse(
                TemplateResponse(
                    request,
                    "identity/unsafe_link_rejected.html",
                    {"provider": sociallogin.account.provider},
                    status=403,
                )
            )
