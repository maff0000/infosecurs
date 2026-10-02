"""
security_baseline.structured_catalogue (docs/design/M008B-QUESTION-
CATALOGUE.md). Pure-Python, no database - every option_code for every
control resolves to the exact documented canonical answer, an unknown
option_code/control_key raises clearly, and the methodology version
constant is exposed and correct.
"""
import pytest

from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
)
from security_baseline.structured_catalogue import (
    CONTROLS_WITH_NOT_APPLICABLE_OPTION,
    FOUNDATIONS_QUESTION_METHODOLOGY_VERSION,
    STRUCTURED_OPTIONS,
    UnknownControlKeyError,
    UnknownOptionCodeError,
    resolve_option,
)

# The exact (control_key, option_code, expected_derived_answer) triples
# transcribed directly from docs/design/M008B-QUESTION-CATALOGUE.md's
# per-control option tables (Revision 2) - every option, for every
# control, exactly as that document specifies.
EXPECTED = [
    ("mfa_user_accounts", "MFA_USER_ALL_REQUIRED", ANSWER_YES),
    ("mfa_user_accounts", "MFA_USER_SOME_REQUIRED", ANSWER_PARTIAL),
    ("mfa_user_accounts", "MFA_USER_AVAILABLE_NOT_ENFORCED", ANSWER_PARTIAL),
    ("mfa_user_accounts", "MFA_USER_NOT_USED", ANSWER_NO),
    ("mfa_user_accounts", "MFA_USER_NOT_SURE", ANSWER_UNKNOWN),
    ("mfa_privileged_accounts", "MFA_ADMIN_ALL_REQUIRED", ANSWER_YES),
    ("mfa_privileged_accounts", "MFA_ADMIN_SOME_REQUIRED", ANSWER_PARTIAL),
    ("mfa_privileged_accounts", "MFA_ADMIN_AVAILABLE_NOT_ENFORCED", ANSWER_PARTIAL),
    ("mfa_privileged_accounts", "MFA_ADMIN_NOT_USED", ANSWER_NO),
    ("mfa_privileged_accounts", "MFA_ADMIN_NOT_SURE", ANSWER_UNKNOWN),
    ("endpoint_protection", "ENDPOINT_PROTECTION_ALL", ANSWER_YES),
    ("endpoint_protection", "ENDPOINT_PROTECTION_MOST", ANSWER_PARTIAL),
    ("endpoint_protection", "ENDPOINT_PROTECTION_COMPANY_ONLY", ANSWER_PARTIAL),
    ("endpoint_protection", "ENDPOINT_PROTECTION_NONE", ANSWER_NO),
    ("endpoint_protection", "ENDPOINT_PROTECTION_NOT_SURE", ANSWER_UNKNOWN),
    ("patching", "PATCHING_AUTOMATIC", ANSWER_YES),
    ("patching", "PATCHING_MOSTLY_CURRENT", ANSWER_PARTIAL),
    ("patching", "PATCHING_IRREGULAR", ANSWER_PARTIAL),
    ("patching", "PATCHING_NONE", ANSWER_NO),
    ("patching", "PATCHING_NOT_SURE", ANSWER_UNKNOWN),
    ("device_encryption", "DEVICE_ENCRYPTION_ALL", ANSWER_YES),
    ("device_encryption", "DEVICE_ENCRYPTION_SOME", ANSWER_PARTIAL),
    ("device_encryption", "DEVICE_ENCRYPTION_NONE", ANSWER_NO),
    ("device_encryption", "DEVICE_ENCRYPTION_NOT_SURE", ANSWER_UNKNOWN),
    ("backups", "BACKUPS_TESTED", ANSWER_YES),
    ("backups", "BACKUPS_RESTORE_UNTESTED", ANSWER_PARTIAL),
    ("backups", "BACKUPS_COVERAGE_PARTIAL", ANSWER_PARTIAL),
    ("backups", "BACKUPS_NONE", ANSWER_NO),
    ("backups", "BACKUPS_NOT_SURE", ANSWER_UNKNOWN),
    ("joiner_mover_leaver", "JML_DEFINED_FOLLOWED", ANSWER_YES),
    ("joiner_mover_leaver", "JML_INFORMAL_USUALLY", ANSWER_PARTIAL),
    ("joiner_mover_leaver", "JML_INCONSISTENT", ANSWER_PARTIAL),
    ("joiner_mover_leaver", "JML_NONE", ANSWER_NO),
    ("joiner_mover_leaver", "JML_NOT_SURE", ANSWER_UNKNOWN),
    ("joiner_mover_leaver", "JML_NOT_APPLICABLE", ANSWER_NOT_APPLICABLE),
    ("privileged_access_separation", "PRIV_SEP_DEDICATED", ANSWER_YES),
    ("privileged_access_separation", "PRIV_SEP_SOME", ANSWER_PARTIAL),
    ("privileged_access_separation", "PRIV_SEP_NONE", ANSWER_NO),
    ("privileged_access_separation", "PRIV_SEP_NOT_SURE", ANSWER_UNKNOWN),
    ("security_awareness_training", "AWARENESS_REGULAR", ANSWER_YES),
    ("security_awareness_training", "AWARENESS_OCCASIONAL", ANSWER_PARTIAL),
    ("security_awareness_training", "AWARENESS_NONE", ANSWER_NO),
    ("security_awareness_training", "AWARENESS_NOT_SURE", ANSWER_UNKNOWN),
    ("incident_reporting_route", "INCIDENT_ROUTE_CLEAR", ANSWER_YES),
    ("incident_reporting_route", "INCIDENT_ROUTE_INFORMAL", ANSWER_PARTIAL),
    ("incident_reporting_route", "INCIDENT_ROUTE_NONE", ANSWER_NO),
    ("incident_reporting_route", "INCIDENT_ROUTE_NOT_SURE", ANSWER_UNKNOWN),
    ("email_phishing_protection", "PHISHING_PROTECTION_ACTIVE_ALL", ANSWER_YES),
    ("email_phishing_protection", "PHISHING_PROTECTION_BASIC_DEFAULT", ANSWER_PARTIAL),
    ("email_phishing_protection", "PHISHING_PROTECTION_PARTIAL", ANSWER_PARTIAL),
    ("email_phishing_protection", "PHISHING_PROTECTION_NONE", ANSWER_NO),
    ("email_phishing_protection", "PHISHING_PROTECTION_NOT_SURE", ANSWER_UNKNOWN),
    ("remote_access_control", "REMOTE_ACCESS_GOVERNED", ANSWER_YES),
    ("remote_access_control", "REMOTE_ACCESS_SOME_UNMANAGED", ANSWER_PARTIAL),
    ("remote_access_control", "REMOTE_ACCESS_NONE_GOVERNED", ANSWER_NO),
    ("remote_access_control", "REMOTE_ACCESS_NOT_SURE", ANSWER_UNKNOWN),
    ("remote_access_control", "REMOTE_ACCESS_NOT_APPLICABLE", ANSWER_NOT_APPLICABLE),
]


