"""
Asset-specific protection/exposure assessment (PID.md M002 §0.5).

The most important test in this file is
TestSingleCanonicalAnswer.test_editing_from_either_page_is_the_identical_underlying_row -
the dispatch's explicit "non-negotiable correctness requirement": proving
the asset-detail page and the general Security Baseline page read/write
the *same* BaselineAnswer row (by primary key and updated_at), not two
pages that merely happen to show the same value.
"""
import pytest
from django.urls import reverse

from key_assets.models import KeyAsset
from security_baseline.catalogue import CATALOGUE
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _all_unknown_baseline_post():
    """
    A minimal valid POST to the *general* (full-catalogue) baseline page:
    every question explicitly answered 'unknown'. Deliberately duplicated
    from security_baseline/tests/test_http_ui.py's identical helper rather
    than imported across the app-test boundary - matching this dispatch's
    existing convention (key_assets/tests/conftest.py duplicates
    organisations' fixtures for the same reason).
    """
    data = {}
    for item in CATALOGUE:
        data[answer_field_name(item["key"])] = "unknown"
        data[note_field_name(item["key"])] = ""
    return data


@pytest.fixture
def endpoint_asset_a(db, org_a):
    return KeyAsset.objects.create(
        organisation=org_a,
        name="Finance laptop",
        category="endpoint",
        criticality="high",
        status=KeyAsset.STATUS_CONFIRMED,
    )


@pytest.mark.django_db
class TestAssetDetailViewRendersRelevantQuestions:
    def test_endpoint_asset_shows_only_endpoint_relevant_questions(
        self, client_a, org_a, endpoint_asset_a
    ):
        response = client_a.get(
            reverse("key_assets:detail", args=[org_a.id, endpoint_asset_a.id])
        )
        assert response.status_code == 200
        content = response.content.decode()

        for expected_key in ("device_encryption", "endpoint_protection", "patching"):
            assert f'name="{answer_field_name(expected_key)}"' in content

        # mfa_user_accounts is an identity/productivity-category question,
        # never relevant to an endpoint asset - must not be rendered here.
        assert f'name="{answer_field_name("mfa_user_accounts")}"' not in content

    def test_asset_with_no_relevant_questions_shows_empty_state_not_an_error(
        self, client_a, org_a
    ):
        other_asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Miscellaneous thing",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        response = client_a.get(reverse("key_assets:detail", args=[org_a.id, other_asset.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "no asset-specific protection checks" in content.lower()

    def test_link_to_general_security_baseline_page_remains_reachable(
        self, client_a, org_a, endpoint_asset_a
    ):
        response = client_a.get(
            reverse("key_assets:detail", args=[org_a.id, endpoint_asset_a.id])
        )
        content = response.content.decode()
        expected_url = reverse("security_baseline:baseline", args=[org_a.id])
        assert expected_url in content

    def test_asset_list_page_links_to_the_new_detail_page(
        self, client_a, org_a, endpoint_asset_a
    ):
        response = client_a.get(reverse("key_assets:list", args=[org_a.id]))
        content = response.content.decode()
        assert reverse("key_assets:detail", args=[org_a.id, endpoint_asset_a.id]) in content


