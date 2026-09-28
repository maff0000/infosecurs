"""
M007-WI6 - Part A: full regression / fresh independent adversarial re-proof
of the session/entitlement/tenant boundary at the HTTP level, against the
FINAL merged M007 source (WI1-WI5 all landed).

This file is deliberately NOT a rewrite of the extensive existing coverage
in `entitlements/tests/test_decorators.py`, `test_capabilities.py`,
`test_session_contract.py`, `test_login_issues_context.py`,
`core/tests/test_route_matrix.py`, `core/tests/test_csrf_and_methods.py` and
`core/tests/test_application_shell.py` - every one of those files was read
in full before writing this one, and every test below either (a) closes a
genuine, specific gap identified in that reading, or (b) re-proves a
property already covered there but through a route/scenario those files do
not themselves exercise (e.g. the WI5 Foundations route, which postdates
`test_decorators.py`'s own TIER1_ROUTES list). Where this file's own
docstrings say "already proven by X", that is a citation, not a claim this
file duplicates it.

See `docs/evidence/M007-SESSION-ENTITLEMENTS.md` for the full WI6 Part A
narrative this file is the mechanical proof for.
"""
from __future__ import annotations

import inspect
import uuid

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from entitlements import capabilities as capabilities_module
from entitlements import session as session_module
from entitlements.session import ENTITLEMENT_VERSION, SCHEMA_VERSION, SESSION_KEY
from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import (
    CODE_FOUNDATION,
    CODE_MONTHLY,
    TIER_FOUNDATION,
    TIER_MONTHLY,
    TIER_PAUSED,
    TIER_PRO,
)
from evidence.models import EvidenceItem
from key_assets.models import CATEGORY_ENDPOINT, CRITICALITY_MEDIUM, KeyAsset
from organisations.models import Organisation, OrganisationMembership
from policy.models import PolicyDocument, PolicyVersion
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from risk_register.models import Risk
from workplace.models import Workplace

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Part A.1 - Full tier matrix, direct URL probes, including the WI5
# Foundations route (not present in test_decorators.py's TIER1_ROUTES - that
# file was written for WI3, before WI5 added Foundations) and a POST-only
# nested-object "action" route (remediation:start), which the dispatch
# explicitly asks be included alongside plain list/detail routes.
# ---------------------------------------------------------------------------
class TestFoundationsRouteTierMatrix:
    """PID §25.1: Foundations is Foundation-tier-and-above, exactly like the
    other min_package_tier=1 areas - proven directly against
    `organisations:foundations`, which `test_decorators.py::TIER1_ROUTES`
    does not itself include. `organisations/tests/test_foundations_view.py::
    TestFoundationsTierMatrix` already proves this same property - this is
    a second, independent confirmation at the session/entitlement layer
    (this file's own subject), not a duplicate of that view-content test."""

    def test_paused_is_denied_foundations(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.get(reverse("organisations:foundations", args=[org_a.id]))
        assert response.status_code == 403

    @pytest.mark.parametrize("tier", [TIER_FOUNDATION, TIER_MONTHLY, TIER_PRO])
    def test_foundation_and_above_reach_foundations(self, client_a, user_a, org_a, tier):
        set_session_tier(client_a, user_a, tier, organisation_id=org_a.id)
        response = client_a.get(reverse("organisations:foundations", args=[org_a.id]))
        assert response.status_code == 200

    def test_copied_foundations_url_does_not_bypass_a_paused_session(self, client_a, user_a, org_a):
        """The exact, correctly-formed URL in hand - not a guess - still
        denied at Paused tier, mirroring `test_decorators.py`'s own
        Customer-Assurance copied-URL proof for this newer route."""
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        url = reverse("organisations:foundations", args=[org_a.id])
        assert client_a.get(url).status_code == 403


class TestPostOnlyNestedObjectRouteTierMatrix:
    """PID §25.1's "POST-only routes, nested object routes" bullet -
    `remediation:start` takes BOTH a POST-only method AND a nested
    `action_id` secondary id, and is wrapped in the same
    `require_capability()` decorator as every other organisation-scoped
    view (confirmed by reading `remediation/views.py`) - the tenant+
    capability gate runs before the view's own method/object lookup either
    way (see `core/tests/test_route_matrix.py`'s own WI3 note), so a denied
    tier must produce 403 regardless of whether the fabricated action_id
    would otherwise 404."""

    def test_paused_session_denied_on_a_post_only_action_route(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        url = reverse("remediation:start", args=[org_a.id, uuid.uuid4()])
        response = client_a.post(url, data={})
        assert response.status_code == 403

    def test_foundation_session_reaches_the_capability_gate_on_the_same_route(
        self, client_a, user_a, org_a
    ):
        """Foundation tier passes the entitlement gate (remediation is a
        `security`-tier=1 capability) - the fabricated action_id then 404s
        inside the view itself, proving the request reached the view body
        at all (not denied at the entitlement layer), distinguishing this
        from the Paused case above."""
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        url = reverse("remediation:start", args=[org_a.id, uuid.uuid4()])
        response = client_a.post(url, data={})
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Part A.2 - Client-side spoofing has zero effect, specifically through the
# NEW Home/Foundations routes (the dispatch's own explicit ask - WI3's own
# `TestClientSuppliedValuesHaveNoAuthority` proves this for key_assets/
# risk_register only, both pre-dating WI5).
# ---------------------------------------------------------------------------
class TestClientSideSpoofingThroughHomeAndFoundations:
    def test_forged_tier_signals_cannot_lift_a_paused_session_on_home(
        self, client_a, user_a, org_a
    ):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        client_a.cookies["package"] = "PRO"
        response = client_a.get(
            reverse("organisations:detail", args=[org_a.id]) + "?tier=3&package_tier=3&package=PRO",
            HTTP_X_PACKAGE_TIER="3",
            HTTP_X_PACKAGE="PRO",
            HTTP_X_INFOSECURS_TIER="3",
        )
        # Home itself is min_package_tier=0 - everyone, including a genuine
        # Paused session, gets 200 here (PID §13.1). The property under
        # test is that the PAUSED CONTENT still renders - i.e. the forged
        # signals did not upgrade what the view believes the tier to be.
        assert response.status_code == 200
        content = response.content.decode()
        assert "Your Infosecurs subscription is currently paused." in content
        assert "Foundational Security Posture" not in content

    def test_forged_tier_signals_cannot_unlock_foundations(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        client_a.cookies["package"] = "PRO"
        response = client_a.get(
            reverse("organisations:foundations", args=[org_a.id]) + "?tier=3&package=PRO",
            HTTP_X_PACKAGE_TIER="3",
            HTTP_X_PACKAGE="PRO",
        )
        assert response.status_code == 403

    def test_forged_post_body_on_foundations_get_only_route_has_no_effect(
        self, client_a, user_a, org_a
    ):
        """Foundations is a read-only GET workspace (PID §15) - a POST
        carrying forged tier fields must not be treated any differently
        from the GET probe above."""
        set_session_tier(client_a, user_a, TIER_PAUSED, organisation_id=org_a.id)
        response = client_a.post(
            reverse("organisations:foundations", args=[org_a.id]),
            {"package_tier": "3", "package_code": "PRO", "tier": "pro"},
        )
        assert response.status_code == 403


class TestClientSuppliedValuesAreStructurallyNeverRead:
    """PID §7.2/§19.2's stronger, code-level claim: it is not merely that
    today's tests happen not to find a bypass, but that `has_capability`
    and `get_validated_context` - the ONLY two functions any route guard
    consults - never reference `request.GET`, `request.POST`,
    `request.headers`, `request.META` or `request.COOKIES` AT ALL. This
    makes the client-supplied-value dimension checkable by source
    inspection, not just by trying representative variants (which the
    tests above and `test_decorators.py::TestClientSuppliedValuesHaveNoAuthority`
    already do) - proving the ABSENCE of a whole class of future regression,
    not just its current non-occurrence.

    This is also the basis for this WI's documented reasoning (PID's own
    ask) for why `localStorage`/`sessionStorage`/a JS global/DOM mutation
    are structurally impossible to matter: none of those are even
    observable server-side (Django's test Client cannot execute JS, and
    more fundamentally, nothing server-side ever asks the browser for any
    of that state) - the request object touched by these two functions
    carries only `request.session` (server-side, opaque cookie reference)
    and `request.user` (server-side, established by the session backend
    before either function runs). See docs/evidence/M007-SESSION-
    ENTITLEMENTS.md for the full write-up.
    """

    @pytest.mark.parametrize(
        "forbidden_token",
        ["request.GET", "request.POST", "request.headers", "request.META", "request.COOKIES"],
    )
    def test_has_capability_never_references_client_supplied_request_data(self, forbidden_token):
        source = inspect.getsource(capabilities_module.has_capability)
        assert forbidden_token not in source

    @pytest.mark.parametrize(
        "forbidden_token",
        ["request.GET", "request.POST", "request.headers", "request.META", "request.COOKIES"],
    )
    def test_get_validated_context_never_references_client_supplied_request_data(
        self, forbidden_token
    ):
        source = inspect.getsource(session_module.get_validated_context)
        assert forbidden_token not in source

    def test_validate_context_itself_only_ever_consumes_its_raw_argument(self):
        """`validate_context` (the fail-closed core) takes a plain `raw`
        dict and a `user` - it has no `request` parameter at all, so it is
        categorically incapable of consulting anything client-supplied
        beyond whatever `get_validated_context` chose to read out of
        `request.session` above."""
        parameters = list(inspect.signature(session_module.validate_context).parameters)
        assert parameters == ["raw", "user"]


# ---------------------------------------------------------------------------
# Part A.3 - Tenant/object isolation, broadly: a client who is a member of
# NEITHER org_a NOR org_b, set to PRO, cannot reach any of org_b's real
# objects across every representative organisation-scoped app. Every
# existing per-app test_tenant_isolation.py file proves "client_b (member
# of org_b only) cannot reach org_a's objects" - this proves the stronger,
# not-yet-covered case: a tier this high, for a user with NO membership
# ANYWHERE, still never substitutes for tenant membership.
# ---------------------------------------------------------------------------
@pytest.fixture
def org_c(db):
    return Organisation.objects.create(name="Org C Synthetic Ltd (no memberships)")


@pytest.fixture
def user_c(make_user):
    return make_user("user_c_no_memberships")


@pytest.fixture
def client_c_pro(user_c, org_c):
    """A user who is a member of `org_c` ONLY (needed so login issues a
    real context at all) but PRO-tier and probed exclusively against
    `org_b`, of which they are a member of nothing - the "member of
    neither org under test" case PID §25.4 asks for."""
    OrganisationMembership.objects.create(
        organisation=org_c, user=user_c, role=OrganisationMembership.ROLE_OWNER
    )
    c = Client()
    c.force_login(user_c)
    set_session_tier(c, user_c, TIER_PRO)
    return c


class TestTrulyNonMemberProTierNeverReachesForeignObjects:
    def test_key_asset(self, client_c_pro, org_b):
        asset = KeyAsset.objects.create(
            organisation=org_b,
            name="Org B laptop fleet",
            category=CATEGORY_ENDPOINT,
            criticality=CRITICALITY_MEDIUM,
            status=KeyAsset.STATUS_CONFIRMED,
        )
        assert client_c_pro.get(reverse("key_assets:list", args=[org_b.id])).status_code == 404
        assert (
            client_c_pro.get(reverse("key_assets:detail", args=[org_b.id, asset.id])).status_code
            == 404
        )

    def test_evidence(self, client_c_pro, org_b, user_b):
        item = EvidenceItem.objects.create(
            organisation=org_b,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Org B evidence",
            reference_url="https://example.test/org-b-evidence",
            recorded_by=user_b,
        )
        assert (
            client_c_pro.get(reverse("evidence:detail", args=[org_b.id, item.id])).status_code
            == 404
        )

    def test_risk(self, client_c_pro, org_b):
        risk = Risk.objects.create(
            organisation=org_b,
            title="Org B risk",
            threat="A threat",
            vulnerability="A gap",
            impact=1,
            likelihood=1,
            rationale="Because reasons.",
            proposed_treatment="Do something about it.",
            status=Risk.STATUS_CONFIRMED,
        )
        assert (
            client_c_pro.get(reverse("risk_register:detail", args=[org_b.id, risk.id])).status_code
            == 404
        )

    def test_policy_version(self, client_c_pro, org_b):
        document = PolicyDocument.objects.create(organisation=org_b)
        version = PolicyVersion.objects.create(
            document=document,
            organisation=org_b,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org B policy",
        )
        assert (
            client_c_pro.get(
                reverse("policy:version_detail", args=[org_b.id, version.id])
            ).status_code
            == 404
        )

    def test_questionnaire_response(self, client_c_pro, org_b, user_b):
        question = QuestionnaireQuestion.objects.create(
            organisation=org_b, question_text="Do you use MFA?", created_by=user_b
        )
        response = QuestionnaireResponse.objects.create(
            organisation=org_b,
            question=question,
            status=QuestionnaireResponse.STATUS_DRAFT,
            interpreted_requirement_summary="Asks about MFA.",
            intent_type="implementation",
            requirement_scope="all",
            selected_keys=["control:mfa_privileged_accounts"],
            evidence_explicitly_requested=False,
            outcome="GAP",
            ai_draft_text="No.",
            current_answer_text="No.",
            review_warnings=[],
        )
        assert (
            client_c_pro.get(
                reverse("questionnaire:response_detail", args=[org_b.id, response.id])
            ).status_code
            == 404
        )

    def test_workplace(self, client_c_pro, org_b):
        workplace = Workplace.objects.create(
            organisation=org_b,
            name="Org B office",
            type=Workplace.TYPE_DEDICATED_OFFICE,
            is_active=True,
        )
        assert (
            client_c_pro.get(reverse("workplace:edit", args=[org_b.id, workplace.id])).status_code
            == 404
        )

    def test_organisation_home_itself(self, client_c_pro, org_b):
        assert (
            client_c_pro.get(reverse("organisations:detail", args=[org_b.id])).status_code == 404
        )


# ---------------------------------------------------------------------------
# Part A.4 - Active organisation alignment: extends
# `test_decorators.py::TestStaleCrossOrganisationSessionRealignment` (which
# already proves organisation_id realignment, session-key rotation and
# package_tier preservation) with the one field it does not itself check -
# `package_code` - and an explicit assertion that no intermediate request
# ever observes a hybrid (org_a tier bound to org_b, or vice versa) state.
# ---------------------------------------------------------------------------
class TestActiveOrganisationAlignmentPreservesPackageCodeToo:
    def test_package_code_survives_realignment_both_directions(self, client_ab, org_a, org_b):
        first = client_ab.get(reverse("organisations:detail", args=[org_a.id]))
        assert first.status_code == 200
        context_a = client_ab.session[SESSION_KEY]
        assert context_a["organisation_id"] == str(org_a.id)
        assert context_a["package_code"] == CODE_MONTHLY  # client_ab's default post-login tier

        second = client_ab.get(reverse("organisations:detail", args=[org_b.id]))
        assert second.status_code == 200
        context_b = client_ab.session[SESSION_KEY]
        assert context_b["organisation_id"] == str(org_b.id)
        assert context_b["package_code"] == context_a["package_code"] == CODE_MONTHLY

        third = client_ab.get(reverse("organisations:detail", args=[org_a.id]))
        assert third.status_code == 200
        context_a_again = client_ab.session[SESSION_KEY]
        assert context_a_again["organisation_id"] == str(org_a.id)
        assert context_a_again["package_code"] == CODE_MONTHLY
        # Never a hybrid: at every step, organisation_id and package_code
        # are read from the SAME snapshot of the session, so "org_a bound
        # with a stale org_b flavoured context" is not a state that can
        # exist between these assertions - each block's own get() call is
        # the only write in between.


# ---------------------------------------------------------------------------
# Part A.5 - Logout/replay: extends
# `test_decorators.py::TestLogoutDestroysAccessAcrossRouteFamilies` (five
# route families, cookie-replay-in-a-fresh-Client already proven) with:
#   - the two NEW routes it doesn't cover (Home, Foundations) plus one
#     representative real object URL;
#   - explicit "accessed a Foundation capability AND a Monthly-only
#     capability before logout" (PID §8.1's own numbered steps 2-3);
#   - the final step PID §8.1 asks for that no existing test proves: a
#     SUBSEQUENT FRESH LOGIN (not force_login) issues a genuinely different
#     session identifier than the one that was captured and replayed.
# ---------------------------------------------------------------------------
class TestFullLogoutReplayFlow:
    def test_pro_session_full_logout_replay_and_fresh_relogin(self, org_a):
        User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()
        user = User.objects.create_user(username="wi6_logout_user", password="a-strong-test-password-123")
        OrganisationMembership.objects.create(
            organisation=org_a, user=user, role=OrganisationMembership.ROLE_OWNER
        )
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="WI6 logout-proof asset",
            category=CATEGORY_ENDPOINT,
            criticality=CRITICALITY_MEDIUM,
            status=KeyAsset.STATUS_CONFIRMED,
        )

        client = Client()
        login_ok = client.login(username="wi6_logout_user", password="a-strong-test-password-123")
        assert login_ok
        set_session_tier(client, user, TIER_PRO, organisation_id=org_a.id)

        # Steps 2-3 (PID §8.1): a Foundation-tier capability AND a
        # Monthly-only capability both genuinely reachable first.
        foundations_before = client.get(reverse("organisations:foundations", args=[org_a.id]))
        assert foundations_before.status_code == 200
        customer_assurance_before = client.get(reverse("questionnaire:list", args=[org_a.id]))
        assert customer_assurance_before.status_code == 200

        old_session_key = client.session.session_key
        old_cookie_value = client.cookies[settings.SESSION_COOKIE_NAME].value

        logout_response = client.post(reverse("logout"))
        assert logout_response.status_code in (200, 302)

        # Step 5: the old server-side session key no longer holds the
        # Infosecurs context at all (it was flushed, not merely
        # unauthenticated) - proven directly against the session store.
        from django.contrib.sessions.models import Session

        assert not Session.objects.filter(session_key=old_session_key).exists()

        # Steps 6-8: replay the OLD cookie in a genuinely fresh Client.
        replay_client = Client()
        replay_client.cookies[settings.SESSION_COOKIE_NAME] = old_cookie_value

        login_url = reverse("login")
        for route_name, args in [
            ("organisations:detail", [org_a.id]),
            ("organisations:foundations", [org_a.id]),
            ("key_assets:list", [org_a.id]),
            ("key_assets:detail", [org_a.id, asset.id]),
            ("security_state:list", [org_a.id]),
            ("evidence:list", [org_a.id]),
            ("policy:detail", [org_a.id]),
            ("organisations:organisation_hub", [org_a.id]),
            ("questionnaire:list", [org_a.id]),
        ]:
            replayed = replay_client.get(reverse(route_name, args=args))
            assert replayed.status_code == 302, f"{route_name} did not redirect after replay"
            assert replayed["Location"].startswith(login_url), (
                f"{route_name} redirected to {replayed['Location']!r}, not the login page"
            )

        # Step 9-11: a genuinely fresh login (real POST, not force_login)
        # issues a session identifier that differs from BOTH the original
        # pre-logout key and the (now-dead) replayed cookie value.
        fresh_client = Client()
        fresh_login = fresh_client.post(
            login_url, {"username": "wi6_logout_user", "password": "a-strong-test-password-123"}
        )
        assert fresh_login.status_code == 302
        new_session_key = fresh_client.session.session_key
        assert new_session_key is not None
        assert new_session_key != old_session_key

        # And the freshly issued context reflects only the newly issued
        # (default MONTHLY) package tier - PID §8.1 step 11 - never the
        # PRO tier this test artificially forced onto the old session via
        # `set_session_tier` above.
        new_context = fresh_client.session[SESSION_KEY]
        assert new_context["package_tier"] == TIER_MONTHLY


# ---------------------------------------------------------------------------
# Part A.6 - Invalid session matrix at the ROUTE level: extends
# `test_decorators.py::TestFailClosedInvalidSessionContextRedirectsToLogin`
# (which already covers UNKNOWN_SCHEMA_VERSION, SUBJECT_MISMATCH,
# TIER_OUT_OF_RANGE=7, CODE_TIER_MISMATCH, ORGANISATION_ID_MALFORMED="" and
# one MISSING_FIELD case + context missing entirely) with: every one of the
# 8 required fields missing individually (not just package_code), and the
# bool-tier type-confusion angle (`entitlements.tiers.is_valid_tier`'s own
# docstring already documents `isinstance(value, bool)` is deliberately
# excluded - `test_session_contract.py::test_tier_out_of_range` already
# parametrizes `True`/`False` at the unit level; this re-proves it end-to-
# end through a real, fully-resolved request).
# ---------------------------------------------------------------------------
class TestEveryRequiredFieldMissingIndividuallyAtRouteLevel:
    ALL_REQUIRED_FIELDS = [
        "schema_version",
        "subject_id",
        "organisation_id",
        "package_tier",
        "package_code",
        "entitlement_version",
        "issued_at",
        "auth_source",
    ]

    def _write_context(self, client, user, org_a, **overrides):
        session = client.session
        raw = {
            "schema_version": SCHEMA_VERSION,
            "subject_id": str(user.pk),
            "organisation_id": str(org_a.id),
            "package_tier": TIER_FOUNDATION,
            "package_code": CODE_FOUNDATION,
            "entitlement_version": ENTITLEMENT_VERSION,
            "issued_at": "2026-09-27T00:00:00+00:00",
            "auth_source": "wi6_test_fixture",
        }
        raw.update(overrides)
        session[SESSION_KEY] = raw
        session.save()

    @pytest.mark.parametrize("missing_field", ALL_REQUIRED_FIELDS)
    def test_each_required_field_missing_individually_redirects_to_login(
        self, client_a, user_a, org_a, missing_field
    ):
        self._write_context(client_a, user_a, org_a)
        session = client_a.session
        del session[SESSION_KEY][missing_field]
        session.save()

        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("login"))


class TestBoolTierTypeConfusionAtRouteLevel:
    """Python's `bool` is an `int` subclass - `True == 1` and `False == 0`
    - so a naive `tier in {0, 1, 2, 3}` membership check would accept a
    JSON `true`/`false` value as a valid tier by accident.
    `entitlements.tiers.is_valid_tier`'s own docstring documents this is
    deliberately excluded; this proves a request carrying exactly that
    tampered shape is genuinely denied end-to-end, not merely rejected by
    the isolated unit test."""

    def test_true_as_tier_is_denied_not_treated_as_foundation(self, client_a, user_a, org_a):
        session = client_a.session
        session[SESSION_KEY] = {
            "schema_version": SCHEMA_VERSION,
            "subject_id": str(user_a.pk),
            "organisation_id": str(org_a.id),
            "package_tier": True,  # == 1, i.e. would silently mean FOUNDATION if unguarded
            "package_code": CODE_FOUNDATION,
            "entitlement_version": ENTITLEMENT_VERSION,
            "issued_at": "2026-09-27T00:00:00+00:00",
            "auth_source": "wi6_test_fixture",
        }
        session.save()

        response = client_a.get(reverse("organisations:foundations", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("login"))

    def test_false_as_tier_is_denied_not_treated_as_paused(self, client_a, user_a, org_a):
        from entitlements.tiers import CODE_PAUSED

        session = client_a.session
        session[SESSION_KEY] = {
            "schema_version": SCHEMA_VERSION,
            "subject_id": str(user_a.pk),
            "organisation_id": str(org_a.id),
            "package_tier": False,  # == 0, i.e. would silently mean PAUSED if unguarded
            "package_code": CODE_PAUSED,
            "entitlement_version": ENTITLEMENT_VERSION,
            "issued_at": "2026-09-27T00:00:00+00:00",
            "auth_source": "wi6_test_fixture",
        }
        session.save()

        # Even Home (min_package_tier=0, which a genuine Paused session
        # CAN reach) must deny a bool-shaped tier - the point is that
        # `False` must never be treated as a legitimate value at all, not
        # that it fails to reach some higher bar.
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("login"))
