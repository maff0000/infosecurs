"""
M008C — the guided, one-question-at-a-time Stage 4 journey
(docs/design/M008C-UX-FLOW-DESIGN.md).

This module is the view-layer home for everything `security_baseline.
structured_catalogue` deliberately does NOT own (see that module's own
docstring): which `option_code`s are actually OFFERED to a given
organisation right now (NOT_APPLICABLE re-gating, plus the pre-existing
`endpoint_protection` BYOD option-set conditioning), the customer-facing
question copy approved in docs/design/M008B-QUESTION-CATALOGUE.md
(deliberately NOT `security_baseline.catalogue`'s own `question`/
`help_text` fields, which are a different, older wording used elsewhere
and frozen for this WI), the deterministic one-sentence explainer shown
after a selection, and the stage-local REVIEWED/confirmed progress pair
(M008C-UX-FLOW-DESIGN.md §6).

Nothing here writes a model - `security_baseline.services.
record_structured_baseline_answer` remains the sole write path. This
module only derives what to show / what to allow.
"""
from __future__ import annotations

from typing import Dict, Optional

from organisations.models import OrganisationProfile
from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.models import ANSWER_NOT_APPLICABLE, ANSWER_UNKNOWN, AnswerSelectionDetail, BaselineAnswer
from security_baseline.structured_catalogue import STRUCTURED_OPTIONS, StructuredOption

# ---------------------------------------------------------------------------
# Approved customer-facing copy (docs/design/M008B-QUESTION-CATALOGUE.md,
# Revision 2) - deliberately separate from security_baseline.catalogue.
# CATALOGUE_BY_KEY's own `question`/`help_text`, which this WI must not
# change (already correctly frozen by WI1) and which are different,
# older wording used by other, unrelated pages. `title` is the short
# customer-facing control name the design doc gives each control (e.g.
# "Staff sign-in protection"); `question` and `why_it_matters` are
# transcribed verbatim from that document.
# ---------------------------------------------------------------------------
QUESTION_COPY: Dict[str, Dict[str, str]] = {
    "mfa_user_accounts": {
        "title": "Staff sign-in protection",
        "question": (
            "How is multi-factor authentication (MFA) used for ordinary "
            "staff accounts (e.g. Microsoft 365, Google Workspace)?"
        ),
        "why_it_matters": (
            "MFA is one of the single most effective protections against "
            "stolen-password account takeover — without it, a leaked or "
            "guessed password is often enough to get in."
        ),
    },
    "mfa_privileged_accounts": {
        "title": "Admin/privileged account protection",
        "question": (
            "How is multi-factor authentication used for admin/privileged "
            "accounts (e.g. IT admin, cloud admin, domain admin)?"
        ),
        "why_it_matters": (
            "Admin accounts can change settings for everyone — if one is "
            "compromised, the attacker can often disable other protections "
            "too."
        ),
    },
    "endpoint_protection": {
        "title": "Device protection",
        "question": "Do the devices staff use for work have anti-malware/endpoint protection?",
        "why_it_matters": (
            "Protects against malware and ransomware that could spread "
            "from an infected device into the rest of the business."
        ),
    },
    "patching": {
        "title": "Keeping software up to date",
        "question": (
            "Are operating systems and business applications kept up to "
            "date with security updates?"
        ),
        "why_it_matters": (
            "Unpatched software is one of the most common ways attackers "
            "get in — many attacks exploit a known, already-fixed flaw."
        ),
    },
    "device_encryption": {
        "title": "Protecting data if a device is lost or stolen",
        "question": (
            "Is full-disk encryption (e.g. BitLocker, FileVault) enabled "
            "on devices that hold business data?"
        ),
        "why_it_matters": (
            "If a laptop is lost or stolen, encryption is what stops "
            "someone simply reading the files off the drive."
        ),
    },
    "backups": {
        "title": "Backups you can actually restore from",
        "question": (
            "Is important business data backed up, and has anyone "
            "actually tried restoring from that backup?"
        ),
        "why_it_matters": (
            "A backup nobody has tested is a hope, not a safeguard — "
            "ransomware and accidental deletion are the two most common "
            "reasons businesses need to restore."
        ),
    },
    "joiner_mover_leaver": {
        "title": "Removing access when someone leaves or changes role",
        "question": (
            "When someone leaves the business or changes role, is their "
            "access removed or adjusted promptly?"
        ),
        "why_it_matters": (
            "Former staff keeping access after they leave is a common, "
            "avoidable way confidential information or systems stay "
            "exposed."
        ),
    },
    "privileged_access_separation": {
        "title": "Keeping admin access separate from everyday accounts",
        "question": (
            "Do people with admin/privileged access use a separate "
            "account for admin tasks, rather than their everyday login?"
        ),
        "why_it_matters": (
            "If the same account does admin tasks and everyday "
            "email/browsing, one phishing click can hand over admin-level "
            "access."
        ),
    },
    "security_awareness_training": {
        "title": "Helping staff recognise security risks",
        "question": (
            "Do staff get any security-awareness training, such as how "
            "to recognise phishing emails?"
        ),
        "why_it_matters": (
            "Most breaches start with a person, not a technical flaw — a "
            "little awareness goes a long way."
        ),
    },
    "incident_reporting_route": {
        "title": "Knowing who to tell if something goes wrong",
        "question": (
            "If a staff member suspects a security incident (e.g. "
            "clicked a bad link, lost a device), do they know who to "
            "tell and what happens next?"
        ),
        "why_it_matters": (
            "Fast reporting limits damage — a known route means problems "
            "get handled in minutes, not discovered weeks later."
        ),
    },
    "email_phishing_protection": {
        "title": "Protecting email from phishing and spam",
        "question": (
            "Are there protections against phishing and malicious email, "
            "beyond normal spam filtering?"
        ),
        "why_it_matters": (
            "Email remains the single most common way attackers first "
            "get in — filtering reduces how many malicious messages "
            "staff ever see."
        ),
    },
    "remote_access_control": {
        "title": "Controlling how systems are reached remotely",
        "question": (
            "Where staff work remotely or access systems away from the "
            "office, is there control over how that access happens (e.g. "
            "VPN, conditional access)?"
        ),
        "why_it_matters": (
            "Uncontrolled remote access is an easy path in if a device "
            "or connection is compromised."
        ),
    },
}

