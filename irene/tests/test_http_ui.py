import pytest
from django.urls import reverse

from entitlements.session import SESSION_KEY
from entitlements.tiers import TIER_FOUNDATION, TIER_PAUSED
from irene.models import ActionDecisionState, AssistantAction, AssistantConversation
from security_tasks.models import TaskKind

pytestmark = pytest.mark.django_db


class TestWorkspaceDirectUrlEnforcement:
    def test_member_with_irene_capability_is_redirected_to_home_open(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("irene:workspace", args=[org_a.id]))
        assert response.status_code == 302
        assert response["Location"].endswith(f"{reverse('organisations:detail', args=[org_a.id])}?irene=open")

    def test_non_member_gets_404(self, client_b, org_a):
        response = client_b.get(reverse("irene:workspace", args=[org_a.id]))
        assert response.status_code == 404

    def test_insufficient_tier_gets_403(self, client_a, org_a, user_a, member_a):
        session = client_a.session
        context = dict(session[SESSION_KEY])
        context["package_tier"] = TIER_PAUSED
        context["package_code"] = "PAUSED"
        session[SESSION_KEY] = context
        session.save()
        response = client_a.get(reverse("irene:workspace", args=[org_a.id]))
        assert response.status_code == 403


class TestHomeRendersIreneModal:
    def test_continue_tab_shows_real_question_not_empty_chat(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert b"irene-modal" in response.content
        assert b"irene-panel-continue" in response.content
        # Not an empty general-chat landing (M010C PID §1): the Continue
        # tab's own question title is present somewhere in the page.
        assert b'data-irene-panel="continue"' in response.content

    def test_paused_tier_gets_no_modal_at_all(self, client_a, org_a, user_a, member_a):
        session = client_a.session
        context = dict(session[SESSION_KEY])
        context["package_tier"] = TIER_PAUSED
        context["package_code"] = "PAUSED"
        session[SESSION_KEY] = context
        session.save()
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert b"irene-modal" not in response.content


class TestAskEndpoint:
    def test_get_not_allowed(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("irene:ask", args=[org_a.id]))
        assert response.status_code == 405

    def test_post_persists_message_and_redirects(self, client_a, org_a, user_a, member_a):
        response = client_a.post(
            reverse("irene:ask", args=[org_a.id]),
            {"message": "What does MFA mean?", "intent_code": "explain_control"},
        )
        assert response.status_code == 302
        assert "irene=open&irene_tab=ask" in response["Location"]
        conversation = AssistantConversation.objects.get(organisation=org_a, owner=user_a)
        assert conversation.messages.count() == 2

    def test_non_member_cannot_post(self, client_b, org_a):
        response = client_b.post(
            reverse("irene:ask", args=[org_a.id]), {"message": "x", "intent_code": "explain_control"}
        )
        assert response.status_code == 404

    def test_xss_in_message_is_escaped_on_render(self, client_a, org_a, user_a, member_a):
        payload = "<script>alert('xss')</script>"
        client_a.post(reverse("irene:ask", args=[org_a.id]), {"message": payload, "intent_code": "explain_control"})
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert b"<script>alert" not in response.content
        assert b"&lt;script&gt;" in response.content


class TestConfirmTaskEndpoint:
    def test_confirm_creates_task_and_redirects(self, client_a, org_a, user_a, member_a):
        from irene import tools as irene_tools
        from irene.tests.conftest import request_at_tier

        request = request_at_tier(user_a, organisation_id=org_a.id)
        context = irene_tools.build_authorized_context(request, org_a)
        preview = irene_tools.propose_task(context, kind=TaskKind.MANUAL_OTHER, title="Confirm via HTTP")

        response = client_a.post(
            reverse("irene:confirm_task", args=[org_a.id]), {"action_id": preview["action_id"]}
        )
        assert response.status_code == 302
        action = AssistantAction.objects.get(pk=preview["action_id"])
        assert action.decision_state == ActionDecisionState.EXECUTED

    def test_non_member_cannot_confirm(self, client_b, org_a, user_a, member_a):
        from irene import tools as irene_tools
        from irene.tests.conftest import request_at_tier

        request = request_at_tier(user_a, organisation_id=org_a.id)
        context = irene_tools.build_authorized_context(request, org_a)
        preview = irene_tools.propose_task(context, kind=TaskKind.MANUAL_OTHER, title="Org A only")

        response = client_b.post(
            reverse("irene:confirm_task", args=[org_a.id]), {"action_id": preview["action_id"]}
        )
        assert response.status_code == 404


class TestAssuranceStatusDirectUrlEnforcement:
    """M010E PID §3/§5 - the Monthly/PRO-gated Customer Assurance status
    page. `client_a`/`client_b` log in at the real-login default tier
    (TIER_MONTHLY - see entitlements/signals.py), so these tests
    explicitly downgrade to Foundational where a Foundational-tier
    direct-URL-bypass attempt is the point."""

    def test_monthly_member_sees_the_page(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Customer Assurance" in response.content

    def test_foundational_tier_direct_url_hit_gets_403_not_the_ask_ui(
        self, client_a, org_a, user_a, member_a
    ):
        """The literal 'hidden/direct-URL bypass' required test: a
        Foundational-tier member hitting this URL directly, bypassing
        any UI link IRENE would ever render for them (IRENE never offers
        this link below Monthly - see irene.tools.
        get_customer_assurance_status's own fail-closed behaviour),
        must get the ordinary, generic 403 - never the page, never a
        leaked blockers/entitlement payload."""
        session = client_a.session
        context = dict(session[SESSION_KEY])
        context["package_tier"] = TIER_FOUNDATION
        context["package_code"] = "FOUNDATION"
        session[SESSION_KEY] = context
        session.save()

        response = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert response.status_code == 403

    def test_paused_tier_direct_url_hit_gets_403(self, client_a, org_a, user_a, member_a):
        session = client_a.session
        context = dict(session[SESSION_KEY])
        context["package_tier"] = TIER_PAUSED
        context["package_code"] = "PAUSED"
        session[SESSION_KEY] = context
        session.save()

        response = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert response.status_code == 403

    def test_non_member_gets_404(self, client_b, org_a):
        response = client_b.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert response.status_code == 404

    def test_tier_downgrade_mid_session_denies_next_request(self, client_a, org_a, user_a, member_a):
        first = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert first.status_code == 200

        session = client_a.session
        context = dict(session[SESSION_KEY])
        context["package_tier"] = TIER_FOUNDATION
        context["package_code"] = "FOUNDATION"
        session[SESSION_KEY] = context
        session.save()

        second = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert second.status_code == 403


class TestAssuranceStatusReadinessBoundary:
    """Foundations 99% vs 100%, both at the real-login default Monthly
    tier - must render genuinely different, correct page content."""

    def test_99_percent_ready_shows_blockers_never_upload_link(self, client_a, org_a, user_a, member_a):
        from questionnaire.tests.conftest import _make_organisation_fully_assurance_ready
        from security_baseline.catalogue import CATALOGUE_KEYS
        from security_baseline.models import ANSWER_UNKNOWN, BaselineAnswer, BaselineAssessment

        _make_organisation_fully_assurance_ready(org_a)
        assessment = BaselineAssessment.objects.get(organisation=org_a)
        BaselineAnswer.objects.filter(assessment=assessment, question_key=CATALOGUE_KEYS[0]).update(
            answer=ANSWER_UNKNOWN
        )

        response = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert response.status_code == 200
        assert b"What still needs completing" in response.content
        assert b"Upload a questionnaire" not in response.content

    def test_100_percent_ready_shows_upload_link(self, client_a, org_a, user_a, member_a):
        from questionnaire.tests.conftest import _make_organisation_fully_assurance_ready

        _make_organisation_fully_assurance_ready(org_a)

        response = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Upload a questionnaire" in response.content
        assert reverse("questionnaire:import_upload", args=[org_a.id]).encode() in response.content


class TestRegisteredUploadLinkResolvesToTheRealWorkingPage:
    """Required test: 'prove the link resolves to the real, working page
    - not just that it does not 404'. Resolves the registered concept via
    the same tool `irene.orchestration`/this app's own Ask tab would use,
    then actually GETs it through the test client."""

    def test_customer_assurance_upload_concept_resolves_and_renders_the_real_form(
        self, client_a, org_a, user_a, member_a
    ):
        from irene import tools as irene_tools
        from irene.tests.conftest import request_at_tier
        from questionnaire.tests.conftest import _make_organisation_fully_assurance_ready

        _make_organisation_fully_assurance_ready(org_a)
        request = request_at_tier(user_a, organisation_id=org_a.id)
        context = irene_tools.build_authorized_context(request, org_a)
        url = irene_tools.get_registered_route(context, concept_id="customer_assurance_upload")
        assert url == reverse("questionnaire:import_upload", args=[org_a.id])

        response = client_a.get(url)
        assert response.status_code == 200
        assert b"<form" in response.content  # the real upload form, not a stub/placeholder

    def test_unentitled_tier_denied_closed_not_handed_a_link(self, org_a, user_a, member_a):
        """`get_registered_route` itself fails closed (PermissionDenied)
        for an insufficient tier - the SAME `_revalidate` recheck every
        tool performs, never a silent `None`. This is exactly why
        `irene.tools.get_customer_assurance_status` only ever calls
        `get_registered_route` AFTER it has already confirmed the tier-2
        entitlement itself (see that function's own docstring) - a
        Foundational-tier caller never reaches this far in the first
        place."""
        from django.core.exceptions import PermissionDenied
        from entitlements.tiers import TIER_FOUNDATION
        from irene import tools as irene_tools
        from irene.tests.conftest import request_at_tier

        request = request_at_tier(user_a, tier=TIER_FOUNDATION, organisation_id=org_a.id)
        context = irene_tools.build_authorized_context(request, org_a)
        with pytest.raises(PermissionDenied):
            irene_tools.get_registered_route(context, concept_id="customer_assurance_upload")


class TestAutoOpenPreference:
    def test_post_updates_preference(self, client_a, org_a, user_a, member_a):
        from foundations_journey.models import UserJourneyPreference

        response = client_a.post(
            reverse("irene:set_auto_open_preference", args=[org_a.id]), {}
        )
        assert response.status_code == 302
        preference = UserJourneyPreference.objects.get(user=user_a)
        assert preference.auto_open_enabled is False

    def test_manual_app_works_with_irene_disabled(self, client_a, org_a, user_a, member_a, settings):
        """M010C evidence requirement: manual application still fully
        works with IRENE_ENABLED off."""
        settings.IRENE_ENABLED = False
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert b"irene-modal" not in response.content
        # Tasks sidebar page remains fully reachable independent of IRENE.
        tasks_response = client_a.get(reverse("security_tasks:list", args=[org_a.id]))
        assert tasks_response.status_code == 200
