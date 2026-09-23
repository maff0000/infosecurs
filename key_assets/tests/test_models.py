import pytest
from django.core.exceptions import ValidationError

from key_assets.models import KeyAsset


@pytest.mark.django_db
class TestKeyAssetDomain:
    def test_default_status_is_suggested(self, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Employee endpoints",
            category="endpoint",
            criticality="medium",
        )
        assert asset.status == KeyAsset.STATUS_SUGGESTED

    def test_manual_asset_can_be_created_confirmed(self, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Payroll system",
            category="business_application",
            criticality="high",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        assert asset.status == KeyAsset.STATUS_CONFIRMED

    def test_update_persists(self, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a, name="Laptop fleet", category="endpoint", criticality="low"
        )
        asset.criticality = "high"
        asset.status = KeyAsset.STATUS_CONFIRMED
        asset.save()

        reloaded = KeyAsset.objects.get(pk=asset.pk)
        assert reloaded.criticality == "high"
        assert reloaded.status == KeyAsset.STATUS_CONFIRMED

    def test_category_enum_rejects_unsupported_value(self, org_a):
        asset = KeyAsset(
            organisation=org_a,
            name="Something",
            category="on_the_moon",
            criticality="low",
        )
        with pytest.raises(ValidationError):
            asset.full_clean()

    def test_criticality_enum_rejects_unsupported_value(self, org_a):
        asset = KeyAsset(
            organisation=org_a,
            name="Something",
            category="other",
            criticality="apocalyptic",
        )
        with pytest.raises(ValidationError):
            asset.full_clean()

    def test_status_enum_rejects_unsupported_value(self, org_a):
        asset = KeyAsset(
            organisation=org_a,
            name="Something",
            category="other",
            criticality="low",
            status="half_confirmed",
        )
        with pytest.raises(ValidationError):
            asset.full_clean()

    def test_name_required(self, org_a):
        asset = KeyAsset(organisation=org_a, name="", category="other", criticality="low")
        with pytest.raises(ValidationError):
            asset.full_clean()

    def test_str_includes_name_and_organisation(self, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a, name="Backups", category="information", criticality="high"
        )
        text = str(asset)
        assert "Backups" in text
        assert org_a.name in text