@pytest.mark.django_db
class TestSingleCanonicalAnswer:
    """
    PID §0.5's non-negotiable rule, proved directly: not just "both pages
    show *a* value" but that the two pages read/write the *identical*
    underlying BaselineAnswer row (same primary key, updated_at advances
    on the second write) - ruling out a coincidental duplicate with the
    same value.
    """

    def test_editing_from_either_page_is_the_identical_underlying_row(
        self, client_a, org_a, endpoint_asset_a
    ):
        detail_url = reverse("key_assets:detail", args=[org_a.id, endpoint_asset_a.id])
        baseline_url = reverse("security_baseline:baseline", args=[org_a.id])

        # --- Step 1: answer from the ASSET-DETAIL page -----------------
        asset_page_note = "Set from the asset-detail page - proof-note-A."
        post_data = {}
        for key in ("device_encryption", "endpoint_protection", "patching"):
            post_data[answer_field_name(key)] = "unknown"
            post_data[note_field_name(key)] = ""
        post_data[answer_field_name("device_encryption")] = "no"
        post_data[note_field_name("device_encryption")] = asset_page_note

        response = client_a.post(detail_url, post_data)
        assert response.status_code == 302

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        answer = BaselineAnswer.objects.get(
            assessment=assessment, question_key="device_encryption"
        )
        first_pk = answer.pk
        first_updated_at = answer.updated_at
        assert answer.answer == "no"
        assert answer.note == asset_page_note
        # Exactly one row for this question - no asset-local duplicate.
        assert (
            BaselineAnswer.objects.filter(
                assessment=assessment, question_key="device_encryption"
            ).count()
            == 1
        )

        # --- Step 2: the GENERAL baseline page shows that exact answer --
        response = client_a.get(baseline_url)
        content = response.content.decode()
        assert asset_page_note in content

        # --- Step 3: answer from the GENERAL baseline page --------------
        baseline_page_note = "Updated from the general baseline page - proof-note-B."
        full_post = _all_unknown_baseline_post()
        full_post[answer_field_name("device_encryption")] = "yes"
        full_post[note_field_name("device_encryption")] = baseline_page_note
        response = client_a.post(baseline_url, full_post)
        assert response.status_code == 302

        answer.refresh_from_db()
        second_pk = answer.pk
        second_updated_at = answer.updated_at

        # The identical row (same primary key), mutated in place, not a
        # second coincidentally-matching row.
        assert second_pk == first_pk
        assert second_updated_at > first_updated_at
        assert answer.answer == "yes"
        assert answer.note == baseline_page_note
        assert (
            BaselineAnswer.objects.filter(
                assessment=assessment, question_key="device_encryption"
            ).count()
            == 1
        )

        # --- Step 4: the ASSET-DETAIL page shows that updated answer ----
        response = client_a.get(detail_url)
        content = response.content.decode()
        assert baseline_page_note in content
        assert asset_page_note not in content


@pytest.mark.django_db
class TestAssetDetailRisksLink:
    def test_shows_empty_state_when_no_risks_recorded_against_asset(
        self, client_a, org_a, endpoint_asset_a
    ):
        response = client_a.get(
            reverse("key_assets:detail", args=[org_a.id, endpoint_asset_a.id])
        )
        content = response.content.decode()
        assert "no risks recorded" in content.lower()

    def test_shows_and_links_a_risk_associated_with_this_asset(
        self, client_a, org_a, endpoint_asset_a
    ):
        from risk_register.models import Risk

        risk = Risk.objects.create(
            organisation=org_a,
            key_asset=endpoint_asset_a,
            title="Unencrypted finance laptop",
            exposure="Portable device.",
            threat="Loss or theft",
            threat_event="Loss or theft",
            vulnerability="No full-disk encryption",
            consequence="Confidential information disclosure",
            scenario_id="endpoint_device_encryption_loss_theft",
            impact=4,
            likelihood=3,
            rationale="Baseline shows device_encryption = no.",
            proposed_treatment="Enable BitLocker/FileVault.",
            grounding_refs=["baseline.device_encryption", f"asset:{endpoint_asset_a.id}"],
            assumptions=[],
            source=Risk.SOURCE_AI,
            status=Risk.STATUS_DRAFT_AI_SUGGESTED,
        )
        response = client_a.get(
            reverse("key_assets:detail", args=[org_a.id, endpoint_asset_a.id])
        )
        content = response.content.decode()
        assert risk.title in content
        assert reverse("risk_register:detail", args=[org_a.id, risk.id]) in content

    def test_risk_register_detail_page_links_back_to_the_asset(
        self, client_a, org_a, endpoint_asset_a
    ):
        """
        The paired half of this dispatch's risk_register/templates/detail.html
        fix: a risk with key_asset set must show and link the asset/context
        reference block (previously dead - it referenced the retired
        Risk.asset_reference field, so this block silently never rendered).
        """
        from risk_register.models import Risk

        risk = Risk.objects.create(
            organisation=org_a,
            key_asset=endpoint_asset_a,
            title="Unencrypted finance laptop",
            exposure="Portable device.",
            threat="Loss or theft",
            threat_event="Loss or theft",
            vulnerability="No full-disk encryption",
            consequence="Confidential information disclosure",
            scenario_id="endpoint_device_encryption_loss_theft",
            impact=4,
            likelihood=3,
            rationale="Baseline shows device_encryption = no.",
            proposed_treatment="Enable BitLocker/FileVault.",
            grounding_refs=["baseline.device_encryption", f"asset:{endpoint_asset_a.id}"],
            assumptions=[],
            source=Risk.SOURCE_AI,
            status=Risk.STATUS_DRAFT_AI_SUGGESTED,
        )
        response = client_a.get(reverse("risk_register:detail", args=[org_a.id, risk.id]))
        content = response.content.decode()
        assert "Asset / context reference" in content
        assert endpoint_asset_a.name in content
        assert reverse("key_assets:detail", args=[org_a.id, endpoint_asset_a.id]) in content
