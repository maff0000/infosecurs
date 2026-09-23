"""
Mechanical tests for M004-POLICY-FOUNDATION §26 "Identity", except the
unsafe-linking rejection (see test_unsafe_linking.py).

Every test here drives the REAL allauth URLs
(`/identity/<provider>/login/`, `/identity/<provider>/login/callback/`)
through Django's test client, with only the two outbound provider network
calls faked - see identity/testing.py and the `fake_login` fixture in
conftest.py.
"""
import os

import pytest
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch, reverse

from allauth.socialaccount.models import SocialAccount

pytestmark = pytest.mark.django_db


class TestStableProviderSubjectMapping:
    """provider+subject stable mapping: the same (provider, uid) returns
    the same local User across multiple logins."""

    def test_same_uid_returns_same_user_across_logins(self, fake_login):
        _, first = fake_login("google", "alice")
        assert first.status_code == 302

        User = get_user_model()
        assert User.objects.count() == 1
        alice = User.objects.get()
        assert SocialAccount.objects.get(provider="google", uid="alice-001").user_id == alice.pk

        # Log in again with the exact same persona (same provider, same uid).
        _, second = fake_login("google", "alice")
        assert second.status_code == 302

        # No second User, no second SocialAccount - same natural-key row.
        assert User.objects.count() == 1
        assert SocialAccount.objects.filter(provider="google", uid="alice-001").count() == 1
        assert SocialAccount.objects.get(provider="google", uid="alice-001").user_id == alice.pk

    def test_second_provider_with_same_persona_email_is_treated_as_the_same_unsafe_collision(
        self, fake_login
    ):
        """
        Sanity check on the fake harness AND on CustomSocialAccountAdapter
        together: "alice" via google and "alice" via microsoft are two
        distinct (provider, uid) identities - (provider, uid) is the
        natural key, not uid alone - but they share the same email
        (alice@example.test). That is exactly the ambiguous-linking
        scenario the adapter rejects (test_unsafe_linking.py), and it does
        not matter whether the pre-existing local User came from a raw
        fixture or from an earlier, unrelated provider login - either way,
        a second provider identity must not be silently attached to it.
        """
        _, google_resp = fake_login("google", "alice")
        assert google_resp.status_code == 302
        assert SocialAccount.objects.filter(provider="google", uid="alice-001").exists()

        _, ms_resp = fake_login("microsoft", "alice")
        assert ms_resp.status_code == 403
        assert not SocialAccount.objects.filter(provider="microsoft", uid="alice-001").exists()
        assert get_user_model().objects.count() == 1, "no second User was created for the rejected microsoft identity"


class TestEmailChangeDoesNotDuplicateIdentity:
    def test_changed_email_same_uid_maps_to_same_user(self, fake_login):
        _, first = fake_login("google", "alice")
        assert first.status_code == 302
        User = get_user_model()
        assert User.objects.count() == 1
        original_user_pk = User.objects.get().pk

        # Same uid ("alice-001"), different email at the provider.
        _, second = fake_login("google", "alice-changed-email")
        assert second.status_code == 302

        assert User.objects.count() == 1, "email change at the provider must not create a duplicate identity/user"
        assert SocialAccount.objects.filter(provider="google", uid="alice-001").count() == 1
        account = SocialAccount.objects.get(provider="google", uid="alice-001")
        assert account.user_id == original_user_pk
        assert account.extra_data.get("email") == "alice.new@example.test"


class TestReturningIdentitySameAccountAndSession:
    def test_login_logout_login_maps_to_same_user_and_org_memberships_visible(self, fake_login):
        from organisations.models import Organisation, OrganisationMembership

        client, first = fake_login("google", "bob")
        assert first.status_code == 302

        User = get_user_model()
        bob = User.objects.get()
        # No apostrophe: avoids an HTML-escaping mismatch between the raw
        # name here and the auto-escaped "&#x27;" Django's templates render.
        org = Organisation.objects.create(name="Bob Synthetic Org")
        OrganisationMembership.objects.create(
            organisation=org, user=bob, role=OrganisationMembership.ROLE_OWNER
        )

        listing = client.get(reverse("organisations:list"))
        assert listing.status_code == 200
        assert org.name.encode() in listing.content

        client.post(reverse("logout"))
        loggedout_listing = client.get(reverse("organisations:list"))
        assert loggedout_listing.status_code == 302, "session must be cleared by logout"

        client, second = fake_login("google", "bob", client=client)
        assert second.status_code == 302

        assert get_user_model().objects.count() == 1
        relisting = client.get(reverse("organisations:list"))
        assert relisting.status_code == 200
        assert org.name.encode() in relisting.content


class TestNoLocalPasswordSignupInNormalFlow:
    def test_allauth_local_password_signup_url_is_not_registered(self):
        """
        We mount only allauth.socialaccount.urls + the google/microsoft
        provider urls (never allauth.account.urls) precisely so there is no
        public local-password registration view - see the PL report for the
        /accounts/ URL-collision resolution. This proves it mechanically:
        `account_signup` must not be a resolvable URL name.
        """
        with pytest.raises(NoReverseMatch):
            reverse("account_signup")

    def test_existing_local_login_view_is_still_reachable(self):
        """Local auth remains for dev/Customer-Zero fixtures (ADR-0002 §2.3) -
        the existing `login` URL name/view must be untouched."""
        assert reverse("login") == "/accounts/login/"


class TestFakeProviderSufficientForCI:
    def test_no_live_provider_credentials_are_configured_in_this_test_run(self):
        """
        Documents (and asserts, rather than merely claims) the ambient
        condition every other test in this module already runs under: no
        live Google/Microsoft credentials anywhere in the environment. The
        whole class/module suite passing under this condition is the actual
        proof requested by PID §26 - this test just makes the condition
        explicit and machine-checked rather than implicit.
        """
        for name in (
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "MICROSOFT_OAUTH_CLIENT_ID",
            "MICROSOFT_OAUTH_CLIENT_SECRET",
        ):
            assert not os.environ.get(name), (
                f"{name} is set in this test environment - the fake-provider "
                f"sufficiency proof requires it to be unset/empty, matching "
                f"normal CI/dev (see config/env.py optional_env)."
            )

    def test_login_initiation_works_with_blank_provider_credentials(self, client):
        """Even the very first step (redirecting to the provider) must not
        crash just because no real client_id/secret is configured -
        PID §28: "do not invent credentials... deterministic library/
        protocol tests... remain required"."""
        for provider in ("google", "microsoft"):
            response = client.get(reverse(f"{provider}_login"))
            assert response.status_code == 302
            assert response.url  # a real redirect URL was built

    def test_fake_login_round_trip_succeeds_with_blank_provider_credentials(self, fake_login):
        _, response = fake_login("google", "alice")
        assert response.status_code == 302
