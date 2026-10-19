"""
The single most important test in this package (M010B PID §6/§7): for
EVERY one of the 12 Stage-4 controls and EVERY option_code that control's
real `security_baseline.structured_catalogue.STRUCTURED_OPTIONS` table
defines - including every duplicate-canonical-answer pair (e.g.
`BACKUPS_RESTORE_UNTESTED`/`BACKUPS_COVERAGE_PARTIAL`, both PARTIAL but
distinct in meaning), the JML `NOT_APPLICABLE` + confirmation-checkbox
path, and the confirmed-no-remote-access `NOT_APPLICABLE` path - submit
the SAME answer through (a) the existing manual
`security_baseline.views.foundations_question` view and (b) this
package's `foundations_journey.services.submit_foundations_option`, on
TWO SEPARATE fixture organisations with IDENTICAL `OrganisationProfile`
facts, and assert the resulting `BaselineAnswer`, `AnswerSelectionDetail`
(provenance/version), Stage-4 progress and 18-item Foundations completion
are IDENTICAL.

Every one of `STRUCTURED_OPTIONS`' ~56 (control, option_code) pairs is
exercised - not "a few representative cases" (see
`docs/evidence/M010B-FOUNDATIONS-PARITY.md` for the resulting matrix).
"""
import pytest
from django.test import Client
from django.urls import reverse

from entitlements.metrics import get_security_foundations_completion
from foundations_journey import services
from organisations.models import Organisation, OrganisationMembership, OrganisationProfile
from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.forms import confirm_field_name, option_field_name
from security_baseline.models import BaselineAssessment
from security_baseline.stage4 import stage4_progress
from security_baseline.structured_catalogue import STRUCTURED_OPTIONS

GOLDEN_CASES = [
    (control_key, option_code)
    for control_key in CATALOGUE_KEYS
    for option_code in STRUCTURED_OPTIONS[control_key]
]

# Sanity check on the golden set itself - every control appears, and the
# two NOT_APPLICABLE-bearing controls' NOT_APPLICABLE option_codes are
# genuinely present in the set this test parametrizes over.
assert len(GOLDEN_CASES) == sum(len(STRUCTURED_OPTIONS[k]) for k in CATALOGUE_KEYS)
assert ("joiner_mover_leaver", "JML_NOT_APPLICABLE") in GOLDEN_CASES
assert ("remote_access_control", "REMOTE_ACCESS_NOT_APPLICABLE") in GOLDEN_CASES
assert ("backups", "BACKUPS_RESTORE_UNTESTED") in GOLDEN_CASES
assert ("backups", "BACKUPS_COVERAGE_PARTIAL") in GOLDEN_CASES


def _case_id(case):
    return f"{case[0]}::{case[1]}"


def _fully_permissive_profile(organisation):
    """Every NOT_APPLICABLE/BYOD-conditional gate open, and identical on
    both sides of the comparison - this test is about whether the two
    WRITE PATHS behave identically given the SAME facts, not about
    offered_options' own gating logic (already exhaustively covered by
    security_baseline/tests/test_foundations_views.py::
    TestNotApplicableForgeryRejected, which this package's own
    test_forgery_and_edge_cases.py mirrors for the guided path)."""
    return OrganisationProfile.objects.create(
        organisation=organisation,
        legal_trading_name=f"{organisation.name} Profile",
        people_with_system_access_count=1,
        has_remote_or_offsite_access="no",
        endpoint_management="both",
    )


