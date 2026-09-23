"""
PID §26 "unsafe/mismatched account-link path rejected" - and the ADR-0002
§2.2 / §24 "no account linking by unverified email alone" requirement it
comes from.

The genuine ambiguous scenario (per the FORGE dispatch brief): an existing
local `User` - created directly, e.g. exactly like a Customer-Zero/dev
fixture (organisations/tests/conftest.py `make_user`), never via a prior
social login - whose email happens to match the email a *brand new*
provider identity (a (provider, uid) never seen before) presents. This must
be rejected: no login, no new User, no SocialAccount created/linked to the
existing user.

See identity/adapters.py::CustomSocialAccountAdapter for the mechanism.
"""
import pytest
from django.contrib.auth import get_user_model

from allauth.socialaccount.models import SocialAccount

pytestmark = pytest.mark.django_db


class TestUnsafeAccountLinkRejected:
    def test_new_provider_identity_with_colliding_email_is_rejected(self, fake_login):
        User = get_user_model()
        existing_user = User.objects.create_user(
            username="preexisting-local-user",
            email="shared@example.test",
            password="a-strong-test-password-123",
        )

        client, response = fake_login("google", "colliding-with-existing-user")

        # Rejected, not silently linked and not silently logged in.
        assert response.status_code == 403
        assert not response.wsgi_request.user.is_authenticated

        # No new User was created, and the existing user gained no
        # SocialAccount at all.
        assert User.objects.count() == 1
        assert User.objects.get().pk == existing_user.pk
        assert not SocialAccount.objects.filter(user=existing_user).exists()
        assert not SocialAccount.objects.filter(provider="google", uid="collider-003").exists()

        # The rejected attempt did not leave the client authenticated as
        # anyone for a subsequent request either.
        from django.urls import reverse

        listing = client.get(reverse("organisations:list"))
        assert listing.status_code == 302, "client must still be anonymous after a rejected link attempt"

    def test_genuinely_new_identity_with_no_colliding_email_is_not_rejected(self, fake_login):
        """
        Negative control for the test above: proves the rejection is about
        the *collision*, not about "any brand-new social login ever fails".
        Without this, test_new_provider_identity_with_colliding_email_is_rejected
        could pass for the wrong reason (e.g. a bug that rejects every new
        signup).
        """
        _, response = fake_login("google", "bob")  # bob@example.test - no existing User
        assert response.status_code == 302
        assert get_user_model().objects.filter(email="bob@example.test").exists()
