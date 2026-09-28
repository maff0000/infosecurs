"""
M007-WI5 tests for the rewritten Home dashboard (`organisations:detail`,
PID §13-14).

Uses a small, real stdlib `html.parser.HTMLParser` walk (not a fragile raw
string search) to mechanically prove PID §14.1/§27's binding "the whole
Needs Attention line is never itself a link" rule - `requirements-dev.txt`
has no BeautifulSoup/lxml pinned (checked before writing this file, and
`core/tests/test_application_shell.py`'s own existing convention is plain
raw-string `in content` checks, not a parsing library), so this uses the
Python standard library's own real HTML parser rather than adding a new
dependency for one test file.

Follows this codebase's own established "small per-app fixture duplication
over cross-app imports" convention (entitlements/tests/conftest.py's own
docstring) - the baseline/policy helpers here mirror `entitlements/tests/
test_metrics.py`'s own equivalents rather than importing across the app
boundary.
"""
from __future__ import annotations

import datetime
from html.parser import HTMLParser

import pytest
from django.urls import reverse
from django.utils import timezone as django_timezone

from entitlements.metrics import (
    get_foundational_security_posture,
    get_needs_attention,
    get_security_foundations_completion,
)
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

# Every catalogue key answered YES - the only combination that makes
# important_controls/not_sure_controls both genuinely zero at once (weight
# >= 3 items are never partial/no, and nothing is unknown).
_ALL_BASELINE_YES = {
    "mfa_user_accounts": ANSWER_YES,
    "mfa_privileged_accounts": ANSWER_YES,
    "endpoint_protection": ANSWER_YES,
    "patching": ANSWER_YES,
    "device_encryption": ANSWER_YES,
    "backups": ANSWER_YES,
    "joiner_mover_leaver": ANSWER_YES,
    "privileged_access_separation": ANSWER_YES,
    "security_awareness_training": ANSWER_YES,
    "incident_reporting_route": ANSWER_YES,
    "email_phishing_protection": ANSWER_YES,
    "remote_access_control": ANSWER_YES,
}


def _set_baseline_answers(organisation, answers: dict[str, str]) -> BaselineAssessment:
    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=organisation, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    for key, answer in answers.items():
        BaselineAnswer.objects.update_or_create(
            assessment=assessment, question_key=key, defaults={"answer": answer}
        )
    return assessment


def _make_approved_policy(organisation, *, next_review_date=None):
    document = PolicyDocument.objects.create(organisation=organisation)
    return PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=1,
        status=PolicyVersion.STATUS_APPROVED,
        title="Information Security Policy",
        next_review_date=next_review_date,
        approved_at=django_timezone.now(),
    )


