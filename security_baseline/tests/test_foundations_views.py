"""
HTTP-level tests for the M008C guided Stage 4 journey
(security_baseline.views.foundations_start/foundations_question) and for
the legacy `security_baseline:baseline` entry point's new redirect-only
behaviour.

The single most important test in this file is
`TestNotApplicableForgeryRejected` - the dispatch's own explicit
"required, not optional" test: proving a forged/unoffered NOT_APPLICABLE
option_code is rejected server-side, with nothing written, regardless of
what a client renders or claims.
"""
import pytest
from django.urls import reverse

from organisations.models import OrganisationProfile
from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.forms import confirm_field_name, option_field_name
from security_baseline.models import ANSWER_UNKNOWN, AnswerSelectionDetail, BaselineAnswer, BaselineAssessment
from security_baseline.stage4 import NOT_SURE_EXPLAINER, explainer_for

# Every control answered at its strongest ("yes") option - used by the
# full round-trip test, which exercises none of the NOT_APPLICABLE gating
# (covered separately and exhaustively below).
HAPPY_PATH_OPTION_CODE = {
    "mfa_user_accounts": "MFA_USER_ALL_REQUIRED",
    "mfa_privileged_accounts": "MFA_ADMIN_ALL_REQUIRED",
    "endpoint_protection": "ENDPOINT_PROTECTION_ALL",
    "patching": "PATCHING_AUTOMATIC",
    "device_encryption": "DEVICE_ENCRYPTION_ALL",
    "backups": "BACKUPS_TESTED",
    "joiner_mover_leaver": "JML_DEFINED_FOLLOWED",
    "privileged_access_separation": "PRIV_SEP_DEDICATED",
    "security_awareness_training": "AWARENESS_REGULAR",
    "incident_reporting_route": "INCIDENT_ROUTE_CLEAR",
    "email_phishing_protection": "PHISHING_PROTECTION_ACTIVE_ALL",
    "remote_access_control": "REMOTE_ACCESS_GOVERNED",
}
assert set(HAPPY_PATH_OPTION_CODE) == set(CATALOGUE_KEYS)


def _question_url(organisation_id, key):
    return reverse(
        "security_baseline:foundations_question", args=[organisation_id, key]
    )


def _make_profile(organisation, **overrides):
    defaults = {"legal_trading_name": f"{organisation.name} Profile"}
    defaults.update(overrides)
    return OrganisationProfile.objects.create(organisation=organisation, **defaults)


