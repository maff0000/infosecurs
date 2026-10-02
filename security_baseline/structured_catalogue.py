"""
Stage 4 structured option-code catalogue
(docs/design/M008B-QUESTION-CATALOGUE.md).

Versioned product methodology, the exact same discipline as
`security_baseline.catalogue` and `risk_register.methodology`: a small,
Git-controlled, plain-Python table - not an editable database table.

This module answers a DIFFERENT question to `security_baseline.catalogue.
CATALOGUE_VERSION`: `FOUNDATIONS_QUESTION_METHODOLOGY_VERSION` versions
the structured *option-code* scheme itself (which `option_code`s exist for
each control, and what canonical five-state answer each one derives) -
`CATALOGUE_VERSION` versions the 12-control question/weighting methodology
(control keys, areas, weights). Both are recorded against a stored answer
(see `security_baseline.services.record_structured_baseline_answer` /
`security_baseline.models.AnswerSelectionDetail`); neither supersedes the
other.

This module supplies ONLY the per-control `option_code` -> canonical-
answer tables (plus which controls even have a NOT_APPLICABLE option at
all). The two new NOT_APPLICABLE *gating* conditions - confirmed
`OrganisationProfile.people_with_system_access_count == 1` plus an
explicit confirmation for `joiner_mover_leaver`; confirmed
`OrganisationProfile.has_remote_or_offsite_access == "no"` for
`remote_access_control` - are about `OrganisationProfile` facts, not about
this option catalogue, and deliberately do not live here. Whether a given
NOT_APPLICABLE option_code may currently be *offered* to a customer is a
later WI's (view-layer) concern; this module only knows how to resolve an
option_code that was actually submitted into its canonical answer, for any
control/option_code pair this catalogue defines - it does not re-check the
gating facts itself.

Display wording (the `label` below) is never identity - only `option_code`
is. `option_code` values are stable identifiers, the same discipline as
`security_baseline.catalogue`'s `key` values: once published, never
renamed or repurposed for a different meaning.
"""
from __future__ import annotations

from typing import NamedTuple

from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
)

FOUNDATIONS_QUESTION_METHODOLOGY_VERSION = "2026-10-structured-v1"


class StructuredOption(NamedTuple):
    """One selectable option for one control's structured Stage 4 question."""

    label: str
    derived_answer: str


