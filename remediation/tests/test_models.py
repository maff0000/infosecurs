import pytest

from remediation.models import RemediationAction


@pytest.mark.django_db
class TestRemediationActionModel:
    def test_defaults_to_open_and_medium_priority(self, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="Do the thing", created_by=user_a
        )
        assert action.status == RemediationAction.STATUS_OPEN
        assert action.priority == RemediationAction.PRIORITY_MEDIUM
        assert action.risk_id is None
        assert action.control_key == ""
        assert action.key_asset_id is None
        assert action.completed_by_id is None
        assert action.completed_at is None

    def test_is_closed_true_only_for_done_or_accepted(self, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="Do the thing", created_by=user_a
        )
        assert action.is_closed is False
        action.status = RemediationAction.STATUS_IN_PROGRESS
        assert action.is_closed is False
        action.status = RemediationAction.STATUS_DONE
        assert action.is_closed is True
        action.status = RemediationAction.STATUS_ACCEPTED
        assert action.is_closed is True

    def test_control_key_label_resolves_from_catalogue(self, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a,
            title="Do the thing",
            created_by=user_a,
            control_key="mfa_user_accounts",
        )
        assert "multi-factor" in action.control_key_label().lower() or "MFA" in action.control_key_label()

    def test_control_key_label_falls_back_to_raw_key_for_unknown_key(self, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a,
            title="Do the thing",
            created_by=user_a,
            control_key="not_a_real_key",
        )
        assert action.control_key_label() == "not_a_real_key"

    def test_control_key_label_empty_when_no_control_key(self, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="Do the thing", created_by=user_a
        )
        assert action.control_key_label() == ""

    def test_str_includes_title_organisation_and_status(self, org_a, user_a):
        action = RemediationAction.objects.create(
            organisation=org_a, title="Do the thing", created_by=user_a
        )
        text = str(action)
        assert "Do the thing" in text
        assert "open" in text
