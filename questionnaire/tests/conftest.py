# Reuse the organisations app's tenant/user fixtures (org_a/org_b, user_a/
# user_b, client_a/client_b, ...) rather than duplicating them - same
# pattern security_state/tests/conftest.py / security_baseline/tests/
# conftest.py already use. Importing pytest fixtures re-exposes them to
# this directory's tests.
from organisations.tests.conftest import (  # noqa: F401
    client_a,
    client_b,
    make_user,
    member_a,
    member_b,
    org_a,
    org_b,
    user_a,
    user_b,
)

from ai_platform.testing import FakeQuestionnaireDraftingGateway, FakeQuestionnaireInterpretationGateway


class _CombinedFakeQuestionnaireGateway:
    """A single object implementing both
    `ai_platform.gateway.QuestionnaireInterpretationGateway` and
    `QuestionnaireDraftingGateway`'s methods (duck-typed - no ABC
    inheritance needed for a test double), mirroring how a real
    `LiteLLMGateway()` instance implements both ABCs (see
    `questionnaire.services.generate_questionnaire_response`'s own
    docstring: "A single LiteLLMGateway instance implements both ABCs").

    Used by `patch_questionnaire_generation_gateways` below to monkeypatch
    `questionnaire.services.LiteLLMGateway` for HTTP-level (view-layer)
    tests that exercise `questionnaire_analyse`/`questionnaire_response_
    regenerate` without an explicit gateway kwarg - those views call
    `generate_questionnaire_response` with its default
    `interpretation_gateway=None`/`drafting_gateway=None`, which then
    construct `LiteLLMGateway()` internally.
    """

    def __init__(self, interpretation_gateway, drafting_gateway):
        self.interpretation_gateway = interpretation_gateway
        self.drafting_gateway = drafting_gateway

    def interpret_questionnaire_question(self, request, prompt_version):
        return self.interpretation_gateway.interpret_questionnaire_question(request, prompt_version)

    def draft_questionnaire_answer(self, request, prompt_version):
        return self.drafting_gateway.draft_questionnaire_answer(request, prompt_version)


def patch_questionnaire_generation_gateways(
    monkeypatch, *, interpretation_result=None, drafting_result=None, mode="valid"
):
    """Monkeypatch `questionnaire.services.LiteLLMGateway` so any HTTP-level
    call into `generate_questionnaire_response` (via
    `questionnaire:analyse`/`questionnaire:response_regenerate`) uses
    deterministic fakes instead of a live gateway. Returns
    `(interpretation_gateway, drafting_gateway)` so a test can still
    inspect `.calls` afterwards."""
    interpretation_gateway = FakeQuestionnaireInterpretationGateway(
        mode=mode, result=interpretation_result
    )
    drafting_gateway = FakeQuestionnaireDraftingGateway(mode=mode, result=drafting_result)
    combined = _CombinedFakeQuestionnaireGateway(interpretation_gateway, drafting_gateway)
    monkeypatch.setattr("questionnaire.services.LiteLLMGateway", lambda: combined)
    return interpretation_gateway, drafting_gateway