@pytest.mark.django_db
class TestLegacyBaselineEntryPointRedirects:
    def test_get_redirects_into_the_guided_journey(self, client_a, org_a):
        response = client_a.get(reverse("security_baseline:baseline", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url == reverse(
            "security_baseline:foundations_start", args=[org_a.id]
        )

    def test_post_also_redirects_and_writes_nothing_even_with_a_forged_note_field(
        self, client_a, org_a
    ):
        """
        Mechanical proof the old free-text note path is unreachable: a
        POST that looks exactly like the old long-form submission
        (including a `note__<key>` field) never even gets parsed into a
        form - it is simply redirected, and nothing is written.
        """
        response = client_a.post(
            reverse("security_baseline:baseline", args=[org_a.id]),
            {
                "answer__device_encryption": "not_applicable",
                "note__device_encryption": "Smuggled free-text note.",
            },
        )
        assert response.status_code == 302
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_cross_tenant_get_is_404(self, client_b, org_a):
        response = client_b.get(reverse("security_baseline:baseline", args=[org_a.id]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestFoundationsStartRedirectsToFirstUnreviewedQuestion:
    def test_brand_new_organisation_lands_on_first_control(self, client_a, org_a):
        response = client_a.get(reverse("security_baseline:foundations_start", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url == _question_url(org_a.id, CATALOGUE_KEYS[0])

    def test_lands_on_first_unreviewed_control_not_the_first_overall(self, client_a, org_a):
        url = _question_url(org_a.id, CATALOGUE_KEYS[0])
        client_a.post(url, {option_field_name(CATALOGUE_KEYS[0]): "MFA_USER_ALL_REQUIRED"})

        response = client_a.get(reverse("security_baseline:foundations_start", args=[org_a.id]))
        assert response.url == _question_url(org_a.id, CATALOGUE_KEYS[1])

    def test_lands_on_first_control_again_once_everything_is_reviewed(self, client_a, org_a):
        for key in CATALOGUE_KEYS:
            client_a.post(_question_url(org_a.id, key), {option_field_name(key): HAPPY_PATH_OPTION_CODE[key]})

        response = client_a.get(reverse("security_baseline:foundations_start", args=[org_a.id]))
        assert response.url == _question_url(org_a.id, CATALOGUE_KEYS[0])


@pytest.mark.django_db
class TestFoundationsQuestionGetNeverWrites:
    def test_get_on_an_unanswered_question_writes_nothing(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_invalid_question_key_is_404(self, client_a, org_a):
        response = client_a.get(_question_url(org_a.id, "not_a_real_control"))
        assert response.status_code == 404


@pytest.mark.django_db
class TestFullTwelveControlRoundTrip:
    def test_answering_all_twelve_controls_via_the_real_http_view(self, client_a, org_a):
        for index, key in enumerate(CATALOGUE_KEYS):
            code = HAPPY_PATH_OPTION_CODE[key]
            url = _question_url(org_a.id, key)

            response = client_a.post(url, {option_field_name(key): code})
            assert response.status_code == 302
            assert response.url == url  # redirects back to the same question

            assessment = BaselineAssessment.objects.get(organisation=org_a)
            answer = assessment.answers.get(question_key=key)
            assert answer.answer == "yes"
            detail = assessment.selection_details.get(question_key=key)
            assert detail.option_code == code

            page = client_a.get(url)
            reviewed = index + 1
            if reviewed == len(CATALOGUE_KEYS):
                assert page.context["progress_copy"] == "Complete"
            else:
                assert (
                    page.context["progress_copy"]
                    == f"{reviewed} of 12 reviewed · 0 still need confirmation"
                )

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert assessment.answers.count() == len(CATALOGUE_KEYS)
        assert assessment.selection_details.count() == len(CATALOGUE_KEYS)


@pytest.mark.django_db
class TestNotApplicableForgeryRejected:
    """
    The dispatch's own required test. Every scenario below asserts BOTH:
    the response does not redirect (the form was rejected, re-rendered
    with an error), AND nothing was written to BaselineAnswer or
    AnswerSelectionDetail as a result of the attempt.
    """

    def test_device_encryption_has_no_not_applicable_option_to_forge_at_all(
        self, client_a, org_a
    ):
        """
        device_encryption never has a NOT_APPLICABLE option, for any
        organisation, under any profile state - a client claiming
        otherwise is simply submitting an option_code that does not
        exist in this control's offered set.
        """
        _make_profile(
            org_a,
            people_with_system_access_count=1,
            has_remote_or_offsite_access="no",
        )
        url = _question_url(org_a.id, "device_encryption")
        response = client_a.post(
            url, {option_field_name("device_encryption"): "DEVICE_ENCRYPTION_NOT_APPLICABLE"}
        )
        assert response.status_code == 200  # re-rendered with an error, no redirect
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_not_applicable_rejected_without_the_confirmation_checkbox(
        self, client_a, org_a
    ):
        """
        Even when the underlying fact genuinely is 1 (so the option IS
        offered), JML_NOT_APPLICABLE must still be rejected if the
        confirmation checkbox was not submitted checked in this exact
        POST.
        """
        _make_profile(org_a, people_with_system_access_count=1)
        url = _question_url(org_a.id, "joiner_mover_leaver")

        # Omit the checkbox entirely.
        response = client_a.post(
            url, {option_field_name("joiner_mover_leaver"): "JML_NOT_APPLICABLE"}
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

        # Submit it explicitly unchecked (BooleanField: absent == False,
        # but prove the "present but false" shape too for completeness).
        response = client_a.post(
            url,
            {
                option_field_name("joiner_mover_leaver"): "JML_NOT_APPLICABLE",
                confirm_field_name("joiner_mover_leaver"): "false",
            },
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_not_applicable_rejected_when_the_count_fact_is_not_one(
        self, client_a, org_a
    ):
        """
        Even WITH the confirmation checkbox checked, JML_NOT_APPLICABLE
        must be rejected when the server-side fact is not 1 - the option
        is simply not offered, so the checkbox is irrelevant.
        """
        _make_profile(org_a, people_with_system_access_count=3)
        url = _question_url(org_a.id, "joiner_mover_leaver")
        response = client_a.post(
            url,
            {
                option_field_name("joiner_mover_leaver"): "JML_NOT_APPLICABLE",
                confirm_field_name("joiner_mover_leaver"): "on",
            },
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_not_applicable_rejected_when_there_is_no_profile_at_all(
        self, client_a, org_a
    ):
        url = _question_url(org_a.id, "joiner_mover_leaver")
        response = client_a.post(
            url,
            {
                option_field_name("joiner_mover_leaver"): "JML_NOT_APPLICABLE",
                confirm_field_name("joiner_mover_leaver"): "on",
            },
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_jml_not_applicable_accepted_when_count_is_one_and_checkbox_checked(
        self, client_a, org_a
    ):
        """Positive control: the legitimate path still works."""
        _make_profile(org_a, people_with_system_access_count=1)
        url = _question_url(org_a.id, "joiner_mover_leaver")
        response = client_a.post(
            url,
            {
                option_field_name("joiner_mover_leaver"): "JML_NOT_APPLICABLE",
                confirm_field_name("joiner_mover_leaver"): "on",
            },
        )
        assert response.status_code == 302
        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert assessment.answers.get(question_key="joiner_mover_leaver").answer == "not_applicable"

    def test_remote_access_not_applicable_rejected_when_fact_is_not_no(
        self, client_a, org_a
    ):
        _make_profile(org_a, has_remote_or_offsite_access="yes")
        url = _question_url(org_a.id, "remote_access_control")
        response = client_a.post(
            url,
            {option_field_name("remote_access_control"): "REMOTE_ACCESS_NOT_APPLICABLE"},
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_remote_access_not_applicable_accepted_when_fact_is_no(self, client_a, org_a):
        """Positive control: the legitimate path still works."""
        _make_profile(org_a, has_remote_or_offsite_access="no")
        url = _question_url(org_a.id, "remote_access_control")
        response = client_a.post(
            url,
            {option_field_name("remote_access_control"): "REMOTE_ACCESS_NOT_APPLICABLE"},
        )
        assert response.status_code == 302
        assessment = BaselineAssessment.objects.get(organisation=org_a)
        assert (
            assessment.answers.get(question_key="remote_access_control").answer
            == "not_applicable"
        )

    def test_a_completely_made_up_option_code_is_rejected_on_any_control(
        self, client_a, org_a
    ):
        url = _question_url(org_a.id, "mfa_user_accounts")
        response = client_a.post(
            url, {option_field_name("mfa_user_accounts"): "DEFINITELY_NOT_A_REAL_OPTION_CODE"}
        )
        assert response.status_code == 200
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()


@pytest.mark.django_db
class TestNotSureRoundTrip:
    def test_not_sure_resolves_to_unknown_counts_as_reviewed_not_confirmed(
        self, client_a, org_a
    ):
        url = _question_url(org_a.id, "mfa_user_accounts")
        response = client_a.post(url, {option_field_name("mfa_user_accounts"): "MFA_USER_NOT_SURE"})
        assert response.status_code == 302

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        answer = assessment.answers.get(question_key="mfa_user_accounts")
        assert answer.answer == ANSWER_UNKNOWN

        page = client_a.get(url)
        assert page.context["progress"]["reviewed"] == 1
        assert page.context["progress"]["still_need_confirmation"] == 1
        assert page.context["explainer"] == NOT_SURE_EXPLAINER

    def test_revisiting_shows_not_sure_still_selected_not_blank(self, client_a, org_a):
        url = _question_url(org_a.id, "mfa_user_accounts")
        client_a.post(url, {option_field_name("mfa_user_accounts"): "MFA_USER_NOT_SURE"})

        page = client_a.get(url)
        assert page.context["option_field"].value() == "MFA_USER_NOT_SURE"


@pytest.mark.django_db
class TestReAnsweringUpdatesInPlace:
    def test_second_answer_updates_the_same_rows_not_a_duplicate(self, client_a, org_a):
        url = _question_url(org_a.id, "backups")
        client_a.post(url, {option_field_name("backups"): "BACKUPS_NONE"})
        assessment = BaselineAssessment.objects.get(organisation=org_a)
        first_answer_pk = assessment.answers.get(question_key="backups").pk
        first_detail_pk = assessment.selection_details.get(question_key="backups").pk

        client_a.post(url, {option_field_name("backups"): "BACKUPS_TESTED"})

        assert BaselineAnswer.objects.filter(assessment=assessment, question_key="backups").count() == 1
        assert (
            AnswerSelectionDetail.objects.filter(assessment=assessment, question_key="backups").count()
            == 1
        )
        answer = BaselineAnswer.objects.get(assessment=assessment, question_key="backups")
        detail = AnswerSelectionDetail.objects.get(assessment=assessment, question_key="backups")
        assert answer.pk == first_answer_pk
        assert detail.pk == first_detail_pk
        assert answer.answer == "yes"
        assert detail.option_code == "BACKUPS_TESTED"


@pytest.mark.django_db
class TestDistinctExplainerTextForSharedCanonicalState:
    """Central Architecture's own named example (backups), proved on-screen."""

    def test_backups_restore_untested_vs_coverage_partial_render_different_text(
        self, client_a, org_a
    ):
        url = _question_url(org_a.id, "backups")

        client_a.post(url, {option_field_name("backups"): "BACKUPS_RESTORE_UNTESTED"})
        page_a = client_a.get(url)
        explainer_a = page_a.context["explainer"]
        assert explainer_a == explainer_for("backups", "BACKUPS_RESTORE_UNTESTED", "partial")

        client_a.post(url, {option_field_name("backups"): "BACKUPS_COVERAGE_PARTIAL"})
        page_b = client_a.get(url)
        explainer_b = page_b.context["explainer"]
        assert explainer_b == explainer_for("backups", "BACKUPS_COVERAGE_PARTIAL", "partial")

        assert explainer_a != explainer_b


@pytest.mark.django_db
class TestFoundationsTenantIsolation:
    def test_member_can_answer_own_organisations_question(self, client_a, org_a):
        url = _question_url(org_a.id, "backups")
        response = client_a.post(url, {option_field_name("backups"): "BACKUPS_TESTED"})
        assert response.status_code == 302
        assert BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_member_cannot_read_other_organisations_question_page(self, client_b, org_a):
        response = client_b.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 404

    def test_member_cannot_post_an_answer_to_other_organisations_question(
        self, client_b, org_a
    ):
        response = client_b.post(
            _question_url(org_a.id, "backups"), {option_field_name("backups"): "BACKUPS_TESTED"}
        )
        assert response.status_code == 404
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()

    def test_member_cannot_read_other_organisations_foundations_start(self, client_b, org_a):
        response = client_b.get(reverse("security_baseline:foundations_start", args=[org_a.id]))
        assert response.status_code == 404

    def test_anonymous_user_is_redirected_to_login(self, client, org_a):
        response = client.get(_question_url(org_a.id, "backups"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