# control_key -> {option_code: StructuredOption(label, derived_answer)}
#
# Transcribed directly from docs/design/M008B-QUESTION-CATALOGUE.md's
# per-control option tables (Revision 2). Every control's full option set
# is reproduced exactly - including every option that collapses to the
# same canonical answer as a sibling option (e.g. `MFA_USER_SOME_REQUIRED`
# and `MFA_USER_AVAILABLE_NOT_ENFORCED` both derive PARTIAL, but are kept
# as two distinct, separately-labelled option_codes per that document's
# own explicit instruction - never collapsed into one option here).
STRUCTURED_OPTIONS: dict[str, dict[str, StructuredOption]] = {
    "mfa_user_accounts": {
        "MFA_USER_ALL_REQUIRED": StructuredOption(
            "MFA required for all staff accounts", ANSWER_YES
        ),
        "MFA_USER_SOME_REQUIRED": StructuredOption(
            "MFA required for some staff/groups, not all", ANSWER_PARTIAL
        ),
        "MFA_USER_AVAILABLE_NOT_ENFORCED": StructuredOption(
            "MFA available but not enforced", ANSWER_PARTIAL
        ),
        "MFA_USER_NOT_USED": StructuredOption(
            "MFA not currently used", ANSWER_NO
        ),
        "MFA_USER_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "mfa_privileged_accounts": {
        "MFA_ADMIN_ALL_REQUIRED": StructuredOption(
            "MFA required for all admin/privileged accounts", ANSWER_YES
        ),
        "MFA_ADMIN_SOME_REQUIRED": StructuredOption(
            "MFA required for some admin accounts, not all", ANSWER_PARTIAL
        ),
        "MFA_ADMIN_AVAILABLE_NOT_ENFORCED": StructuredOption(
            "MFA available but not enforced for admin accounts", ANSWER_PARTIAL
        ),
        "MFA_ADMIN_NOT_USED": StructuredOption(
            "MFA not used for admin accounts", ANSWER_NO
        ),
        "MFA_ADMIN_NOT_SURE": StructuredOption(
            "Not sure / don't know who holds admin accounts", ANSWER_UNKNOWN
        ),
    },
    "endpoint_protection": {
        "ENDPOINT_PROTECTION_ALL": StructuredOption(
            "All work devices have endpoint protection", ANSWER_YES
        ),
        "ENDPOINT_PROTECTION_MOST": StructuredOption(
            "Most/some work devices have it, not all", ANSWER_PARTIAL
        ),
        "ENDPOINT_PROTECTION_COMPANY_ONLY": StructuredOption(
            "Company devices do, personal/BYOD devices don't", ANSWER_PARTIAL
        ),
        "ENDPOINT_PROTECTION_NONE": StructuredOption(
            "No endpoint protection in place", ANSWER_NO
        ),
        "ENDPOINT_PROTECTION_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "patching": {
        "PATCHING_AUTOMATIC": StructuredOption(
            "Automatic updates enabled everywhere, checked regularly", ANSWER_YES
        ),
        "PATCHING_MOSTLY_CURRENT": StructuredOption(
            "Updates mostly kept current, some gaps", ANSWER_PARTIAL
        ),
        "PATCHING_IRREGULAR": StructuredOption(
            "Updates happen irregularly / only when something breaks", ANSWER_PARTIAL
        ),
        "PATCHING_NONE": StructuredOption(
            "No consistent update practice", ANSWER_NO
        ),
        "PATCHING_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "device_encryption": {
        "DEVICE_ENCRYPTION_ALL": StructuredOption(
            "Enabled on all relevant devices", ANSWER_YES
        ),
        "DEVICE_ENCRYPTION_SOME": StructuredOption(
            "Enabled on some, not all", ANSWER_PARTIAL
        ),
        "DEVICE_ENCRYPTION_NONE": StructuredOption(
            "Not enabled", ANSWER_NO
        ),
        "DEVICE_ENCRYPTION_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "backups": {
        "BACKUPS_TESTED": StructuredOption(
            "Backed up AND a restore has been tested", ANSWER_YES
        ),
        "BACKUPS_RESTORE_UNTESTED": StructuredOption(
            "Backed up, but a restore has never been tested", ANSWER_PARTIAL
        ),
        "BACKUPS_COVERAGE_PARTIAL": StructuredOption(
            "Backed up, but only some systems/data are covered", ANSWER_PARTIAL
        ),
        "BACKUPS_NONE": StructuredOption(
            "Not backed up", ANSWER_NO
        ),
        "BACKUPS_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "joiner_mover_leaver": {
        "JML_DEFINED_FOLLOWED": StructuredOption(
            "Defined process, followed consistently", ANSWER_YES
        ),
        "JML_INFORMAL_USUALLY": StructuredOption(
            "Informal process, usually followed", ANSWER_PARTIAL
        ),
        "JML_INCONSISTENT": StructuredOption(
            "Happens inconsistently / depends who remembers", ANSWER_PARTIAL
        ),
        "JML_NONE": StructuredOption(
            "No process", ANSWER_NO
        ),
        "JML_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
        "JML_NOT_APPLICABLE": StructuredOption(
            "Not applicable - confirmed single person with system access, "
            "no other staff, contractor or shared/service accounts exist",
            ANSWER_NOT_APPLICABLE,
        ),
    },
    "privileged_access_separation": {
        "PRIV_SEP_DEDICATED": StructuredOption(
            "Dedicated separate admin accounts, used only for admin tasks", ANSWER_YES
        ),
        "PRIV_SEP_SOME": StructuredOption(
            "Some separation, not consistently used", ANSWER_PARTIAL
        ),
        "PRIV_SEP_NONE": StructuredOption(
            "Same account used for both", ANSWER_NO
        ),
        "PRIV_SEP_NOT_SURE": StructuredOption(
            "Not sure / don't know who has admin access", ANSWER_UNKNOWN
        ),
    },
    "security_awareness_training": {
        "AWARENESS_REGULAR": StructuredOption(
            "Regular, structured awareness activity", ANSWER_YES
        ),
        "AWARENESS_OCCASIONAL": StructuredOption(
            "Occasional/informal", ANSWER_PARTIAL
        ),
        "AWARENESS_NONE": StructuredOption(
            "No training provided", ANSWER_NO
        ),
        "AWARENESS_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "incident_reporting_route": {
        "INCIDENT_ROUTE_CLEAR": StructuredOption(
            "Clear, known route and a named responsible person", ANSWER_YES
        ),
        "INCIDENT_ROUTE_INFORMAL": StructuredOption(
            "Staff mostly know who to tell, but it's informal", ANSWER_PARTIAL
        ),
        "INCIDENT_ROUTE_NONE": StructuredOption(
            "No clear route", ANSWER_NO
        ),
        "INCIDENT_ROUTE_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "email_phishing_protection": {
        "PHISHING_PROTECTION_ACTIVE_ALL": StructuredOption(
            "Active anti-phishing protection enabled on all business email", ANSWER_YES
        ),
        "PHISHING_PROTECTION_BASIC_DEFAULT": StructuredOption(
            "Basic/default platform filtering only, nothing extra configured", ANSWER_PARTIAL
        ),
        "PHISHING_PROTECTION_PARTIAL": StructuredOption(
            "Enabled for some accounts/domains, not all", ANSWER_PARTIAL
        ),
        "PHISHING_PROTECTION_NONE": StructuredOption(
            "No specific protection beyond whatever arrives by default", ANSWER_NO
        ),
        "PHISHING_PROTECTION_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
    },
    "remote_access_control": {
        "REMOTE_ACCESS_GOVERNED": StructuredOption(
            "Governed remote access for all applicable work", ANSWER_YES
        ),
        "REMOTE_ACCESS_SOME_UNMANAGED": StructuredOption(
            "Some unmanaged/unguarded remote access paths exist", ANSWER_PARTIAL
        ),
        "REMOTE_ACCESS_NONE_GOVERNED": StructuredOption(
            "No control over remote access", ANSWER_NO
        ),
        "REMOTE_ACCESS_NOT_SURE": StructuredOption(
            "Not sure", ANSWER_UNKNOWN
        ),
        "REMOTE_ACCESS_NOT_APPLICABLE": StructuredOption(
            "Not applicable - confirmed no remote/offsite access exists",
            ANSWER_NOT_APPLICABLE,
        ),
    },
}

