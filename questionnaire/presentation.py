"""
The ONE place M005's outcome-language wording (PID §26) and grounding
display shaping live (m005-2-review-history dispatch) - mirroring
`policy.presentation`'s own stated rationale exactly (see that module's
docstring): one shared Python function is the ONE place outcome-language
wording is generated, so it can never drift between the HTML template and
any other future consumer (e.g. a PDF export, should one ever be built).

`outcome_presentation` renders PID §26's wording VERBATIM - never
paraphrased, never re-derived per outcome from scratch in a template
`{% if %}` chain. `grounding_facts_for_display` is the render-ready
projection of `response.grounding_snapshot` the "Why this answer?" panel
(PID §16, §25) iterates, keyed by a `"kind"` discriminator so the template
itself needs no `startswith("control:")`-style prefix logic (that
dispatch/parsing responsibility belongs here, next to the one place that
already knows the three key-family shapes - see `questionnaire.grounding`
for where each fact dict's fields originate).
"""
from __future__ import annotations

from ai_platform.questionnaire_drafting_contracts import (
    OUTCOME_CONFIRM,
    OUTCOME_GAP,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_SUPPORTED,
)
from questionnaire.catalogue import CATALOGUE_BY_KEY

_CONTROL_PREFIX = "control:"
_POLICY_SECTION_PREFIX = "policy_section:"
_ORG_PREFIX = "org:"


def outcome_presentation(response) -> dict:
    """
    Returns `{"headline": str, "sub_notes": list[str]}` using PID §26's
    exact wording, verbatim, for `response.outcome`.

    Never adds "Verified" wording merely because supporting evidence
    exists (PID §26 explicit instruction) - the SUPPORTED sub_note below is
    the ONLY evidence-related sub_note this function ever produces, and it
    deliberately says "Supporting evidence is attached", not "Verified".
    """
    if response.outcome == OUTCOME_SUPPORTED:
        sub_notes = []
        for fact in response.grounding_snapshot.values():
            if isinstance(fact, dict) and fact.get("active_supporting_evidence_count", 0) > 0:
                sub_notes.append("Supporting evidence is attached.")
                break
        return {
            "headline": "Current Infosecurs state supports this answer.",
            "sub_notes": sub_notes,
        }
    if response.outcome == OUTCOME_CONFIRM:
        return {
            "headline": (
                "Infosecurs needs a fact or evidence item confirmed before giving a "
                "definitive answer."
            ),
            "sub_notes": [],
        }
    if response.outcome == OUTCOME_GAP:
        sub_notes = []
        for fact in response.grounding_snapshot.values():
            if isinstance(fact, dict) and fact.get("relevant_remediation"):
                sub_notes.append("The gap is recognised and tracked through remediation.")
                break
        return {
            "headline": "The requirement is not currently fully met.",
            "sub_notes": sub_notes,
        }
    if response.outcome == OUTCOME_NOT_APPLICABLE:
        return {
            "headline": (
                "The requirement does not apply based on the organisation facts "
                "currently recorded."
            ),
            "sub_notes": [],
        }
    # Fail safe, not fail loud (should not happen - every persisted
    # QuestionnaireResponse.outcome is validated against ALLOWED_OUTCOMES at
    # write time) - matches this codebase's established defensive-fallback
    # style elsewhere (e.g. questionnaire.grounding._control_fact's
    # "not a real baseline catalogue key" branch).
    return {"headline": response.outcome, "sub_notes": []}


def _control_display(key: str, control_key: str, fact: dict) -> dict:
    description = CATALOGUE_BY_KEY.get(key, {}).get("description", control_key)
    return {
        "kind": "control",
        "key": key,
        "control_key": control_key,
        "description": description,
        "answer": fact.get("answer"),
        "assurance_label": fact.get("assurance_label"),
        "active_supporting_evidence_count": fact.get("active_supporting_evidence_count"),
        "active_contradicting_evidence_count": fact.get("active_contradicting_evidence_count"),
        "stale_evidence_count": fact.get("stale_evidence_count"),
        "relevant_remediation": fact.get("relevant_remediation", []),
    }


def _policy_section_display(key: str, fact: dict) -> dict:
    description = CATALOGUE_BY_KEY.get(key, {}).get("description", key)
    # Deliberately never includes fact["section_content"] here - PID §16
    # ("Do not expose internal UUIDs, raw prompts or other-tenant data")
    # plus the general discipline of not dumping raw policy text into a
    # compact "why" summary panel. See this dispatch's own report for the
    # judgment call this represents.
    return {
        "kind": "policy_section",
        "key": key,
        "description": description,
        "policy_exists": fact.get("policy_exists"),
        "approved_version_number": fact.get("approved_version_number"),
        "section_present": fact.get("section_present"),
    }


def _org_display(key: str, fact: dict) -> dict:
    description = CATALOGUE_BY_KEY.get(key, {}).get("description", key)
    return {
        "kind": "org",
        "key": key,
        "description": description,
        "value": fact.get("value"),
        "workplaces": fact.get("workplaces"),
    }


def grounding_facts_for_display(response) -> list:
    """
    Render-ready projection of `response.grounding_snapshot`, in
    `response.selected_keys`' original order (skipping any key with no
    snapshot entry rather than raising - fail-safe, matching
    `questionnaire.grounding`'s own discipline for an unexpected/missing
    key).
    """
    facts = []
    for key in response.selected_keys:
        fact = response.grounding_snapshot.get(key)
        if fact is None:
            continue
        if key.startswith(_CONTROL_PREFIX):
            facts.append(_control_display(key, key[len(_CONTROL_PREFIX):], fact))
        elif key.startswith(_POLICY_SECTION_PREFIX):
            facts.append(_policy_section_display(key, fact))
        elif key.startswith(_ORG_PREFIX):
            facts.append(_org_display(key, fact))
        # Any other prefix is not one this display layer knows how to
        # render - silently omitted rather than raising, mirroring
        # questionnaire.grounding.build_questionnaire_grounding_snapshot's
        # own "any other prefix" discipline.
    return facts


__all__ = ["outcome_presentation", "grounding_facts_for_display"]
