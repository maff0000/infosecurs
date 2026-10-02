"""
M008D-WI4 - `policy.implementation_status`'s own required proofs
(dispatch §B):

1. Every one of the 12 controls appears exactly once, regardless of
   review state.
2. An unreviewed control produces `STATUS_NOT_YET_CONFIRMED`, never
   `STATUS_GAP`.
3. The two named PARTIAL-collision examples (`BACKUPS_RESTORE_UNTESTED`
   vs `BACKUPS_COVERAGE_PARTIAL`) produce genuinely different text.
4. `status` is always consistent with the real `derived_answer`, proven by
   checking it directly against
   `security_baseline.structured_catalogue.STRUCTURED_OPTIONS` - not a
   hand-asserted value that could silently drift from the real mapping.
"""
from __future__ import annotations

import pytest

from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.models import (
    ANSWER_NOT_APPLICABLE,
    ANSWER_UNKNOWN,
    ANSWER_YES,
    BaselineAssessment,
)
from security_baseline.services import record_structured_baseline_answer
from security_baseline.structured_catalogue import STRUCTURED_OPTIONS
from policy.implementation_status import (
    STATUS_GAP,
    STATUS_MET,
    STATUS_NOT_YET_CONFIRMED,
    implementation_status_for_organisation,
)


@pytest.mark.django_db
class TestAlwaysTwelveRows:
    def test_fresh_organisation_with_no_assessment_at_all_gets_twelve_rows(self, org_a):
        assert not BaselineAssessment.objects.filter(organisation=org_a).exists()
        rows = implementation_status_for_organisation(org_a)
        assert len(rows) == 12
        assert sorted(r.control_key for r in rows) == sorted(CATALOGUE_KEYS)

    def test_fully_reviewed_organisation_still_gets_exactly_twelve_rows(self, org_a, user_a):
        for control_key, options in STRUCTURED_OPTIONS.items():
            option_code = next(iter(options.keys()))
            record_structured_baseline_answer(org_a, control_key, option_code, actor=user_a)
        rows = implementation_status_for_organisation(org_a)
        assert len(rows) == 12
        assert sorted(r.control_key for r in rows) == sorted(CATALOGUE_KEYS)


@pytest.mark.django_db
class TestUnreviewedControlIsNeverGap:
    def test_unreviewed_control_is_not_yet_confirmed_not_gap(self, org_a, user_a):
        # Review only one control - every other one of the 12 is unreviewed.
        record_structured_baseline_answer(
            org_a, "mfa_user_accounts", "MFA_USER_NOT_USED", actor=user_a
        )
        rows = {r.control_key: r for r in implementation_status_for_organisation(org_a)}

        reviewed_row = rows["mfa_user_accounts"]
        assert reviewed_row.status == STATUS_GAP
        assert reviewed_row.option_code == "MFA_USER_NOT_USED"

        for control_key, row in rows.items():
            if control_key == "mfa_user_accounts":
                continue
            assert row.status == STATUS_NOT_YET_CONFIRMED, (
                f"{control_key} was never reviewed but got status {row.status!r}"
            )
            assert row.option_code is None


@pytest.mark.django_db
class TestBackupsPartialCollisionProducesDistinctText:
    def test_restore_untested_and_coverage_partial_are_different_text(self, org_a, org_b, user_a, user_b):
        record_structured_baseline_answer(
            org_a, "backups", "BACKUPS_RESTORE_UNTESTED", actor=user_a
        )
        record_structured_baseline_answer(
            org_b, "backups", "BACKUPS_COVERAGE_PARTIAL", actor=user_b
        )
        row_a = next(
            r for r in implementation_status_for_organisation(org_a) if r.control_key == "backups"
        )
        row_b = next(
            r for r in implementation_status_for_organisation(org_b) if r.control_key == "backups"
        )
        assert row_a.status == STATUS_GAP
        assert row_b.status == STATUS_GAP
        assert row_a.current_state_text != row_b.current_state_text
        assert row_a.action_text != row_b.action_text


@pytest.mark.django_db
class TestStatusAlwaysConsistentWithRealDerivedAnswer:
    """Checked against STRUCTURED_OPTIONS directly - never a hand-asserted
    value that could silently drift from the real option->answer mapping."""

    @pytest.mark.parametrize(
        "control_key",
        list(STRUCTURED_OPTIONS.keys()),
    )
    def test_every_option_codes_row_status_matches_its_real_derived_answer(
        self, org_a, user_a, control_key
    ):
        for option_code, option in STRUCTURED_OPTIONS[control_key].items():
            record_structured_baseline_answer(org_a, control_key, option_code, actor=user_a)
            row = next(
                r
                for r in implementation_status_for_organisation(org_a)
                if r.control_key == control_key
            )
            real_derived_answer = STRUCTURED_OPTIONS[control_key][option_code].derived_answer
            if real_derived_answer in (ANSWER_YES, ANSWER_NOT_APPLICABLE):
                assert row.status == STATUS_MET
            elif real_derived_answer == ANSWER_UNKNOWN:
                assert row.status == STATUS_NOT_YET_CONFIRMED
            else:
                assert row.status == STATUS_GAP
            assert row.option_code == option_code
