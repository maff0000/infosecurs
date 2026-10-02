"""
Closed-form replacement choices for `risk_register.RiskEditForm`'s
`rationale`/`proposed_treatment` fields (M008-FREE-TEXT-REPLACEMENT-
REGISTER.md rows 8-9, M008C-WI3 dispatch).

Neither `rationale` nor `proposed_treatment` gained a new database column
- both stay exactly the `TextField`s they already were
(`risk_register/models.py`); only what `RiskEditForm` lets a customer
WRITE into them changes, from open text to one of a small, versioned,
Git-controlled set of stable codes defined here. This mirrors
`risk_register.methodology`'s own "versioned Python data, not editable
database rows" convention, and `evidence.ControlEvidenceLinkForm.
rationale`'s "same column, repurposed to a selected code" pattern
(register row 5, reused by rows 8/9).

Why these are plain module-level constants rather than a `TextChoices`
enum or a database table: both value sets are small, change rarely (a new
code is additive - never a rename/repurpose of an existing one, same
discipline as `risk_register.methodology.MethodologyScenario.scenario_id`),
and need no FK/relational behaviour - a `ChoiceField`'s own `choices=`
kwarg is all either one is for.

Legacy/pre-existing values (deterministic scenario-engine provenance text
such as `risk_register.scenario_engine._build_rationale`'s output, the
scenario's own `suggested_treatment` sentence, or - pre-M008C-WI3 - a
customer's own free-text edit) are NEVER migrated or discarded: see
`risk_register.forms.RiskEditForm`'s own "legacy value" injection, which
displays whatever is already stored as an extra, clearly-labelled choice
rather than forcing a silent re-categorisation of history (same rule as
M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 5's "no forced
re-categorisation of history").
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Row 9: `proposed_treatment` treatment-category choices (PID's exact
# proposed shape: "Accept / Mitigate via suggested action / Mitigate via
# custom remediation already created / Transfer").
# ---------------------------------------------------------------------------
TREATMENT_ACCEPT = "treatment_accept"
TREATMENT_MITIGATE_SUGGESTED = "treatment_mitigate_suggested"
TREATMENT_MITIGATE_CUSTOM = "treatment_mitigate_custom"
TREATMENT_TRANSFER = "treatment_transfer"

TREATMENT_CATEGORY_CHOICES: List[Tuple[str, str]] = [
    (
        TREATMENT_MITIGATE_SUGGESTED,
        "Mitigate via the suggested treatment (shown above)",
    ),
    (
        TREATMENT_MITIGATE_CUSTOM,
        "Mitigate via a different remediation action already created",
    ),
    (TREATMENT_ACCEPT, "Accept this risk for now"),
    (TREATMENT_TRANSFER, "Transfer this risk (e.g. insurance, a third party)"),
]
TREATMENT_CATEGORY_LABELS: Dict[str, str] = dict(TREATMENT_CATEGORY_CHOICES)

# ---------------------------------------------------------------------------
# Row 8: `rationale` choices, tied to the actual impact/likelihood value
# selected (PID's own worked example: "Would affect a system handling
# confidential data" for higher impact). Two small, separate catalogues -
# one keyed by impact (1-5), one by likelihood (1-5) - rather than one
# combined 25-way table: each dimension's reasoning is independent (why a
# risk matters vs. how probable it is), and a combined table would need up
# to 25 cells for no extra expressive power. `risk_register.forms.
# RiskEditForm` offers the UNION of the current impact level's codes and
# the current likelihood level's codes (a "simpler combined approach" -
# see that form's own docstring for why no JS/re-render step is needed).
# ---------------------------------------------------------------------------
IMPACT_RATIONALE_CHOICES: Dict[int, List[Tuple[str, str]]] = {
    1: [
        ("impact_1_non_sensitive", "Affects non-sensitive data or a non-critical system"),
        ("impact_1_quick_recovery", "Any disruption would be quick and easy to recover from"),
        ("impact_1_no_compliance", "No regulatory, contractual or compliance exposure"),
    ],
    2: [
        ("impact_2_limited_scope", "Affects a limited scope of data or a single non-critical system"),
        ("impact_2_manageable_disruption", "Would cause manageable, short-term business disruption"),
        ("impact_2_some_sensitivity", "Involves some business-sensitive information, not customer data"),
    ],
    3: [
        ("impact_3_confidential_data", "Would affect a system or data classed as confidential business information"),
        ("impact_3_moderate_disruption", "Would cause a moderate interruption to normal business operations"),
        ("impact_3_customer_facing", "Has some customer-facing or reputational element"),
    ],
    4: [
        ("impact_4_personal_data", "Would affect personal or customer data at meaningful scale"),
        ("impact_4_significant_disruption", "Would cause significant disruption requiring senior management attention"),
        ("impact_4_compliance_exposure", "Creates a real regulatory or contractual compliance exposure"),
    ],
    5: [
        ("impact_5_severe_data", "Would affect highly sensitive, special-category or large-scale customer data"),
        ("impact_5_existential_disruption", "Could threaten the ongoing operation of the business"),
        ("impact_5_severe_compliance", "Creates severe regulatory, legal or contractual exposure"),
    ],
}

LIKELIHOOD_RATIONALE_CHOICES: Dict[int, List[Tuple[str, str]]] = {
    1: [
        ("likelihood_1_no_known_path", "No known realistic path for this to occur currently"),
        ("likelihood_1_strong_controls", "Existing controls elsewhere make this very unlikely"),
    ],
    2: [
        ("likelihood_2_uncommon", "Would require an uncommon combination of circumstances"),
        ("likelihood_2_some_controls", "Some mitigating controls exist that reduce the chance"),
    ],
    3: [
        ("likelihood_3_plausible", "A plausible event given the organisation's current setup"),
        ("likelihood_3_industry_common", "A commonly seen threat across similar organisations"),
    ],
    4: [
        ("likelihood_4_realistic_gap", "A realistic, fairly easy path exists given the current control gap"),
        ("likelihood_4_targeted", "The organisation's profile makes this a likely target"),
    ],
    5: [
        ("likelihood_5_near_certain", "Near-certain to occur without intervention given the current exposure"),
        ("likelihood_5_active_threat", "An actively, commonly exploited threat with no mitigating control in place"),
    ],
}

# All stable rationale codes, flattened, for a template/lookup that needs a
# label for whatever code is currently stored without knowing which rating
# it came from.
RATIONALE_CODE_LABELS: Dict[str, str] = {
    code: label
    for choices in (*IMPACT_RATIONALE_CHOICES.values(), *LIKELIHOOD_RATIONALE_CHOICES.values())
    for code, label in choices
}

# --- Catalogue-wide invariants (mirrors risk_register/methodology.py's own
# assert-at-import-time discipline) -----------------------------------
assert set(IMPACT_RATIONALE_CHOICES.keys()) == {1, 2, 3, 4, 5}, (
    "IMPACT_RATIONALE_CHOICES must cover every impact rating 1-5."
)
assert set(LIKELIHOOD_RATIONALE_CHOICES.keys()) == {1, 2, 3, 4, 5}, (
    "LIKELIHOOD_RATIONALE_CHOICES must cover every likelihood rating 1-5."
)
for _level, _choices in IMPACT_RATIONALE_CHOICES.items():
    assert 2 <= len(_choices) <= 5, f"impact level {_level}: keep rationale codes to 2-5 per level."
for _level, _choices in LIKELIHOOD_RATIONALE_CHOICES.items():
    assert 2 <= len(_choices) <= 5, f"likelihood level {_level}: keep rationale codes to 2-5 per level."
assert len(RATIONALE_CODE_LABELS) == sum(
    len(choices)
    for choices in (*IMPACT_RATIONALE_CHOICES.values(), *LIKELIHOOD_RATIONALE_CHOICES.values())
), "Every rationale code across both catalogues must be globally unique."
del _level, _choices

__all__ = [
    "TREATMENT_ACCEPT",
    "TREATMENT_MITIGATE_SUGGESTED",
    "TREATMENT_MITIGATE_CUSTOM",
    "TREATMENT_TRANSFER",
    "TREATMENT_CATEGORY_CHOICES",
    "TREATMENT_CATEGORY_LABELS",
    "IMPACT_RATIONALE_CHOICES",
    "LIKELIHOOD_RATIONALE_CHOICES",
    "RATIONALE_CODE_LABELS",
]
