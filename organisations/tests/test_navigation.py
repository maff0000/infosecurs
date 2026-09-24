"""
Mechanical tests for the primary organisation-scoped navigation added to
`templates/base.html` (M006 PID §5, §22 "navigation/active organisation").

Complements `core/tests/test_active_nav.py` (which tests the mapping
function in isolation): these tests prove the mapping is actually wired
into a real rendered page - the seven links are present, the current
section is marked `aria-current="page"`, the nav is absent where PID §5
says it must be, and every one of the seven destinations is genuinely
reachable for a member (PID §18.19 "navigate the whole journey using
product navigation, not crafted URLs" - this proves the URLs the nav
itself points at are each live, even though the full customer-journey
walk-through is done as this dispatch's own manual sanity check, not
re-run test-by-test here).
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestPrimaryNavigationPresence:
    def test_all_seven_destinations_are_linked_from_the_overview_page(self, client_a, org_a):
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        content = response.content.decode()
        for url_name in (
            "organisations:detail",
            "security_state:list",
            "evidence:list",
            "policy:detail",
            "questionnaire:list",
            "activity:list",
            "organisations:organisation_hub",
        ):
            assert reverse(url_name, args=[org_a.id]) in content

    def test_nav_is_absent_on_the_pre_organisation_selection_page(self, client_a):
        response = client_a.get(reverse("organisations:list"))
        content = response.content.decode()
        assert "app-header__nav-primary" not in content


@pytest.mark.django_db
class TestActiveNavigationMarking:
    def test_overview_page_marks_overview_active(self, client_a, org_a):
        response = client_a.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.context["active_nav"] == "overview"
        assert response.content.decode().count('aria-current="page"') == 1

    def test_security_state_page_marks_security_active(self, client_a, org_a):
        response = client_a.get(reverse("security_state:list", args=[org_a.id]))
        assert response.context["active_nav"] == "security"
        assert response.content.decode().count('aria-current="page"') == 1

    def test_organisation_hub_page_marks_organisation_active(self, client_a, org_a):
        response = client_a.get(reverse("organisations:organisation_hub", args=[org_a.id]))
        assert response.context["active_nav"] == "organisation"
        assert response.content.decode().count('aria-current="page"') == 1


@pytest.mark.django_db
class TestPrimaryNavigationDestinationsAreReachable:
    @pytest.mark.parametrize(
        "url_name",
        [
            "organisations:detail",
            "security_state:list",
            "evidence:list",
            "policy:detail",
            "questionnaire:list",
            "activity:list",
            "organisations:organisation_hub",
        ],
    )
    def test_destination_returns_200_for_a_member_with_no_data_yet(
        self, client_a, org_a, url_name
    ):
        response = client_a.get(reverse(url_name, args=[org_a.id]))
        assert response.status_code == 200
