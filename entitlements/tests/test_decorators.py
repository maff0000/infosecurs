"""
M007-WI3 route/capability guard (PID §9, §25-27) - `entitlements.
decorators.require_capability`, proven at the full HTTP-request level
(real `django.test.Client`, real resolved URLs, real seeded `ProductArea`
rows), not just as an isolated unit. This is the file that proves the gap
PID §9 itself names is actually closed: "hiding a sidebar item is not
access control" - `entitlements/tests/test_capabilities.py` already proves
`has_capability` in isolation, and `entitlements/tests/test_navigation.py`
already proves the WI2 sidebar filters correctly, but until this WI/this
file, nothing proved a DIRECT REQUEST to any of the ~63 organisation-scoped
routes was actually blocked by that same decision.

Every test below reuses this app's own `conftest.py` fixtures
(`org_a`/`org_b`/`user_a`/`user_b`/`client_a`/`client_b`/`set_session_tier`)
and the new `user_ab`/`client_ab` fixtures (a user who is a genuine member
of BOTH seed organisations - see conftest.py for why that is its own
fixture, distinct from the single-organisation ones).
"""
from __future__ import annotations

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from django.urls import reverse

from entitlements.session import ENTITLEMENT_VERSION, SCHEMA_VERSION, SESSION_KEY
from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED, TIER_PRO

pytestmark = pytest.mark.django_db


# Every route requiring exactly `min_package_tier=1` ("security"/"policies"/
# "company" ProductAreas), one representative view per app this dispatch
# decorated - deliberately the SAME representative set
# `core/tests/test_application_shell.py`'s `REPRESENTATIVE_ORG_SCOPED_ROUTES`
# already uses for the sidebar-content proof, so the route-level proof here
# and the sidebar-content proof there are provably talking about the exact
# same routes.
TIER1_ROUTES = [
    "organisations:organisation_hub",
    "organisations:profile",
    "activity:list",
    "governance:roles",
    "workplace:list",
    "key_assets:list",
    "risk_register:list",
    "evidence:list",
    "remediation:list",
    "security_state:list",
    "security_baseline:baseline",
    "policy:detail",
]
# The one seeded `min_package_tier=2` ("customer_assurance") route.
TIER2_ROUTES = ["questionnaire:list"]
HOME_ROUTE = "organisations:detail"  # min_package_tier=0


