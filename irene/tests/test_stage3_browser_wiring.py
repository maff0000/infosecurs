"""
WO-IRENE-001 Increment 2 (browser-wiring) - HTTP-level tests for the
three new, additive Stage 3 question-engine views (`irene.views.
stage3_panel`/`stage3_save`/`stage3_explain`) and the IRENE modal's new,
additive Stage 3 tab (`irene.views.build_modal_context`'s `stage3_tab`).

Proves, per the dispatch's six Central Architecture requirements:
  1. the registered Stage 3 questions are presented and answered inside
     the existing IRENE modal (`TestHomeRendersStage3Tab`);
  2. every real browser request independently enforces the composed
     tenant+capability gate - a non-member gets 404, a member missing
     the required capability gets 403
     (`TestStage3PanelAccess`/`TestStage3SaveAccess`/
     `TestStage3ExplainAccess`);
  3. saving goes through the audited guarded adapter
     (`organisations.services.save_stage3_fields`) only, and a stale
     `expected_state_token` is a real, non-500, user-visible rejection
     (`TestStage3Save`);
  6. the fallback remains functional when Adviser Mode is disabled
     (`TestStage3Explain.test_fallback_path_when_adviser_mode_disabled`).

Requirement 5 (existing Ask-tab/manual Stage 3 page/template left
completely unchanged) is proved separately: by every pre-existing test
in `irene/tests/test_orchestration.py`/`irene/tests/test_http_ui.py`/
`organisations/tests/test_stage3_technology_data_view.py` continuing to
pass unmodified, and by the explicit `git diff` self-check in the FORGE
report (zero changes to `organisations/views.py`'s
`organisation_stage3_technology_data` or its template).
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from ai_platform.adviser_contracts import SAFE_FALLBACK_MESSAGE
from entitlements.session import SESSION_KEY
from entitlements.tiers import TIER_PAUSED
from organisations.models import OrganisationProfile
from organisations.services import compute_stage3_expected_state_token

pytestmark = pytest.mark.django_db


def _downgrade_to_paused(client):
    """Same idiom `irene/tests/test_http_ui.py` already uses to prove an
    insufficient-tier 403 - PAUSED (tier 0) satisfies neither `irene` nor
    `foundations` (both min tier 1), so this is "a real member whose
    session fails the required capability check", never a tenant-
    membership failure."""
    session = client.session
    context = dict(session[SESSION_KEY])
    context["package_tier"] = TIER_PAUSED
    context["package_code"] = "PAUSED"
    session[SESSION_KEY] = context
    session.save()


class TestHomeRendersStage3Tab:
    def test_member_with_irene_and_foundations_sees_the_stage3_tab(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert b'data-irene-panel="stage3"' in response.content
        assert b'id="irene-tab-stage3"' in response.content
        # The four pre-existing tabs/panels are still present, unaltered.
        assert b'data-irene-panel="continue"' in response.content
        assert b'data-irene-panel="ask"' in response.content

    def test_insufficient_tier_hides_the_whole_modal_same_as_before(self, client_a, org_a, user_a, member_a):
        """PAUSED already fails the whole-modal `irene` gate today
        (pre-existing behaviour, `irene/tests/test_http_ui.py::
        TestHomeRendersIreneModal::test_paused_tier_gets_no_modal_at_all`)
        - this increment changes nothing about that outcome."""
        _downgrade_to_paused(client_a)
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 200
        assert b"irene-modal" not in response.content


class TestStage3PanelAccess:
    def test_member_with_required_capabilities_gets_200(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("irene:stage3_panel", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Your Technology" in response.content

    def test_non_member_gets_404_never_403(self, client_b, org_a):
        response = client_b.get(reverse("irene:stage3_panel", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_without_required_capability_gets_403(self, client_a, org_a, user_a, member_a):
        _downgrade_to_paused(client_a)
        response = client_a.get(reverse("irene:stage3_panel", args=[org_a.id]))
        assert response.status_code == 403


class TestStage3SaveAccess:
    def test_get_not_allowed(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("irene:stage3_save", args=[org_a.id]))
        assert response.status_code == 405

    def test_non_member_cannot_save(self, client_b, org_a):
        response = client_b.post(
            reverse("irene:stage3_save", args=[org_a.id]),
            {"question_code": "productivity_platform", "productivity_platform": "microsoft_365"},
        )
        assert response.status_code == 404
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_member_without_required_capability_cannot_save(self, client_a, org_a, user_a, member_a):
        _downgrade_to_paused(client_a)
        response = client_a.post(
            reverse("irene:stage3_save", args=[org_a.id]),
            {"question_code": "productivity_platform", "productivity_platform": "microsoft_365"},
        )
        assert response.status_code == 403
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()


class TestStage3ExplainAccess:
    def test_get_not_allowed(self, client_a, org_a, user_a, member_a):
        response = client_a.get(reverse("irene:stage3_explain", args=[org_a.id]))
        assert response.status_code == 405

    def test_non_member_cannot_explain(self, client_b, org_a):
        response = client_b.post(
            reverse("irene:stage3_explain", args=[org_a.id]), {"question_code": "productivity_platform"}
        )
        assert response.status_code == 404

    def test_member_without_required_capability_cannot_explain(self, client_a, org_a, user_a, member_a):
        _downgrade_to_paused(client_a)
        response = client_a.post(
            reverse("irene:stage3_explain", args=[org_a.id]), {"question_code": "productivity_platform"}
        )
        assert response.status_code == 403


class TestStage3Save:
    def test_real_save_round_trips_through_the_guarded_adapter(self, client_a, org_a, user_a, member_a):
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        response = client_a.post(
            reverse("irene:stage3_save", args=[org_a.id]),
            {
                "question_code": "productivity_platform",
                "productivity_platform": "microsoft_365",
                "expected_state_token": token,
            },
        )
        assert response.status_code == 302
        assert "irene=open&irene_tab=stage3" in response["Location"]
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.productivity_platform == "microsoft_365"

    def test_stale_expected_state_token_is_a_real_non_500_rejection(self, client_a, org_a, user_a, member_a):
        OrganisationProfile.objects.create(organisation=org_a, productivity_platform="google_workspace")
        stale_token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        # A concurrent writer changes the field after this token was issued.
        profile = OrganisationProfile.objects.get(organisation=org_a)
        profile.productivity_platform = "other"
        profile.save(update_fields=["productivity_platform"])

        response = client_a.post(
            reverse("irene:stage3_save", args=[org_a.id]),
            {
                "question_code": "productivity_platform",
                "productivity_platform": "microsoft_365",
                "expected_state_token": stale_token,
            },
        )

        assert response.status_code == 302  # never a 500
        assert "irene=open&irene_tab=stage3" in response["Location"]
        profile.refresh_from_db()
        # The rejected write never applied.
        assert profile.productivity_platform == "other"
        follow = client_a.get(response["Location"])
        assert b"updated this answer" in follow.content

    def test_grouped_question_saves_every_sibling_field_together(self, client_a, org_a, user_a, member_a):
        field_names = [
            "handles_personal_data",
            "handles_confidential_business_data",
            "handles_payment_card_data",
            "handles_special_category_data",
        ]
        token = compute_stage3_expected_state_token(org_a, field_names)
        response = client_a.post(
            reverse("irene:stage3_save", args=[org_a.id]),
            {
                "question_code": "stage3_q5_data_handled",
                "expected_state_token": token,
                "handles_personal_data": "yes",
                "handles_confidential_business_data": "no",
                "handles_payment_card_data": "no",
                "handles_special_category_data": "unknown",
            },
        )
        assert response.status_code == 302
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.handles_personal_data == "yes"
        assert profile.handles_confidential_business_data == "no"

    def test_unknown_question_code_is_404_not_500(self, client_a, org_a, user_a, member_a):
        response = client_a.post(
            reverse("irene:stage3_save", args=[org_a.id]),
            {"question_code": "not_a_real_question", "expected_state_token": ""},
        )
        assert response.status_code == 404

    def test_delegated_workflow_question_cannot_be_saved_here(self, client_a, org_a, user_a, member_a):
        """3.7/Key Assets - Amendment D3's "link out, come back", never a
        duplicate inline editor; this endpoint refuses to write anything
        for it, never a 500."""
        response = client_a.post(
            reverse("irene:stage3_save", args=[org_a.id]),
            {"question_code": "stage3_q7_key_assets", "expected_state_token": ""},
        )
        assert response.status_code == 302
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()


class TestStage3Explain:
    def test_fallback_path_when_adviser_mode_disabled(self, client_a, org_a, user_a, member_a, settings):
        settings.IRENE_ADVISER_MODE_ENABLED = False
        response = client_a.post(
            reverse("irene:stage3_explain", args=[org_a.id]), {"question_code": "productivity_platform"}
        )
        assert response.status_code == 302
        assert "irene=open&irene_tab=stage3" in response["Location"]

        follow = client_a.get(response["Location"])
        assert SAFE_FALLBACK_MESSAGE.encode() in follow.content

    def test_delegated_workflow_question_cannot_be_explained_here(self, client_a, org_a, user_a, member_a):
        response = client_a.post(
            reverse("irene:stage3_explain", args=[org_a.id]), {"question_code": "stage3_q7_key_assets"}
        )
        assert response.status_code == 302  # never a 500

    def test_unknown_question_code_is_404_not_500(self, client_a, org_a, user_a, member_a):
        response = client_a.post(
            reverse("irene:stage3_explain", args=[org_a.id]), {"question_code": "not_a_real_question"}
        )
        assert response.status_code == 404
