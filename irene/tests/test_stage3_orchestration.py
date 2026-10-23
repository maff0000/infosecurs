"""
WO-IRENE-001 Increment 2 (browser-wiring) - unit tests for
`irene.question_engine.stage3_orchestration.ask_irene_stage3_explain`,
the new, additive Stage 3 "Explain this" orchestration entry point.
Mirrors `irene/tests/test_orchestration.py`'s own test shape/idiom
exactly (fake gateway injection via `ai_platform.testing.
FakeAdviserGateway`, `IRENE_ADVISER_MODE_ENABLED` on/off,
`GatewayError` failure -> fallback) - proving this function's behaviour
directly, independent of the HTTP view layer
(`irene/tests/test_stage3_browser_wiring.py` covers that separately).

Also proves this module's own documented design choice (module
docstring: "shares zero code path with `ask_irene`'s body... never
reads/writes `AssistantConversation`/`AssistantMessage`") -
`TestNeverTouchesAssistantMessageTable` below.
"""
from __future__ import annotations

import pytest

from ai_platform.adviser_contracts import SAFE_FALLBACK_MESSAGE
from ai_platform.testing import FakeAdviserGateway
from irene.question_engine.adapters.stage3_technology_data import (
    SECTION_CODE,
    answered_values_for_profile,
    resolve_stage3_explanation,
)
from irene.question_engine.registry import get_section
from irene.question_engine.stage3_orchestration import ask_irene_stage3_explain

pytestmark = pytest.mark.django_db


def _dispatch_for(organisation, question_code="productivity_platform"):
    section = get_section(SECTION_CODE)
    question = next(q for q in section.questions if q.question_code == question_code)
    return resolve_stage3_explanation(
        organisation=organisation,
        question=question,
        answered_values=answered_values_for_profile(None),
    )


class TestAdviserModeOffIsTheShippedDefault:
    def test_returns_exact_documented_fallback_and_never_touches_gateway(self, org_a, user_a, settings, monkeypatch):
        settings.IRENE_ADVISER_MODE_ENABLED = False

        def _explode(*args, **kwargs):
            raise AssertionError("LiteLLMGateway must never be constructed when the flag is off")

        monkeypatch.setattr("ai_platform.gateway.LiteLLMGateway.__init__", _explode)

        dispatch = _dispatch_for(org_a)
        response = ask_irene_stage3_explain(organisation=org_a, user=user_a, dispatch=dispatch)

        assert response.message == SAFE_FALLBACK_MESSAGE
        assert response.uncertainty_flag is True


class TestAdviserModeOnWithFakeGateway:
    def test_full_path_with_fake_gateway_builds_typed_minimised_request(self, org_a, user_a, settings):
        settings.IRENE_ADVISER_MODE_ENABLED = True
        dispatch = _dispatch_for(org_a)
        fake = FakeAdviserGateway(mode="valid")

        response = ask_irene_stage3_explain(organisation=org_a, user=user_a, dispatch=dispatch, gateway=fake)

        assert len(fake.calls) == 1
        assert response.message != SAFE_FALLBACK_MESSAGE
        sent_request, prompt_version = fake.calls[0]
        assert prompt_version == "adviser_v1"
        assert sent_request.intent_code == dispatch.context.intent_code
        # The typed, minimised question context only - never a raw
        # OrganisationProfile row or free text (WO §1a R1).
        assert dispatch.context.question_title in sent_request.user_message
        assert sent_request.organisation_id == str(org_a.id)

    def test_gateway_failure_falls_back_safely(self, org_a, user_a, settings):
        settings.IRENE_ADVISER_MODE_ENABLED = True
        dispatch = _dispatch_for(org_a)
        fake = FakeAdviserGateway(mode="timeout")

        response = ask_irene_stage3_explain(organisation=org_a, user=user_a, dispatch=dispatch, gateway=fake)

        assert response.message == SAFE_FALLBACK_MESSAGE

    def test_no_skill_resolves_to_fallback_without_calling_gateway(self, org_a, user_a, settings):
        """Mirrors `irene.orchestration.ask_irene`'s own "no skill ->
        fallback, zero gateway calls" behaviour for an unresolvable
        intent code."""
        import dataclasses

        settings.IRENE_ADVISER_MODE_ENABLED = True
        dispatch = _dispatch_for(org_a)
        unresolved_dispatch = dataclasses.replace(dispatch, skill=None)
        fake = FakeAdviserGateway(mode="valid")

        response = ask_irene_stage3_explain(organisation=org_a, user=user_a, dispatch=unresolved_dispatch, gateway=fake)

        assert fake.calls == []
        assert response.message == SAFE_FALLBACK_MESSAGE


class TestNeverTouchesAssistantMessageTable:
    def test_a_real_call_writes_no_conversation_rows(self, org_a, user_a, settings):
        from irene.models import AssistantMessage

        settings.IRENE_ADVISER_MODE_ENABLED = True
        dispatch = _dispatch_for(org_a)
        fake = FakeAdviserGateway(mode="valid")

        ask_irene_stage3_explain(organisation=org_a, user=user_a, dispatch=dispatch, gateway=fake)

        assert AssistantMessage.objects.count() == 0
