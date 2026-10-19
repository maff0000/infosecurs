"""
M010 Supplementary Audit D (2026-10-19), Scope D sub-case 2:

    "Change an answer via the manual (non-IRENE) Foundations page, then
    confirm IRENE's own view of that answer/status reflects the change
    correctly on next load."

Independent corroboration fixture written by this supplementary audit.
Uses the real `security_baseline:foundations_question` view (the manual,
non-guided, non-IRENE page `security_baseline/views.py` itself documents
as "the guided, one-question-at-a-time Stage 4 screen", as distinct from
IRENE's own modal/tool reads) to change an answer, then calls
`irene.tools.get_next_structured_question` - the EXACT function
`irene.views.build_modal_context`'s "Continue" tab and IRENE's own chat
tool-calling path both delegate to - to read IRENE's own view of that
same control, built from a real authenticated request/session (not a
mock), to prove there is no stale/cached value anywhere on that read
path.

All 12 controls are answered first so the journey reaches
`JOURNEY_COMPLETE`, at which point `current_question_key` legitimately
wraps back to the first control (`security_baseline.catalogue.
CATALOGUE_KEYS[0]`) - the one state in which that control is both
"IRENE's current question" and a control that already has a genuine
saved answer, so IRENE's own `saved_option_code` field is meaningfully
exercised.
"""
import pytest
from django.test import RequestFactory
from django.urls import reverse

from irene.tools import AuthorizedContext, get_next_structured_question

pytestmark = pytest.mark.django_db

PASSWORD = "a-strong-test-password-123"

_ALL_ANSWERS = [
    ("mfa_user_accounts", "MFA_USER_ALL_REQUIRED"),
    ("mfa_privileged_accounts", "MFA_ADMIN_ALL_REQUIRED"),
    ("endpoint_protection", "ENDPOINT_PROTECTION_ALL"),
    ("patching", "PATCHING_AUTOMATIC"),
    ("device_encryption", "DEVICE_ENCRYPTION_ALL"),
    ("backups", "BACKUPS_TESTED"),
    ("joiner_mover_leaver", "JML_DEFINED_FOLLOWED"),
    ("privileged_access_separation", "PRIV_SEP_DEDICATED"),
    ("security_awareness_training", "AWARENESS_REGULAR"),
    ("incident_reporting_route", "INCIDENT_ROUTE_CLEAR"),
    ("email_phishing_protection", "PHISHING_PROTECTION_ACTIVE_ALL"),
    ("remote_access_control", "REMOTE_ACCESS_GOVERNED"),
]


def _build_authorized_context(client, user, organisation):
    """Real session (same backing store the real login just created),
    real user, real organisation - only the bare `request` wrapper is
    synthesised, exactly as `irene.views`/`irene.tools` themselves
    require, since there is no bare-JSON HTTP endpoint for this
    internal tool to call over the wire."""
    request = RequestFactory().get("/")
    request.session = client.session
    request.user = user
    return AuthorizedContext(
        request=request,
        organisation_id=str(organisation.id),
        user_id=str(user.pk),
        request_id="audit-d-case2-probe",
    )


def test_manual_answer_change_is_reflected_in_irenes_own_view(client, user_a, member_a, org_a):
    resp = client.post(reverse("login"), {"username": user_a.username, "password": PASSWORD})
    assert resp.status_code == 302

    for key, option in _ALL_ANSWERS:
        resp = client.post(
            reverse("security_baseline:foundations_question", args=[org_a.id, key]),
            {f"option__{key}": option},
        )
        assert resp.status_code == 302, f"Answering {key!r} failed: {resp.content[:500]}"

    context = _build_authorized_context(client, user_a, org_a)

    before = get_next_structured_question(context)
    assert before["question_key"] == "mfa_user_accounts"
    assert before["saved_option_code"] == "MFA_USER_ALL_REQUIRED"

    # Change the answer via the MANUAL (non-IRENE) Foundations page.
    resp = client.post(
        reverse("security_baseline:foundations_question", args=[org_a.id, "mfa_user_accounts"]),
        {"option__mfa_user_accounts": "MFA_USER_NOT_USED"},
    )
    assert resp.status_code == 302

    after = get_next_structured_question(context)
    assert after["saved_option_code"] == "MFA_USER_NOT_USED", (
        "IRENE's own read tool must reflect the freshly-changed answer on its "
        "very next load, not a stale/cached value."
    )

    # Checkpoint-level status (the other IRENE read tool) must also stay
    # consistent - still complete, same completion figures (changing WHICH
    # option was picked for an already-answered control must never flip
    # completion state).
    from irene.tools import get_foundations_summary
    from foundations_journey.models import CheckpointState

    summary = get_foundations_summary(context)
    assert summary["checkpoint_state"] == CheckpointState.JOURNEY_COMPLETE
