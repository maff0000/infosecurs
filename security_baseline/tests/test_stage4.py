"""
security_baseline.stage4 (docs/design/M008B-QUESTION-CATALOGUE.md §0;
docs/design/M008C-UX-FLOW-DESIGN.md §2/§6).

Pure unit tests for the view-layer gating/progress/explainer helpers -
`offered_options`'s NOT_APPLICABLE re-gating is the single most important
thing in this file (everything the HTTP-level forgery tests in
test_foundations_views.py rely on is this function returning the right
set).
"""
import pytest

from organisations.models import OrganisationProfile
from security_baseline.models import (
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    AnswerSelectionDetail,
    BaselineAnswer,
    BaselineAssessment,
)
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.stage4 import (
    NOT_SURE_EXPLAINER,
    explainer_for,
    offered_options,
    progress_copy,
    stage4_progress,
)


def _make_profile(organisation, **overrides):
    defaults = {"legal_trading_name": f"{organisation.name} Profile"}
    defaults.update(overrides)
    return OrganisationProfile.objects.create(organisation=organisation, **defaults)


# ---------------------------------------------------------------------------
# NOT_APPLICABLE re-gating - the controls that must NEVER offer it.
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestNeverOffersNotApplicable:
    """
    device_encryption, endpoint_protection, security_awareness_training,
    privileged_access_separation - no NOT_APPLICABLE option under any
    condition (M008B-QUESTION-CATALOGUE.md Revision 2's explicit removal).
    """

    @pytest.mark.parametrize(
        "control_key",
        [
            "device_encryption",
            "endpoint_protection",
            "security_awareness_training",
            "privileged_access_separation",
        ],
    )
    def test_no_not_applicable_option_even_with_a_maximally_permissive_profile(
        self, org_a, control_key
    ):
        _make_profile(
            org_a,
            people_with_system_access_count=1,
            has_remote_or_offsite_access="no",
            endpoint_management="both",
        )
        offered = offered_options(control_key, org_a)
        assert not any(
            option.derived_answer == ANSWER_NOT_APPLICABLE for option in offered.values()
        )

    @pytest.mark.parametrize(
        "control_key",
        [
            "device_encryption",
            "endpoint_protection",
            "security_awareness_training",
            "privileged_access_separation",
        ],
    )
    def test_no_not_applicable_option_with_no_profile_at_all(self, org_a, control_key):
        offered = offered_options(control_key, org_a)
        assert not any(
            option.derived_answer == ANSWER_NOT_APPLICABLE for option in offered.values()
        )


@pytest.mark.django_db
class TestJoinerMoverLeaverGate:
    def test_not_applicable_offered_when_count_is_exactly_one(self, org_a):
        _make_profile(org_a, people_with_system_access_count=1)
        offered = offered_options("joiner_mover_leaver", org_a)
        assert "JML_NOT_APPLICABLE" in offered

    def test_not_applicable_not_offered_when_count_is_two(self, org_a):
        _make_profile(org_a, people_with_system_access_count=2)
        offered = offered_options("joiner_mover_leaver", org_a)
        assert "JML_NOT_APPLICABLE" not in offered

    def test_not_applicable_not_offered_when_count_is_unset(self, org_a):
        _make_profile(org_a)  # people_with_system_access_count left null
        offered = offered_options("joiner_mover_leaver", org_a)
        assert "JML_NOT_APPLICABLE" not in offered

    def test_not_applicable_not_offered_with_no_profile_at_all(self, org_a):
        offered = offered_options("joiner_mover_leaver", org_a)
        assert "JML_NOT_APPLICABLE" not in offered

    def test_staff_count_alone_is_never_consulted(self, org_a):
        """
        `staff_count` must never be sufficient authority for this gate -
        only `people_with_system_access_count` (docs/design/
        M008B-QUESTION-CATALOGUE.md control 7).
        """
        _make_profile(org_a, staff_count=1, people_with_system_access_count=None)
        offered = offered_options("joiner_mover_leaver", org_a)
        assert "JML_NOT_APPLICABLE" not in offered


@pytest.mark.django_db
class TestRemoteAccessControlGate:
    def test_not_applicable_offered_when_fact_is_no(self, org_a):
        _make_profile(org_a, has_remote_or_offsite_access="no")
        offered = offered_options("remote_access_control", org_a)
        assert "REMOTE_ACCESS_NOT_APPLICABLE" in offered

    def test_not_applicable_not_offered_when_fact_is_yes(self, org_a):
        _make_profile(org_a, has_remote_or_offsite_access="yes")
        offered = offered_options("remote_access_control", org_a)
        assert "REMOTE_ACCESS_NOT_APPLICABLE" not in offered

    def test_not_applicable_not_offered_when_fact_is_unknown(self, org_a):
        _make_profile(org_a, has_remote_or_offsite_access="unknown")
        offered = offered_options("remote_access_control", org_a)
        assert "REMOTE_ACCESS_NOT_APPLICABLE" not in offered

    def test_not_applicable_not_offered_with_no_profile_at_all(self, org_a):
        offered = offered_options("remote_access_control", org_a)
        assert "REMOTE_ACCESS_NOT_APPLICABLE" not in offered

    def test_never_inferred_from_working_model(self, org_a):
        """working_model=="remote" must not, by itself, offer the option."""
        _make_profile(org_a, working_model="remote", has_remote_or_offsite_access="unknown")
        offered = offered_options("remote_access_control", org_a)
        assert "REMOTE_ACCESS_NOT_APPLICABLE" not in offered


