"""
M008D-WI4 — the deterministic NORMATIVE clause library (docs/design/
M008D-POLICY-ARCHITECTURE.md §2, docs/design/M008D-POLICY-TRUTH-MATRIX.md
Table 1).

Same discipline as `risk_register.methodology`/`risk_register.risk_choices`:
a small, Git-controlled, plain-Python table - not an editable database
table, not AI-generated. Every clause below is FIXED template text,
identical for every organisation regardless of current control state (the
NORMATIVE/implementation-status split - see `docs/design/
M008D-POLICY-ARCHITECTURE.md` §1-2). The current-state/gap-or-action text
that DOES vary by organisation lives in `policy.implementation_status`
instead, and is never rendered into the distributable PDF (see that
module's own docstring).

== Provenance of each clause's wording ==

Table 1 (`docs/design/M008D-POLICY-TRUTH-MATRIX.md`) gives already-approved,
exact wording for most clauses - transcribed verbatim below wherever given,
with two judgement calls recorded here (not silently resolved elsewhere):

1. Table 1's own rows are printed there with a trailing "..." for several
   clauses (e.g. "This policy applies to all staff, contractors and
   systems..."). That ellipsis is the design document's own illustrative
   truncation for a table cell, not an instruction to render a literal
   "...". Every such clause below opens with Table 1's exact given prefix,
   verbatim, and is completed with a plain, unembellished ending in the
   same register - never adding a NEW requirement Table 1 did not already
   imply.

2. Table 1's single MFA row - "Multi-factor authentication must be used
   for all staff and administrator accounts." - textually covers BOTH
   `mfa_user_accounts` AND `mfa_privileged_accounts` in one sentence. This
   WI's own instructions ask for exactly one clause per control (12
   total), so this exact sentence is assigned, verbatim, to
   `mfa_user_accounts` (the control it names first and most directly -
   "staff... accounts"). Repeating the IDENTICAL sentence a second time for
   `mfa_privileged_accounts` would read as an obviously duplicated
   paragraph once both clauses are concatenated into the same
   `access_and_authentication` section - so `mfa_privileged_accounts` gets
   its OWN, separately-authored clause below (never contradicting Table
   1's sentence - it narrows further onto admin/privileged accounts
   specifically, grounded in `security_baseline.stage4.QUESTION_COPY
   ["mfa_privileged_accounts"]`'s own subject matter: "Admin accounts can
   change settings for everyone...").

Every other control this file writes its own clause for (`patching`,
`device_encryption`, `joiner_mover_leaver`, `email_phishing_protection`, and
`mfa_privileged_accounts` per point 2 above) is grounded directly in that
same control's `security_baseline.stage4.QUESTION_COPY` entry - a plain,
unconditional "must" statement, true regardless of current state, in the
same voice as Table 1's own given clauses. None of these five invents a
requirement unrelated to what its control actually assesses.

== Section-key assignment ==

Every clause is assigned to exactly one of the 8 `policy.section_labels.
SECTION_LABELS` keys. The judgement calls the WI's own dispatch flags as
"your call, document it":

- `joiner_mover_leaver` -> `access_and_authentication` (removing ACCESS
  when someone leaves/changes role is an access-control matter, the same
  section `mfa_*`/`privileged_access_separation` already sit in).
- `remote_access_control` -> `workplace_and_remote_working` (it is
  specifically about HOW WORK happens remotely, distinct from the
  day-to-day sign-in/access clauses grouped under
  `access_and_authentication`).
- `email_phishing_protection` -> `devices_protection_and_updates` (a
  technical protective control on the email channel, grouped with the
  other technical device/software controls - endpoint protection,
  patching, device encryption - rather than with the
  people/process-shaped `security_incidents_and_reporting` clauses).
- `security_awareness_training` -> `security_incidents_and_reporting`
  (both are "helping people respond well" clauses - recognising threats
  and knowing how to report them - grouped together per the dispatch's
  own suggested pairing).

== Governance-role interpolation ==

Three clauses below (`senior_leadership_accountability`,
`security_responsible_accountability`/`incident_reporting_route`,
`review_approval`) name a governance role's currently-assigned person.
`_role_name` resolves this from `governance.GovernanceRoleAssignment`
exactly as `policy.services.get_policy_authoriser` already does for the
Policy Authoriser - and substitutes the literal placeholder
`UNASSIGNED_ROLE_NAME_PLACEHOLDER` ("[name not yet confirmed]") when no
assignment exists yet (M008D-SAMPLE-POLICIES.md Scenario C's approved
behaviour for an unassigned role), rather than leaving a blank or raising.
This is the ONLY place that placeholder is produced - every clause
template reaches it via `_role_name`, never by its own ad-hoc string.
"""
from __future__ import annotations

