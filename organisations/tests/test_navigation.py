"""
Mechanical tests originally written (M006 PID §5, §22 "navigation/active
organisation") for the primary organisation-scoped navigation this file's
own tests were named after in `templates/base.html`.

M007-WI6 stale-assumption sweep note (2026-09): `templates/base.html`'s own
`{% if organisation %}`-gated `<nav class="app-header__nav-primary">` block
is no longer reachable for ANY currently-registered route. Every
organisation-scoped template (`organisations/templates/organisations/
detail.html` included) now `{% extends "application_shell.html" %}` (M007-
WI2/WI5) - a standalone template that does not itself extend `base.html` -
so `organisation` is never in a `base.html`-rendered context any more;
only the pre-organisation-selection pages (login, `organisations:list`/
`:create`) still extend `base.html`, and none of them ever has `organisation`
in context either. `core.context_processors.active_nav`'s mapping function
itself is untouched and still computes the same values (see
`core/tests/test_active_nav.py`), but nothing renders them into
`base.html`'s markup any more.

The tests below still pass, and are still a genuine, valuable proof - just
of a DIFFERENT rendering than their own original docstrings claimed: the
seven destinations they check are now linked from the WI2/WI5 sidebar
(`entitlements.navigation.build_navigation_tree`, rendered by
`application_shell.html`), and the single `aria-current="page"` they count
is that sidebar's own active-item marking (`entitlements/tests/
test_navigation.py`'s own subject), not `base.html`'s. This is a
documentation-only correction (no assertion below was touched) - see
`docs/evidence/M007-SESSION-ENTITLEMENTS.md`'s Part D table for the full
classification. `core/tests/test_application_shell.py::
TestShellIsRenderedOnceNotDuplicatedPerPage`/`TestSidebarContentMatchesTierThroughRealHtml`
are the current, WI2/WI5-native equivalent of this file's own intent - this
file is kept (not deleted, PID's "never weaken/delete existing coverage")
because it still independently proves the same seven-destination-reachable
property this file's original PID §5/§22 authority names.
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
