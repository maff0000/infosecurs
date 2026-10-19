"""
M010C PID §6's required proof: "Explicit proof the Continue/Tasks/Activity
tabs make zero AI gateway calls". Same technique Work Package B's
`foundations_journey/tests/test_zero_ai_calls.py` already established:
`ai_platform.gateway.LiteLLMGateway._send` is the SOLE real network
boundary in this codebase - patching it and asserting it is never invoked
proves no AI gateway call happened, regardless of which higher-level
gateway method might otherwise have been called.

Unlike `foundations_journey` (fully `ai_platform`-import-free by design),
`irene` DOES import `ai_platform` at module level (the optional Ask-tab
adviser path) - so the static "no ai_platform import anywhere in this
package" check that module's sibling test uses does not apply here. This
file's proof is entirely dynamic instead.
"""
from unittest.mock import patch

import pytest
from django.urls import reverse

from ai_platform.gateway import LiteLLMGateway

pytestmark = pytest.mark.django_db


class TestHomeRenderWithModalMakesZeroAICalls:
    def test_full_home_page_render_zero_gateway_calls(self, client_a, org_a, user_a, member_a):
        with patch.object(LiteLLMGateway, "_send") as mock_send:
            response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert mock_send.call_count == 0

    def test_workspace_redirect_zero_gateway_calls(self, client_a, org_a, user_a, member_a):
        with patch.object(LiteLLMGateway, "_send") as mock_send:
            response = client_a.get(reverse("irene:workspace", args=[org_a.id]))
        assert response.status_code == 302
        assert mock_send.call_count == 0


class TestAssuranceStatusPageMakesZeroAICalls:
    """M010E PID §5 - the new Customer Assurance status page/tool is
    entirely deterministic (readiness/entitlement/ORM reads only); it
    must make zero AI-gateway calls regardless of IRENE_ADVISER_MODE_
    ENABLED, and a simulated AI-provider failure must leave it (and the
    existing manual M009 upload/status flow) completely unaffected -
    reusing this file's own established `LiteLLMGateway._send` patch
    technique for every surface M010E adds."""

    def test_assurance_status_page_zero_gateway_calls(self, client_a, org_a, user_a, member_a):
        with patch.object(LiteLLMGateway, "_send") as mock_send:
            response = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert response.status_code == 200
        assert mock_send.call_count == 0

    def test_assurance_status_tool_zero_gateway_calls_even_if_adviser_mode_on(
        self, org_a, user_a, member_a, settings
    ):
        """Even with adviser mode flagged on, this tool itself never
        touches the gateway - it is a plain, deterministic read, exactly
        like every other Class R tool in irene.tools."""
        from entitlements.tiers import TIER_MONTHLY
        from irene import tools as irene_tools
        from irene.tests.conftest import request_at_tier

        settings.IRENE_ADVISER_MODE_ENABLED = True
        request = request_at_tier(user_a, tier=TIER_MONTHLY, organisation_id=org_a.id)
        context = irene_tools.build_authorized_context(request, org_a)
        with patch.object(LiteLLMGateway, "_send") as mock_send:
            irene_tools.get_customer_assurance_status(context)
        assert mock_send.call_count == 0

    def test_simulated_ai_provider_failure_leaves_manual_m009_upload_unaffected(
        self, client_a, org_a, user_a, member_a
    ):
        """A simulated AI-gateway failure must never affect the real,
        manual M009 upload/status flow this package only reads from and
        links to - that flow has no AI dependency of its own at all."""
        from questionnaire.tests.conftest import _make_organisation_fully_assurance_ready

        _make_organisation_fully_assurance_ready(org_a)
        with patch.object(LiteLLMGateway, "_send", side_effect=RuntimeError("simulated provider outage")):
            upload_response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
            assurance_response = client_a.get(reverse("irene:assurance_status", args=[org_a.id]))
        assert upload_response.status_code == 200
        assert assurance_response.status_code == 200
        assert b"Upload a questionnaire" in assurance_response.content


class TestAskTabWithAdviserModeOffMakesZeroAICalls:
    def test_ask_post_with_flag_off_zero_gateway_calls(self, client_a, org_a, user_a, member_a, settings):
        settings.IRENE_ADVISER_MODE_ENABLED = False
        with patch.object(LiteLLMGateway, "_send") as mock_send:
            response = client_a.post(
                reverse("irene:ask", args=[org_a.id]),
                {"message": "What does MFA mean?", "intent_code": "explain_control"},
            )
        assert response.status_code == 302
        assert mock_send.call_count == 0


def test_tools_module_never_imports_ai_platform():
    """Static corroboration: the tool registry/read-tool implementations
    themselves have no AI dependency at all - only `irene.orchestration`/
    `irene.views` ever touch `ai_platform`."""
    import ast
    import pathlib

    path = pathlib.Path(__file__).resolve().parent.parent / "tools.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    offending = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module] if node.module else []
        else:
            continue
        if any(name and name.startswith("ai_platform") for name in names):
            offending.append(str(path))
    assert offending == []