import dataclasses

from ai_platform.policy_contracts import PolicySection
from governance.models import GovernanceRoleAssignment
from policy.section_labels import SECTION_LABELS
from security_baseline.catalogue import CATALOGUE_KEYS

CLAUSE_LIBRARY_VERSION = "2026-10-deterministic-v1"

# M008D-SAMPLE-POLICIES.md Scenario C's approved placeholder for a
# governance role with no current assignment - substituted literally into
# clause prose, never a blank string, never a raised error.
UNASSIGNED_ROLE_NAME_PLACEHOLDER = "[name not yet confirmed]"

# The exact, adopted-verbatim statement (M008D-POLICY-ARCHITECTURE.md §6
# condition 5) - also used as this clause library's own final NORMATIVE
# clause (Table 1's last row), so the one sentence the readiness gate's
# approval-confirmation screen must show and the one sentence every
# distributed policy ends with are structurally the same string, not two
# separately-maintained copies.
APPROVAL_DOES_NOT_CERTIFY_COMPLIANCE_STATEMENT = (
    "Approving this policy records your organisation's security "
    "commitments. It does not certify that every control is currently in "
    "place — see Implementation status for the current picture."
)


@dataclasses.dataclass(frozen=True)
class Clause:
    """One fixed, versioned normative clause.

    `control_key` is the exact `security_baseline.catalogue` control key
    this clause's requirement corresponds to, or `None` for a structural
    clause that is not tied to one specific control (policy scope,
    governance accountability, review/approval, the final statement).
    `template` may reference `{policy_authoriser_name}` /
    `{security_responsible_name}` / `{senior_leadership_name}` - rendered
    by `_render_clause_text` below, never raw string concatenation at a
    call site.
    """

    clause_id: str
    section_key: str
    control_key: "str | None"
    template: str


