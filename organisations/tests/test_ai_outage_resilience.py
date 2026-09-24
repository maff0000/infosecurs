"""
M006 PID §10 "AI outages must not break non-AI product areas" - mechanical
proof, not just an assumption from reading the code.

Two properties are exercised here:

1. Browsing pages that don't themselves trigger an AI call must keep
   working even when the AI gateway is completely unreachable. Every
   service module's own `LiteLLMGateway()` construction point
   (`policy.services.LiteLLMGateway`, `questionnaire.services.
   LiteLLMGateway`, `risk_register.interpretation_service.LiteLLMGateway`)
   is monkeypatched to a stand-in that raises `AssertionError` the instant
   it is *constructed* - stronger than merely leaving AI gateway env vars
   unset (which `LiteLLMGateway` already tolerates lazily), because it
   would fail LOUDLY if any of these read-only pages ever tried to reach
   the gateway, rather than silently happening not to. Every page below is
   read-only navigation reachable from the primary product journey (PID
   §5) and never calls into `ai_platform` at all in its own view code.

2. An AI action itself (questionnaire analyse, policy generate, risk
   interpret) fails cleanly and retryably when the gateway errors, without
   persisting malformed/partial state. `policy` and `risk_register`
   already have this proven at HTTP/service level elsewhere
   (`policy/tests/test_http_ui.py`'s `invalid_schema` case,
   `risk_register/tests/test_interpretation_service.py`'s `auth_error`/
   `always_fail_retryable` cases). This file adds the one gap this
   dispatch's own audit found: no HTTP-level test exercised
   `questionnaire_analyse` under a genuine gateway-unreachable mode
   (`timeout`), and no HTTP-level test exercised the gateway-unreachable
   mode specifically (as opposed to `invalid_schema`) for policy or risk
   interpretation - added below alongside the non-AI-page proof so all
   three AI surfaces' outage behaviour is asserted at the same altitude in
   one place.
"""
import pytest
from django.urls import reverse

from ai_platform.testing import (
    FakeInterpretationGateway,
    FakePolicyGateway,
    FakeQuestionnaireInterpretationGateway,
)
from key_assets.models import KeyAsset
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from risk_register.models import Risk
from risk_register.services import generate_draft_risks
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _unreachable_gateway_factory(name):
    """A stand-in for `LiteLLMGateway` that fails the test immediately if
    the page under test ever tries to construct a real gateway - proves
    the page genuinely never calls out to AI, rather than merely
    happening not to because AI_GATEWAY_* env vars are unset in test."""

    def _factory(*args, **kwargs):
        raise AssertionError(
            f"{name}: this read-only page must never construct an AI gateway "
            "at all - it is not one of the product's AI-triggering actions."
        )

    return _factory


@pytest.fixture
def gateway_completely_unreachable(monkeypatch):
    """Patches every AI-triggering service module's `LiteLLMGateway`
    construction point so any of them exploding proves an outage was
    genuinely simulated end-to-end, not just assumed."""
    monkeypatch.setattr(
        "policy.services.LiteLLMGateway", _unreachable_gateway_factory("policy.services")
    )
    monkeypatch.setattr(
        "questionnaire.services.LiteLLMGateway",
        _unreachable_gateway_factory("questionnaire.services"),
    )
    monkeypatch.setattr(
        "risk_register.interpretation_service.LiteLLMGateway",
        _unreachable_gateway_factory("risk_register.interpretation_service"),
    )


@pytest.mark.django_db
class TestNonAiPagesSurviveAGatewayOutage:
    """Every page below is reachable from primary navigation (PID §5) and
    is read-only with respect to AI - none of them should even attempt to
    construct a gateway, let alone fail because one is unreachable."""

    @pytest.mark.parametrize(
        "url_name",
        [
            "organisations:detail",  # Overview
            "security_baseline:baseline",
            "key_assets:list",
            "risk_register:list",
            "evidence:list",
            "remediation:list",
            "security_state:list",
            "policy:detail",
            "questionnaire:list",
            "activity:list",
            "organisations:organisation_hub",
        ],
    )
    def test_page_returns_200_with_ai_gateway_completely_unreachable(
        self, client_a, org_a, gateway_completely_unreachable, url_name
    ):
        response = client_a.get(reverse(url_name, args=[org_a.id]))
        assert response.status_code == 200


@pytest.mark.django_db
class TestAiActionsFailCleanlyOnGatewayOutage:
    """The one property that *should* be affected by an outage: the AI
    action itself. It must fail with a customer-facing message, remain
    retryable, and never persist malformed/partial state."""

    def test_questionnaire_analyse_fails_cleanly_on_gateway_timeout(self, client_a, org_a, monkeypatch):
        monkeypatch.setattr(
            "questionnaire.services.LiteLLMGateway",
            lambda: FakeQuestionnaireInterpretationGateway(mode="timeout"),
        )
        response = client_a.post(
            reverse("questionnaire:analyse", args=[org_a.id]),
            {"question_text": "Do you enforce MFA on privileged accounts?", "source_label": ""},
            follow=True,
        )
        # PID §22: the question itself is saved unconditionally up front -
        # that is a real, safe, complete fact ("a question was asked"), not
        # malformed/partial AI output - but no response was manufactured.
        assert QuestionnaireQuestion.objects.filter(organisation=org_a).count() == 1
        assert QuestionnaireResponse.objects.filter(organisation=org_a).count() == 0
        messages = [str(m) for m in response.context["messages"]]
        assert any("could not analyse" in m for m in messages)
        # Retryable: the question is still there to re-analyse, and the
        # list page itself still renders normally afterwards.
        assert response.status_code == 200
        assert b"Do you enforce MFA on privileged accounts?" in response.content

    def test_policy_generate_fails_cleanly_on_gateway_timeout(self, client_a, org_a, monkeypatch):
        from policy.models import PolicyVersion

        monkeypatch.setattr(
            "policy.services.LiteLLMGateway", lambda: FakePolicyGateway(mode="timeout")
        )
        response = client_a.post(reverse("policy:generate", args=[org_a.id]), follow=True)
        assert PolicyVersion.objects.filter(organisation=org_a).count() == 0
        messages = [str(m) for m in response.context["messages"]]
        assert any("could not be completed" in m for m in messages)

    def test_risk_interpret_fails_cleanly_on_gateway_timeout_and_leaves_risks_untouched(
        self, client_a, org_a, monkeypatch
    ):
        # A real, scenario-engine-produced draft risk (not hand-built), so
        # the gateway is actually invoked rather than short-circuiting on
        # an empty eligible-risk list.
        KeyAsset.objects.create(
            organisation=org_a,
            name="Org A endpoint",
            description="A staff laptop used for everyday work.",
            category="endpoint",
            criticality="medium",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(assessment=assessment, question_key="device_encryption", answer="no")
        created = generate_draft_risks(org_a)
        assert created  # sanity: a real draft risk exists for the gateway to be called over

        before = {r.id: (r.impact, r.likelihood, r.status) for r in Risk.objects.filter(organisation=org_a)}

        monkeypatch.setattr(
            "risk_register.interpretation_service.LiteLLMGateway",
            lambda: FakeInterpretationGateway(mode="timeout"),
        )
        response = client_a.post(reverse("risk_register:interpret", args=[org_a.id]), follow=True)

        after = {r.id: (r.impact, r.likelihood, r.status) for r in Risk.objects.filter(organisation=org_a)}
        assert before == after  # completely untouched, not partially updated
        messages = [str(m) for m in response.context["messages"]]
        assert any("could not be completed" in m for m in messages)
