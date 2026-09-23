import pytest
from django.urls import reverse

from organisations.models import OrganisationProfile

from key_assets.models import KeyAsset

VALID_ASSET_POST = {
    "name": "Payroll system",
    "category": "business_application",
    "criticality": "high",
    "description": "Processes monthly payroll.",
}


@pytest.mark.django_db
class TestKeyAssetListView:
    def test_renders_without_profile(self, client_a, org_a):
        response = client_a.get(reverse("key_assets:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Key assets" in response.content

    def test_deterministic_suggestions_appear_on_list_page(self, client_a, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name=org_a.name,
            productivity_platform="microsoft_365",
        )
        response = client_a.get(reverse("key_assets:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Microsoft 365" in content
        assert "Suggested" in content

    def test_list_view_is_idempotent_for_suggestion_generation(self, client_a, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name=org_a.name,
            productivity_platform="microsoft_365",
        )
        client_a.get(reverse("key_assets:list", args=[org_a.id]))
        client_a.get(reverse("key_assets:list", args=[org_a.id]))
        client_a.get(reverse("key_assets:list", args=[org_a.id]))
        assert KeyAsset.objects.filter(organisation=org_a).count() == 1

    def test_confirmed_and_dismissed_sections_show_correct_assets(self, client_a, org_a):
        KeyAsset.objects.create(
            organisation=org_a,
            name="Confirmed one",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        KeyAsset.objects.create(
            organisation=org_a,
            name="Dismissed one",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_DISMISSED,
        )
        response = client_a.get(reverse("key_assets:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Confirmed one" in content
        assert "Dismissed one" in content

    def test_requires_login(self, client, org_a):
        response = client.get(reverse("key_assets:list", args=[org_a.id]))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


@pytest.mark.django_db
class TestKeyAssetCreateView:
    def test_get_renders_form(self, client_a, org_a):
        response = client_a.get(reverse("key_assets:create", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="name"' in content
        assert 'name="category"' in content
        assert 'name="criticality"' in content
        assert "csrfmiddlewaretoken" in content

    def test_valid_post_creates_confirmed_manual_asset(self, client_a, org_a):
        response = client_a.post(
            reverse("key_assets:create", args=[org_a.id]), VALID_ASSET_POST
        )
        assert response.status_code == 302
        asset = KeyAsset.objects.get(organisation=org_a)
        assert asset.name == "Payroll system"
        assert asset.status == KeyAsset.STATUS_CONFIRMED
        assert asset.suggestion_key == ""

    def test_invalid_post_does_not_save_and_shows_error(self, client_a, org_a):
        response = client_a.post(
            reverse("key_assets:create", args=[org_a.id]),
            {**VALID_ASSET_POST, "name": ""},
        )
        assert response.status_code == 200
        assert not KeyAsset.objects.filter(organisation=org_a).exists()
        content = response.content.decode()
        assert "cannot be empty" in content.lower() or "required" in content.lower()

    def test_invalid_category_rejected(self, client_a, org_a):
        response = client_a.post(
            reverse("key_assets:create", args=[org_a.id]),
            {**VALID_ASSET_POST, "category": "not_a_real_category"},
        )
        assert response.status_code == 200
        assert not KeyAsset.objects.filter(organisation=org_a).exists()


@pytest.mark.django_db
class TestKeyAssetEditView:
    def test_edit_updates_fields_without_changing_status(self, client_a, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Old name",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_SUGGESTED,
        )
        response = client_a.post(
            reverse("key_assets:edit", args=[org_a.id, asset.id]),
            {**VALID_ASSET_POST, "name": "New name"},
        )
        assert response.status_code == 302
        asset.refresh_from_db()
        assert asset.name == "New name"
        # Editing a suggestion's fields must not silently confirm it.
        assert asset.status == KeyAsset.STATUS_SUGGESTED


@pytest.mark.django_db
class TestKeyAssetConfirmDismissViews:
    def test_confirm_moves_suggested_to_confirmed(self, client_a, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Suggested asset",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_SUGGESTED,
        )
        response = client_a.post(reverse("key_assets:confirm", args=[org_a.id, asset.id]))
        assert response.status_code == 302
        asset.refresh_from_db()
        assert asset.status == KeyAsset.STATUS_CONFIRMED

    def test_dismiss_moves_suggested_to_dismissed(self, client_a, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Suggested asset",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_SUGGESTED,
        )
        response = client_a.post(reverse("key_assets:dismiss", args=[org_a.id, asset.id]))
        assert response.status_code == 302
        asset.refresh_from_db()
        assert asset.status == KeyAsset.STATUS_DISMISSED

    def test_confirm_rejects_get(self, client_a, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a, name="A", category="other", criticality="low"
        )
        response = client_a.get(reverse("key_assets:confirm", args=[org_a.id, asset.id]))
        assert response.status_code == 405
        asset.refresh_from_db()
        assert asset.status == KeyAsset.STATUS_SUGGESTED

    def test_dismiss_rejects_get(self, client_a, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a, name="A", category="other", criticality="low"
        )
        response = client_a.get(reverse("key_assets:dismiss", args=[org_a.id, asset.id]))
        assert response.status_code == 405
        asset.refresh_from_db()
        assert asset.status == KeyAsset.STATUS_SUGGESTED
