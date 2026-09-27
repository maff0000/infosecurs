"""
PID §6.6/§8.2/§25.3: a real login through the existing Django LoginView
(config/urls.py's "login") issues a genuine `infosecurs_context` via the
`user_logged_in` signal wiring (entitlements/apps.py + signals.py), and the
session identifier rotates as part of that - proven end-to-end through
Django's own test Client, not by calling the service functions directly (
those are proven in isolation in test_session_contract.py).
"""
import pytest
from django.urls import reverse

from entitlements.session import SESSION_KEY
from entitlements.tiers import CODE_MONTHLY, TIER_MONTHLY

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="alice", password="a-strong-test-password-123")


class TestRealLoginIssuesInfosecursContext:
    def test_login_issues_a_valid_context_at_the_documented_default_tier(self, client, user):
        response = client.post(
            reverse("login"), {"username": "alice", "password": "a-strong-test-password-123"}
        )
        assert response.status_code == 302

        context = client.session[SESSION_KEY]
        assert context["schema_version"] == 1
        assert context["subject_id"] == str(user.pk)
        assert context["package_tier"] == TIER_MONTHLY
        assert context["package_code"] == CODE_MONTHLY
        assert context["auth_source"] == "django_beta"
        assert context["organisation_id"] is None

    def test_login_rotates_the_session_key(self, client, user):
        # Force a pre-authentication session to exist so there is a real
        # "before" key to compare against (PID §8.2 - session fixation).
        session = client.session
        session["pre_auth_marker"] = True
        session.save()
        pre_auth_key = session.session_key
        assert pre_auth_key is not None

        client.post(reverse("login"), {"username": "alice", "password": "a-strong-test-password-123"})

        post_auth_key = client.session.session_key
        assert post_auth_key != pre_auth_key

    def test_login_context_is_readable_via_the_validated_context_reader(self, client, user):
        from entitlements.session import InfosecursContext, validate_context

        client.post(reverse("login"), {"username": "alice", "password": "a-strong-test-password-123"})
        raw = client.session[SESSION_KEY]

        result = validate_context(raw, user=user)
        assert isinstance(result, InfosecursContext)
        assert result.package_tier == TIER_MONTHLY
