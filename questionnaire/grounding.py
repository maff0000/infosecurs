"""
Questionnaire grounding-snapshot assembly (M005 PID §7.3, §11 -
m005-1-foundation dispatch): the piece that takes an ALREADY-VALIDATED
interpretation's `selected_keys` and assembles the exact, bounded,
tenant-scoped grounding snapshot an answer is derived from and drafted
against.

SAFETY-CRITICAL (mirrors `policy.grounding`'s own "the last item is
critical" framing - PID §16/§23, and this module's own catalogue-key
dispatch mirrors that module's fact-group dispatch): whatever
`build_questionnaire_grounding_snapshot` returns becomes both (a) the input
`questionnaire.outcome.derive_outcome` reads to decide SUPPORTED/CONFIRM/
GAP/NOT_APPLICABLE, and (b) an outbound AI drafting-request payload. It must
be structurally impossible for it to read or include another organisation's
data, and it must never contain more than PID §7.3/§11 permit.

How that is enforced here, not just asserted - identical discipline to
`policy.grounding.build_policy_grounding_payload` (read that module's own
docstring again before changing this one):

1. `build_questionnaire_grounding_snapshot` takes a single `organisation`
   object PLUS the already-validated `selected_keys` list - never an
   organisation id plus a separate lookup, and never an unvalidated key
   list (the caller, `questionnaire.services`, only ever passes
   `interpretation.selected_keys` - a list that
   `QuestionnaireInterpretation.from_response_dict` has already proven is a
   subset of the catalogue keys actually offered).
2. Every DB access below is EITHER a reverse one-to-one/one-to-many
   traversal FROM that exact `organisation` object
   (`organisation.profile`), or an explicit
   `.filter(organisation=organisation, ...)`
   (`RemediationAction`, `Workplace`), or a call to
   `security_state.services.get_security_state(organisation)` /
   `organisation.policy_document` - each already built to this same
   discipline. Nothing here ever calls `.objects.get(pk=...)` without an
   organisation filter, and nothing accepts a raw id from outside this
   function's own `organisation` argument.
3. `selected_keys` is BOUNDED, not "the whole tenant state" (PID §7.3:
   "bounded" / PID §11: "Do not send evidence file bytes... Do not send
   unrelated evidence/free text simply because it exists") - only the
   specific facts for the specific keys the interpretation actually
   selected are ever assembled; nothing here iterates "every control" or
   "every policy section" regardless of `selected_keys`.
4. Evidence is represented only as BOUNDED COUNTS
   (`active_supporting_evidence_count` etc.) and remediation summaries -
   never evidence file bytes, never a raw evidence description blob (PID
   §11 "Do not send evidence file bytes to AI").
5. Owner/target-date are never invented (ADR-0003 §5, PID §11 "Do not
   invent owner/date"): a `RemediationAction` with no `assigned_to`/
   `target_date` produces `None` in the snapshot, never a placeholder name
   or date - see `_owner_display_name`/the `relevant_remediation` list
   comprehension below.

This module decides which control/policy/organisation facts belong in the
snapshot for a given selected key; `questionnaire.catalogue` only decides
which keys exist to be selected in the first place (a separate, prior
concern - see that module's own docstring).
"""
from __future__ import annotations

import datetime
from typing import Optional

from organisations.models import OrganisationProfile
from policy.models import PolicyDocument, PolicyVersion
from remediation.models import RemediationAction
from security_state.services import get_security_state
from workplace.models import Workplace

_CONTROL_PREFIX = "control:"
_POLICY_SECTION_PREFIX = "policy_section:"
_ORG_PREFIX = "org:"

# Plain OrganisationProfile tri-state/enum fields this module resolves
# directly by attribute name - every one of these is read-only reference
# against a field that already exists on organisation.profile (PID §11
# "explicit certification status" / "relevant explicit data-handling/
# profile facts"). Deliberately excludes "org:certification_*" and
# "org:working_model", which have their own richer handling below.
_ORG_PROFILE_FIELD_KEYS = {
    "org:handles_personal_data": "handles_personal_data",
    "org:handles_confidential_business_data": "handles_confidential_business_data",
    "org:handles_payment_card_data": "handles_payment_card_data",
    "org:handles_special_category_data": "handles_special_category_data",
    "org:receives_security_questionnaires": "receives_security_questionnaires",
    "org:develops_hosts_own_software": "develops_hosts_own_software",
}


