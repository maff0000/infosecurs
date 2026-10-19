"""
M010 Supplementary Audit D (2026-10-19), Scope D sub-case 1:

    "Pause a Foundations journey at a specific question, log out, log
    back in, confirm resume lands at the exact same checkpoint/question."

Independent corroboration fixture written by this supplementary audit -
not a rerun of any existing M010B test. Deliberately exercises the REAL
`login`/`logout` Django views via explicit POSTs to their real URLs
(never `Client.force_login()`/`Client.login()` shortcuts), so the whole
real authentication view stack - including the `entitlements.signals`
post-login `issue_context` wiring that `irene`/`foundations_journey`'s
own capability checks depend on - is genuinely exercised end to end, the
same as a real browser session doing a real logout-then-login.
"""
import pytest
from django.urls import reverse

from foundations_journey.models import CheckpointState, JourneyCheckpoint

pytestmark = pytest.mark.django_db

PASSWORD = "a-strong-test-password-123"  # matches conftest.make_user's default


def _post_login(client, username, password):
    return client.post(reverse("login"), {"username": username, "password": password})


def _post_logout(client):
    return client.post(reverse("logout"))


def test_pause_then_real_logout_login_resumes_at_exact_checkpoint(client, user_a, member_a, org_a):
    first_key = "mfa_user_accounts"
    second_key = "mfa_privileged_accounts"

    # --- Real login (first session) ---
    resp = _post_login(client, user_a.username, PASSWORD)
    assert resp.status_code == 302, resp.content

    # Answer the first control for real, via the real guided view, so
    # there is a genuine prior answer on record.
    resp = client.get(reverse("foundations_journey:guided_question", args=[org_a.id, first_key]))
    assert resp.status_code == 200
    resp = client.post(
        reverse("foundations_journey:guided_question", args=[org_a.id, first_key]),
        {"option__mfa_user_accounts": "MFA_USER_ALL_REQUIRED"},
    )
    assert resp.status_code == 302

    # The journey is now sitting at the SECOND control, not yet answered.
    resp = client.get(reverse("foundations_journey:guided_question", args=[org_a.id, second_key]))
    assert resp.status_code == 200
    checkpoint = JourneyCheckpoint.objects.get(organisation=org_a, user=user_a)
    assert checkpoint.current_question_key == second_key
    paused_version_arg = checkpoint.version

    # Pause here - a known, specific, un-answered question.
    resp = client.post(
        reverse("foundations_journey:pause", args=[org_a.id]),
        {"expected_version": paused_version_arg},
    )
    assert resp.status_code == 302

    checkpoint.refresh_from_db()
    assert checkpoint.checkpoint_state == CheckpointState.PAUSED
    assert checkpoint.current_question_key == second_key

    # --- Real logout ---
    resp = _post_logout(client)
    assert resp.status_code == 302

    # Prove the session is genuinely gone: a protected page now bounces to login.
    resp = client.get(reverse("organisations:detail", args=[org_a.id]))
    assert resp.status_code == 302
    assert reverse("login") in resp["Location"]

    # --- Real login again (brand new session) ---
    resp = _post_login(client, user_a.username, PASSWORD)
    assert resp.status_code == 302

    # A mere reconciling read (navigating back to Foundations) must not
    # silently un-pause the journey.
    resp = client.get(reverse("foundations_journey:guided_question", args=[org_a.id, second_key]))
    assert resp.status_code == 200
    checkpoint.refresh_from_db()
    assert checkpoint.checkpoint_state == CheckpointState.PAUSED
    assert checkpoint.current_question_key == second_key

    # Resume, using the checkpoint's own current version (read back off
    # the freshly-reloaded row - this is exactly what the real resume
    # form in the page would have pre-filled for a real browser).
    resp = client.post(
        reverse("foundations_journey:resume", args=[org_a.id]),
        {"expected_version": checkpoint.version},
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "foundations_journey:guided_question", args=[org_a.id, second_key]
    ), "Resume must land on the EXACT question that was paused - not an earlier or later one."

    checkpoint.refresh_from_db()
    assert checkpoint.checkpoint_state != CheckpointState.PAUSED
    assert checkpoint.current_question_key == second_key