assert set(QUESTION_COPY.keys()) == set(CATALOGUE_KEYS), (
    "security_baseline.stage4.QUESTION_COPY must cover exactly the same "
    "12 control keys as security_baseline.catalogue - never more, never "
    "fewer."
)


# ---------------------------------------------------------------------------
# NOT_APPLICABLE re-gating + endpoint_protection's BYOD option-set
# conditioning (docs/design/M008B-QUESTION-CATALOGUE.md §0; docs/design/
# M008C-UX-FLOW-DESIGN.md §2) - the single place this is decided. Every
# caller (both Stage 4 views AND key_assets' asset-specific protection
# checks page) goes through this function, never re-implements the gating
# itself.
# ---------------------------------------------------------------------------

def _profile_or_none(organisation) -> Optional[OrganisationProfile]:
    """
    `organisation.profile` if one exists, else `None` - never raises.
    An organisation with no profile row yet has confirmed none of the
    gating facts below, so every gate below is correctly treated as
    "not satisfied" (NOT_APPLICABLE/the BYOD-only option are never
    offered) rather than erroring.
    """
    try:
        return organisation.profile
    except OrganisationProfile.DoesNotExist:
        return None


def offered_options(control_key: str, organisation) -> "dict[str, StructuredOption]":
    """
    The option_codes actually OFFERED to this organisation for
    `control_key` right now, in the catalogue's own display order -
    server-derived from `OrganisationProfile` facts, never from anything
    client-supplied (a hidden field, a query parameter, or a rendered-but-
    not-really-offered option in some other response).

    This is the ONE place `StructuredAnswerForm` (security_baseline.forms)
    builds its `option_code` field's `choices` from - an option this
    function excludes can never pass that field's validation, regardless
    of what a request claims. This is deliberate defence-in-depth, not
    just a template-rendering decision: a forged POST of an unoffered
    option_code is rejected by ordinary Django ChoiceField validation
    before `security_baseline.services.record_structured_baseline_answer`
    is ever called.

    `control_key` must be one of the 12 real `security_baseline.catalogue`
    keys - raises `KeyError` otherwise (every caller in this codebase
    validates `control_key` against `CATALOGUE_KEYS`/`CATALOGUE_BY_KEY`
    before calling this).
    """
    options = STRUCTURED_OPTIONS[control_key]
    profile = _profile_or_none(organisation)

    offered: "dict[str, StructuredOption]" = {}
    for option_code, option in options.items():
        if option.derived_answer == ANSWER_NOT_APPLICABLE:
            if control_key == "joiner_mover_leaver":
                # M008B §0 / control 7: requires the CONFIRMED structured
                # fact == 1 - `staff_count` is never consulted, and a
                # missing profile is never treated as satisfying this.
                if profile is None or profile.people_with_system_access_count != 1:
                    continue
            elif control_key == "remote_access_control":
                # M008B §0 / control 12: requires the CONFIRMED structured
                # fact == "no" - never inferred from `working_model`.
                if profile is None or profile.has_remote_or_offsite_access != "no":
                    continue
            else:
                # No other control has a NOT_APPLICABLE option at all
                # (security_baseline.structured_catalogue.
                # CONTROLS_WITH_NOT_APPLICABLE_OPTION enforces this at
                # import time) - this branch is unreachable in practice,
                # kept only so a future catalogue change fails safe
                # (excluded) rather than silently offering an
                # unauthorised NOT_APPLICABLE option.
                continue
        elif control_key == "endpoint_protection" and option_code == "ENDPOINT_PROTECTION_COMPANY_ONLY":
            # Pre-existing option-set conditioning (M008B control 3),
            # unrelated to the NOT_APPLICABLE correction above - only
            # ever offered to a confirmed BYOD/both organisation.
            if profile is None or profile.endpoint_management not in ("byod", "both"):
                continue
        offered[option_code] = option
    return offered


