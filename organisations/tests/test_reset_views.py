"""
M008A - view/HTTP-surface tests for `organisations.views.
customer_zero_reset` (docs/evidence/M008A-RESET-DELETION-MANIFEST.md).

Service-level deletion-correctness tests (full round trip, repeatability,
second-tenant isolation, model-drift fail-closed, bootstrap-invariant
byte-for-byte survival) live in
`organisations/tests/test_reset_service.py`. This file is the adversarial
HTTP surface: environment gates, fixture identity, forged UUIDs, access
control, and HTTP method/CSRF/confirmation discipline.
"""
import pytest
from django.test import Client
from django.urls import reverse

from entitlements.session import SESSION_KEY
from organisations.models import CustomerZeroFixture, Organisation, OrganisationMembership, OrganisationProfile


def _reset_url(organisation_id):
    return reverse("organisations:customer_zero_reset", args=[organisation_id])


@pytest.mark.django_db
class TestEnvironmentGate:
    def test_get_404_when_flag_disabled(self, customer_zero_client, customer_zero_org, settings):
        settings.CUSTOMER_ZERO_RESET_ENABLED = False
        response = customer_zero_client.get(_reset_url(customer_zero_org.id))
        assert response.status_code == 404

    def test_post_404_when_flag_disabled(self, customer_zero_client, customer_zero_org, settings):
        settings.CUSTOMER_ZERO_RESET_ENABLED = False
        response = customer_zero_client.post(
            _reset_url(customer_zero_org.id), {"confirmation": "RESET"}
        )
        assert response.status_code == 404
        # Nothing ran - the fixture marker (and everything else) is
        # exactly as it was.
        assert CustomerZeroFixture.objects.filter(organisation=customer_zero_org).exists()

    def test_debug_true_alone_is_never_sufficient(
        self, customer_zero_client, customer_zero_org, settings
    ):
        """
        PID §A2.1's own non-negotiable, proved directly: forcing
        settings.DEBUG = True, WITHOUT also setting
        CUSTOMER_ZERO_RESET_ENABLED (which stays at its real,
        independently-computed value - False in this test environment,
        since DJANGO_ENV is "test", not "development"), must still 404 for
        a real, well-formed request from the real fixture organisation's
        real owner.
        """
        settings.DEBUG = True
        assert settings.CUSTOMER_ZERO_RESET_ENABLED is False
        response = customer_zero_client.get(_reset_url(customer_zero_org.id))
        assert response.status_code == 404
        response = customer_zero_client.post(
            _reset_url(customer_zero_org.id), {"confirmation": "RESET"}
        )
        assert response.status_code == 404

    def test_enabled_get_renders_confirmation_and_post_resets(
        self, customer_zero_client, customer_zero_org, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        get_response = customer_zero_client.get(_reset_url(customer_zero_org.id))
        assert get_response.status_code == 200
        assert customer_zero_org.name.encode() in get_response.content

        post_response = customer_zero_client.post(
            _reset_url(customer_zero_org.id), {"confirmation": "RESET"}
        )
        assert post_response.status_code == 302
        assert post_response.url == reverse("login")


@pytest.mark.django_db
class TestFixtureIdentity:
    def test_same_display_name_impostor_organisation_404s(
        self, customer_zero_client, customer_zero_user, customer_zero_org, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        impostor = Organisation.objects.create(name=customer_zero_org.name)
        OrganisationMembership.objects.create(
            organisation=impostor,
            user=customer_zero_user,
            role=OrganisationMembership.ROLE_OWNER,
        )
        assert not CustomerZeroFixture.objects.filter(organisation=impostor).exists()

        get_response = customer_zero_client.get(_reset_url(impostor.id))
        assert get_response.status_code == 404

        post_response = customer_zero_client.post(
            _reset_url(impostor.id), {"confirmation": "RESET"}
        )
        assert post_response.status_code == 404
        # The real fixture organisation was never touched by the attempt.
        assert CustomerZeroFixture.objects.filter(organisation=customer_zero_org).exists()
        assert OrganisationMembership.objects.filter(
            organisation=customer_zero_org, user=customer_zero_user
        ).exists()


@pytest.mark.django_db
class TestForgedUUID:
    def test_non_member_cannot_reset_the_real_fixture_by_its_uuid(
        self, org_a, user_a, member_a, customer_zero_org, settings
    ):
        """user_a is an authenticated owner of org_a only - not a member of
        the real Customer Zero fixture organisation at all."""
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        client = Client()
        client.force_login(user_a)

        response = client.post(
            _reset_url(customer_zero_org.id), {"confirmation": "RESET"}
        )
        # The SAME ordinary Http404 every other cross-tenant access
        # attempt in this codebase gets - not reset-specific logic.
        assert response.status_code == 404
        assert CustomerZeroFixture.objects.filter(organisation=customer_zero_org).exists()


@pytest.mark.django_db
class TestAccessControl:
    def test_unauthenticated_request_redirects_to_login(self, customer_zero_org, settings):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        response = Client().get(_reset_url(customer_zero_org.id))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_tampered_session_context_redirects_to_login_not_reset_specific(
        self, customer_zero_client, customer_zero_org, settings
    ):
        """
        Reuses the exact existing M007 fail-closed session-validation path
        (entitlements.session.get_validated_context) - see
        entitlements/tests/test_decorators.py's own equivalent proof for
        the decorator-guarded routes. Still authenticated at the Django
        session layer (login_required alone would not catch this) - only
        the structured `infosecurs_context` is missing/invalid.
        """
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        session = customer_zero_client.session
        del session[SESSION_KEY]
        session.save()

        response = customer_zero_client.get(_reset_url(customer_zero_org.id))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_no_non_owner_role_distinction_exists_in_this_codebase(self):
        """
        `organisations.models.OrganisationMembership.ROLE_CHOICES` is
        `[(ROLE_OWNER, "Owner")]` only - every member of every
        organisation in this codebase IS an owner, so "non-owner member"
        is not a reachable state to test separately from plain
        non-membership (already covered by TestForgedUUID above).
        Documented here rather than silently omitted.
        """
        assert [choice[0] for choice in OrganisationMembership.ROLE_CHOICES] == [
            OrganisationMembership.ROLE_OWNER
        ]


@pytest.mark.django_db
class TestHttpMethodCsrfConfirmationDiscipline:
    def test_get_never_deletes_anything_even_with_confirmation_query_param(
        self, customer_zero_client, customer_zero_org, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        OrganisationProfile.objects.create(
            organisation=customer_zero_org, legal_trading_name="Should survive a GET"
        )

        response = customer_zero_client.get(
            _reset_url(customer_zero_org.id), {"confirmation": "RESET"}
        )

        assert response.status_code == 200
        assert OrganisationProfile.objects.filter(organisation=customer_zero_org).exists()

    def test_missing_or_invalid_csrf_token_is_rejected_not_a_200(
        self, customer_zero_user, customer_zero_org, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        OrganisationProfile.objects.create(
            organisation=customer_zero_org, legal_trading_name="Should survive a CSRF failure"
        )
        enforcing_client = Client(enforce_csrf_checks=True)
        enforcing_client.force_login(customer_zero_user)

        response = enforcing_client.post(
            _reset_url(customer_zero_org.id), {"confirmation": "RESET"}
        )

        assert response.status_code == 403
        assert OrganisationProfile.objects.filter(organisation=customer_zero_org).exists()

    @pytest.mark.parametrize("bad_confirmation", ["reset", "Reset", "RESET ", "", "yes"])
    def test_incorrect_confirmation_text_deletes_nothing(
        self, customer_zero_client, customer_zero_org, settings, bad_confirmation
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        OrganisationProfile.objects.create(
            organisation=customer_zero_org, legal_trading_name="Should survive a bad confirmation"
        )

        response = customer_zero_client.post(
            _reset_url(customer_zero_org.id), {"confirmation": bad_confirmation}
        )

        assert response.status_code == 200
        assert OrganisationProfile.objects.filter(organisation=customer_zero_org).exists()


@pytest.mark.django_db
class TestSuccessfulResetSessionHandling:
    def test_successful_reset_fully_logs_out_the_current_session(
        self, customer_zero_client, customer_zero_org, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        response = customer_zero_client.post(
            _reset_url(customer_zero_org.id), {"confirmation": "RESET"}
        )
        assert response.status_code == 302
        assert response.url == reverse("login")

        # The session is genuinely destroyed, not merely redirected - a
        # follow-up request to any authenticated page is anonymous again.
        follow_up = customer_zero_client.get(reverse("organisations:list"))
        assert follow_up.status_code == 302
        assert follow_up.url.startswith(reverse("login"))

    def test_other_users_sessions_are_completely_unaffected(
        self, customer_zero_client, customer_zero_org, org_a, user_a, member_a, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        other_client = Client()
        other_client.force_login(user_a)
        # Prove other_client is genuinely authenticated before the reset.
        assert other_client.get(reverse("organisations:list")).status_code == 200

        customer_zero_client.post(_reset_url(customer_zero_org.id), {"confirmation": "RESET"})

        # Django's logout(request) only ever touches the CURRENT request's
        # own session - other_client's own session is a completely
        # independent server-side Session row.
        assert other_client.get(reverse("organisations:list")).status_code == 200
