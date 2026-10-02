# M008D — Policy Clause-to-Source Truth Matrix (Revision 2)

**Status:** DESIGN ARTEFACT — this file's own Revision 1 content (as
merged in PR #84) is superseded by the NORMATIVE/implementation-status
split documented in `docs/design/M008D-POLICY-ARCHITECTURE.md` and
option-level provenance (Central Architecture §4). Two tables: the fixed
normative clauses (same across every organisation, in the distributable
PDF) and the implementation-status rows (keyed to exact `option_code`,
shown only in
the in-product review screen, never the PDF).

## Table 1 — Normative clauses (distributable PDF)

Every row below is **fixed template text**, identical for every
organisation regardless of current state — "source" here means *why
this clause exists at all*, not a confirmed fact about this specific
organisation.

| Policy statement (as rendered) | Source | Classification |
|---|---|---|
| "This policy applies to all staff, contractors and systems..." | Fixed normative template | NORMATIVE_REQUIREMENT |
| "Senior leadership, represented by &lt;name&gt;, maintains overall accountability..." | `GovernanceRoleAssignment` where `role == ROLE_SENIOR_LEADERSHIP` → `OrganisationPerson.full_name` | NORMATIVE_REQUIREMENT (role existence is a confirmed fact; the *obligation* is fixed) |
| "The Security responsible person, &lt;name&gt;, is accountable for day-to-day information security matters..." | `role == ROLE_SECURITY_RESPONSIBLE` → name | NORMATIVE_REQUIREMENT |
| "Multi-factor authentication must be used for all staff and administrator accounts." | Fixed normative template | NORMATIVE_REQUIREMENT |
| "Administrator/privileged access must be kept separate..." | Fixed normative template | NORMATIVE_REQUIREMENT |
| "Work devices must run appropriate endpoint protection..." | Fixed normative template | NORMATIVE_REQUIREMENT |
| "Important business data must be backed up, and the ability to restore... must be periodically tested." | Fixed normative template | NORMATIVE_REQUIREMENT |
| "Any remote or offsite access to business systems, where it exists, must be governed and controlled." | Fixed normative template (deliberately phrased to hold true whether or not remote access currently applies — see note below) | NORMATIVE_REQUIREMENT |
| "Staff must have a clear, known route to report suspected security incidents to &lt;name&gt;." | `role == ROLE_SECURITY_RESPONSIBLE` → name | NORMATIVE_REQUIREMENT |
| "Staff must receive regular security-awareness activity..." | Fixed normative template | NORMATIVE_REQUIREMENT |
| "This policy is reviewed at least annually... and is approved by &lt;name&gt; before distribution." | `role == ROLE_POLICY_AUTHORISER` → name | NORMATIVE_REQUIREMENT |
| "Approving this policy records the organisation&rsquo;s security commitments. It does not certify that every control is currently in place..." | Fixed normative template | NORMATIVE_REQUIREMENT |

**Note on section 6's universal phrasing:** "where it exists" is
deliberate — it lets the same fixed sentence hold true for an
organisation that has confirmed no remote/offsite access at all
(`REMOTE_ACCESS_NOT_APPLICABLE`) and one that has real, ungoverned
remote access today. Applicability (NOT_APPLICABLE) is a genuinely
different concept from current-state (MET/GAP) — this is the one place
the normative text's own wording, not just the implementation-status
row, had to be written carefully to stay true in both cases rather than
assert a commitment that would be nonsensical for a confirmed-no-remote
organisation.

## Table 2 — Implementation status (in-product review screen only, keyed to exact `option_code`)

This is the literal mechanism for Central Architecture's §4 rule. Every
row's "source" is the exact `option_code` selected, not the collapsed
canonical state — demonstrated here for every control that has more
than one option mapping to the same state, across all three sample
scenarios, not merely the backups example named in the instruction.

| Control | `option_code` | Current-state text | Action text | Status |
|---|---|---|---|---|
| MFA (staff) | `MFA_USER_SOME_REQUIRED` | "required for some, not all" | "Extend enforcement to every account." | GAP |
| MFA (staff) | `MFA_USER_AVAILABLE_NOT_ENFORCED` | "available but not enforced" | "Enforce MFA, not merely offer it." | GAP (different wording from the row above, same canonical state) |
| Endpoint protection | `ENDPOINT_PROTECTION_MOST` | "in place for most, not all devices" | "Extend coverage to the remaining devices." | GAP |
| Endpoint protection | `ENDPOINT_PROTECTION_COMPANY_ONLY` | "company devices protected; personal/BYOD devices are not" | "Extend protection to personally owned devices used for work." | GAP (materially different gap from the row above) |
| Patching | `PATCHING_MOSTLY_CURRENT` | "mostly current, some gaps" | "Close the remaining patching gaps." | GAP |
| Patching | `PATCHING_IRREGULAR` | "irregular, no consistent cadence" | "Establish a routine patching cadence." | GAP (worse gap, different action) |
| Backups | `BACKUPS_RESTORE_UNTESTED` | "backed up, restore never tested" | "Schedule and carry out a test restore." | GAP |
| Backups | `BACKUPS_COVERAGE_PARTIAL` | "backed up, but not all systems covered" | "Extend backup coverage to the remaining systems." | GAP (Central Architecture's own named example) |
| Email/phishing | `PHISHING_PROTECTION_BASIC_DEFAULT` | "default platform filtering only" | "Enable active anti-phishing protection beyond platform defaults." | GAP |
| Email/phishing | `PHISHING_PROTECTION_PARTIAL` | "enabled for some accounts/domains" | "Extend protection to every account/domain." | GAP (different gap shape) |

## The one hard rule this matrix enforces (unchanged principle, now proven at the option level)

Every PARTIAL-mapped option gets its own, specific current-state and
action sentence pair — never a single generic "partially in place"
sentence shared across options that mean different things. Proven above
for five of the twelve controls (every control in Revision 2's catalogue
that actually has more than one option mapping to the same canonical
state); the other seven controls have exactly one PARTIAL (or no
PARTIAL) option each, so no collapsing risk exists for them and no
extra row is needed.

UNKNOWN rows (`status: NOT_YET_CONFIRMED`) are never written as GAP —
see Scenario C's full implementation-status record
(`docs/design/policies/M008D-status-c.pdf`) for all twelve controls in
this state simultaneously.