class TestEveryDocumentedOptionResolvesToItsCanonicalAnswer:
    @pytest.mark.parametrize("control_key,option_code,expected_answer", EXPECTED)
    def test_resolve_option_matches_the_design_doc(self, control_key, option_code, expected_answer):
        option = resolve_option(control_key, option_code)
        assert option.derived_answer == expected_answer

    def test_every_catalogue_control_key_is_covered(self):
        assert set(STRUCTURED_OPTIONS.keys()) == set(CATALOGUE_KEYS)

    def test_exactly_the_documented_option_count_per_control(self):
        expected_counts = {}
        for control_key, _option_code, _answer in EXPECTED:
            expected_counts[control_key] = expected_counts.get(control_key, 0) + 1
        for control_key, options in STRUCTURED_OPTIONS.items():
            assert len(options) == expected_counts[control_key], control_key

    def test_only_joiner_mover_leaver_and_remote_access_control_have_a_not_applicable_option(self):
        assert CONTROLS_WITH_NOT_APPLICABLE_OPTION == frozenset(
            {"joiner_mover_leaver", "remote_access_control"}
        )
        for control_key, options in STRUCTURED_OPTIONS.items():
            has_na = any(opt.derived_answer == ANSWER_NOT_APPLICABLE for opt in options.values())
            assert has_na == (control_key in CONTROLS_WITH_NOT_APPLICABLE_OPTION)

    def test_two_options_that_share_a_canonical_answer_keep_distinct_labels(self):
        """
        Central Architecture's own named example: BACKUPS_RESTORE_UNTESTED
        and BACKUPS_COVERAGE_PARTIAL both derive PARTIAL but must remain
        two distinct, separately-labelled options, never collapsed.
        """
        restore_untested = resolve_option("backups", "BACKUPS_RESTORE_UNTESTED")
        coverage_partial = resolve_option("backups", "BACKUPS_COVERAGE_PARTIAL")
        assert restore_untested.derived_answer == coverage_partial.derived_answer == ANSWER_PARTIAL
        assert restore_untested.label != coverage_partial.label


class TestUnknownLookupsRaiseClearly:
    def test_unknown_control_key_raises(self):
        with pytest.raises(UnknownControlKeyError):
            resolve_option("not_a_real_control", "ANYTHING")

    def test_unknown_option_code_for_a_real_control_raises(self):
        with pytest.raises(UnknownOptionCodeError):
            resolve_option("mfa_user_accounts", "NOT_A_REAL_OPTION_CODE")

    def test_valid_option_code_for_the_wrong_control_raises(self):
        # JML_NOT_APPLICABLE is real, but only for joiner_mover_leaver.
        with pytest.raises(UnknownOptionCodeError):
            resolve_option("remote_access_control", "JML_NOT_APPLICABLE")

    def test_both_exceptions_are_key_errors(self):
        assert issubclass(UnknownControlKeyError, KeyError)
        assert issubclass(UnknownOptionCodeError, KeyError)


class TestMethodologyVersion:
    def test_methodology_version_is_exposed_and_correct(self):
        assert FOUNDATIONS_QUESTION_METHODOLOGY_VERSION == "2026-10-structured-v1"
