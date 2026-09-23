import uuid

import pytest
from django.urls import reverse

from key_assets.models import KeyAsset


@pytest.mark.django_db
class TestKeyAssetTenantIsolation:
    """
    Release-blocking (PID.md M002 §16, §21 "Assets" -> tenant isolation).
    Two synthetic organisations, two users each a member of exactly one,
    proving organisation A cannot read, edit, confirm or dismiss
    organisation B's key assets.
    """

    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_own_organisations_assets(self, client_a, org_a):
        KeyAsset.objects.create(
            organisation=org_a, name="Org A test asset", category="other", criticality="low"
        )
        response = client_a.get(reverse("key_assets:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Org A test asset" in response.content

    # --- cross-tenant read negative ---------------------------------------
    def test_member_cannot_read_other_organisations_asset_list(self, client_b, org_a):
        KeyAsset.objects.create(
            organisation=org_a, name="Org A secret asset", category="other", criticality="low"
        )
        response = client_b.get(reverse("key_assets:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_asset_edit_form(self, client_b, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a, name="Org A test asset", category="other", criticality="low"
        )
        response = client_b.get(reverse("key_assets:edit", args=[org_a.id, asset.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_asset_detail_page(self, client_b, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a, name="Org A secret asset", category="endpoint", criticality="low"
        )
        response = client_b.get(reverse("key_assets:detail", args=[org_a.id, asset.id]))
        assert response.status_code == 404

    def test_member_cannot_post_protection_checks_to_other_organisations_asset(
        self, client_b, org_a
    ):
        """
        Critical negative case for PID §0.5's asset-specific protection
        checks: org B must not be able to write a BaselineAnswer onto org
        A's baseline via org A's asset-detail URL.
        """
        from security_baseline.forms import answer_field_name, note_field_name
        from security_baseline.models import BaselineAnswer

        asset = KeyAsset.objects.create(
            organisation=org_a, name="Org A endpoint", category="endpoint", criticality="low"
        )
        response = client_b.post(
            reverse("key_assets:detail", args=[org_a.id, asset.id]),
            {
                answer_field_name("device_encryption"): "no",
                note_field_name("device_encryption"): "Hijacked by user_b",
                answer_field_name("endpoint_protection"): "unknown",
                note_field_name("endpoint_protection"): "",
                answer_field_name("patching"): "unknown",
                note_field_name("patching"): "",
            },
        )
        assert response.status_code == 404
        assert not BaselineAnswer.objects.filter(
            question_key="device_encryption", note="Hijacked by user_b"
        ).exists()

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_edit_other_organisations_asset(self, client_b, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Original name",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        response = client_b.post(
            reverse("key_assets:edit", args=[org_a.id, asset.id]),
            {"name": "Hijacked by user_b", "category": "other", "criticality": "critical"},
        )
        assert response.status_code == 404
        asset.refresh_from_db()
        assert asset.name == "Original name"
        assert asset.criticality == "low"

    def test_member_cannot_confirm_other_organisations_asset(self, client_b, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Org A suggestion",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_SUGGESTED,
        )
        response = client_b.post(reverse("key_assets:confirm", args=[org_a.id, asset.id]))
        assert response.status_code == 404
        asset.refresh_from_db()
        assert asset.status == KeyAsset.STATUS_SUGGESTED

    def test_member_cannot_dismiss_other_organisations_asset(self, client_b, org_a):
        asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Org A suggestion",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_SUGGESTED,
        )
        response = client_b.post(reverse("key_assets:dismiss", args=[org_a.id, asset.id]))
        assert response.status_code == 404
        asset.refresh_from_db()
        assert asset.status == KeyAsset.STATUS_SUGGESTED

    def test_member_cannot_create_asset_on_other_organisation(self, client_b, org_a):
        response = client_b.post(
            reverse("key_assets:create", args=[org_a.id]),
            {"name": "Hijacked asset", "category": "other", "criticality": "low"},
        )
        assert response.status_code == 404
        assert not KeyAsset.objects.filter(organisation=org_a).exists()

    # --- URL / cross-organisation asset-id manipulation ---------------------
    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("key_assets:list", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_asset_id_from_a_different_organisation_is_404_even_for_a_member(
        self, client_a, org_a, org_b
    ):
        """
        user_a is a member of org_a. An asset that belongs to org_b must not
        be reachable through org_a's URL prefix, even though user_a is
        authenticated and a genuine member of *some* organisation.
        """
        other_org_asset = KeyAsset.objects.create(
            organisation=org_b, name="Org B test asset", category="other", criticality="low"
        )
        response = client_a.get(reverse("key_assets:edit", args=[org_a.id, other_org_asset.id]))
        assert response.status_code == 404

    def test_asset_detail_id_from_a_different_organisation_is_404_even_for_a_member(
        self, client_a, org_a, org_b
    ):
        other_org_asset = KeyAsset.objects.create(
            organisation=org_b, name="Org B test asset", category="endpoint", criticality="low"
        )
        response = client_a.get(
            reverse("key_assets:detail", args=[org_a.id, other_org_asset.id])
        )
        assert response.status_code == 404

    def test_member_does_not_see_other_organisations_assets_mixed_into_their_own_list(
        self, client_a, org_a, org_b
    ):
        KeyAsset.objects.create(
            organisation=org_a, name="Org A own asset", category="other", criticality="low"
        )
        KeyAsset.objects.create(
            organisation=org_b, name="Org B test asset", category="other", criticality="low"
        )
        response = client_a.get(reverse("key_assets:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Org A own asset" in content
        assert "Org B test asset" not in content
