import pytest
from django.urls import reverse

from organisations.models import AuditEvent, OrganisationProfile

VALID_PROFILE_POST = {
    "legal_trading_name": "Org A Synthetic Ltd",
    "description": "A synthetic test business.",
    "staff_count": "15",
    "working_model": "office",
    "endpoint_management": "company_managed",
    "productivity_platform": "microsoft_365",
    "primary_cloud_provider": "unknown",
    "develops_hosts_own_software": "no",
    "handles_personal_data": "yes",
    "handles_confidential_business_data": "yes",
    "handles_payment_card_data": "no",
    "handles_special_category_data": "no",
    "receives_security_questionnaires": "yes",
    "cyber_essentials_status": "in_progress",
    "iso27001_status": "not_certified",
    "commercial_security_driver": "A major customer requires Cyber Essentials.",
}


@pytest.mark.django_db
class TestOrganisationProfileHttpUi:
    def test_form_renders_with_expected_fields(self, client_a, org_a):
        response = client_a.get(reverse("organisations:profile", args=[org_a.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="legal_trading_name"' in content
        assert 'name="working_model"' in content
        assert 'name="handles_personal_data"' in content
        assert "csrfmiddlewaretoken" in content

    def test_invalid_submission_shows_visible_validation_and_does_not_save(
        self, client_a, org_a
    ):
        response = client_a.post(
            reverse("organisations:profile", args=[org_a.id]),
            {**VALID_PROFILE_POST, "legal_trading_name": "", "staff_count": "-5"},
        )
        assert response.status_code == 200  # re-renders the form, no redirect
        content = response.content.decode()
        assert "required" in content.lower() or "cannot be empty" in content.lower()
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_valid_submission_saves_and_redirects_with_success_message(
        self, client_a, org_a
    ):
        response = client_a.post(
            reverse("organisations:profile", args=[org_a.id]), VALID_PROFILE_POST
        )
        assert response.status_code == 302

        follow = client_a.get(response.url)
        content = follow.content.decode()
        assert "saved" in content.lower()

        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.legal_trading_name == "Org A Synthetic Ltd"
        assert profile.staff_count == 15

    def test_save_creates_exactly_one_audit_event_for_a_new_profile(self, client_a, org_a):
        client_a.post(reverse("organisations:profile", args=[org_a.id]), VALID_PROFILE_POST)
        events = AuditEvent.objects.filter(organisation=org_a)
        assert events.count() == 1
        assert events.first().action == AuditEvent.ACTION_PROFILE_CREATED

    def test_second_save_records_an_update_event(self, client_a, org_a):
        client_a.post(reverse("organisations:profile", args=[org_a.id]), VALID_PROFILE_POST)
        client_a.post(
            reverse("organisations:profile", args=[org_a.id]),
            {**VALID_PROFILE_POST, "staff_count": "20"},
        )
        events = AuditEvent.objects.filter(organisation=org_a).order_by("timestamp")
        assert events.count() == 2
        assert events.last().action == AuditEvent.ACTION_PROFILE_UPDATED

    def test_reload_after_save_shows_persisted_values_in_the_form(self, client_a, org_a):
        client_a.post(reverse("organisations:profile", args=[org_a.id]), VALID_PROFILE_POST)

        response = client_a.get(reverse("organisations:profile", args=[org_a.id]))
        content = response.content.decode()
        assert "Org A Synthetic Ltd" in content
        assert 'value="15"' in content

    def test_enum_field_rejecting_bad_value_is_visible_to_the_user(self, client_a, org_a):
        response = client_a.post(
            reverse("organisations:profile", args=[org_a.id]),
            {**VALID_PROFILE_POST, "working_model": "on_the_moon"},
        )
        assert response.status_code == 200
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()


@pytest.mark.django_db
class TestOrganisationCreateHttpUi:
    def test_create_organisation_form_renders(self, client_a):
        response = client_a.get(reverse("organisations:create"))
        assert response.status_code == 200
        assert 'name="name"' in response.content.decode()

    def test_create_organisation_and_it_appears_in_list(self, client_a):
        response = client_a.post(reverse("organisations:create"), {"name": "New Synthetic Co"})
        assert response.status_code == 302

        response = client_a.get(reverse("organisations:list"))
        assert b"New Synthetic Co" in response.content

    def test_create_organisation_with_blank_name_shows_validation(self, client_a):
        response = client_a.post(reverse("organisations:create"), {"name": "   "})
        assert response.status_code == 200
        # Django's CharField strips whitespace before validation, so a
        # whitespace-only submission is caught by the required check
        # itself; clean_name()'s explicit message covers a value that is
        # non-empty-but-blank in a way strip() wouldn't already catch.
        assert "field is required" in response.content.decode().lower()

    def test_create_organisation_atomically_creates_account_holder_person_and_role_events(
        self, client_a, user_a
    ):
        """
        PID §6-7 (M004-1d-closeout): organisation_create must atomically
        create the Account Holder's governance person + default role
        assignments alongside the Organisation/OrganisationMembership rows
        - proven here end-to-end through the real view, plus PID §22's
        activity events those governance.services calls emit.
        """
        from activity.models import ActivityEvent

        from governance.models import GovernanceRoleAssignment, OrganisationPerson

        from organisations.models import Organisation

        response = client_a.post(reverse("organisations:create"), {"name": "New Synthetic Co"})
        assert response.status_code == 302

        organisation = Organisation.objects.get(name="New Synthetic Co")

        person = OrganisationPerson.objects.get(organisation=organisation, user=user_a)
        assert (
            GovernanceRoleAssignment.objects.filter(organisation=organisation, person=person).count()
            == 3
        )

        assert (
            ActivityEvent.objects.filter(
                organisation=organisation,
                event_type=ActivityEvent.EVENT_ORGANISATION_PERSON_CREATED,
            ).count()
            == 1
        )
        role_events = ActivityEvent.objects.filter(
            organisation=organisation, event_type=ActivityEvent.EVENT_GOVERNANCE_ROLE_CHANGED
        )
        assert role_events.count() == 3
        for event in role_events:
            assert event.metadata["previous_person_id"] is None
            assert event.metadata["new_person_id"] == str(person.id)