@pytest.mark.django_db
class TestEndpointProtectionConditioning:
    """Pre-existing option-set conditioning (unrelated to the NOT_APPLICABLE
    correction) - COMPANY_ONLY only for a confirmed BYOD/both org."""

    @pytest.mark.parametrize("value", ["byod", "both"])
    def test_company_only_offered_for_byod_or_both(self, org_a, value):
        _make_profile(org_a, endpoint_management=value)
        offered = offered_options("endpoint_protection", org_a)
        assert "ENDPOINT_PROTECTION_COMPANY_ONLY" in offered

    def test_company_only_not_offered_for_company_managed(self, org_a):
        _make_profile(org_a, endpoint_management="company_managed")
        offered = offered_options("endpoint_protection", org_a)
        assert "ENDPOINT_PROTECTION_COMPANY_ONLY" not in offered

    def test_company_only_not_offered_with_no_profile_at_all(self, org_a):
        offered = offered_options("endpoint_protection", org_a)
        assert "ENDPOINT_PROTECTION_COMPANY_ONLY" not in offered


# ---------------------------------------------------------------------------
# Explainer text
# ---------------------------------------------------------------------------
class TestExplainerText:
    def test_not_sure_is_uniform_regardless_of_control(self):
        assert explainer_for("backups", "BACKUPS_NOT_SURE", ANSWER_UNKNOWN) == NOT_SURE_EXPLAINER
        assert (
            explainer_for("mfa_user_accounts", "MFA_USER_NOT_SURE", ANSWER_UNKNOWN)
            == NOT_SURE_EXPLAINER
        )

    def test_two_option_codes_sharing_a_canonical_state_have_distinct_text(self):
        """Central Architecture's own named example (M008B §6)."""
        untested = explainer_for("backups", "BACKUPS_RESTORE_UNTESTED", ANSWER_PARTIAL)
        partial_coverage = explainer_for("backups", "BACKUPS_COVERAGE_PARTIAL", ANSWER_PARTIAL)
        assert untested != partial_coverage
        assert "restore" in untested.lower()
        assert "cover" in partial_coverage.lower()


# ---------------------------------------------------------------------------
# Progress (M008C-UX-FLOW-DESIGN.md §6)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestStage4Progress:
    def test_no_assessment_at_all_is_zero_reviewed(self):
        progress = stage4_progress(None)
        assert progress == {
            "reviewed": 0,
            "still_need_confirmation": 0,
            "total": 12,
            "complete": False,
        }
        assert progress_copy(progress) == "0 of 12 reviewed · 0 still need confirmation"

    def test_some_reviewed_some_unknown(self, org_a):
        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        BaselineAnswer.objects.create(
            assessment=assessment, question_key="mfa_user_accounts", answer="yes"
        )
        AnswerSelectionDetail.objects.create(
            assessment=assessment,
            question_key="mfa_user_accounts",
            option_code="MFA_USER_ALL_REQUIRED",
            methodology_version="2026-10-structured-v1",
        )
        BaselineAnswer.objects.create(
            assessment=assessment, question_key="backups", answer=ANSWER_UNKNOWN
        )
        AnswerSelectionDetail.objects.create(
            assessment=assessment,
            question_key="backups",
            option_code="BACKUPS_NOT_SURE",
            methodology_version="2026-10-structured-v1",
        )
        progress = stage4_progress(assessment)
        assert progress["reviewed"] == 2
        assert progress["still_need_confirmation"] == 1
        assert progress["complete"] is False
        assert progress_copy(progress) == "2 of 12 reviewed · 1 still need confirmation"

    def test_complete_only_when_all_reviewed_and_zero_unknown(self, org_a):
        from security_baseline.catalogue import CATALOGUE_KEYS

        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        for key in CATALOGUE_KEYS:
            BaselineAnswer.objects.create(assessment=assessment, question_key=key, answer="yes")
            AnswerSelectionDetail.objects.create(
                assessment=assessment,
                question_key=key,
                option_code="placeholder",
                methodology_version="2026-10-structured-v1",
            )
        progress = stage4_progress(assessment)
        assert progress["reviewed"] == 12
        assert progress["still_need_confirmation"] == 0
        assert progress["complete"] is True
        assert progress_copy(progress) == "Complete"

    def test_all_reviewed_but_some_unknown_is_not_complete(self, org_a):
        from security_baseline.catalogue import CATALOGUE_KEYS

        assessment = BaselineAssessment.objects.create(
            organisation=org_a, catalogue_version=CATALOGUE_VERSION
        )
        for i, key in enumerate(CATALOGUE_KEYS):
            answer = ANSWER_UNKNOWN if i == 0 else "yes"
            BaselineAnswer.objects.create(assessment=assessment, question_key=key, answer=answer)
            AnswerSelectionDetail.objects.create(
                assessment=assessment,
                question_key=key,
                option_code="placeholder",
                methodology_version="2026-10-structured-v1",
            )
        progress = stage4_progress(assessment)
        assert progress["reviewed"] == 12
        assert progress["still_need_confirmation"] == 1
        assert progress["complete"] is False
        assert progress_copy(progress) == "12 of 12 reviewed · 1 still need confirmation"
