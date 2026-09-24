"""
Questionnaire canonical-key catalogue (M005 PID §10 - m005-1-foundation
dispatch): the "small allowlisted catalogue of available canonical
fact/control/policy keys and human-readable meanings" the interpretation AI
is offered on every call.

This is versioned Python data, not database rows - mirroring
`security_baseline/catalogue.py`'s own shape and rationale exactly (that
module's docstring: "This is versioned product methodology, not user data,
so it lives in Git as plain Python rather than editable database rows").
It lives in `questionnaire/`, not `ai_platform/`, because it is
questionnaire-domain data (which canonical facts this module chooses to
offer the interpretation model), not generic AI-adapter infrastructure -
the same app-ownership boundary `security_baseline/catalogue.py` observes
for its own domain.

`CATALOGUE_VERSION` is bumped whenever the key set/descriptions change
materially, mirroring `security_baseline.catalogue.CATALOGUE_VERSION`'s own
convention, so a historical `QuestionnaireResponse`'s recorded
`selected_keys` remain interpretable even after the catalogue evolves.

== Why this catalogue exists (PID §10, §F) ==
The interpretation AI "may select only supplied allowlisted keys" -
"Application validates every key. Invented/unknown keys invalidate the
interpretation." This module is the single source of truth for what
"allowlisted" means for the questionnaire-interpretation task; every entry
here is intentionally either a `security_baseline` control key, an
`ai_platform.policy_contracts` approved policy-section key, or an explicit
`OrganisationProfile` fact the grounding layer (`questionnaire.grounding`)
knows how to resolve - see that module for the one-to-one mapping from a
catalogue key's prefix to how its grounding fact is actually assembled.

== The four key families ==

1. ``control:<baseline_key>`` - one entry per
   `security_baseline.catalogue.CATALOGUE` key (12 entries). Description is
   that catalogue entry's own `"question"` text, since that is the exact
   wording a customer-facing interpretation model needs to recognise "this
   external question is asking about the same thing as this internal
   control" - closer to natural language than the shorter `"area"` label.

2. ``policy_section:<section_key>`` - one entry per
   `ai_platform.policy_contracts.ALLOWED_SECTION_KEYS` (8 entries).
   Descriptions are adapted from
   `ai_platform.prompts.policy_generation_v1._SECTION_DESCRIPTIONS` (reused,
   not reimplemented from scratch - the module docstring below explains why
   that source reads cleanly enough to adapt rather than justifying a
   second, independently-worded description set).

3. ``org:certification_*`` / ``org:working_model`` /
   ``org:handles_*`` / ``org:receives_security_questionnaires`` /
   ``org:develops_hosts_own_software`` - existing `OrganisationProfile`
   tri-state/enum facts (9 entries), useful for `organisation_fact` and
   `certification` intent questions ("Do you allow remote working?", "Are
   you ISO 27001 certified?").

Total: 12 + 8 + 9 = 29 entries.

This catalogue is small enough (29 entries, each a short key + one-sentence
description) to send to the AI IN FULL on every interpretation call - PID
§10's own framing ("a small allowlisted catalogue") - so, unlike a large
document corpus, no relevance-filtering/retrieval step is needed before
offering it.
"""
from __future__ import annotations

from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS
from security_baseline.catalogue import CATALOGUE as _BASELINE_CATALOGUE

CATALOGUE_VERSION = "questionnaire-catalogue-v1"

# Adapted from ai_platform.prompts.policy_generation_v1._SECTION_DESCRIPTIONS
# (reused rather than reimplemented independently - see module docstring).
# Reworded very slightly here to read naturally as "what this policy
# section covers" from an interpretation-time perspective rather than a
# drafting-time instruction.
_POLICY_SECTION_DESCRIPTIONS = {
    "purpose_and_scope": "Why the security policy exists and who/what it covers.",
    "responsibilities_and_governance": "Who is responsible for information security, including named governance roles.",
    "access_and_authentication": "Policy requirements for account access, passwords/authentication and privileged access.",
    "devices_protection_and_updates": "Policy requirements for protecting and updating staff devices/endpoints.",
    "information_handling_and_backup": "Policy requirements for handling confidential/personal information and backing up important business information.",
    "workplace_and_remote_working": "Policy requirements that vary by where people work (office / home / shared / hybrid).",
    "security_incidents_and_reporting": "Policy requirements for what staff must do if they suspect or discover a security incident.",
    "review_approval_and_document_control": "How and when the security policy is reviewed, approved and version-controlled.",
}

_ORG_FACT_DESCRIPTIONS = {
    "org:certification_cyber_essentials": "The organisation's Cyber Essentials certification status.",
    "org:certification_iso27001": "The organisation's ISO 27001 certification status.",
    "org:working_model": "How the organisation's staff mainly work (office / remote / hybrid), derived from its recorded workplaces.",
    "org:handles_personal_data": "Whether the organisation handles personal data.",
    "org:handles_confidential_business_data": "Whether the organisation handles customer confidential/sensitive business data.",
    "org:handles_payment_card_data": "Whether the organisation handles payment-card data directly.",
    "org:handles_special_category_data": "Whether the organisation handles special-category/highly sensitive personal data.",
    "org:receives_security_questionnaires": "Whether customers send the organisation security questionnaires.",
    "org:develops_hosts_own_software": "Whether the organisation develops or hosts its own software/service.",
}
# Order matches the dispatch instruction's own listing.
_ORG_FACT_KEYS = [
    "org:certification_cyber_essentials",
    "org:certification_iso27001",
    "org:working_model",
    "org:handles_personal_data",
    "org:handles_confidential_business_data",
    "org:handles_payment_card_data",
    "org:handles_special_category_data",
    "org:receives_security_questionnaires",
    "org:develops_hosts_own_software",
]

CATALOGUE = (
    [
        {"key": f"control:{item['key']}", "description": item["question"]}
        for item in _BASELINE_CATALOGUE
    ]
    + [
        {"key": f"policy_section:{section_key}", "description": _POLICY_SECTION_DESCRIPTIONS[section_key]}
        for section_key in ALLOWED_SECTION_KEYS
    ]
    + [{"key": key, "description": _ORG_FACT_DESCRIPTIONS[key]} for key in _ORG_FACT_KEYS]
)

CATALOGUE_BY_KEY = {entry["key"]: entry for entry in CATALOGUE}
CATALOGUE_KEYS = list(CATALOGUE_BY_KEY.keys())

assert len(CATALOGUE_KEYS) == len(CATALOGUE), "Catalogue keys must be unique."