def _isoformat_or_none(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value)


def _owner_display_name(user) -> Optional[str]:
    """Best-effort human display name for a `RemediationAction.assigned_to`
    user, or `None` if no owner is assigned. Deliberately returns `None`,
    never a placeholder string such as "Unknown" - unlike
    `policy.presentation._user_display_name` (which always names an actor
    that is expected to exist), an absent owner here is a genuinely
    meaningful, honestly-represented state (ADR-0003 §5 "Do not invent
    dates or owners... surface that as an incomplete governance item")."""
    if user is None:
        return None
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = (get_full_name() or "").strip()
        if full_name:
            return full_name
    username = (getattr(user, "username", "") or "").strip()
    return username or None


def _control_fact(organisation, baseline_key: str, security_state_by_key: dict) -> dict:
    """Bounded grounding fact for `control:<baseline_key>` (PID §11
    "Security baseline / Current Security State" + "Managed
    exceptions/remediation"). `security_state_by_key` is
    `security_state.services.get_security_state(organisation)` pre-indexed
    by `control_key` by the caller, so this function never re-runs that
    already tenant-scoped, already deterministic query per key."""
    entry = security_state_by_key.get(baseline_key)
    if entry is None:
        # Not a real baseline catalogue key (should not happen for a
        # validated selected_keys entry, but fail safe rather than KeyError).
        return {
            "answer": "unknown",
            "answer_updated_at": None,
            "assurance_label": "Not confirmed",
            "active_supporting_evidence_count": 0,
            "active_contradicting_evidence_count": 0,
            "stale_evidence_count": 0,
            "open_remediation_count": 0,
            "relevant_remediation": [],
        }

    remediation_actions = RemediationAction.objects.filter(
        organisation=organisation,
        control_key=baseline_key,
        status__in=RemediationAction.ACTIVE_STATUSES,
    ).select_related("assigned_to")

    relevant_remediation = [
        {
            "status": action.status,
            "owner": _owner_display_name(action.assigned_to),
            "target_date": _isoformat_or_none(action.target_date),
            "treatment_summary": action.title,
        }
        for action in remediation_actions
    ]

    return {
        "answer": entry["answer"],
        "answer_updated_at": _isoformat_or_none(entry["answer_updated_at"]),
        "assurance_label": entry["assurance_label"],
        "active_supporting_evidence_count": len(entry["active_supporting_evidence"]),
        "active_contradicting_evidence_count": len(entry["active_contradictory_evidence"]),
        "stale_evidence_count": len(entry["stale_evidence"]),
        "open_remediation_count": entry["open_remediation_count"],
        "relevant_remediation": relevant_remediation,
    }


def _approved_policy_version(organisation) -> Optional[PolicyVersion]:
    """This organisation's current APPROVED `PolicyVersion`, or `None` - a
    plain read-only query against the `policy` app's own models, scoped via
    `organisation.policy_document`'s reverse OneToOneField accessor (never
    a bare `.get(pk=...)`). Only an APPROVED version counts as "the
    organisation's policy" for questionnaire-grounding purposes (ADR-0003:
    "approved policy is authoritative for what the organisation requires";
    a draft policy is not yet the organisation's adopted position) - the
    same "approved, never draft" discipline
    `policy.grounding._open_risk_facts`'s own "CONFIRMED only" filter
    applies to a different fact group.
    """
    try:
        document = organisation.policy_document
    except PolicyDocument.DoesNotExist:
        return None
    return document.versions.filter(status=PolicyVersion.STATUS_APPROVED).first()


def _policy_section_fact(approved_version: Optional[PolicyVersion], section_key: str) -> dict:
    """Bounded grounding fact for `policy_section:<section_key>` (PID §11
    "Approved policy": "approved policy existence/version", "relevant
    approved section/clause text"). Policy text is never used as proof of
    implementation - that discipline lives in `questionnaire.outcome.
    derive_outcome`, not here; this function only reports what the
    approved policy currently says, honestly."""
    if approved_version is None:
        return {
            "policy_exists": False,
            "approved_version_number": None,
            "section_present": False,
            "section_content": None,
        }
    section_content = None
    for section in approved_version.sections:
        if section.get("section_key") == section_key:
            section_content = section.get("content")
            break
    return {
        "policy_exists": True,
        "approved_version_number": approved_version.version_number,
        "section_present": section_content is not None,
        "section_content": section_content,
    }