assert set(STRUCTURED_OPTIONS.keys()) == set(CATALOGUE_KEYS), (
    "security_baseline.structured_catalogue must cover exactly the same "
    "12 control keys as security_baseline.catalogue - never more, never "
    "fewer."
)

# Only these two controls have a NOT_APPLICABLE option at all (M008B-
# QUESTION-CATALOGUE.md Revision 2 removed it everywhere else).
CONTROLS_WITH_NOT_APPLICABLE_OPTION = frozenset(
    {"joiner_mover_leaver", "remote_access_control"}
)

for _control_key, _options in STRUCTURED_OPTIONS.items():
    _has_na = any(
        option.derived_answer == ANSWER_NOT_APPLICABLE for option in _options.values()
    )
    assert _has_na == (_control_key in CONTROLS_WITH_NOT_APPLICABLE_OPTION), (
        f"{_control_key!r}'s NOT_APPLICABLE option presence does not match "
        "CONTROLS_WITH_NOT_APPLICABLE_OPTION."
    )
del _control_key, _options, _has_na


class UnknownControlKeyError(KeyError):
    """Raised when `resolve_option` is called with a `control_key` that is
    not one of the 12 real `security_baseline.catalogue` control keys."""


class UnknownOptionCodeError(KeyError):
    """Raised when `resolve_option` is called with an `option_code` that is
    not a real, defined option for the given (valid) `control_key`."""


def resolve_option(control_key: str, option_code: str) -> StructuredOption:
    """
    Resolves a (control_key, option_code) pair to its `StructuredOption`
    (`label`, `derived_answer`).

    Never trusts a caller's claimed derived answer, and never silently
    falls back to a default for an unrecognised pair - raises
    `UnknownControlKeyError` if `control_key` is not a real catalogue
    control, or `UnknownOptionCodeError` if `option_code` is not a real,
    defined option for that (valid) control.
    """
    try:
        options = STRUCTURED_OPTIONS[control_key]
    except KeyError:
        raise UnknownControlKeyError(
            f"{control_key!r} is not a known security_baseline control key."
        ) from None

    try:
        return options[option_code]
    except KeyError:
        raise UnknownOptionCodeError(
            f"{option_code!r} is not a known option code for control "
            f"{control_key!r}."
        ) from None
