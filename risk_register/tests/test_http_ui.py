"""
HTTP-level tests for the risk_register review/confirm/dismiss UI
(PID §19, §20, §21).

`TestRiskGenerationView` REWRITTEN by the M002-3b dispatch: generation is
now the deterministic scenario-instantiation engine
(risk_register.scenario_engine) - there is no gateway to substitute any
more, so these tests set up ordinary KeyAsset/BaselineAnswer fixtures and
POST directly, exactly like a real request. No ai_platform import
anywhere in this file.
"""
import pytest
from django.urls import reverse

from key_assets.models import KeyAsset
from risk_register.models import Risk

MAX_ASSET_NAME_LENGTH = KeyAsset._meta.get_field("name").max_length


@pytest.mark.django_db
class TestRiskGenerationView:
    def test_get_is_not_allowed(self, client_a, org_a):
        response = client_a.get(reverse("risk_register:generate", args=[org_a.id]))
        assert response.status_code == 405

    def test_post_success_creates_draft_risks_and_redirects_to_list(self, client_a, org_a):
        KeyAsset.objects.create(
            organisation=org_a, name="Staff laptop", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        response = client_a.post(reverse("risk_register:generate", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url == reverse("risk_register:list", args=[org_a.id])
        assert Risk.objects.filter(organisation=org_a, status=Risk.STATUS_DRAFT_AI_SUGGESTED).count() > 0

    def test_post_with_no_confirmed_assets_creates_no_risks_and_shows_a_clear_message(
        self, client_a, org_a
    ):
        response = client_a.post(reverse("risk_register:generate", args=[org_a.id]), follow=True)
        assert Risk.objects.filter(organisation=org_a).count() == 0
        messages = [str(m) for m in response.context["messages"]]
        assert any("did not propose any new risks" in m for m in messages)

    def test_post_twice_creates_no_duplicates_and_leaves_a_confirmed_risk_untouched(
        self, client_a, org_a
    ):
        KeyAsset.objects.create(
            organisation=org_a, name="Staff laptop", category="endpoint",
            criticality="medium", status=KeyAsset.STATUS_CONFIRMED,
        )
        client_a.post(reverse("risk_register:generate", args=[org_a.id]))
        existing = Risk.objects.filter(organisation=org_a).first()
        existing.status = Risk.STATUS_CONFIRMED
        existing.save()
        before_count = Risk.objects.filter(organisation=org_a).count()

        client_a.post(reverse("risk_register:generate", args=[org_a.id]))

        existing.refresh_from_db()
        assert existing.status == Risk.STATUS_CONFIRMED
        assert Risk.objects.filter(organisation=org_a).count() == before_count


@pytest.mark.django_db
class TestMaximumLengthAssetNameGenerationRegression:
    """
    M006-AUDIT-0003 H1's own required HTTP/browser regression: this closes
    the actual customer-facing dead end PID §18 item 7 requires (a
    `django.db.utils.DataError` 500 at "Find candidate risks", pre-
    correction), not merely the underlying `_build_title` function in
    isolation (see `risk_register/tests/test_scenario_engine.py` for the
    exhaustive mechanical proofs of that function).

    Exercises the REAL customer-facing views end to end - the real
    `KeyAssetForm` submission (`key_assets:create`, which sets a manually-
    added asset straight to `STATUS_CONFIRMED` - see
    `key_assets.views.key_asset_create`), then the real "Find candidate
    risks" POST (`risk_register:generate`) - not
    `instantiate_risks_for_organisation`/`generate_draft_risks` called
    directly. A plain Django `Client`-based HTTP test is sufficient to
    prove this flow: the assertions needed (normal redirect/success, no
    500, the candidate risk visible on the resulting page) do not require
    real browser rendering/CSS the way the H2 narrow-viewport regressions
    do, so no Playwright/real-browser dependency is introduced here.
    """

    def test_maximum_length_asset_name_through_the_real_form_produces_a_visible_candidate_risk(
        self, client_a, org_a
    ):
        max_length_name = "A" * MAX_ASSET_NAME_LENGTH

        create_response = client_a.post(
            reverse("key_assets:create", args=[org_a.id]),
            {
                "name": max_length_name,
                "category": "endpoint",
                "description": "",
                "criticality": "medium",
            },
        )
        assert create_response.status_code == 302
        assert KeyAsset.objects.filter(
            organisation=org_a, name=max_length_name, status=KeyAsset.STATUS_CONFIRMED
        ).exists()

        generate_response = client_a.post(reverse("risk_register:generate", args=[org_a.id]))
        assert generate_response.status_code == 302, (
            "the real 'Find candidate risks' submission must redirect normally, "
            "never a 500 (django.db.utils.DataError, pre-correction)"
        )
        assert generate_response.url == reverse("risk_register:list", args=[org_a.id])

        created_risks = Risk.objects.filter(
            organisation=org_a, status=Risk.STATUS_DRAFT_AI_SUGGESTED
        )
        assert created_risks.exists(), "the candidate risk must be genuinely created, not silently skipped"
        for risk in created_risks:
            assert len(risk.title) <= Risk._meta.get_field("title").max_length

        list_response = client_a.get(generate_response.url)
        assert list_response.status_code == 200
        content = list_response.content.decode()
        # the candidate is genuinely visible on the resulting page - not
        # merely persisted in the database
        for risk in created_risks:
            assert risk.title in content


@pytest.mark.django_db
class TestRiskListView:
    def test_lists_risks_grouped_by_status(self, client_a, org_a):
        Risk.objects.create(
            organisation=org_a, title="Draft one", threat="t", vulnerability="v",
            impact=3, likelihood=3, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_AI,
        )
        Risk.objects.create(
            organisation=org_a, title="Confirmed one", threat="t", vulnerability="v",
            impact=2, likelihood=2, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_CONFIRMED, source=Risk.SOURCE_AI,
        )
        response = client_a.get(reverse("risk_register:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Draft one" in response.content
        assert b"Confirmed one" in response.content


@pytest.mark.django_db
class TestRiskDetailWording:
    """PID §19: 'AI suggested' vs 'Customer confirmed'; never 'verified',
    'certified', 'compliant' or 'audited' as a status label."""

    def test_draft_risk_shows_ai_suggested_wording(self, client_a, org_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Draft risk", threat="t", vulnerability="v",
            impact=3, likelihood=3, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_AI,
            grounding_refs=["profile.endpoint_management"], assumptions=["staff count unknown"],
        )
        response = client_a.get(reverse("risk_register:detail", args=[org_a.id, risk.id]))
        content = response.content.decode()
        assert "AI suggested" in content
        assert "profile.endpoint_management" in content
        assert "staff count unknown" in content
        lowered = content.lower()
        assert "verified" not in lowered
        assert "certified" not in lowered
        assert "compliant" not in lowered
        assert "audited" not in lowered

    def test_confirmed_risk_shows_customer_confirmed_wording(self, client_a, org_a, user_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Confirmed risk", threat="t", vulnerability="v",
            impact=3, likelihood=3, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_CONFIRMED, source=Risk.SOURCE_AI,
            confirmed_by=user_a,
        )
        from django.utils import timezone

        risk.confirmed_at = timezone.now()
        risk.save()
        response = client_a.get(reverse("risk_register:detail", args=[org_a.id, risk.id]))
        content = response.content.decode()
        assert "Customer confirmed" in content
        lowered = content.lower()
        assert "verified" not in lowered
        assert "certified" not in lowered
        assert "compliant" not in lowered
        assert "audited" not in lowered


@pytest.mark.django_db
class TestRiskEditView:
    def test_edit_updates_a_draft_risk(self, client_a, org_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Original title", threat="t", vulnerability="v",
            impact=2, likelihood=2, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_AI,
        )
        response = client_a.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            {
                "title": "Edited title",
                "threat": "edited threat",
                "vulnerability": "edited vulnerability",
                "impact": "5",
                "likelihood": "5",
                "rationale": "edited rationale",
                "proposed_treatment": "edited treatment",
            },
        )
        assert response.status_code == 302
        risk.refresh_from_db()
        assert risk.title == "Edited title"
        assert risk.impact == 5
        assert risk.likelihood == 5
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED

    def test_cannot_edit_a_confirmed_risk(self, client_a, org_a, user_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Confirmed title", threat="t", vulnerability="v",
            impact=2, likelihood=2, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_CONFIRMED, source=Risk.SOURCE_AI, confirmed_by=user_a,
        )
        response = client_a.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            {
                "title": "Hijacked title",
                "threat": "t", "vulnerability": "v",
                "impact": "5", "likelihood": "5",
                "rationale": "r", "proposed_treatment": "p",
            },
            follow=True,
        )
        risk.refresh_from_db()
        assert risk.title == "Confirmed title"


@pytest.mark.django_db
class TestRiskConfirmDismissViews:
    def _draft(self, org_a):
        return Risk.objects.create(
            organisation=org_a, title="Draft", threat="t", vulnerability="v",
            impact=3, likelihood=3, rationale="r", proposed_treatment="p",
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_AI,
        )

    def test_confirm_requires_post(self, client_a, org_a):
        risk = self._draft(org_a)
        response = client_a.get(reverse("risk_register:confirm", args=[org_a.id, risk.id]))
        assert response.status_code == 405

    def test_dismiss_requires_post(self, client_a, org_a):
        risk = self._draft(org_a)
        response = client_a.get(reverse("risk_register:dismiss", args=[org_a.id, risk.id]))
        assert response.status_code == 405

    def test_confirm_records_actor_and_timestamp_and_flips_status(self, client_a, org_a, user_a):
        risk = self._draft(org_a)
        response = client_a.post(reverse("risk_register:confirm", args=[org_a.id, risk.id]))
        assert response.status_code == 302
        risk.refresh_from_db()
        assert risk.status == Risk.STATUS_CONFIRMED
        assert risk.confirmed_by_id == user_a.id
        assert risk.confirmed_at is not None
        assert risk.dismissed_by_id is None
        assert risk.dismissed_at is None

    def test_dismiss_records_actor_and_timestamp_and_flips_status(self, client_a, org_a, user_a):
        risk = self._draft(org_a)
        response = client_a.post(reverse("risk_register:dismiss", args=[org_a.id, risk.id]))
        assert response.status_code == 302
        risk.refresh_from_db()
        assert risk.status == Risk.STATUS_DISMISSED
        assert risk.dismissed_by_id == user_a.id
        assert risk.dismissed_at is not None
        assert risk.confirmed_by_id is None

    def test_cannot_confirm_an_already_dismissed_risk(self, client_a, org_a, user_a):
        risk = self._draft(org_a)
        client_a.post(reverse("risk_register:dismiss", args=[org_a.id, risk.id]))
        client_a.post(reverse("risk_register:confirm", args=[org_a.id, risk.id]))
        risk.refresh_from_db()
        assert risk.status == Risk.STATUS_DISMISSED
