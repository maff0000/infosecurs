"""
Application-owned assurance-outcome derivation (M005 PID §2, §3, §12, §14 -
m005-1-foundation dispatch).

**This is the single most safety-critical piece of M005.** `derive_outcome`
is the ONLY place in the entire product that decides SUPPORTED / CONFIRM /
GAP / NOT_APPLICABLE. It is pure, deterministic Python over an
already-validated `QuestionnaireInterpretation` and an already-assembled
`grounding_snapshot` (`questionnaire.grounding.
build_questionnaire_grounding_snapshot`'s output) - it calls no AI, reads no
untrusted free text, and makes no network/database call itself. Neither AI
task in this module (`ai_platform.questionnaire_interpretation_contracts`/
`ai_platform.questionnaire_drafting_contracts`) can influence this function
in any way: the interpretation AI only ever supplies `intent_type`/
`requirement_scope`/`selected_keys`/`evidence_explicitly_requested` (facts
about what was ASKED, not facts about current state), and the drafting AI
runs only AFTER this function has already produced a fixed `outcome` it
cannot change (PID §13, PID §20's second safety boundary).

The algorithm below is transcribed EXACTLY from the m005-1-foundation
dispatch's own specification, branch for branch - it has already been
checked against every one of PID §27's 18 required test cases (see
`questionnaire/tests/test_outcome.py`). Do not "simplify" or "improve" any
branch below without re-verifying every one of those 18 cases plus the
worked examples in PID §12/§14 - a change that reads as more elegant but
alters even one branch's precedence can silently convert a real customer's
unmet requirement into a false SUPPORTED, which is exactly the failure mode
this whole module exists to prevent.

== Signals ==
For each selected grounding key, `_signal_for_key` returns exactly one of:
"supported", "confirm", "gap", "not_applicable", "irrelevant". "irrelevant"
means the signal is excluded from aggregation entirely - it contributes
neither positively nor negatively (used only for the "single selected
control key is canonically not_applicable" special case - see that
branch's own comment below).

== Aggregation ==
`derive_outcome` combines every selected key's signal per PID §12.5's
conservative rule: any GAP wins outright; otherwise any CONFIRM wins;
otherwise NOT_APPLICABLE only if every signal is not_applicable; otherwise
SUPPORTED. Never averaged, never a fifth outcome invented.
"""
from __future__ import annotations

from ai_platform.questionnaire_drafting_contracts import (
    OUTCOME_CONFIRM,
    OUTCOME_GAP,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_SUPPORTED,
)
from ai_platform.questionnaire_interpretation_contracts import (
    INTENT_UNCLEAR,
    SCOPE_ALL,
    SCOPE_EXISTENCE,
    SCOPE_NOT_APPLICABLE_TEST,
    SCOPE_SOME,
    SCOPE_UNSPECIFIED,
    QuestionnaireInterpretation,
)

_SIGNAL_SUPPORTED = "supported"
_SIGNAL_CONFIRM = "confirm"
_SIGNAL_GAP = "gap"
_SIGNAL_NOT_APPLICABLE = "not_applicable"
_SIGNAL_IRRELEVANT = "irrelevant"

_CONTROL_PREFIX = "control:"
_POLICY_SECTION_PREFIX = "policy_section:"
_CERTIFICATION_ORG_KEYS = frozenset(
    {"org:certification_cyber_essentials", "org:certification_iso27001"}
)

_ANSWER_UNKNOWN = "unknown"
_ANSWER_NOT_APPLICABLE = "not_applicable"
_ANSWER_NO = "no"
_ANSWER_PARTIAL = "partial"
_ANSWER_YES = "yes"

_LABEL_EVIDENCE_CONFLICT = "Evidence conflict"
_LABEL_EVIDENCE_STALE = "Evidence stale"
_LABEL_NOT_CONFIRMED = "Not confirmed"

_CERTIFIED = "certified"
_NOT_CERTIFIED = "not_certified"
_IN_PROGRESS = "in_progress"


def _owner_or_placeholder(owner) -> str:
    return owner if owner else "not yet assigned"


def _target_date_or_placeholder(target_date) -> str:
    return target_date if target_date else "not yet set"


