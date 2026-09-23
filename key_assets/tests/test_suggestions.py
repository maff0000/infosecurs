import pytest

from organisations.models import OrganisationProfile

from key_assets.models import KeyAsset
from key_assets.suggestions import ensure_starter_suggestions, starter_suggestion_specs


def _make_profile(org, **overrides):
    defaults = {"legal_trading_name": org.name}
    defaults.update(overrides)
    return OrganisationProfile.objects.create(organisation=org, **defaults)


@pytest.mark.django_db
class TestStarterSuggestionSpecs:
    """
    Pure-function tests against PID.md M002 §7.1's deterministic rules.
    No AI/LLM call is exercised anywhere - these are plain conditionals
    over OrganisationProfile fields.
    """

    def test_blank_profile_suggests_nothing(self, org_a):
        profile = _make_profile(org_a)
        assert starter_suggestion_specs(profile) == []

    def test_microsoft_365_suggests_identity_asset(self, org_a):
        profile = _make_profile(org_a, productivity_platform="microsoft_365")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "productivity_microsoft_365" in keys
        assert "productivity_google_workspace" not in keys

    def test_google_workspace_suggests_analogous_identity_asset(self, org_a):
        profile = _make_profile(org_a, productivity_platform="google_workspace")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "productivity_google_workspace" in keys
        assert "productivity_microsoft_365" not in keys

    def test_staff_count_above_zero_suggests_employee_endpoints(self, org_a):
        profile = _make_profile(org_a, staff_count=12)
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "employee_endpoints" in keys

    def test_staff_count_zero_does_not_suggest_endpoints(self, org_a):
        profile = _make_profile(org_a, staff_count=0)
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "employee_endpoints" not in keys

    def test_unset_staff_count_does_not_suggest_endpoints(self, org_a):
        profile = _make_profile(org_a)
        assert profile.staff_count is None
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "employee_endpoints" not in keys

    def test_known_cloud_provider_suggests_cloud_environment(self, org_a):
        profile = _make_profile(org_a, primary_cloud_provider="azure")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "primary_cloud_environment" in keys

    def test_cloud_provider_none_does_not_suggest_cloud_environment(self, org_a):
        profile = _make_profile(org_a, primary_cloud_provider="none")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "primary_cloud_environment" not in keys

    def test_cloud_provider_unknown_does_not_suggest_cloud_environment(self, org_a):
        profile = _make_profile(org_a, primary_cloud_provider="unknown")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "primary_cloud_environment" not in keys

    def test_develops_own_software_yes_suggests_hosted_application(self, org_a):
        profile = _make_profile(org_a, develops_hosts_own_software="yes")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "hosted_application" in keys

    def test_develops_own_software_unknown_does_not_suggest_hosted_application(self, org_a):
        profile = _make_profile(org_a, develops_hosts_own_software="unknown")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "hosted_application" not in keys

    def test_develops_own_software_no_does_not_suggest_hosted_application(self, org_a):
        profile = _make_profile(org_a, develops_hosts_own_software="no")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "hosted_application" not in keys

    @pytest.mark.parametrize(
        "field",
        [
            "handles_personal_data",
            "handles_confidential_business_data",
            "handles_special_category_data",
        ],
    )
    def test_sensitive_data_handling_suggests_information_asset(self, org_a, field):
        profile = _make_profile(org_a, **{field: "yes"})
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "sensitive_information" in keys

    def test_payment_card_data_alone_does_not_suggest_information_asset(self, org_a):
        # Deliberately not one of the PID.md §7.1 trigger fields.
        profile = _make_profile(org_a, handles_payment_card_data="yes")
        keys = {s["suggestion_key"] for s in starter_suggestion_specs(profile)}
        assert "sensitive_information" not in keys

    def test_fully_populated_profile_suggests_every_rule_once(self, org_a):
        profile = _make_profile(
            org_a,
            productivity_platform="microsoft_365",
            staff_count=25,
            primary_cloud_provider="aws",
            develops_hosts_own_software="yes",
            handles_personal_data="yes",
        )
        specs = starter_suggestion_specs(profile)
        keys = [s["suggestion_key"] for s in specs]
        assert len(keys) == len(set(keys)) == 5


@pytest.mark.django_db
class TestEnsureStarterSuggestions:
    def test_no_profile_creates_nothing(self, org_a):
        assert not hasattr(org_a, "profile")
        created = ensure_starter_suggestions(org_a)
        assert created == []
        assert KeyAsset.objects.filter(organisation=org_a).count() == 0

    def test_creates_expected_suggestions_as_suggested_not_confirmed(self, org_a):
        _make_profile(org_a, productivity_platform="microsoft_365", staff_count=10)

        created = ensure_starter_suggestions(org_a)

        assert len(created) == 2
        for asset in created:
            # The core M002 invariant under test: a freshly-generated
            # deterministic suggestion is SUGGESTED, never CONFIRMED
            # (PID.md M002 §2, §7.1, §21 "Assets").
            assert asset.status == KeyAsset.STATUS_SUGGESTED
            assert asset.status != KeyAsset.STATUS_CONFIRMED

        stored = KeyAsset.objects.filter(organisation=org_a)
        assert stored.count() == 2
        assert all(a.status == KeyAsset.STATUS_SUGGESTED for a in stored)

    def test_is_idempotent_across_repeated_calls(self, org_a):
        _make_profile(org_a, productivity_platform="microsoft_365")

        ensure_starter_suggestions(org_a)
        ensure_starter_suggestions(org_a)
        ensure_starter_suggestions(org_a)

        assert KeyAsset.objects.filter(organisation=org_a).count() == 1

    def test_does_not_recreate_a_confirmed_suggestion(self, org_a):
        _make_profile(org_a, productivity_platform="microsoft_365")
        ensure_starter_suggestions(org_a)
        asset = KeyAsset.objects.get(organisation=org_a)
        asset.status = KeyAsset.STATUS_CONFIRMED
        asset.save()

        ensure_starter_suggestions(org_a)

        assets = KeyAsset.objects.filter(organisation=org_a)
        assert assets.count() == 1
        assert assets.get().status == KeyAsset.STATUS_CONFIRMED

    def test_does_not_recreate_a_dismissed_suggestion(self, org_a):
        _make_profile(org_a, productivity_platform="microsoft_365")
        ensure_starter_suggestions(org_a)
        asset = KeyAsset.objects.get(organisation=org_a)
        asset.status = KeyAsset.STATUS_DISMISSED
        asset.save()

        ensure_starter_suggestions(org_a)

        assets = KeyAsset.objects.filter(organisation=org_a)
        assert assets.count() == 1
        assert assets.get().status == KeyAsset.STATUS_DISMISSED

    def test_manual_assets_do_not_block_deterministic_suggestions(self, org_a):
        """A manually-added asset has no suggestion_key, so it must never be
        mistaken for an already-suggested deterministic asset."""
        KeyAsset.objects.create(
            organisation=org_a,
            name="Something the customer typed in themselves",
            category="other",
            criticality="low",
            status=KeyAsset.STATUS_CONFIRMED,
        )
        _make_profile(org_a, productivity_platform="microsoft_365")

        ensure_starter_suggestions(org_a)

        assert KeyAsset.objects.filter(organisation=org_a).count() == 2
        assert KeyAsset.objects.filter(
            organisation=org_a, suggestion_key="productivity_microsoft_365"
        ).exists()
