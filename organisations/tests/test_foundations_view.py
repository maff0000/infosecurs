"""
M007-WI5 tests for the new Foundations workspace route (PID §15) - plus the
"Home and Foundations are genuinely distinct routes after migration 0004"
proof PID's own dispatch groups under "Routes/entitlements".

Follows this codebase's own established "small per-app fixture duplication
over cross-app imports" convention (entitlements/tests/conftest.py's own
docstring) - `_set_baseline_answers`/`_make_approved_policy`-shaped local
helpers here mirror `entitlements/tests/test_metrics.py`'s own, rather than
importing across the app boundary.
"""
from __future__ import annotations

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone as django_timezone

from entitlements.metrics import (
    get_foundations_requirement_states,
    get_security_foundations_completion,
)
from entitlements.models import ProductArea
from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED, TIER_PRO
from policy.models import PolicyDocument, PolicyVersion
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
    BaselineAnswer,
    BaselineAssessment,
)

pytestmark = pytest.mark.django_db


def _set_baseline_answers(organisation, answers: dict[str, str]) -> BaselineAssessment:
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=organisation, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    for key, answer in answers.items():
        BaselineAnswer.objects.update_or_create(
            assessment=assessment, question_key=key, defaults={"answer": answer}
        )
    return assessment


def _make_approved_policy(organisation):
    document = PolicyDocument.objects.create(organisation=organisation)
    return PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=1,
        status=PolicyVersion.STATUS_APPROVED,
        title="Information Security Policy",
        approved_at=django_timezone.now(),
    )


# ---------------------------------------------------------------------------
# Routes/entitlements: Home and Foundations are genuinely distinct routes
# after migration 0004 (PID dispatch's own "Routes/entitlements" bullet).
# ---------------------------------------------------------------------------
class TestFoundationsIsAGenuinelyDistinctRoute:
    def test_foundations_url_differs_from_home_url(self, org_a):
        home_url = reverse("organisations:detail", args=[org_a.id])
        foundations_url = reverse("organisations:foundations", args=[org_a.id])
        assert home_url != foundations_url

    def test_seeded_foundations_product_area_now_points_at_the_real_workspace(self):
        """Proves migration 0004 actually landed in the database this test
        suite runs against - not just that the two URL *names* differ."""
        area = ProductArea.objects.get(code="foundations")
        assert area.destination_view_name == "organisations:foundations"


# ---------------------------------------------------------------------------
# Tier matrix (PID dispatch's own "Paused gets denied (403)... Foundation/
# Monthly/Pro all get 200").
# ---------------------------------------------------------------------------
class TestFoundationsTierMatrix:
    def test_paused_session_is_denied(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED)
        response = client_a.get(reverse("organisations:foundations", args=[org_a.id]))
        assert response.status_code == 403

    @pytest.mark.parametrize("tier", [TIER_FOUNDATION, TIER_MONTHLY, TIER_PRO])
    def test_foundation_monthly_and_pro_sessions_are_allowed(self, client_a, user_a, org_a, tier):
        set_session_tier(client_a, user_a, tier)
        response = client_a.get(reverse("organisations:foundations", args=[org_a.id]))
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Workspace content (PID §15/§27's own tests bullet).
# ---------------------------------------------------------------------------
class TestFoundationsWorkspaceContent:
    def test_completion_summary_numbers_match_the_live_service_output(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(
            org_a,
            {
                "mfa_privileged_accounts": ANSWER_YES,
                "patching": ANSWER_PARTIAL,
                "backups": ANSWER_NO,
            },
        )
        expected = get_security_foundations_completion(org_a)

        content = client_a.get(reverse("organisations:foundations", args=[org_a.id])).content.decode()

        assert f"{expected.percentage}%" in content
        assert f"{expected.completed_count} of {expected.total_count} items completed." in content

    def test_exactly_the_current_v1_requirement_count_is_displayed(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        expected_states = get_foundations_requirement_states(org_a)
        expected_total = len(expected_states)
        # PID §12.3's own v1 total - asserted here as a sanity check on the
        # test's own fixture, not a value this view hard-codes anywhere.
        assert expected_total == 18

        content = client_a.get(reverse("organisations:foundations", args=[org_a.id])).content.decode()
        for state in expected_states:
            assert state.title in content
        assert content.count('class="foundations-row"') == expected_total

    @staticmethod
    def _row_html(content, title):
        """Isolates exactly one `<li class="foundations-row">...</li>`
        segment by its (unique) requirement title, so an assertion about
        one row's badge never accidentally passes because of an unrelated
        row elsewhere on the page (e.g. most baseline rows default to the
        same 'Not sure' badge when unanswered)."""
        start = content.index(title)
        end = content.index("</li>", start)
        return content[start:end]

    def test_a_baseline_answer_real_state_is_preserved_not_flattened(self, client_a, user_a, org_a):
        """A 'Partially' answer must render as the real answer, never a
        flattened 'Complete'/'Incomplete' (PID §15's binding rule)."""
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(org_a, {"mfa_privileged_accounts": ANSWER_PARTIAL})

        content = client_a.get(reverse("organisations:foundations", args=[org_a.id])).content.decode()
        # Title per entitlements/migrations/0003_seed_foundation_requirements.py's BASELINE_ROWS.
        row = self._row_html(content, "Multi-factor authentication (admin)")

        assert ">Partially<" in row
        assert ">Complete<" not in row
        assert ">Incomplete<" not in row

    def test_a_not_sure_baseline_answer_is_shown_as_not_sure_not_incomplete(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(org_a, {"mfa_user_accounts": ANSWER_UNKNOWN})

        content = client_a.get(reverse("organisations:foundations", args=[org_a.id])).content.decode()
        row = self._row_html(content, "Multi-factor authentication (staff)")

        assert ">Not sure<" in row
        assert ">Incomplete<" not in row
        assert ">Complete<" not in row

    def test_a_derived_milestone_shows_complete_or_needs_completion_wording(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _make_approved_policy(org_a)  # completes the policy_approved milestone only

        content = client_a.get(reverse("organisations:foundations", args=[org_a.id])).content.decode()
        # Titles per entitlements/migrations/0003_seed_foundation_requirements.py's MILESTONE_ROWS.
        policy_row = self._row_html(content, "Information Security Policy approved")
        workplace_row = self._row_html(content, "At least one active workplace recorded")

        assert ">Complete<" in policy_row
        assert ">Needs completion<" in workplace_row

    def test_each_row_action_link_resolves_to_the_correct_real_route(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        states = get_foundations_requirement_states(org_a)

        content = client_a.get(reverse("organisations:foundations", args=[org_a.id])).content.decode()

        area_by_code = {area.code: area for area in ProductArea.objects.active()}
        for state in states:
            expected_url = reverse(
                area_by_code[state.product_area_code].destination_view_name,
                kwargs={"organisation_id": org_a.id},
            )
            assert expected_url in content, (state.code, expected_url)

    def test_no_form_post_or_editable_checkbox_exists_on_the_page(self, client_a, user_a, org_a):
        """No checkbox anywhere on the page at all, and no `<form>` inside
        this page's OWN content (`{% block content %}`) - the shell's own
        logout form (`application_shell.html`, unrelated to Foundations) is
        deliberately excluded from this check, matching the dispatch's own
        "no form with a completion-related action" wording."""
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        content = client_a.get(reverse("organisations:foundations", args=[org_a.id])).content.decode()

        assert 'type="checkbox"' not in content

        main_start = content.index('id="main-content"')
        page_content = content[main_start:]
        assert "<form" not in page_content