# ---------------------------------------------------------------------------
# Deterministic, one-sentence explainer text (M008B §B5 / M008C §3.4) -
# shown immediately after a selection, never from any AI call. "Not sure"
# gets the same honest, non-corrective wording regardless of which
# control (M008C-UX-FLOW-DESIGN.md §4), so it is handled uniformly below
# rather than duplicated per control.
# ---------------------------------------------------------------------------
NOT_SURE_EXPLAINER = (
    "We'll mark this as not yet confirmed — you can come back to it any time."
)

EXPLAINER_TEXT: Dict[str, Dict[str, str]] = {
    "mfa_user_accounts": {
        "MFA_USER_ALL_REQUIRED": (
            "All staff accounts are protected by MFA — this is the "
            "strongest position for this control."
        ),
        "MFA_USER_SOME_REQUIRED": (
            "MFA is enforced for some staff or groups but not all — "
            "accounts outside that group remain exposed to password-only "
            "takeover."
        ),
        "MFA_USER_AVAILABLE_NOT_ENFORCED": (
            "MFA is available but nobody is required to use it — in "
            "practice this offers little protection unless staff turn it "
            "on themselves."
        ),
        "MFA_USER_NOT_USED": (
            "No MFA is in use for staff accounts — a leaked or guessed "
            "password alone would be enough to sign in."
        ),
    },
    "mfa_privileged_accounts": {
        "MFA_ADMIN_ALL_REQUIRED": (
            "All admin/privileged accounts require MFA — this is the "
            "strongest position for this control."
        ),
        "MFA_ADMIN_SOME_REQUIRED": (
            "MFA is required for some admin accounts but not all — the "
            "uncovered admin accounts remain a high-value target."
        ),
        "MFA_ADMIN_AVAILABLE_NOT_ENFORCED": (
            "MFA is available for admin accounts but not enforced — an "
            "admin account without it is one password away from "
            "compromise."
        ),
        "MFA_ADMIN_NOT_USED": (
            "No MFA is in use for admin accounts — the accounts that can "
            "change settings for everyone are unprotected."
        ),
    },
    "endpoint_protection": {
        "ENDPOINT_PROTECTION_ALL": (
            "All work devices have endpoint protection — this is the "
            "strongest position for this control."
        ),
        "ENDPOINT_PROTECTION_MOST": (
            "Most work devices have endpoint protection but some don't — "
            "the uncovered devices are a route for malware to spread."
        ),
        "ENDPOINT_PROTECTION_COMPANY_ONLY": (
            "Company devices are protected but personal/BYOD devices used "
            "for work are not — those devices are an unprotected route in."
        ),
        "ENDPOINT_PROTECTION_NONE": (
            "No endpoint protection is in place — devices used for work "
            "have no defence against malware or ransomware."
        ),
    },
    "patching": {
        "PATCHING_AUTOMATIC": (
            "Updates are automatic and checked regularly — this is the "
            "strongest position for this control."
        ),
        "PATCHING_MOSTLY_CURRENT": (
            "Updates are mostly kept current with some gaps — those gaps "
            "are still an open door for known, already-fixed "
            "vulnerabilities."
        ),
        "PATCHING_IRREGULAR": (
            "Updates happen irregularly with no real cadence — this is a "
            "weaker position than occasional gaps, since there's no "
            "routine catching issues."
        ),
        "PATCHING_NONE": (
            "There is no consistent update practice — known, "
            "already-fixed vulnerabilities are likely to remain open."
        ),
    },
    "device_encryption": {
        "DEVICE_ENCRYPTION_ALL": (
            "Full-disk encryption is enabled on all relevant devices — "
            "this is the strongest position for this control."
        ),
        "DEVICE_ENCRYPTION_SOME": (
            "Encryption is enabled on some devices but not all — a lost "
            "or stolen unencrypted device would expose its data."
        ),
        "DEVICE_ENCRYPTION_NONE": (
            "No devices have full-disk encryption — a lost or stolen "
            "device would expose its data to anyone who finds it."
        ),
    },
    "backups": {
        "BACKUPS_TESTED": (
            "Data is backed up and a restore has actually been tested — "
            "this is the strongest position for this control."
        ),
        "BACKUPS_RESTORE_UNTESTED": (
            "Backups exist but a restore has never been tested — we'll "
            "record this honestly and suggest testing a restore as a "
            "next action."
        ),
        "BACKUPS_COVERAGE_PARTIAL": (
            "Backups exist but only cover some systems or data — we'll "
            "suggest extending coverage to the rest as a next action."
        ),
        "BACKUPS_NONE": (
            "No backups exist — data could not be recovered after loss, "
            "ransomware, or accidental deletion."
        ),
    },
    "joiner_mover_leaver": {
        "JML_DEFINED_FOLLOWED": (
            "There's a defined process for removing access and it's "
            "followed consistently — this is the strongest position for "
            "this control."
        ),
        "JML_INFORMAL_USUALLY": (
            "The process is informal but usually followed — it still "
            "broadly works, though nothing guarantees consistency."
        ),
        "JML_INCONSISTENT": (
            "Access removal happens inconsistently and depends on who "
            "remembers — this is a real process gap."
        ),
        "JML_NONE": (
            "There's no process for removing access when someone leaves "
            "or changes role — former staff may keep access they no "
            "longer need."
        ),
        "JML_NOT_APPLICABLE": (
            "Recorded as not applicable — you've confirmed only one "
            "person has system access and no other staff, contractor, "
            "or shared/service accounts exist."
        ),
    },
    "privileged_access_separation": {
        "PRIV_SEP_DEDICATED": (
            "Admin tasks are done from a dedicated, separate account — "
            "this is the strongest position for this control."
        ),
        "PRIV_SEP_SOME": (
            "There's some separation between admin and everyday accounts "
            "but it isn't used consistently — a phishing click on the "
            "shared account could still hand over admin access."
        ),
        "PRIV_SEP_NONE": (
            "The same account is used for both admin tasks and everyday "
            "use — a single phishing click could hand over admin-level "
            "access."
        ),
    },
    "security_awareness_training": {
        "AWARENESS_REGULAR": (
            "Staff get regular, structured security-awareness activity — "
            "this is the strongest position for this control."
        ),
        "AWARENESS_OCCASIONAL": (
            "Awareness activity happens but only occasionally or "
            "informally — staff may not recognise newer or less obvious "
            "threats."
        ),
        "AWARENESS_NONE": (
            "No security-awareness training is provided — staff have no "
            "structured way to recognise phishing or other common "
            "threats."
        ),
    },
    "incident_reporting_route": {
        "INCIDENT_ROUTE_CLEAR": (
            "There's a clear, known route and a named responsible person "
            "— this is the strongest position for this control."
        ),
        "INCIDENT_ROUTE_INFORMAL": (
            "Staff mostly know who to tell but it's informal — a genuine "
            "incident could still be delayed or missed."
        ),
        "INCIDENT_ROUTE_NONE": (
            "There's no clear reporting route — a genuine incident could "
            "go unreported until the damage has spread."
        ),
    },
    "email_phishing_protection": {
        "PHISHING_PROTECTION_ACTIVE_ALL": (
            "Active anti-phishing protection is enabled on all business "
            "email — this is the strongest position for this control."
        ),
        "PHISHING_PROTECTION_BASIC_DEFAULT": (
            "Only the basic/default platform filtering is in place, with "
            "nothing extra configured — this catches less than an "
            "actively configured setup would."
        ),
        "PHISHING_PROTECTION_PARTIAL": (
            "Active protection is enabled for some accounts or domains "
            "but not all — the uncovered accounts remain exposed to "
            "phishing."
        ),
        "PHISHING_PROTECTION_NONE": (
            "There's no specific protection against phishing beyond "
            "whatever arrives by default — malicious email is more "
            "likely to reach staff."
        ),
    },
    "remote_access_control": {
        "REMOTE_ACCESS_GOVERNED": (
            "Remote access is governed for all applicable work — this is "
            "the strongest position for this control."
        ),
        "REMOTE_ACCESS_SOME_UNMANAGED": (
            "Some remote access paths are unmanaged or unguarded — those "
            "paths are an easier way in if a device or connection is "
            "compromised."
        ),
        "REMOTE_ACCESS_NONE_GOVERNED": (
            "There's no control over remote access — any compromised "
            "device or connection has an open path into your systems."
        ),
        "REMOTE_ACCESS_NOT_APPLICABLE": (
            "Recorded as not applicable — you've confirmed nobody "
            "accesses systems or data remotely or offsite."
        ),
    },
}