def _control_signal_and_warning(key: str, entry: dict, interpretation, *, control_key_count: int):
    baseline_key = key[len(_CONTROL_PREFIX):]

    # First branch, per spec: intent_type == "unclear" always -> confirm,
    # checked before anything else in this function (in the full pipeline
    # `derive_outcome`'s own top-level unclear short-circuit already
    # returns before any key is ever evaluated - this branch exists so
    # `_signal_for_key` stays independently correct if ever called
    # directly, e.g. from a future caller or a test).
    if interpretation.intent_type == INTENT_UNCLEAR:
        return _SIGNAL_CONFIRM, None

    answer = entry.get("answer", _ANSWER_UNKNOWN)
    assurance_label = entry.get("assurance_label", _LABEL_NOT_CONFIRMED)

    if answer == _ANSWER_UNKNOWN:
        return _SIGNAL_CONFIRM, f"Baseline control '{baseline_key}' is unconfirmed."

    if answer == _ANSWER_NOT_APPLICABLE:
        # PID §12.4: a single selected control genuinely, canonically
        # marked not_applicable propagates NOT_APPLICABLE. A
        # not_applicable control amid OTHER selected control keys is not
        # itself evidence the whole requirement is inapplicable, so it is
        # excluded from aggregation entirely rather than treated as either
        # a positive or negative signal.
        if control_key_count == 1:
            return _SIGNAL_NOT_APPLICABLE, None
        return _SIGNAL_IRRELEVANT, None

    if answer == _ANSWER_NO:
        return _SIGNAL_GAP, f"Baseline control '{baseline_key}' is not currently implemented."

    if answer == _ANSWER_PARTIAL:
        scope = interpretation.requirement_scope
        if scope == SCOPE_ALL:
            warning = (
                f"Baseline control '{baseline_key}' is only partially implemented, and "
                "the requirement applies to all instances."
            )
            remediation = entry.get("relevant_remediation") or []
            if remediation:
                first = remediation[0]
                warning += (
                    f" Open remediation exists (owner: {_owner_or_placeholder(first.get('owner'))}, "
                    f"target date: {_target_date_or_placeholder(first.get('target_date'))})."
                )
            return _SIGNAL_GAP, warning
        if scope in (SCOPE_SOME, SCOPE_EXISTENCE):
            return _SIGNAL_SUPPORTED, None
        # SCOPE_UNSPECIFIED, SCOPE_NOT_APPLICABLE_TEST
        return (
            _SIGNAL_CONFIRM,
            f"Baseline control '{baseline_key}' is partially implemented and the "
            "requirement's scope is not clearly specified.",
        )

    # answer == "yes"
    if assurance_label == _LABEL_EVIDENCE_CONFLICT:
        return (
            _SIGNAL_CONFIRM,
            f"Evidence for '{baseline_key}' conflicts with the recorded answer.",
        )
    # PID §12.1/§H: an explicit evidence/proof request with no suitable
    # ACTIVE supporting evidence must never return SUPPORTED. Checked via
    # the active-support COUNT, not an assurance_label string match -
    # correction, 2026-09-24: the original label-based check
    # (`assurance_label in ("Evidence stale", "Not confirmed")`) missed the
    # ordinary, very much reachable "yes, evidence explicitly requested,
    # but zero evidence was ever attached" case, whose real
    # `security_state.services` label is "Customer stated" (not "Not
    # confirmed" - that label only ever arises for an unknown/absent
    # answer, never alongside answer=="yes"). The count check is the
    # correct, robust signal: it uniformly covers "Customer stated" (zero
    # evidence ever attached), "Evidence stale" (evidence exists but none
    # currently active) and any other future label sharing the same real
    # underlying meaning - "no ACTIVE support exists right now" - without
    # needing to enumerate label strings by hand.
    if interpretation.evidence_explicitly_requested and entry.get("active_supporting_evidence_count", 0) == 0:
        return (
            _SIGNAL_CONFIRM,
            f"The question explicitly requested evidence for '{baseline_key}', but no "
            "current active supporting evidence is on file.",
        )
    return _SIGNAL_SUPPORTED, None


def _policy_section_signal_and_warning(key: str, entry: dict, interpretation):
    section_key = key[len(_POLICY_SECTION_PREFIX):]

    if interpretation.intent_type == INTENT_UNCLEAR:
        return _SIGNAL_CONFIRM, None

    policy_exists = entry.get("policy_exists", False)
    section_present = entry.get("section_present", False)

    if interpretation.intent_type == "artefact_existence":
        if policy_exists:
            return _SIGNAL_SUPPORTED, None
        return _SIGNAL_GAP, "No approved security policy currently exists."

    # policy_requirement, mixed, or any other intent selecting a
    # policy_section key - all treated identically (PID's MFA
    # policy-vs-implementation worked example: the policy signal must never
    # independently short-circuit to SUPPORTED before aggregation runs).
    if policy_exists and section_present:
        return _SIGNAL_SUPPORTED, None
    if policy_exists and not section_present:
        return (
            _SIGNAL_GAP,
            f"The approved security policy does not currently cover '{section_key}'.",
        )
    return _SIGNAL_GAP, "No approved security policy currently exists."


def _org_certification_signal_and_warning(key: str, entry: dict, interpretation):
    if interpretation.intent_type == INTENT_UNCLEAR:
        return _SIGNAL_CONFIRM, None
    value = entry.get("value", _ANSWER_UNKNOWN)
    if value == _CERTIFIED:
        return _SIGNAL_SUPPORTED, None
    if value == _ANSWER_UNKNOWN:
        return _SIGNAL_CONFIRM, f"Certification status for '{key}' is not yet confirmed."
    if value in (_NOT_CERTIFIED, _IN_PROGRESS):
        return _SIGNAL_GAP, f"'{key}' is not currently certified."
    return _SIGNAL_CONFIRM, f"Certification status for '{key}' is not yet confirmed."


