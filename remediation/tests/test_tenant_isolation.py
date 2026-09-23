"""
Release-blocking tenant isolation tests for the remediation domain,
mirroring risk_register/tests/test_tenant_isolation.py and
key_assets/tests/test_tenant_isolation.py exactly: two synthetic
organisations, two users each a member of exactly one, proving
organisation A cannot read, list, edit or transition organisation B's
remediation actions, and cannot create an action from organisation B's
risk via a manipulated URL.
"""
import uuid

import pytest
from django.urls import reverse

from remediation.models import RemediationAction


def _action(org, user, **overrides):
    defaults = dict(organisation=org, title="Org action", created_by=user)
    defaults.update(overrides)
    return RemediationAction.objects.create(**defaults)


@pytest.mark.django_db
class TestRemediationActionTenantIsolation:
    # --- same-tenant positive -------------------------------------------
    def test_member_can_read_own_organisations_action_list(self, client_a, org_a, user_a):
        _action(org_a, user_a, title="Org A test action")
        response = client_a.get(reverse("remediation:list", args=[org_a.id]))
        assert response.status_code == 200
        assert b"Org A test action" in response.content

    # --- cross-tenant read negative ---------------------------------------
    def test_member_cannot_read_other_organisations_action_list(self, client_b, org_a, user_a):
        _action(org_a, user_a, title="Org A secret action")
        response = client_b.get(reverse("remediation:list", args=[org_a.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_action_detail(self, client_b, org_a, user_a):
        action = _action(org_a, user_a)
        response = client_b.get(reverse("remediation:detail", args=[org_a.id, action.id]))
        assert response.status_code == 404

    def test_member_cannot_read_other_organisations_action_edit_form(self, client_b, org_a, user_a):
        action = _action(org_a, user_a)
        response = client_b.get(reverse("remediation:edit", args=[org_a.id, action.id]))
        assert response.status_code == 404

    def test_member_cannot_reach_create_from_risk_for_other_organisation(
        self, client_b, org_a, risk_a
    ):
        response = client_b.get(
            reverse("remediation:create_from_risk", args=[org_a.id, risk_a.id])
        )
        assert response.status_code == 404

    # --- cross-tenant write negative ---------------------------------------
    def test_member_cannot_edit_other_organisations_action(self, client_b, org_a, user_a):
        action = _action(org_a, user_a, title="Original title")
        response = client_b.post(
            reverse("remediation:edit", args=[org_a.id, action.id]),
            {
                "title": "Hijacked by user_b",
                "description": "",
                "priority": "medium",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 404
        action.refresh_from_db()
        assert action.title == "Original title"

    def test_member_cannot_start_other_organisations_action(self, client_b, org_a, user_a):
        action = _action(org_a, user_a)
        response = client_b.post(reverse("remediation:start", args=[org_a.id, action.id]))
        assert response.status_code == 404
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_OPEN

    def test_member_cannot_complete_other_organisations_action(self, client_b, org_a, user_a):
        action = _action(org_a, user_a)
        response = client_b.post(reverse("remediation:complete", args=[org_a.id, action.id]))
        assert response.status_code == 404
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_OPEN
        assert action.completed_by_id is None

    def test_member_cannot_accept_other_organisations_action(self, client_b, org_a, user_a):
        action = _action(org_a, user_a)
        response = client_b.post(reverse("remediation:accept", args=[org_a.id, action.id]))
        assert response.status_code == 404
        action.refresh_from_db()
        assert action.status == RemediationAction.STATUS_OPEN
        assert action.completed_by_id is None

    def test_member_cannot_create_action_from_other_organisations_risk(
        self, client_b, org_a, risk_a
    ):
        response = client_b.post(
            reverse("remediation:create_from_risk", args=[org_a.id, risk_a.id]),
            {
                "title": "Hijacked action",
                "description": "",
                "priority": "medium",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 404
        assert RemediationAction.objects.filter(organisation=org_a).count() == 0

    def test_member_cannot_create_action_directly_for_other_organisation(self, client_b, org_a):
        response = client_b.post(
            reverse("remediation:create", args=[org_a.id]),
            {
                "title": "Hijacked action",
                "description": "",
                "priority": "medium",
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
        )
        assert response.status_code == 404
        assert RemediationAction.objects.filter(organisation=org_a).count() == 0

    # --- URL / cross-organisation action-id manipulation --------------------
    def test_nonexistent_organisation_id_in_url_is_404(self, client_a):
        response = client_a.get(reverse("remediation:list", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_action_id_from_a_different_organisation_is_404_even_for_a_member(
        self, client_a, org_a, org_b, user_b
    ):
        """
        user_a is a member of org_a. An action that belongs to org_b must
        not be reachable through org_a's URL prefix, even though user_a is
        authenticated and a genuine member of *some* organisation.
        """
        other_org_action = _action(org_b, user_b, title="Org B test action")
        response = client_a.get(
            reverse("remediation:detail", args=[org_a.id, other_org_action.id])
        )
        assert response.status_code == 404

    def test_member_does_not_see_other_organisations_actions_mixed_into_their_own_list(
        self, client_a, org_a, org_b, user_a, user_b
    ):
        _action(org_a, user_a, title="Org A own action")
        _action(org_b, user_b, title="Org B test action")
        response = client_a.get(reverse("remediation:list", args=[org_a.id]))
        content = response.content.decode()
        assert "Org A own action" in content
        assert "Org B test action" not in content

    def test_action_form_never_offers_another_organisations_key_asset_or_user_in_dropdowns(
        self, client_a, org_a, org_b, confirmed_asset_a
    ):
        """
        Not just a "can't save it" check: the create form's own dropdown
        options must not even list another tenant's asset/user names,
        which would itself be a tenant-isolation leak.
        """
        from key_assets.models import KeyAsset

        other_asset = KeyAsset.objects.create(
            organisation=org_b,
            name="Org B secret asset name",
            category="endpoint",
            criticality="medium",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        response = client_a.get(reverse("remediation:create", args=[org_a.id]))
        content = response.content.decode()
        assert confirmed_asset_a.name in content
        assert other_asset.name not in content