def explainer_for(control_key: str, option_code: str, derived_answer: str) -> str:
    """
    The deterministic one-sentence explainer for an already-resolved
    (control_key, option_code, derived_answer) triple. Callers are
    expected to only call this with a triple that has actually been
    stored (or is about to be, immediately after `resolve_option`
    succeeded) - this function does not itself re-validate the pair
    against `security_baseline.structured_catalogue`.

    Every `*_NOT_SURE` option_code, across every control, resolves to the
    same uniform, honesty-respecting text (M008C-UX-FLOW-DESIGN.md §4) -
    checked via `derived_answer == ANSWER_UNKNOWN` rather than hard-coding
    every `*_NOT_SURE` code name here a second time.
    """
    if derived_answer == ANSWER_UNKNOWN:
        return NOT_SURE_EXPLAINER
    return EXPLAINER_TEXT[control_key][option_code]


# ---------------------------------------------------------------------------
# Stage-local REVIEWED / confirmed progress (M008C-UX-FLOW-DESIGN.md §6).
# ---------------------------------------------------------------------------
PROGRESS_TOTAL = len(CATALOGUE_KEYS)


def stage4_progress(assessment) -> Dict[str, object]:
    """
    `{"reviewed": N, "still_need_confirmation": M, "total": 12, "complete": bool}`.

    "Reviewed" (N) = how many of the 12 controls have ANY recorded
    `AnswerSelectionDetail` - a deliberate selection was made, including
    "Not sure". "Still need confirmation" (M) = of those N, how many
    resolved to the canonical UNKNOWN answer. `complete` is true only
    when N == 12 AND M == 0 (M008C §6's one hard rule: never a bare
    "Complete" state while any UNKNOWN remains).

    `assessment` may be `None` (no BaselineAssessment row created yet,
    e.g. a brand-new organisation that has not answered anything) - this
    is the same as zero reviewed, not an error.
    """
    if assessment is None:
        return {
            "reviewed": 0,
            "still_need_confirmation": 0,
            "total": PROGRESS_TOTAL,
            "complete": False,
        }

    reviewed_keys = set(
        AnswerSelectionDetail.objects.filter(
            assessment=assessment, question_key__in=CATALOGUE_KEYS
        ).values_list("question_key", flat=True)
    )
    reviewed = len(reviewed_keys)
    if reviewed == 0:
        return {
            "reviewed": 0,
            "still_need_confirmation": 0,
            "total": PROGRESS_TOTAL,
            "complete": False,
        }

    still_need_confirmation = BaselineAnswer.objects.filter(
        assessment=assessment,
        question_key__in=reviewed_keys,
        answer=ANSWER_UNKNOWN,
    ).count()

    return {
        "reviewed": reviewed,
        "still_need_confirmation": still_need_confirmation,
        "total": PROGRESS_TOTAL,
        "complete": reviewed == PROGRESS_TOTAL and still_need_confirmation == 0,
    }


def progress_copy(progress: Dict[str, object]) -> str:
    """
    Central Architecture's own exact wording, adopted verbatim
    (M008C-UX-FLOW-DESIGN.md §6): `"12 of 12 reviewed · 3 still need
    confirmation"`, or a bare `"Complete"` only when `progress["complete"]`
    is true.
    """
    if progress["complete"]:
        return "Complete"
    return (
        f'{progress["reviewed"]} of {progress["total"]} reviewed · '
        f'{progress["still_need_confirmation"]} still need confirmation'
    )