@pytest.mark.django_db
class TestManualVsGuidedParity:
    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=_case_id)
    def test_identical_canonical_effects_on_separate_organisations(self, case, make_user):
        question_key, option_code = case

        manual_org = Organisation.objects.create(name=f"Manual parity org ({_case_id(case)})")
        guided_org = Organisation.objects.create(name=f"Guided parity org ({_case_id(case)})")
        user = make_user(f"parity_user_{abs(hash(_case_id(case)))}")
        OrganisationMembership.objects.create(
            organisation=manual_org, user=user, role=OrganisationMembership.ROLE_OWNER
        )
        OrganisationMembership.objects.create(
            organisation=guided_org, user=user, role=OrganisationMembership.ROLE_OWNER
        )

        _fully_permissive_profile(manual_org)
        _fully_permissive_profile(guided_org)

        manual_client = Client()
        manual_client.force_login(user)

        post_data = {option_field_name(question_key): option_code}
        confirmation = False
        if question_key == "joiner_mover_leaver" and option_code == "JML_NOT_APPLICABLE":
            post_data[confirm_field_name(question_key)] = "on"
            confirmation = True

        manual_response = manual_client.post(
            reverse("security_baseline:foundations_question", args=[manual_org.id, question_key]),
            post_data,
        )
        assert manual_response.status_code == 302, (
            f"Manual path rejected a genuinely offered option: {manual_response.context['form'].errors if manual_response.context else 'no context'}"
        )

        receipt = services.submit_foundations_option(
            guided_org,
            user,
            question_key=question_key,
            option_code=option_code,
            confirmation=confirmation,
        )

        manual_assessment = BaselineAssessment.objects.get(organisation=manual_org)
        guided_assessment = BaselineAssessment.objects.get(organisation=guided_org)

        manual_answer = manual_assessment.answers.get(question_key=question_key)
        guided_answer = guided_assessment.answers.get(question_key=question_key)
        assert manual_answer.answer == guided_answer.answer
        assert guided_answer.answer == receipt.derived_answer

        manual_detail = manual_assessment.selection_details.get(question_key=question_key)
        guided_detail = guided_assessment.selection_details.get(question_key=question_key)
        assert manual_detail.option_code == guided_detail.option_code == option_code
        assert manual_detail.methodology_version == guided_detail.methodology_version
        assert guided_detail.methodology_version == receipt.methodology_version

        manual_progress = stage4_progress(manual_assessment)
        guided_progress = stage4_progress(guided_assessment)
        assert manual_progress == guided_progress

        manual_completion = get_security_foundations_completion(manual_org)
        guided_completion = get_security_foundations_completion(guided_org)
        assert manual_completion.percentage == guided_completion.percentage
        assert manual_completion.completed_count == guided_completion.completed_count
        assert manual_completion.total_count == guided_completion.total_count


@pytest.mark.django_db
class TestManualVsGuidedParityReAnswerAndFullRun:
    def test_reanswering_an_existing_selection_stays_in_lockstep(self, client_a, org_a, user_a):
        """Re-answer the SAME control twice through the manual path and
        twice through the guided path, on separate organisations with
        the same two answers in the same order, and assert identical
        final state (row counts stay at 1, final answer/option match)."""
        other_org = Organisation.objects.create(name="Guided re-answer org")
        OrganisationMembership.objects.create(
            organisation=other_org, user=user_a, role=OrganisationMembership.ROLE_OWNER
        )

        url = reverse("security_baseline:foundations_question", args=[org_a.id, "backups"])
        client_a.post(url, {option_field_name("backups"): "BACKUPS_NONE"})
        client_a.post(url, {option_field_name("backups"): "BACKUPS_TESTED"})

        services.submit_foundations_option(
            other_org, user_a, question_key="backups", option_code="BACKUPS_NONE"
        )
        services.submit_foundations_option(
            other_org, user_a, question_key="backups", option_code="BACKUPS_TESTED"
        )

        manual_assessment = BaselineAssessment.objects.get(organisation=org_a)
        guided_assessment = BaselineAssessment.objects.get(organisation=other_org)

        assert manual_assessment.answers.filter(question_key="backups").count() == 1
        assert guided_assessment.answers.filter(question_key="backups").count() == 1
        assert (
            manual_assessment.answers.get(question_key="backups").answer
            == guided_assessment.answers.get(question_key="backups").answer
            == "yes"
        )
        assert (
            manual_assessment.selection_details.get(question_key="backups").option_code
            == guided_assessment.selection_details.get(question_key="backups").option_code
            == "BACKUPS_TESTED"
        )

    def test_full_twelve_control_run_reaches_identical_completion_both_ways(
        self, client_a, org_a, user_a
    ):
        """A full, realistic 12-control run (every control answered at
        its strongest 'yes'-deriving option) through each path
        separately, asserting identical final 18-item completion and
        stage progress - the end-to-end analogue of security_baseline's
        own TestFullTwelveControlRoundTrip, proved on BOTH paths."""
        other_org = Organisation.objects.create(name="Guided full run org")
        OrganisationMembership.objects.create(
            organisation=other_org, user=user_a, role=OrganisationMembership.ROLE_OWNER
        )

        happy_path = {
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
        assert set(happy_path) == set(CATALOGUE_KEYS)

        for key in CATALOGUE_KEYS:
            client_a.post(
                reverse("security_baseline:foundations_question", args=[org_a.id, key]),
                {option_field_name(key): happy_path[key]},
            )
            services.submit_foundations_option(
                other_org, user_a, question_key=key, option_code=happy_path[key]
            )

        manual_assessment = BaselineAssessment.objects.get(organisation=org_a)
        guided_assessment = BaselineAssessment.objects.get(organisation=other_org)
        assert stage4_progress(manual_assessment) == stage4_progress(guided_assessment)
        assert stage4_progress(manual_assessment)["complete"] is True

        manual_completion = get_security_foundations_completion(org_a)
        guided_completion = get_security_foundations_completion(other_org)
        assert manual_completion.percentage == guided_completion.percentage
        assert manual_completion.completed_count == guided_completion.completed_count
