import pytest

from organisations.models import OrganisationProfile


@pytest.mark.django_db
def test_profile_save_and_reload_preserves_all_fields(org_a):
    profile = OrganisationProfile.objects.create(
        organisation=org_a,
        legal_trading_name="Org A Synthetic Ltd",
        description="A synthetic test organisation.",
        staff_count=27,
        working_model="hybrid",
        endpoint_management="both",
        productivity_platform="microsoft_365",
        primary_cloud_provider="azure",
        develops_hosts_own_software="yes",
        handles_personal_data="yes",
        handles_confidential_business_data="yes",
        handles_payment_card_data="no",
        handles_special_category_data="unknown",
        receives_security_questionnaires="yes",
        cyber_essentials_status="in_progress",
        iso27001_status="not_certified",
        commercial_security_driver="A key customer requires evidence of security controls.",
    )
    profile_id = profile.pk

    reloaded = OrganisationProfile.objects.get(pk=profile_id)

    assert reloaded.legal_trading_name == "Org A Synthetic Ltd"
    assert reloaded.description == "A synthetic test organisation."
    assert reloaded.staff_count == 27
    assert reloaded.working_model == "hybrid"
    assert reloaded.endpoint_management == "both"
    assert reloaded.productivity_platform == "microsoft_365"
    assert reloaded.primary_cloud_provider == "azure"
    assert reloaded.develops_hosts_own_software == "yes"
    assert reloaded.handles_personal_data == "yes"
    assert reloaded.handles_confidential_business_data == "yes"
    assert reloaded.handles_payment_card_data == "no"
    assert reloaded.handles_special_category_data == "unknown"
    assert reloaded.receives_security_questionnaires == "yes"
    assert reloaded.cyber_essentials_status == "in_progress"
    assert reloaded.iso27001_status == "not_certified"
    assert (
        reloaded.commercial_security_driver
        == "A key customer requires evidence of security controls."
    )


@pytest.mark.django_db
def test_profile_edit_and_reload_reflects_new_values_not_stale_ones(org_a):
    profile = OrganisationProfile.objects.create(
        organisation=org_a,
        legal_trading_name="Org A Synthetic Ltd",
        cyber_essentials_status="not_certified",
    )
    profile.cyber_essentials_status = "certified"
    profile.save()

    reloaded = OrganisationProfile.objects.get(pk=profile.pk)
    assert reloaded.cyber_essentials_status == "certified"