class _NeedsAttentionParser(HTMLParser):
    """Real HTML parse (stdlib `html.parser`) of every
    `<p class="needs-attention__line">` element - proves, mechanically,
    that each one is never itself nested inside an `<a>` and contains
    exactly one `<a>` child whose own text is exactly 'click here'."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tag_stack: list[str] = []
        self.lines: list[dict] = []
        self._current_line = None
        self._current_anchor_href = None
        self._current_anchor_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "p" and attrs_dict.get("class") == "needs-attention__line":
            self._current_line = {"inside_anchor": "a" in self.tag_stack, "anchors": []}
        elif tag == "a" and self._current_line is not None:
            self._current_anchor_href = attrs_dict.get("href")
            self._current_anchor_text = []
        self.tag_stack.append(tag)

    def handle_endtag(self, tag):
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
        if tag == "a" and self._current_line is not None and self._current_anchor_href is not None:
            self._current_line["anchors"].append(
                (self._current_anchor_href, "".join(self._current_anchor_text).strip())
            )
            self._current_anchor_href = None
            self._current_anchor_text = []
        if tag == "p" and self._current_line is not None:
            self.lines.append(self._current_line)
            self._current_line = None

    def handle_data(self, data):
        if self._current_anchor_href is not None:
            self._current_anchor_text.append(data)


def _parse_needs_attention_lines(content: str) -> list[dict]:
    parser = _NeedsAttentionParser()
    parser.feed(content)
    return parser.lines


# ---------------------------------------------------------------------------
# Tier 0 / Paused (PID §13.1)
# ---------------------------------------------------------------------------
class TestPausedHome:
    def test_paused_session_sees_neither_metric_card(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "metric-card-row" not in content
        assert "Foundational Security Posture" not in content
        assert "Security Foundations Completion" not in content

    def test_paused_session_sees_no_needs_attention_block(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "needs-attention" not in content
        assert "Needs attention" not in content

    def test_paused_session_sees_the_paused_wording(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_PAUSED)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "Your Infosecurs subscription is currently paused." in content
        assert "Product areas are unavailable while the subscription is paused." in content
        assert "Account management is handled separately." in content

    def test_paused_session_still_gets_200_not_denied(self, client_a, user_a, org_a):
        """`home`'s own ProductArea.min_package_tier is 0 - PID §13.1's own
        "everyone, including Paused, is allowed to REACH the Home URL"."""
        set_session_tier(client_a, user_a, TIER_PAUSED)
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Foundation / Monthly / Pro: the real dashboard (PID §13)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tier", [TIER_FOUNDATION, TIER_MONTHLY, TIER_PRO])
class TestNonPausedHomeMetricCards:
    def test_both_cards_show_the_exact_live_service_percentages(self, client_a, user_a, org_a, tier):
        set_session_tier(client_a, user_a, tier)
        _set_baseline_answers(
            org_a,
            {
                "mfa_privileged_accounts": ANSWER_PARTIAL,
                "patching": ANSWER_NO,
            },
        )
        expected_posture = get_foundational_security_posture(org_a)
        expected_completion = get_security_foundations_completion(org_a)

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "Foundational Security Posture" in content
        assert "Security Foundations Completion" in content
        assert f"{expected_posture.percentage}%" in content
        assert f"{expected_completion.percentage}%" in content
        assert (
            f"{expected_completion.completed_count} of {expected_completion.total_count} "
            "Foundations items completed."
        ) in content

    def test_posture_disclaimer_text_is_present(self, client_a, user_a, org_a, tier):
        set_session_tier(client_a, user_a, tier)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "Based on your recorded foundational security state." in content
        assert "This is not an independent security assessment." in content
        # PID §11.1 - the forbidden certification-adjacent wording must never appear.
        for forbidden in ("Certification", "Compliance Score", "Verified Security", "Maturity Rating"):
            assert forbidden not in content

    def test_action_links_present_and_point_at_real_routes(self, client_a, user_a, org_a, tier):
        set_session_tier(client_a, user_a, tier)
        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert reverse("security_state:list", args=[org_a.id]) in content
        assert reverse("organisations:foundations", args=[org_a.id]) in content
        assert "View security state" in content
        assert "Continue Foundations" in content


# ---------------------------------------------------------------------------
# Needs Attention (PID §14/§27)
# ---------------------------------------------------------------------------
class TestNeedsAttention:
    def test_zero_count_signal_produces_no_rendered_line_at_all(self, client_a, user_a, org_a):
        """Every catalogue item answered YES and no policy exists yet:
        important_controls/not_sure_controls/policy_review_overdue are all
        genuinely zero (a totally UNTOUCHED baseline would NOT do this -
        every unanswered item defaults to UNKNOWN, which would make
        not_sure_controls non-zero - entitlements.metrics's own "missing ==
        unknown" rule). foundations_incomplete is still non-zero here
        (milestones untouched), so this asserts on the OTHER three signals
        specifically, plus confirms the block only ever shows non-zero
        lines."""
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(org_a, _ALL_BASELINE_YES)
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.important_controls.count == 0
        assert needs_attention.not_sure_controls.count == 0
        assert needs_attention.policy_review_overdue.count == 0

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert "not fully implemented" not in content
        assert "marked Not sure" not in content
        assert "policy review is overdue" not in content
        assert "policy reviews are overdue" not in content

    def test_non_zero_signal_renders_exactly_one_correct_line(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        _make_approved_policy(org_a, next_review_date=yesterday)  # overdue -> count=1
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.policy_review_overdue.count == 1

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "1 policy review is overdue" in content
        assert "— " in content  # the em dash separator before "click here"
        assert ">click here<" in content

    def test_important_controls_line_has_the_correct_count_and_wording(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(
            org_a,
            {
                "mfa_privileged_accounts": ANSWER_NO,  # weight 5, important
                "patching": ANSWER_PARTIAL,  # weight 5, important
            },
        )
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.important_controls.count == 2

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "2 important security controls are not fully implemented" in content

    def test_not_sure_controls_line_uses_unknown_only(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        answers = dict(_ALL_BASELINE_YES)
        answers["mfa_user_accounts"] = ANSWER_UNKNOWN
        _set_baseline_answers(org_a, answers)
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.not_sure_controls.count == 1

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        assert "1 security control is marked Not sure" in content

    def test_every_rendered_line_is_not_itself_a_link_only_click_here_is(self, client_a, user_a, org_a):
        """The mechanical, real-HTML-parse proof (PID §27's own bullet)
        that the whole line is never itself one giant anchor - only the
        literal words 'click here' are the <a>."""
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        _make_approved_policy(org_a, next_review_date=yesterday)
        _set_baseline_answers(
            org_a,
            {
                "mfa_privileged_accounts": ANSWER_NO,
                "patching": ANSWER_PARTIAL,
                "mfa_user_accounts": ANSWER_UNKNOWN,
            },
        )
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.important_controls.count > 0
        assert needs_attention.not_sure_controls.count > 0
        assert needs_attention.foundations_incomplete.count > 0
        assert needs_attention.policy_review_overdue.count == 1

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        lines = _parse_needs_attention_lines(content)

        assert len(lines) == 4  # every signal is non-zero in this scenario
        for line in lines:
            assert line["inside_anchor"] is False, "a Needs Attention line must never be nested inside an <a>"
            assert len(line["anchors"]) == 1, "exactly one <a> per line"
            href, text = line["anchors"][0]
            assert text == "click here"
            assert href  # a real, non-empty destination

    def test_important_controls_link_points_at_security_state(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(org_a, {"mfa_privileged_accounts": ANSWER_NO})
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.important_controls.count == 1

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        lines = _parse_needs_attention_lines(content)
        expected_url = reverse("security_state:list", args=[org_a.id])
        hrefs = [href for line in lines for href, _text in line["anchors"]]
        assert expected_url in hrefs

    def test_foundations_incomplete_link_points_at_foundations_workspace(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        needs_attention = get_needs_attention(org_a)
        assert needs_attention.foundations_incomplete.count > 0  # fresh org - nothing completed yet

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        lines = _parse_needs_attention_lines(content)
        expected_url = reverse("organisations:foundations", args=[org_a.id])
        hrefs = [href for line in lines for href, _text in line["anchors"]]
        assert expected_url in hrefs

    def test_policy_review_overdue_link_points_at_policies(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        _make_approved_policy(org_a, next_review_date=yesterday)

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        lines = _parse_needs_attention_lines(content)
        expected_url = reverse("policy:detail", args=[org_a.id])
        hrefs = [href for line in lines for href, _text in line["anchors"]]
        assert expected_url in hrefs

    def test_not_sure_controls_link_points_at_baseline(self, client_a, user_a, org_a):
        set_session_tier(client_a, user_a, TIER_FOUNDATION)
        _set_baseline_answers(org_a, {"mfa_user_accounts": ANSWER_UNKNOWN})

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()
        lines = _parse_needs_attention_lines(content)
        expected_url = reverse("security_baseline:baseline", args=[org_a.id])
        hrefs = [href for line in lines for href, _text in line["anchors"]]
        assert expected_url in hrefs