class TestTierMatrixAtRouteLevel:
    """PID §25.1's exact tier matrix, proven against real HTTP responses to
    real resolved URLs - not the tree-building function
    (`entitlements/tests/test_navigation.py`'s job)."""

    def test_paused_reaches_home(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.get(reverse(HOME_ROUTE, args=[org_a.id]))
        assert response.status_code == 200

    @pytest.mark.parametrize("route_name", TIER1_ROUTES + TIER2_ROUTES)
    def test_paused_is_denied_every_tier1_and_above_route(self, client_a, user_a, org_a, route_name):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.get(reverse(route_name, args=[org_a.id]))
        assert response.status_code == 403

    @pytest.mark.parametrize("route_name", TIER1_ROUTES)
    def test_foundation_reaches_every_tier1_route(self, client_a, user_a, org_a, route_name):
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        response = client_a.get(reverse(route_name, args=[org_a.id]))
        # M008C-WI2b: `security_baseline:baseline` itself now always
        # redirects (302) into the guided Stage 4 journey on a GET it
        # has been allowed to reach at all (see security_baseline.views.
        # baseline_view) - every other TIER1_ROUTES member still renders
        # 200 directly. The property this test proves is "the capability
        # gate did not deny this tier", not "this exact route renders a
        # 200 body" - a 302 from the view ITSELF (as opposed to a 403
        # from require_capability) is just as valid a proof of "allowed
        # through" as a 200.
        assert response.status_code in (200, 302)

    def test_foundation_is_denied_customer_assurance(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        response = client_a.get(reverse("questionnaire:list", args=[org_a.id]))
        assert response.status_code == 403

    def test_copied_url_does_not_bypass_tier_check_even_with_exact_url_in_hand(
        self, client_a, user_a, org_a
    ):
        """Same proof as `test_foundation_is_denied_customer_assurance`,
        phrased explicitly for the dispatch's own 'copied/typed URLs do not
        bypass tier checks' acceptance criterion: a Foundation-tier session
        requesting the EXACT, correctly-formed, non-guessed Customer
        Assurance URL - exactly what a customer would have if they copied
        the link from a Monthly/Pro colleague, or simply typed it - is
        still denied. There is no way to reach this page merely by having
        the URL in hand that a hidden sidebar link would otherwise have
        prevented."""
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        url = reverse("questionnaire:list", args=[org_a.id])
        response = client_a.get(url)
        assert response.status_code == 403

    @pytest.mark.parametrize("route_name", TIER1_ROUTES + TIER2_ROUTES)
    def test_monthly_reaches_every_route_including_customer_assurance(
        self, client_a, user_a, org_a, route_name
    ):
        set_session_tier(client_a, user_a, TIER_MONTHLY, organisation_id=org_a.id)
        response = client_a.get(reverse(route_name, args=[org_a.id]))
        # See test_foundation_reaches_every_tier1_route's comment above -
        # security_baseline:baseline legitimately redirects (302) rather
        # than rendering 200 directly as of M008C-WI2b.
        assert response.status_code in (200, 302)

    def test_pro_inherits_every_route_monthly_reaches(self, client_a, user_a, org_a):
        """Proves the inheritance PROPERTY itself (PID §25.1's own "must
        prove inheritance, not duplicated flags") rather than merely
        re-asserting the same fixed list twice: whatever the Monthly
        session can reach, the Pro session can reach too."""
        all_routes = TIER1_ROUTES + TIER2_ROUTES + [HOME_ROUTE]
        # security_baseline:baseline redirects (302) rather than
        # rendering 200 directly as of M008C-WI2b - see
        # test_foundation_reaches_every_tier1_route's comment above.
        allowed_statuses = (200, 302)

        set_session_tier(client_a, user_a, TIER_MONTHLY, organisation_id=org_a.id)
        monthly_ok = {
            route_name
            for route_name in all_routes
            if client_a.get(reverse(route_name, args=[org_a.id])).status_code in allowed_statuses
        }

        set_session_tier(client_a, user_a, TIER_PRO, organisation_id=org_a.id)
        pro_ok = {
            route_name
            for route_name in all_routes
            if client_a.get(reverse(route_name, args=[org_a.id])).status_code in allowed_statuses
        }

        assert monthly_ok <= pro_ok
        assert pro_ok == set(all_routes)


class TestSidebarHiddenRoutesAreAlsoBlockedDirectly:
    """PID dispatch's own acceptance bullet: WI2 already proves these exact
    routes are hidden from the sidebar at each tier boundary
    (`core/tests/test_application_shell.py`'s
    `TestSidebarContentMatchesTierThroughRealHtml`) - this proves the SAME
    routes are not merely hidden but genuinely unreachable by direct
    navigation, closing PID §9's "hiding a sidebar item is not access
    control" gap for one route per tier boundary."""

    def test_foundation_customer_assurance_hidden_and_blocked(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        response = client_a.get(reverse("questionnaire:list", args=[org_a.id]))
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "route_name", ["key_assets:list", "policy:detail", "workplace:list"]
    )
    def test_paused_security_policies_company_hidden_and_blocked(
        self, client_a, user_a, org_a, route_name
    ):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.get(reverse(route_name, args=[org_a.id]))
        assert response.status_code == 403


class TestTenantMembershipDominatesOverTier:
    """PID §25.4/§9.3: package entitlement and tenant authorisation are
    separate, never-substitutable gates. `client_a`'s user is a genuine
    member of `org_a` only - every one of these requests targets `org_b`,
    of which they are not a member, and must be denied (ordinary 404,
    this codebase's existing non-member convention) regardless of tier,
    including artificially raised to PRO via `set_session_tier` - proving a
    high tier never substitutes for tenant membership."""

    @pytest.mark.parametrize(
        "route_name",
        ["organisations:detail", "key_assets:list", "questionnaire:list", "policy:detail"],
    )
    def test_default_monthly_tier_cannot_reach_a_foreign_organisation(
        self, client_a, org_b, route_name
    ):
        response = client_a.get(reverse(route_name, args=[org_b.id]))
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "route_name",
        ["organisations:detail", "key_assets:list", "questionnaire:list"],
    )
    def test_pro_tier_still_cannot_reach_a_foreign_organisation(
        self, client_a, user_a, org_b, route_name
    ):
        """The acceptance criterion's own explicit phrasing: 'prove this
        holds even when client_a's session tier is artificially set to
        PRO'."""
        set_session_tier(client_a, user_a, TIER_PRO)
        response = client_a.get(reverse(route_name, args=[org_b.id]))
        assert response.status_code == 404


class TestStaleCrossOrganisationSessionRealignment:
    """PID §6.5/§9's new "active organisation alignment" gate, proven with
    a user who is a LEGITIMATE member of both seed organisations
    (`client_ab`/`user_ab` - see conftest.py's own docstring for why this
    needs its own fixture, distinct from the single-organisation tenant-
    isolation fixtures above). A session that is valid and aligned to
    `org_a` must transparently realign (and rotate its session key, PID
    §19.1) when the SAME legitimately-authorised user next requests a URL
    under `org_b` - and a subsequent request must reflect `org_b`'s
    alignment cleanly, never a stale mix of the two."""

    def test_visiting_a_second_legitimate_organisation_realigns_and_rotates(
        self, client_ab, org_a, org_b
    ):
        first = client_ab.get(reverse("organisations:detail", args=[org_a.id]))
        assert first.status_code == 200
        session_key_after_a = client_ab.session.session_key
        context_after_a = client_ab.session[SESSION_KEY]
        assert context_after_a["organisation_id"] == str(org_a.id)

        second = client_ab.get(reverse("organisations:detail", args=[org_b.id]))
        assert second.status_code == 200
        session_key_after_b = client_ab.session.session_key
        context_after_b = client_ab.session[SESSION_KEY]
        assert context_after_b["organisation_id"] == str(org_b.id)
        # Genuine key rotation (PID §6.5/§19.1), not just a rewritten value
        # under the same key.
        assert session_key_after_b != session_key_after_a
        # The tier itself is untouched by realignment - only the bound
        # organisation changes.
        assert context_after_b["package_tier"] == context_after_a["package_tier"]

        # A subsequent request to a DIFFERENT org_b route reflects the
        # now-current org_b alignment, not a stale mix.
        third = client_ab.get(reverse("key_assets:list", args=[org_b.id]))
        assert third.status_code == 200

        # And swinging back to org_a realigns again - proving this is a
        # live, per-request decision, not a one-off/cached correction.
        fourth = client_ab.get(reverse("key_assets:list", args=[org_a.id]))
        assert fourth.status_code == 200
        assert client_ab.session[SESSION_KEY]["organisation_id"] == str(org_a.id)


class TestClientSuppliedValuesHaveNoAuthority:
    """PID §7.2/§19.2: none of a forged header, a forged query parameter,
    or a forged/unrelated cookie value may influence the entitlement
    decision - it must come only from the server-side validated session."""

    def test_forged_header_query_param_and_cookie_are_all_inert(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        # An attacker-controlled, entirely unrelated cookie claiming a
        # package tier - no code path in this product ever reads
        # request.COOKIES for entitlement, but PID §7.2 explicitly lists
        # this variant to try anyway.
        client_a.cookies["package"] = "PRO"

        response = client_a.get(
            reverse("key_assets:list", args=[org_a.id]) + "?tier=pro&package=PRO",
            HTTP_X_PACKAGE_TIER="3",
            HTTP_X_PACKAGE="PRO",
            HTTP_X_INFOSECURS_TIER="3",
        )
        assert response.status_code == 403

    def test_forged_post_body_tier_is_inert_on_a_post_only_route(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.post(
            reverse("risk_register:generate", args=[org_a.id]),
            {"package_tier": "3", "package": "PRO", "tier": "pro"},
        )
        assert response.status_code == 403


class TestLogoutDestroysAccessAcrossRouteFamilies:
    """`core/tests/test_application_shell.py`'s own
    `test_logout_still_actually_destroys_the_session` already proves this
    for Home (`organisations:detail`) using the SAME client's own (now
    logged-out) cookie jar. PID §8.1 requires proving it across several
    different route families AND via genuine cookie replay - a second,
    independent `Client` presenting the EXACT old session cookie value, not
    merely the same client continuing on with whatever its jar now holds.
    """

    ROUTE_FAMILIES = [
        "key_assets:list",  # Security
        "evidence:list",  # Evidence
        "policy:detail",  # Policy
        "workplace:list",  # Company
        "questionnaire:list",  # the Pro-capability-guard-test family (Monthly+)
    ]

    @pytest.mark.parametrize("route_name", ROUTE_FAMILIES)
    def test_old_session_cookie_replay_fails_after_logout(
        self, client_a, user_a, org_a, route_name
    ):
        set_session_tier(client_a, user_a, TIER_PRO, organisation_id=org_a.id)
        before = client_a.get(reverse(route_name, args=[org_a.id]))
        assert before.status_code == 200

        old_session_cookie_value = client_a.cookies[settings.SESSION_COOKIE_NAME].value

        client_a.post(reverse("logout"))

        replay_client = Client()
        replay_client.cookies[settings.SESSION_COOKIE_NAME] = old_session_cookie_value
        replayed = replay_client.get(reverse(route_name, args=[org_a.id]))

        # The flushed session carries no authentication at all any more -
        # @login_required (outermost on every one of these views) denies it
        # with its own ordinary redirect-to-login, before this WI's own
        # decorator ever runs.
        assert replayed.status_code == 302
        assert replayed["Location"].startswith(reverse("login"))


class TestFailClosedInvalidSessionContextRedirectsToLogin:
    """PID §6.4/§25.2's fail-closed tampering matrix
    (`entitlements/tests/test_session_contract.py` already proves
    `validate_context` itself denies every one of these in isolation) -
    this proves a REQUEST carrying one of these tampered contexts can never
    reach a protected view, and that this decorator's explicit, documented
    resolution (see `entitlements/decorators.py`'s own docstring) is a
    redirect to login, never any access and never a bare, unexplained 403
    that would leave the user permanently stuck."""

    def _write_tampered_context(self, client, user, **overrides):
        session = client.session
        raw = {
            "schema_version": SCHEMA_VERSION,
            "subject_id": str(user.pk),
            "organisation_id": None,
            "package_tier": TIER_PRO,
            "package_code": "PRO",
            "entitlement_version": ENTITLEMENT_VERSION,
            "issued_at": "2026-09-27T00:00:00+00:00",
            "auth_source": "tampered",
        }
        raw.update(overrides)
        session[SESSION_KEY] = raw
        session.save()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"schema_version": 999},  # UNKNOWN_SCHEMA_VERSION
            {"subject_id": "not-this-user"},  # SUBJECT_MISMATCH
            {"package_tier": 7},  # TIER_OUT_OF_RANGE
            {"package_code": "SUPER-PRO"},  # CODE_TIER_MISMATCH
            {"organisation_id": ""},  # ORGANISATION_ID_MALFORMED
        ],
    )
    def test_tampered_context_redirects_to_login_never_grants_access(
        self, client_a, user_a, org_a, overrides
    ):
        self._write_tampered_context(client_a, user_a, **overrides)
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("login"))

    def test_missing_field_context_redirects_to_login(self, client_a, user_a, org_a):
        session = client_a.session
        session[SESSION_KEY] = {
            "schema_version": SCHEMA_VERSION,
            "subject_id": str(user_a.pk),
            "organisation_id": None,
            "package_tier": TIER_PRO,
            # package_code deliberately omitted (MISSING_FIELD).
            "entitlement_version": ENTITLEMENT_VERSION,
            "issued_at": "2026-09-27T00:00:00+00:00",
            "auth_source": "tampered",
        }
        session.save()
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("login"))

    def test_missing_context_entirely_redirects_to_login(self, client_a, org_a):
        session = client_a.session
        del session[SESSION_KEY]
        session.save()
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("login"))


class TestDecoratorMisuseIsCaughtLoudly:
    """A programming-time error (a future view wired up without an
    `organisation_id` URL kwarg), not a request-time security decision -
    still worth a fast, explicit failure rather than an obscure
    `KeyError`/`AttributeError` the first time such a route is exercised."""

    def test_raises_improperly_configured_without_an_organisation_id_kwarg(self):
        from entitlements.decorators import require_capability

        @require_capability(capability_code="home")
        def view(request, **kwargs):
            raise AssertionError("the view body must never run")

        with pytest.raises(ImproperlyConfigured):
            view(request=None)
