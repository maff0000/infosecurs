"""
Mechanical accessibility regression (M006 PID §9/§22): "every rendered
form input has an associated label" across a representative sweep of the
product's real forms, using `core.tests.html_a11y`'s stdlib-only checker
(chosen over adding BeautifulSoup/lxml as a new dependency - see that
module's docstring).

Every page below is reachable from primary navigation or its owning
list/detail page and carries at least one real form. This does not
replace a real-browser accessibility pass; it is the deterministic,
CI-safe regression net for the one property PID §22 explicitly names as
mechanically checkable.
"""
import pytest
from django.urls import reverse

from core.tests.html_a11y import find_unlabelled_form_controls
from governance.models import OrganisationPerson


def _assert_fully_labelled(response):
    assert response.status_code == 200
    unlabelled = find_unlabelled_form_controls(response.content.decode())
    assert not unlabelled, f"unlabelled form control(s): {unlabelled}"


@pytest.mark.django_db
def test_login_page_forms_are_labelled(client):
    # django_db: allauth's LoginView reads django.contrib.sites'
    # Site.objects.get_current(), a real DB read even on a plain GET.
    _assert_fully_labelled(client.get(reverse("login")))


@pytest.mark.django_db
class TestOrganisationScopedFormsAreLabelled:
    def test_organisation_profile_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("organisations:profile", args=[org_a.id])))

    def test_organisation_create_form(self, client_a):
        _assert_fully_labelled(client_a.get(reverse("organisations:create")))

    def test_security_baseline_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("security_baseline:baseline", args=[org_a.id])))

    def test_key_assets_create_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("key_assets:create", args=[org_a.id])))

    def test_evidence_upload_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("evidence:upload", args=[org_a.id])))

    def test_evidence_add_reference_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("evidence:add_reference", args=[org_a.id])))

    def test_workplace_create_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("workplace:create", args=[org_a.id])))

    def test_workplace_onboarding_start_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("workplace:onboarding_start", args=[org_a.id])))

    def test_governance_edit_my_details_form(self, client_a, org_a, user_a):
        # This view is scoped to the requesting user's own linked
        # `OrganisationPerson` (governance/views.py's own docstring) - org_a
        # is a bare synthetic fixture, not created via the real
        # `organisation_create` flow that normally guarantees this row via
        # `ensure_account_holder_person`, so it must be created explicitly
        # here (mirrors policy/tests/conftest.py's `person_a` fixture).
        OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Ada Holder", job_title="Managing Director"
        )
        _assert_fully_labelled(client_a.get(reverse("governance:edit_my_details", args=[org_a.id])))

    def test_questionnaire_paste_question_form(self, client_a, org_a):
        _assert_fully_labelled(client_a.get(reverse("questionnaire:list", args=[org_a.id])))