def _workplace_summaries(organisation) -> list:
    workplaces = Workplace.objects.filter(organisation=organisation, is_active=True)
    return [
        {
            "name": w.name,
            "type": w.type,
            "location_label": w.location_label,
            "approx_people_count": w.approx_people_count,
        }
        for w in workplaces
    ]


def _org_fact(organisation, key: str) -> dict:
    """Bounded grounding fact for an `org:*` key (PID §11 "Organisation/
    Profile": "organisation name", "Workplace-derived working model",
    "workplace summaries", "relevant explicit data-handling/profile
    facts", "explicit certification status"). Every `org:*` entry is
    represented as `{"value": ...}` (plus `"workplaces"` for
    `org:working_model` specifically), matching the uniform shape
    `questionnaire.outcome._signal_for_key` reads."""
    try:
        profile = organisation.profile
    except OrganisationProfile.DoesNotExist:
        profile = None

    if key == "org:certification_cyber_essentials":
        return {"value": profile.cyber_essentials_status if profile else "unknown"}
    if key == "org:certification_iso27001":
        return {"value": profile.iso27001_status if profile else "unknown"}
    if key == "org:working_model":
        return {
            "value": profile.working_model if profile else "unknown",
            "workplaces": _workplace_summaries(organisation),
        }

    field_name = _ORG_PROFILE_FIELD_KEYS.get(key)
    if field_name is not None:
        return {"value": getattr(profile, field_name) if profile else "unknown"}

    # Should never be reached for a validated selected_keys entry (every
    # "org:" key in questionnaire.catalogue.CATALOGUE is handled above) -
    # fail safe rather than raise, so an unexpected key degrades to an
    # honest "unknown" fact rather than a 500.
    return {"value": "unknown"}


def build_questionnaire_grounding_snapshot(organisation, selected_keys: list) -> dict:
    """Assemble the bounded, tenant-scoped grounding snapshot for
    `organisation` covering exactly `selected_keys` (PID §7.3, §11).

    `selected_keys` MUST already be validated (i.e. every entry was a key
    genuinely offered to, and selected by, a `QuestionnaireInterpretation` -
    see `ai_platform.questionnaire_interpretation_contracts.
    QuestionnaireInterpretation.from_response_dict`). This function does
    not re-validate against `questionnaire.catalogue` itself - that
    responsibility belongs entirely to the interpretation contract, which
    has already run by the time this is called (PID §2's pipeline: AI
    interpretation -> application validates -> application assembles
    grounding -> application derives outcome).

    Returns `{key: fact_dict, ...}`, one entry per `selected_keys` entry,
    keyed exactly by the catalogue key. Dispatches on each key's prefix
    (`control:`, `policy_section:`, `org:`) to the matching bounded builder
    above.
    """
    security_state_by_key = {entry["control_key"]: entry for entry in get_security_state(organisation)}
    approved_version = _approved_policy_version(organisation)

    snapshot = {}
    for key in selected_keys:
        if key.startswith(_CONTROL_PREFIX):
            baseline_key = key[len(_CONTROL_PREFIX):]
            snapshot[key] = _control_fact(organisation, baseline_key, security_state_by_key)
        elif key.startswith(_POLICY_SECTION_PREFIX):
            section_key = key[len(_POLICY_SECTION_PREFIX):]
            snapshot[key] = _policy_section_fact(approved_version, section_key)
        elif key.startswith(_ORG_PREFIX):
            snapshot[key] = _org_fact(organisation, key)
        # Any other prefix is not a key this grounding layer knows how to
        # resolve - silently omitted rather than raising, since
        # from_response_dict has already guaranteed every selected_keys
        # entry came from questionnaire.catalogue.CATALOGUE, whose every
        # entry uses one of the three prefixes above.

    return snapshot


__all__ = ["build_questionnaire_grounding_snapshot"]