# ---------------------------------------------------------------------------
# The clause set itself (Table 1 + the 5 self-authored control clauses -
# see module docstring). Order within this list is the DETERMINISTIC
# composition order within each clause's own section - never alphabetical,
# never DB-ordering-dependent.
# ---------------------------------------------------------------------------
CLAUSES: "list[Clause]" = [
    # --- purpose_and_scope ---------------------------------------------
    Clause(
        clause_id="scope",
        section_key="purpose_and_scope",
        control_key=None,
        template=(
            "This policy applies to all staff, contractors and systems "
            "used in connection with the organisation's business."
        ),
    ),
    # --- responsibilities_and_governance --------------------------------
    Clause(
        clause_id="senior_leadership_accountability",
        section_key="responsibilities_and_governance",
        control_key=None,
        template=(
            "Senior leadership, represented by {senior_leadership_name}, "
            "maintains overall accountability for information security "
            "within the organisation."
        ),
    ),
    Clause(
        clause_id="security_responsible_accountability",
        section_key="responsibilities_and_governance",
        control_key=None,
        template=(
            "The Security responsible person, {security_responsible_name}, "
            "is accountable for day-to-day information security matters."
        ),
    ),
    # --- access_and_authentication ---------------------------------------
    Clause(
        clause_id="mfa_user_accounts",
        section_key="access_and_authentication",
        control_key="mfa_user_accounts",
        template=(
            "Multi-factor authentication must be used for all staff and "
            "administrator accounts."
        ),
    ),
    Clause(
        clause_id="mfa_privileged_accounts",
        section_key="access_and_authentication",
        control_key="mfa_privileged_accounts",
        template=(
            "Administrator and other privileged accounts must additionally "
            "require multi-factor authentication, reflecting the greater "
            "impact if such an account is compromised."
        ),
    ),
    Clause(
        clause_id="privileged_access_separation",
        section_key="access_and_authentication",
        control_key="privileged_access_separation",
        template=(
            "Administrator/privileged access must be kept separate from "
            "everyday user accounts and used only for administrative tasks."
        ),
    ),
    Clause(
        clause_id="joiner_mover_leaver",
        section_key="access_and_authentication",
        control_key="joiner_mover_leaver",
        template=(
            "When someone leaves the organisation or changes role, their "
            "access to business systems and data must be removed or "
            "adjusted promptly."
        ),
    ),
    # --- devices_protection_and_updates ------------------------------------
    Clause(
        clause_id="endpoint_protection",
        section_key="devices_protection_and_updates",
        control_key="endpoint_protection",
        template=(
            "Work devices must run appropriate endpoint protection to guard "
            "against malware."
        ),
    ),
    Clause(
        clause_id="patching",
        section_key="devices_protection_and_updates",
        control_key="patching",
        template=(
            "Operating systems and business applications must be kept up "
            "to date with security updates."
        ),
    ),
    Clause(
        clause_id="device_encryption",
        section_key="devices_protection_and_updates",
        control_key="device_encryption",
        template=(
            "Devices that hold business data must have full-disk "
            "encryption enabled."
        ),
    ),
    Clause(
        clause_id="email_phishing_protection",
        section_key="devices_protection_and_updates",
        control_key="email_phishing_protection",
        template=(
            "Business email must be protected against phishing and other "
            "malicious email beyond basic default spam filtering."
        ),
    ),
    # --- information_handling_and_backup -----------------------------------
    Clause(
        clause_id="backups",
        section_key="information_handling_and_backup",
        control_key="backups",
        template=(
            "Important business data must be backed up, and the ability to "
            "restore from backup must be periodically tested."
        ),
    ),
    # --- workplace_and_remote_working ---------------------------------------
    Clause(
        clause_id="remote_access_control",
        section_key="workplace_and_remote_working",
        control_key="remote_access_control",
        template=(
            "Any remote or offsite access to business systems, where it "
            "exists, must be governed and controlled."
        ),
    ),
    # --- security_incidents_and_reporting ------------------------------------
    Clause(
        clause_id="incident_reporting_route",
        section_key="security_incidents_and_reporting",
        control_key="incident_reporting_route",
        template=(
            "Staff must have a clear, known route to report suspected "
            "security incidents to {security_responsible_name}."
        ),
    ),
    Clause(
        clause_id="security_awareness_training",
        section_key="security_incidents_and_reporting",
        control_key="security_awareness_training",
        template=(
            "Staff must receive regular security-awareness activity to "
            "help them recognise and respond to common security threats."
        ),
    ),
    # --- review_approval_and_document_control --------------------------------
    Clause(
        clause_id="review_approval",
        section_key="review_approval_and_document_control",
        control_key=None,
        template=(
            "This policy is reviewed at least annually, and any new "
            "version is approved by {policy_authoriser_name} before "
            "distribution."
        ),
    ),
    Clause(
        clause_id="final_statement",
        section_key="review_approval_and_document_control",
        control_key=None,
        template=APPROVAL_DOES_NOT_CERTIFY_COMPLIANCE_STATEMENT,
    ),
]

# --- Catalogue-wide invariants (assert-at-import-time, mirrors
# risk_register.methodology/risk_register.risk_choices's own discipline) ---
assert CLAUSE_LIBRARY_VERSION, "CLAUSE_LIBRARY_VERSION must be set."

_CONTROL_CLAUSE_KEYS = [c.control_key for c in CLAUSES if c.control_key is not None]
assert set(_CONTROL_CLAUSE_KEYS) == set(CATALOGUE_KEYS), (
    "policy.clause_library must carry exactly one normative clause per "
    "security_baseline control key - never more, never fewer."
)
assert len(_CONTROL_CLAUSE_KEYS) == len(set(_CONTROL_CLAUSE_KEYS)), (
    "policy.clause_library must not carry more than one clause for the "
    "same control_key."
)

_VALID_SECTION_KEYS = frozenset(SECTION_LABELS.keys())
for _clause in CLAUSES:
    assert _clause.section_key in _VALID_SECTION_KEYS, (
        f"Clause {_clause.clause_id!r} has an unrecognised section_key "
        f"{_clause.section_key!r} - must be one of {sorted(_VALID_SECTION_KEYS)!r}."
    )