def _org_fact_signal_and_warning(key: str, entry: dict, interpretation):
    if interpretation.intent_type == INTENT_UNCLEAR:
        return _SIGNAL_CONFIRM, None
    value = entry.get("value", _ANSWER_UNKNOWN)
    if value and value != _ANSWER_UNKNOWN:
        return _SIGNAL_SUPPORTED, None
    return _SIGNAL_CONFIRM, f"'{key}' has not yet been confirmed for this organisation."


def _signal_for_key(key: str, entry: dict, interpretation, *, control_key_count: int):
    """Returns `(signal, warning_or_None)` for one selected grounding key -
    see module docstring for the fixed signal vocabulary."""
    if entry is None:
        return _SIGNAL_CONFIRM, f"'{key}' could not be resolved to a recorded fact."
    if key.startswith(_CONTROL_PREFIX):
        return _control_signal_and_warning(key, entry, interpretation, control_key_count=control_key_count)
    if key.startswith(_POLICY_SECTION_PREFIX):
        return _policy_section_signal_and_warning(key, entry, interpretation)
    if key in _CERTIFICATION_ORG_KEYS:
        return _org_certification_signal_and_warning(key, entry, interpretation)
    if key.startswith("org:"):
        return _org_fact_signal_and_warning(key, entry, interpretation)
    # Not a recognised prefix - fail safe to CONFIRM rather than silently
    # ignoring an unresolvable key.
    return _SIGNAL_CONFIRM, f"'{key}' could not be resolved to a recognised fact family."


def derive_outcome(interpretation: QuestionnaireInterpretation, grounding_snapshot: dict):
    """Derive the application-owned assurance outcome (PID §12) from an
    already-validated `interpretation` and its `grounding_snapshot`
    (`questionnaire.grounding.build_questionnaire_grounding_snapshot`'s
    output, keyed by the same `selected_keys`).

    Returns `(outcome, review_warnings)` where `outcome` is exactly one of
    `ai_platform.questionnaire_drafting_contracts.ALLOWED_OUTCOMES` and
    `review_warnings` is a `list[str]` explaining why, whenever the outcome
    is not a clean SUPPORTED (PID §16, ADR-0003 §5's "surface as an
    incomplete governance item rather than silently filling it in").
    """
    # 1. intent_type == "unclear" -> CONFIRM immediately, skip per-key
    # evaluation entirely (PID §8).
    if interpretation.intent_type == INTENT_UNCLEAR:
        warnings = []
        if interpretation.ambiguity_note:
            warnings.append(interpretation.ambiguity_note)
        else:
            warnings.append("This question was materially unclear and needs human review.")
        return OUTCOME_CONFIRM, warnings

    selected_keys = interpretation.selected_keys

    # 7. selected_keys empty (checked here, before aggregation, so an empty
    # signal list can never vacuously satisfy the "every signal is
    # supported" rule below).
    if not selected_keys:
        return OUTCOME_CONFIRM, ["No canonical facts could be identified for this question."]

    control_key_count = sum(1 for k in selected_keys if k.startswith(_CONTROL_PREFIX))

    signals = []
    warnings = []
    for key in selected_keys:
        entry = grounding_snapshot.get(key)
        signal, warning = _signal_for_key(key, entry, interpretation, control_key_count=control_key_count)
        signals.append(signal)
        if warning:
            warnings.append(warning)

    contributing = [s for s in signals if s != _SIGNAL_IRRELEVANT]

    # 3. any GAP -> GAP.
    if any(s == _SIGNAL_GAP for s in contributing):
        return OUTCOME_GAP, warnings

    # 4. else any CONFIRM -> CONFIRM.
    if any(s == _SIGNAL_CONFIRM for s in contributing):
        return OUTCOME_CONFIRM, warnings

    # 5. else, if every contributing signal is NOT_APPLICABLE (and there is
    # at least one) -> NOT_APPLICABLE.
    if contributing and all(s == _SIGNAL_NOT_APPLICABLE for s in contributing):
        return OUTCOME_NOT_APPLICABLE, warnings

    # Defensive safety net, not one of the spec's numbered rules: every
    # selected signal folded to "irrelevant" (e.g. more than one selected
    # control key, every one of them canonically not_applicable - PID
    # §12.4's single-key special case never applies, so none of them ever
    # became a real not_applicable/supported/gap/confirm signal). Nothing
    # here actually SUPPORTS the claim, so this must never silently fall
    # through to SUPPORTED - fail conservatively to CONFIRM instead.
    if not contributing:
        return (
            OUTCOME_CONFIRM,
            warnings
            + ["No selected fact could be used on its own to support this answer."],
        )

    # 6. else every contributing signal is SUPPORTED (NOT_APPLICABLE mixed
    # with SUPPORTED folds into SUPPORTED territory - it contributed
    # nothing negative) -> SUPPORTED.
    return OUTCOME_SUPPORTED, warnings


__all__ = ["derive_outcome"]
