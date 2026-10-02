"""
M008D-WI4 — the implementation-status projection (docs/design/
M008D-POLICY-ARCHITECTURE.md §3, docs/design/M008D-POLICY-TRUTH-MATRIX.md
Table 2).

Deterministic, zero-AI, LIVE-COMPUTED, NEVER PERSISTED. This is the
"current state + gap/action, keyed to the exact `option_code` selected"
view that sits ALONGSIDE the normative policy (`policy.clause_library`)
but is never rendered into the distributable PDF (see
`docs/design/M008D-POLICY-ARCHITECTURE.md` §3-4 and `policy.pdf`'s own
module docstring - nothing in this module is ever passed to
`render_policy_pdf`).

== Live, never persisted - the judgement call this module makes explicit ==

`implementation_status_for_organisation` re-derives its result FRESH from
`security_baseline.models.AnswerSelectionDetail`/`BaselineAnswer` on every
call - it is never cached on `PolicyVersion`, never written anywhere. This
follows the exact "never trust a stale snapshot" discipline
`risk_register.scenario_engine.current_trigger_variant`/
`current_unconfirmed_control_keys` already established in this codebase
(M008C-WI3) for the equivalent problem (a risk's own stored fields can go
stale the moment the organisation's baseline answers change after the risk
was instantiated - the fix there was the same one applied here: re-resolve
against CURRENT canonical state on every read, never read back something
computed earlier).

This is also the right default independently of that precedent, for a
reason specific to this WI: `PolicyVersion.sections` is a FROZEN,
versioned artefact once approved (`policy.models.PolicyVersion.save()`'s
immutability guard) - a customer's Implementation status view, by
contrast, is explicitly a live, in-product REVIEW screen
(`docs/design/M008D-POLICY-ARCHITECTURE.md` §4: "surfaced only in the
in-product 'Implementation status' review screen"), not a frozen artefact
of its own. Persisting it onto (or alongside) a `PolicyVersion` would
create a second place "current state" could silently drift out of sync
with the organisation's real, continuously-changing `BaselineAnswer`/
`AnswerSelectionDetail` rows - exactly the "second control-truth system"
`policy.services._deterministic_review_warnings`'s own docstring already
warns against for a different but structurally identical reason. Computing
it fresh, every time, from the same `security_baseline.structured_catalogue.
STRUCTURED_OPTIONS` this app's other canonical consumers already trust,
is therefore not merely compliant with the architecture note - it is this
module's own, independently-justified choice.

== Status derivation - never a parallel truth system ==

`status` is DERIVED from `security_baseline.structured_catalogue.
STRUCTURED_OPTIONS[control_key][option_code].derived_answer` every time -
never hand-maintained as a second value that could drift from the real
option->answer mapping (`_status_for_derived_answer` below is the ONE
place this mapping is expressed). `MET` for YES/NOT_APPLICABLE, `GAP` for
NO/PARTIAL, `NOT_YET_CONFIRMED` for UNKNOWN - the exact three-way split
`docs/design/M008D-POLICY-TRUTH-MATRIX.md` §3 specifies, preserving the
`UNKNOWN != NO` doctrine (never silently folded into GAP) that this
codebase's catalogue-level `ANSWER_UNKNOWN` discipline already requires
throughout.

== The "distinct option, same canonical state, distinct text" rule ==

`IMPLEMENTATION_STATUS_TEXT` gives every `option_code` its OWN
`current_state_text`/`action_text` pair - never a single generic sentence
shared between two options that collapse to the same canonical answer. The
dispatch names five controls Table 2 already gives worked, approved text
for (`mfa_user_accounts`, `endpoint_protection`, `patching`, `backups`,
`email_phishing_protection` - transcribed verbatim below) and states "the
other seven controls have exactly one PARTIAL (or no PARTIAL) option each,
so no collapsing risk exists for them".

Cross-checked directly against `security_baseline.structured_catalogue.
STRUCTURED_OPTIONS` (not merely against the design document's own prose):
that count is off by two. `mfa_privileged_accounts` (`MFA_ADMIN_SOME_
REQUIRED` / `MFA_ADMIN_AVAILABLE_NOT_ENFORCED`) and `joiner_mover_leaver`
(`JML_INFORMAL_USUALLY` / `JML_INCONSISTENT`) ALSO carry two distinct
PARTIAL-mapped options each, exactly like the five controls Table 2 names
- the structured catalogue was evidently extended after the truth matrix
document's "seven simple controls" count was written, and that count was
never updated to match. This is flagged as a documentation discrepancy in
the Engineer's report, not silently corrected by quietly matching the
doc's wrong count: Table 2's own stated HARD RULE ("every PARTIAL-mapped
option gets its own, specific current-state and action sentence pair -
never a single generic... sentence shared across options that mean
different things") is honoured literally for BOTH of these two controls
below too, each with its own distinct, self-authored pair - rather than
honouring the doc's incidental "five/seven" tally, which is merely
descriptive of an instance count and demonstrably wrong against the actual
shipped catalogue.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
    AnswerSelectionDetail,
    BaselineAssessment,
)
from security_baseline.structured_catalogue import STRUCTURED_OPTIONS

STATUS_MET = "met"
STATUS_GAP = "gap"
STATUS_NOT_YET_CONFIRMED = "not_yet_confirmed"

_STATUS_BY_DERIVED_ANSWER = {
    ANSWER_YES: STATUS_MET,
    ANSWER_NOT_APPLICABLE: STATUS_MET,
    ANSWER_NO: STATUS_GAP,
    ANSWER_PARTIAL: STATUS_GAP,
    ANSWER_UNKNOWN: STATUS_NOT_YET_CONFIRMED,
}


def _status_for_derived_answer(derived_answer: str) -> str:
    """The ONE place a `security_baseline` canonical answer is mapped to
    this projection's three-way `status` - see module docstring. Raises
    `KeyError` for anything outside the five real `ANSWER_*` values, same
    fail-loud discipline `security_baseline.structured_catalogue.
    resolve_option` already applies to an unrecognised option_code."""
    return _STATUS_BY_DERIVED_ANSWER[derived_answer]


@dataclasses.dataclass(frozen=True)
class ImplementationStatusText:
    """One option_code's fixed `(current_state_text, action_text)` pair -
    see `IMPLEMENTATION_STATUS_TEXT` below. `action_text` is `""` for a
    MET-only option_code (YES/NOT_APPLICABLE) - a clean position needs no
    suggested action; see module-level catalogue comment for why a
    `current_state_text` is still written for every option regardless."""

    current_state_text: str
    action_text: str = ""


# control_key -> {option_code: ImplementationStatusText}. Every option_code
# `security_baseline.structured_catalogue.STRUCTURED_OPTIONS` defines gets
# an entry here - asserted below. The five controls Table 2
# (docs/design/M008D-POLICY-TRUTH-MATRIX.md) gives verbatim worked text for
# are transcribed exactly; every other entry is self-authored, grounded in
# `security_baseline.stage4.QUESTION_COPY`/`EXPLAINER_TEXT`'s own subject
# matter for that control (never inventing new subject matter), in the
# same short, factual register Table 2's own given examples use.
IMPLEMENTATION_STATUS_TEXT: "dict[str, dict[str, ImplementationStatusText]]" = {
    "mfa_user_accounts": {
        "MFA_USER_ALL_REQUIRED": ImplementationStatusText(
            "MFA is required for all staff accounts."
        ),
        # Table 2 verbatim.
        "MFA_USER_SOME_REQUIRED": ImplementationStatusText(
            "MFA is currently required for some staff accounts, not all.",
            "Extend MFA enforcement to every staff account.",
        ),
        # Table 2 verbatim.
        "MFA_USER_AVAILABLE_NOT_ENFORCED": ImplementationStatusText(
            "MFA is available for staff accounts but not enforced.",
            "Enforce MFA, not merely offer it.",
        ),
        "MFA_USER_NOT_USED": ImplementationStatusText(
            "No MFA is currently used for staff accounts.",
            "Introduce MFA for all staff accounts.",
        ),
        "MFA_USER_NOT_SURE": ImplementationStatusText(
            "Whether MFA is used for staff accounts has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "mfa_privileged_accounts": {
        "MFA_ADMIN_ALL_REQUIRED": ImplementationStatusText(
            "MFA is required for all admin/privileged accounts."
        ),
        # Self-authored - see module docstring's documented discrepancy
        # with Table 2's "seven simple controls" count.
        "MFA_ADMIN_SOME_REQUIRED": ImplementationStatusText(
            "MFA is currently required for some admin accounts, not all.",
            "Extend MFA enforcement to every admin/privileged account.",
        ),
        "MFA_ADMIN_AVAILABLE_NOT_ENFORCED": ImplementationStatusText(
            "MFA is available for admin accounts but not enforced.",
            "Enforce MFA for admin accounts, not merely offer it.",
        ),
        "MFA_ADMIN_NOT_USED": ImplementationStatusText(
            "No MFA is currently used for admin/privileged accounts.",
            "Introduce MFA for all admin/privileged accounts.",
        ),
        "MFA_ADMIN_NOT_SURE": ImplementationStatusText(
            "Whether MFA is used for admin/privileged accounts has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "endpoint_protection": {
        "ENDPOINT_PROTECTION_ALL": ImplementationStatusText(
            "Endpoint protection is in place on all work devices."
        ),
        # Table 2 verbatim.
        "ENDPOINT_PROTECTION_MOST": ImplementationStatusText(
            "Endpoint protection is in place for most, not all, devices.",
            "Extend coverage to the remaining devices.",
        ),
        # Table 2 verbatim.
        "ENDPOINT_PROTECTION_COMPANY_ONLY": ImplementationStatusText(
            "Company devices are protected; personal/BYOD devices are not.",
            "Extend protection to personally owned devices used for work.",
        ),
        "ENDPOINT_PROTECTION_NONE": ImplementationStatusText(
            "No endpoint protection is currently in place.",
            "Put endpoint protection in place on work devices.",
        ),
        "ENDPOINT_PROTECTION_NOT_SURE": ImplementationStatusText(
            "Whether endpoint protection is in place has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "patching": {
        "PATCHING_AUTOMATIC": ImplementationStatusText(
            "Updates are automatic and checked regularly."
        ),
        # Table 2 verbatim.
        "PATCHING_MOSTLY_CURRENT": ImplementationStatusText(
            "Updates are mostly kept current, with some gaps.",
            "Close the remaining patching gaps.",
        ),
        # Table 2 verbatim.
        "PATCHING_IRREGULAR": ImplementationStatusText(
            "Updates happen irregularly, with no consistent cadence.",
            "Establish a routine patching cadence.",
        ),
        "PATCHING_NONE": ImplementationStatusText(
            "No consistent update practice is in place.",
            "Establish a routine for keeping software up to date.",
        ),
        "PATCHING_NOT_SURE": ImplementationStatusText(
            "Whether software is kept up to date has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "device_encryption": {
        "DEVICE_ENCRYPTION_ALL": ImplementationStatusText(
            "Full-disk encryption is enabled on all relevant devices."
        ),
        "DEVICE_ENCRYPTION_SOME": ImplementationStatusText(
            "Encryption is enabled on some devices, not all.",
            "Extend encryption to the remaining devices.",
        ),
        "DEVICE_ENCRYPTION_NONE": ImplementationStatusText(
            "No devices currently have full-disk encryption enabled.",
            "Enable full-disk encryption on devices that hold business data.",
        ),
        "DEVICE_ENCRYPTION_NOT_SURE": ImplementationStatusText(
            "Whether full-disk encryption is enabled has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "backups": {
        "BACKUPS_TESTED": ImplementationStatusText(
            "Data is backed up and a restore has actually been tested."
        ),
        # Table 2 verbatim - Central Architecture's own named example.
        "BACKUPS_RESTORE_UNTESTED": ImplementationStatusText(
            "Backups exist but a restore has never been tested.",
            "Schedule and carry out a test restore.",
        ),
        # Table 2 verbatim - Central Architecture's own named example.
        "BACKUPS_COVERAGE_PARTIAL": ImplementationStatusText(
            "Backups exist but do not cover all systems/data.",
            "Extend backup coverage to the remaining systems.",
        ),
        "BACKUPS_NONE": ImplementationStatusText(
            "No backups currently exist.",
            "Put a backup process in place for important business data.",
        ),
        "BACKUPS_NOT_SURE": ImplementationStatusText(
            "Whether data is backed up has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "joiner_mover_leaver": {
        "JML_DEFINED_FOLLOWED": ImplementationStatusText(
            "A defined access-removal process exists and is followed consistently."
        ),
        # Self-authored - see module docstring's documented discrepancy
        # with Table 2's "seven simple controls" count.
        "JML_INFORMAL_USUALLY": ImplementationStatusText(
            "An informal process exists and is usually followed.",
            "Formalise the access-removal process so it does not depend on memory.",
        ),
        "JML_INCONSISTENT": ImplementationStatusText(
            "Access removal happens inconsistently, depending on who remembers.",
            "Establish and follow a consistent process every time someone leaves or changes role.",
        ),
        "JML_NONE": ImplementationStatusText(
            "No process exists for removing access when someone leaves or changes role.",
            "Put a process in place for removing or adjusting access promptly.",
        ),
        "JML_NOT_SURE": ImplementationStatusText(
            "Whether access is removed promptly has not yet been confirmed.",
            "Confirm current practice.",
        ),
        "JML_NOT_APPLICABLE": ImplementationStatusText(
            "Not applicable — confirmed that only one person has system "
            "access and no other staff, contractor or shared/service "
            "accounts exist."
        ),
    },
    "privileged_access_separation": {
        "PRIV_SEP_DEDICATED": ImplementationStatusText(
            "Admin tasks are carried out from a dedicated, separate account."
        ),
        "PRIV_SEP_SOME": ImplementationStatusText(
            "Some separation exists between admin and everyday accounts, but it is not used consistently.",
            "Use a dedicated admin account consistently for admin tasks.",
        ),
        "PRIV_SEP_NONE": ImplementationStatusText(
            "The same account is currently used for both admin tasks and everyday use.",
            "Set up a dedicated, separate account for admin tasks.",
        ),
        "PRIV_SEP_NOT_SURE": ImplementationStatusText(
            "Whether admin access is kept separate has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "security_awareness_training": {
        "AWARENESS_REGULAR": ImplementationStatusText(
            "Staff receive regular, structured security-awareness activity."
        ),
        "AWARENESS_OCCASIONAL": ImplementationStatusText(
            "Awareness activity happens, but only occasionally or informally.",
            "Put regular, structured security-awareness activity in place.",
        ),
        "AWARENESS_NONE": ImplementationStatusText(
            "No security-awareness training is currently provided.",
            "Introduce regular security-awareness activity for staff.",
        ),
        "AWARENESS_NOT_SURE": ImplementationStatusText(
            "Whether staff receive security-awareness activity has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "incident_reporting_route": {
        "INCIDENT_ROUTE_CLEAR": ImplementationStatusText(
            "There is a clear, known route and a named responsible person for reporting incidents."
        ),
        "INCIDENT_ROUTE_INFORMAL": ImplementationStatusText(
            "Staff mostly know who to tell, but the route is informal.",
            "Establish and communicate a clear, formal incident-reporting route.",
        ),
        "INCIDENT_ROUTE_NONE": ImplementationStatusText(
            "No clear incident-reporting route currently exists.",
            "Put a clear incident-reporting route in place and communicate it to staff.",
        ),
        "INCIDENT_ROUTE_NOT_SURE": ImplementationStatusText(
            "Whether a clear incident-reporting route exists has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "email_phishing_protection": {
        "PHISHING_PROTECTION_ACTIVE_ALL": ImplementationStatusText(
            "Active anti-phishing protection is enabled on all business email."
        ),
        # Table 2 verbatim.
        "PHISHING_PROTECTION_BASIC_DEFAULT": ImplementationStatusText(
            "Only basic/default platform filtering is in place, nothing extra configured.",
            "Enable active anti-phishing protection beyond platform defaults.",
        ),
        # Table 2 verbatim.
        "PHISHING_PROTECTION_PARTIAL": ImplementationStatusText(
            "Active protection is enabled for some accounts/domains, not all.",
            "Extend protection to every account/domain.",
        ),
        "PHISHING_PROTECTION_NONE": ImplementationStatusText(
            "No specific protection beyond whatever arrives by default.",
            "Enable active anti-phishing protection for business email.",
        ),
        "PHISHING_PROTECTION_NOT_SURE": ImplementationStatusText(
            "Whether email is protected against phishing has not yet been confirmed.",
            "Confirm current practice.",
        ),
    },
    "remote_access_control": {
        "REMOTE_ACCESS_GOVERNED": ImplementationStatusText(
            "Remote access is governed for all applicable work."
        ),
        "REMOTE_ACCESS_SOME_UNMANAGED": ImplementationStatusText(
            "Some remote access paths are unmanaged or unguarded.",
            "Bring the remaining remote access paths under control.",
        ),
        "REMOTE_ACCESS_NONE_GOVERNED": ImplementationStatusText(
            "There is currently no control over remote access.",
            "Put controls in place over remote access to business systems.",
        ),
        "REMOTE_ACCESS_NOT_SURE": ImplementationStatusText(
            "Whether remote access is controlled has not yet been confirmed.",
            "Confirm current practice.",
        ),
        "REMOTE_ACCESS_NOT_APPLICABLE": ImplementationStatusText(
            "Not applicable — confirmed that no remote or offsite access exists."
        ),
    },
}

# --- Catalogue-wide invariants (assert-at-import-time) ---------------------
assert set(IMPLEMENTATION_STATUS_TEXT.keys()) == set(CATALOGUE_KEYS), (
    "policy.implementation_status.IMPLEMENTATION_STATUS_TEXT must cover "
    "exactly the same 12 control keys as security_baseline.catalogue."
)
for _control_key, _options in STRUCTURED_OPTIONS.items():
    assert set(IMPLEMENTATION_STATUS_TEXT[_control_key].keys()) == set(_options.keys()), (
        f"policy.implementation_status.IMPLEMENTATION_STATUS_TEXT[{_control_key!r}] "
        "must cover exactly the same option_codes as "
        "security_baseline.structured_catalogue.STRUCTURED_OPTIONS[{_control_key!r}]."
    )
del _control_key, _options

# Reflects "the implementation-status projection, keyed to the exact
# option_code selected" (never a hand-picked second status value) - every
# MET-mapped option has empty action_text, every non-MET option has a
# non-empty one, checked directly against STRUCTURED_OPTIONS's own
# derived_answer so this invariant cannot silently drift.
for _control_key, _options in STRUCTURED_OPTIONS.items():
    for _option_code, _option in _options.items():
        _text = IMPLEMENTATION_STATUS_TEXT[_control_key][_option_code]
        _status = _status_for_derived_answer(_option.derived_answer)
        if _status == STATUS_MET:
            assert _text.action_text == "", (
                f"{_control_key}/{_option_code} resolves to MET but has a "
                "non-empty action_text - a clean/not-applicable position "
                "should carry no suggested action."
            )
        else:
            assert _text.action_text != "", (
                f"{_control_key}/{_option_code} resolves to {_status} but "
                "has an empty action_text."
            )
del _control_key, _options, _option_code, _option, _text, _status


@dataclasses.dataclass(frozen=True)
class ImplementationStatusRow:
    """One control's current implementation-status row (docs/design/
    M008D-POLICY-TRUTH-MATRIX.md Table 2's own shape).

    `option_code` is `None` when this control has never been reviewed
    through the structured Stage 4 flow at all (no `AnswerSelectionDetail`
    row exists) - `status` is then always `STATUS_NOT_YET_CONFIRMED`,
    regardless of whether some OTHER, non-structured answer happens to
    exist for this control (see `implementation_status_for_organisation`'s
    own docstring for why a legacy, non-option-level answer is never
    allowed to produce a MET/GAP row here)."""

    control_key: str
    option_code: Optional[str]
    status: str
    current_state_text: str
    action_text: str


_NOT_YET_REVIEWED_TEXT = ImplementationStatusText(
    current_state_text="This control has not yet been reviewed.",
    action_text="Complete the structured review question for this control.",
)


def implementation_status_for_organisation(organisation) -> "list[ImplementationStatusRow]":
    """
    The CURRENT implementation-status row for every one of the 12
    `security_baseline.catalogue` controls, in `CATALOGUE_KEYS` order -
    always exactly 12 rows, regardless of how much of Stage 4 has been
    completed (an unreviewed control still gets a row, with
    `status=STATUS_NOT_YET_CONFIRMED` - see class docstring).

    Re-derived FRESH from `security_baseline.models.AnswerSelectionDetail`
    on every call - see module docstring's "live, never persisted"
    discussion. Only a control with an actual `AnswerSelectionDetail` row
    (i.e. genuinely reviewed through the structured Stage 4 one-question-
    at-a-time flow, M008C) can ever resolve to `STATUS_MET`/`STATUS_GAP` -
    a control answered only through the older, pre-M008B free-form
    baseline path (a `BaselineAnswer` with no matching
    `AnswerSelectionDetail`) is deliberately still reported as
    `STATUS_NOT_YET_CONFIRMED` here: this projection's whole mechanism is
    "keyed to the exact option_code selected" (`docs/design/
    M008D-POLICY-TRUTH-MATRIX.md` §3), and a legacy answer has no
    option_code to key on - treating it as confirmed would mean guessing
    which option it corresponds to, which this module never does.

    `organisation` with no `BaselineAssessment` row at all (Stage 4 never
    started) is handled identically to one with an assessment but no
    `AnswerSelectionDetail` rows yet - both produce 12
    `STATUS_NOT_YET_CONFIRMED` rows, never a missing/short list and never
    an exception.
    """
    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()

    details_by_control_key = {}
    if assessment is not None:
        details_by_control_key = {
            detail.question_key: detail
            for detail in AnswerSelectionDetail.objects.filter(
                assessment=assessment, question_key__in=CATALOGUE_KEYS
            )
        }

    rows = []
    for control_key in CATALOGUE_KEYS:
        detail = details_by_control_key.get(control_key)
        if detail is None:
            text = _NOT_YET_REVIEWED_TEXT
            rows.append(
                ImplementationStatusRow(
                    control_key=control_key,
                    option_code=None,
                    status=STATUS_NOT_YET_CONFIRMED,
                    current_state_text=text.current_state_text,
                    action_text=text.action_text,
                )
            )
            continue

        option_code = detail.option_code
        option = STRUCTURED_OPTIONS.get(control_key, {}).get(option_code)
        if option is None:
            # Defensive only - unreachable in practice while
            # `record_structured_baseline_answer` remains the sole write
            # path for `AnswerSelectionDetail` (it validates option_code
            # against this exact catalogue before writing). Guards against
            # a retired option_code left behind by a future catalogue
            # change, rather than raising out of a read-only projection.
            rows.append(
                ImplementationStatusRow(
                    control_key=control_key,
                    option_code=option_code,
                    status=STATUS_NOT_YET_CONFIRMED,
                    current_state_text=(
                        "This control's recorded answer no longer matches a "
                        "known option - review and re-confirm it."
                    ),
                    action_text="Re-confirm current practice for this control.",
                )
            )
            continue

        status = _status_for_derived_answer(option.derived_answer)
        text = IMPLEMENTATION_STATUS_TEXT[control_key][option_code]
        rows.append(
            ImplementationStatusRow(
                control_key=control_key,
                option_code=option_code,
                status=status,
                current_state_text=text.current_state_text,
                action_text=text.action_text,
            )
        )

    return rows


__all__ = [
    "STATUS_MET",
    "STATUS_GAP",
    "STATUS_NOT_YET_CONFIRMED",
    "ImplementationStatusText",
    "IMPLEMENTATION_STATUS_TEXT",
    "ImplementationStatusRow",
    "implementation_status_for_organisation",
]
