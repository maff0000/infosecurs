"""
M010B PID §6's required proof: "No model calls for the entire
deterministic flow." `ai_platform.gateway.LiteLLMGateway._send` is the
SOLE real network boundary in this codebase (every one of
`generate`/`interpret`/`generate_policy`/`interpret_questionnaire_
question`/`draft_questionnaire_answer` ultimately calls through it -
confirmed by direct read of ai_platform/gateway.py before writing this
test) - patching it and asserting it is never invoked, across a full
12-control guided run (every control answered, including the UNKNOWN/
PARTIAL/NO paths that trigger a follow-up-task offer), proves no AI
gateway call happened anywhere in this package, regardless of which
higher-level gateway method might otherwise have been called.
"""
import uuid
from unittest.mock import patch

import pytest

from ai_platform.gateway import LiteLLMGateway
from foundations_journey import services
from security_baseline.catalogue import CATALOGUE_KEYS


@pytest.mark.django_db
def test_full_twelve_control_guided_run_makes_zero_ai_gateway_calls(org_a, user_a, member_a):
    from organisations.models import OrganisationProfile

    OrganisationProfile.objects.create(
        organisation=org_a,
        legal_trading_name="Zero AI org",
        people_with_system_access_count=1,
        has_remote_or_offsite_access="no",
        endpoint_management="both",
    )

    # A representative answer per control, deliberately including
    # UNKNOWN/PARTIAL/NO/NOT_APPLICABLE paths (the ones that also trigger
    # a follow-up-task offer below) - not just the all-YES happy path.
    answers = {
        "mfa_user_accounts": "MFA_USER_NOT_SURE",
        "mfa_privileged_accounts": "MFA_ADMIN_ALL_REQUIRED",
        "endpoint_protection": "ENDPOINT_PROTECTION_NONE",
        "patching": "PATCHING_MOSTLY_CURRENT",
        "device_encryption": "DEVICE_ENCRYPTION_ALL",
        "backups": "BACKUPS_RESTORE_UNTESTED",
        "joiner_mover_leaver": "JML_NOT_APPLICABLE",
        "privileged_access_separation": "PRIV_SEP_DEDICATED",
        "security_awareness_training": "AWARENESS_NONE",
        "incident_reporting_route": "INCIDENT_ROUTE_CLEAR",
        "email_phishing_protection": "PHISHING_PROTECTION_ACTIVE_ALL",
        "remote_access_control": "REMOTE_ACCESS_NOT_APPLICABLE",
    }
    assert set(answers) == set(CATALOGUE_KEYS)

    with patch.object(LiteLLMGateway, "_send") as mock_send:
        for key, option_code in answers.items():
            confirmation = key in ("joiner_mover_leaver",)
            services.submit_foundations_option(
                org_a, user_a, question_key=key, option_code=option_code, confirmation=confirmation
            )
            view_model = services.get_foundations_question(org_a, user_a, key)
            assert view_model is not None
            services.get_journey_checkpoint(org_a, user_a)

        # Also exercise the explicit task-handoff path for the
        # UNKNOWN/PARTIAL/NO controls above - still zero AI calls.
        for key in ("mfa_user_accounts", "backups", "security_awareness_training"):
            services.offer_foundations_followup_task(
                org_a, user_a, question_key=key, idempotency_key=str(uuid.uuid4())
            )

        assert mock_send.call_count == 0, (
            f"Expected zero AI gateway calls for the deterministic guided journey, "
            f"got {mock_send.call_count}."
        )


def test_no_foundations_journey_module_imports_ai_platform():
    """Static corroboration of the dynamic proof above: none of this
    package's own modules import `ai_platform` at all."""
    import ast
    import pathlib

    package_dir = pathlib.Path(__file__).resolve().parent.parent
    offending = []
    for path in package_dir.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module else []
            else:
                continue
            if any(name and name.startswith("ai_platform") for name in names):
                offending.append(str(path))
    assert offending == [], f"Unexpected ai_platform import(s): {offending}"