del _clause

assert {c.section_key for c in CLAUSES} == _VALID_SECTION_KEYS, (
    "Every one of the 8 policy.section_labels.SECTION_LABELS keys must "
    "have at least one clause assigned to it."
)

_CLAUSE_IDS = [c.clause_id for c in CLAUSES]
assert len(_CLAUSE_IDS) == len(set(_CLAUSE_IDS)), "Every clause_id must be unique."
del _CLAUSE_IDS, _CONTROL_CLAUSE_KEYS


def _role_name(organisation, role: str) -> str:
    """The current full name of whoever holds `role` for `organisation`
    right now, or `UNASSIGNED_ROLE_NAME_PLACEHOLDER` if the role has no
    current `GovernanceRoleAssignment` - never a blank string, never a
    raised error (M008D-SAMPLE-POLICIES.md Scenario C). Mirrors
    `policy.services.get_policy_authoriser`'s own organisation-scoped
    lookup exactly, generalised to any of the three fixed roles."""
    assignment = (
        GovernanceRoleAssignment.objects.filter(organisation=organisation, role=role)
        .select_related("person")
        .first()
    )
    if assignment is None:
        return UNASSIGNED_ROLE_NAME_PLACEHOLDER
    return assignment.person.full_name


def _role_names(organisation) -> dict:
    """The `{placeholder_name: resolved_name}` mapping every clause
    template's `.format(**role_names)` call below needs, computed ONCE per
    generation call (never once per clause) so a single organisation
    lookup per role is shared across every clause that happens to
    reference it (e.g. `security_responsible_name` is used by both
    `security_responsible_accountability` and
    `incident_reporting_route`)."""
    return {
        "policy_authoriser_name": _role_name(
            organisation, GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        ),
        "security_responsible_name": _role_name(
            organisation, GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE
        ),
        "senior_leadership_name": _role_name(
            organisation, GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP
        ),
    }


def _section_order() -> "list[str]":
    """`policy.section_labels.SECTION_LABELS`'s own key order - the single
    deterministic section order every generated policy's `sections` list
    follows (matches `ai_platform.policy_contracts.ALLOWED_SECTION_KEYS`'s
    own order, which that dictionary was built to mirror)."""
    return list(SECTION_LABELS.keys())


def build_normative_sections(organisation) -> "list[PolicySection]":
    """
    Render every `CLAUSES` entry against `organisation`'s CURRENT
    governance-role assignments, group by `section_key` (in
    `_section_order()`'s fixed order, clauses within a section in
    `CLAUSES`'s own fixed order), and return one `PolicySection` per
    section - the exact shape `policy.services._persist_draft`/
    `ai_platform.policy_contracts.PolicyGenerationResult` already expect,
    so a deterministic draft's `sections` list is structurally
    indistinguishable from an AI-generated one (same `section_key`/
    `content` shape) to every downstream consumer (the editor, the PDF
    renderer, the approval flow).

    Every one of the 8 sections is populated (`CLAUSES`'s own
    assert-at-import-time invariant above guarantees at least one clause
    per section), so this always returns exactly 8 `PolicySection`s,
    regardless of `organisation`'s own state - the defining property of a
    NORMATIVE clause set (docs/design/M008D-POLICY-ARCHITECTURE.md §2):
    identical structure for every organisation, only governance-role NAMES
    (or the unassigned placeholder) vary.
    """
    role_names = _role_names(organisation)

    clauses_by_section: "dict[str, list[str]]" = {key: [] for key in _section_order()}
    for clause in CLAUSES:
        clauses_by_section[clause.section_key].append(clause.template.format(**role_names))

    return [
        PolicySection(section_key=section_key, content="\n\n".join(texts))
        for section_key, texts in clauses_by_section.items()
        if texts
    ]


__all__ = [
    "CLAUSE_LIBRARY_VERSION",
    "UNASSIGNED_ROLE_NAME_PLACEHOLDER",
    "APPROVAL_DOES_NOT_CERTIFY_COMPLIANCE_STATEMENT",
    "Clause",
    "CLAUSES",
    "build_normative_sections",
]
