# M008B — Complete Security Foundations Question Catalogue (Design Proposal, Revision 2)

**Status:** DESIGN ARTEFACT — Revision 2, incorporating Central
Architecture's correction pass on PR #84's Revision 1. Overall direction
APPROVED; this revision implements the bounded corrections, not a
reinterpretation.

**What changed since Revision 1:**
1. Every bounded free-text follow-up removed (no "Which groups?", no
   "What's covered?") — replaced with finite options or omitted.
2. NOT_APPLICABLE removed entirely for `device_encryption`,
   `endpoint_protection`, `security_awareness_training`,
   `privileged_access_separation`. `remote_access_control` and
   `joiner_mover_leaver` NOT_APPLICABLE now gated on new, dedicated
   structured facts (§0 below) — never on `staff_count`, cloud-provider
   selection, or office-working status alone.
3. Every option now carries a stable, machine-readable `option_code`.
4. A new, separately versioned methodology identifier governs this
   structured-question layer (§0).
5. Where two options collapse to the same canonical five-state answer
   but mean materially different things, each keeps its own
   `option_code` and its own downstream wording — applied to all 12
   controls, not just the backups example Central Architecture named.
6. **[WI-ERRATA]** `CATALOGUE_VERSION` bumps to `"2026-10-baseline-v2"`
   — corrected from this revision's own earlier "stays unchanged"
   claim, since question wording has materially changed (§0).

## 0. New versioning

**[WI-ERRATA correction]** This section originally stated
`CATALOGUE_VERSION` stays unchanged. Central Architecture corrected
this: the existing source contract requires a version bump whenever
question *wording* changes (which it has, extensively, in this
revision), even though control keys and weights do not change. The
corrected versioning is:

- `security_baseline.catalogue.CATALOGUE_VERSION` bumps to
  `"2026-10-baseline-v2"` — the **12 control keys, their weights, and
  every `risk_register.methodology` scenario ID remain exactly
  unchanged**; only the version identifier itself changes, reflecting
  that the question wording/catalogue presented to the customer has
  materially changed since `"2026-09-baseline-v1"`.
- A second, separate identifier versions the new structured-question
  layer itself (option codes, provenance shape): `FOUNDATIONS_QUESTION_
  METHODOLOGY_VERSION = "2026-10-structured-v1"` — unchanged from
  Revision 2's own proposal.
- The two identifiers answer two different questions: `CATALOGUE_
  VERSION` answers "which version of the 12-control question/weighting
  methodology was this answered against" (existing M002/M007 contract);
  `FOUNDATIONS_QUESTION_METHODOLOGY_VERSION` answers "which version of
  the *structured option-code* scheme produced this specific stored
  answer." Both are recorded per answer (below) — neither supersedes
  the other.
- Persisted provenance per answer (the `AnswerSelectionDetail`-shaped
  model from §B4, Revision 1 — unchanged in shape, now with explicit
  fields, **corrected to carry both version identifiers**):
  `control_key`, `option_code`, `derived_answer` (the canonical
  five-state value), `catalogue_version` (the `security_baseline.
  catalogue.CATALOGUE_VERSION` this answer was given against),
  `methodology_version` (the `FOUNDATIONS_QUESTION_METHODOLOGY_VERSION`
  that produced this `option_code`). Display wording is never identity
  — only `option_code` is.
- **Two new dedicated structured facts** (new `OrganisationProfile` or
  sibling fields — additive, not replacing anything):
  - `has_remote_or_offsite_access` (tri-state: `yes` / `no` /
    `unknown`, default `unknown`) — "Does anyone access business
    systems or data from outside your normal workplace(s), even
    occasionally (e.g. from home, while travelling)?" This, not
    `working_model`, is the sole authority for `remote_access_control`'s
    NOT_APPLICABLE eligibility.
  - `people_with_system_access_count` (integer, nullable) — "How many
    people (including contractors or anyone else, not just staff) have
    access to your business systems or accounts?" This, not
    `staff_count`, is the sole authority for `joiner_mover_leaver`'s
    NOT_APPLICABLE eligibility (requires confirmed value `== 1`
    **and** a confirmed "no other accounts exist" follow-up choice — see
    control 7 below).

## Format per control

Stable key, title, plain-English question, why it matters, predefined
answers **with stable `option_code`s**, canonical mapping, NOT_APPLICABLE
eligibility (now far more restrictive), deterministic risk/policy
consequences (unchanged scenario IDs/section keys from Revision 1),
evidence expectations, completion effect.

---

## 1. `mfa_user_accounts` — Multi-factor authentication (staff)

**[WI-ERRATA correction]** This control's "Why it matters" line was
dropped when this document was rewritten for the correction pass.
Restored below, verbatim from the original approved wording (git
history `9873ca6`) — this applies to every control in this document
below marked the same way, not a new design decision.

- **Customer-facing title:** Staff sign-in protection
- **Question:** "How is multi-factor authentication (MFA) used for
  ordinary staff accounts (e.g. Microsoft 365, Google Workspace)?"
- **Why it matters:** "MFA is one of the single most effective
  protections against stolen-password account takeover — without it, a
  leaked or guessed password is often enough to get in."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `MFA_USER_ALL_REQUIRED` | MFA required for all staff accounts | YES |
  | `MFA_USER_SOME_REQUIRED` | MFA required for some staff/groups, not all | PARTIAL |
  | `MFA_USER_AVAILABLE_NOT_ENFORCED` | MFA available but not enforced | PARTIAL |
  | `MFA_USER_NOT_USED` | MFA not currently used | NO |
  | `MFA_USER_NOT_SURE` | Not sure | UNKNOWN |
- **No follow-up field** (Revision 1's "Which groups?" removed —
  `MFA_USER_SOME_REQUIRED` and `MFA_USER_AVAILABLE_NOT_ENFORCED` are
  themselves the distinguishing structured facts; no further detail is
  collected).
- **NOT_APPLICABLE eligible:** No (unchanged).
- **Option-level provenance note:** `MFA_USER_SOME_REQUIRED` ("enforced
  for some, not for others") and `MFA_USER_AVAILABLE_NOT_ENFORCED`
  ("technically on, enforced for nobody") both map to PARTIAL but are
  materially different — downstream policy wording must address each
  distinctly (§4 below), never collapsed to one generic "partially
  enabled" sentence.
- Risk/policy/weight/evidence: unchanged from Revision 1.

## 2. `mfa_privileged_accounts` — Multi-factor authentication (admin)

- **Customer-facing title:** Admin/privileged account protection
- **Question:** "How is multi-factor authentication used for admin/
  privileged accounts (e.g. IT admin, cloud admin, domain admin)?"
- **Why it matters:** "Admin accounts can change settings for everyone
  — if one is compromised, the attacker can often disable other
  protections too."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `MFA_ADMIN_ALL_REQUIRED` | MFA required for all admin/privileged accounts | YES |
  | `MFA_ADMIN_SOME_REQUIRED` | MFA required for some admin accounts, not all | PARTIAL |
  | `MFA_ADMIN_AVAILABLE_NOT_ENFORCED` | MFA available but not enforced for admin accounts | PARTIAL |
  | `MFA_ADMIN_NOT_USED` | MFA not used for admin accounts | NO |
  | `MFA_ADMIN_NOT_SURE` | Not sure / don't know who holds admin accounts | UNKNOWN |
- **NOT_APPLICABLE eligible:** No (unchanged).
- **Option-level provenance:** `MFA_ADMIN_SOME_REQUIRED` vs.
  `MFA_ADMIN_AVAILABLE_NOT_ENFORCED` kept distinct, same reasoning as
  control 1.

## 3. `endpoint_protection` — Endpoint protection

- **Customer-facing title:** Device protection
- **Question:** "Do the devices staff use for work have anti-malware/
  endpoint protection?"
- **Why it matters:** "Protects against malware and ransomware that
  could spread from an infected device into the rest of the business."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `ENDPOINT_PROTECTION_ALL` | All work devices have endpoint protection | YES |
  | `ENDPOINT_PROTECTION_MOST` | Most/some work devices have it, not all | PARTIAL |
  | `ENDPOINT_PROTECTION_COMPANY_ONLY` | Company devices do, personal/BYOD devices don't | PARTIAL |
  | `ENDPOINT_PROTECTION_NONE` | No endpoint protection in place | NO |
  | `ENDPOINT_PROTECTION_NOT_SURE` | Not sure | UNKNOWN |
- **Conditional option availability (unchanged from Revision 1, this is
  option-set conditioning, not a free-text field):** `ENDPOINT_
  PROTECTION_COMPANY_ONLY` is only offered when `OrganisationProfile.
  endpoint_management` is `"byod"` or `"both"`.
- **NOT_APPLICABLE eligible:** **No — removed per Central Architecture's
  correction.** Revision 1's rare-edge-case NA eligibility is withdrawn;
  every organisation with any work devices answers this directly.
- **Option-level provenance:** `ENDPOINT_PROTECTION_MOST` vs.
  `ENDPOINT_PROTECTION_COMPANY_ONLY` both PARTIAL, kept distinct — the
  first is "coverage gap, unclear which devices"; the second is a
  specific, known BYOD gap — different downstream wording.

## 4. `patching` — Patching

- **Customer-facing title:** Keeping software up to date
- **Question:** "Are operating systems and business applications kept
  up to date with security updates?"
- **Why it matters:** "Unpatched software is one of the most common
  ways attackers get in — many attacks exploit a known, already-fixed
  flaw."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `PATCHING_AUTOMATIC` | Automatic updates enabled everywhere, checked regularly | YES |
  | `PATCHING_MOSTLY_CURRENT` | Updates mostly kept current, some gaps | PARTIAL |
  | `PATCHING_IRREGULAR` | Updates happen irregularly / only when something breaks | PARTIAL |
  | `PATCHING_NONE` | No consistent update practice | NO |
  | `PATCHING_NOT_SURE` | Not sure | UNKNOWN |
- **NOT_APPLICABLE eligible:** No (unchanged).
- **Option-level provenance:** `PATCHING_MOSTLY_CURRENT` ("mostly fine,
  some gaps") vs. `PATCHING_IRREGULAR` ("no real cadence") kept distinct
  — the latter is a materially worse PARTIAL, different action wording.

## 5. `device_encryption` — Device encryption

- **Customer-facing title:** Protecting data if a device is lost or
  stolen
- **Question:** "Is full-disk encryption (e.g. BitLocker, FileVault)
  enabled on devices that hold business data?"
- **Why it matters:** "If a laptop is lost or stolen, encryption is
  what stops someone simply reading the files off the drive."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `DEVICE_ENCRYPTION_ALL` | Enabled on all relevant devices | YES |
  | `DEVICE_ENCRYPTION_SOME` | Enabled on some, not all | PARTIAL |
  | `DEVICE_ENCRYPTION_NONE` | Not enabled | NO |
  | `DEVICE_ENCRYPTION_NOT_SURE` | Not sure | UNKNOWN |
- **NOT_APPLICABLE eligible:** **No — removed per Central Architecture's
  correction.** Revision 1's cloud-only-business NA gate is withdrawn
  entirely; `DEVICE_ENCRYPTION_ALL`/`_SOME`/`_NONE`/`_NOT_SURE` are the
  complete option set, no fifth "doesn't apply" option.

## 6. `backups` — Backups

- **Customer-facing title:** Backups you can actually restore from
- **Question:** "Is important business data backed up, and has anyone
  actually tried restoring from that backup?"
- **Why it matters:** "A backup nobody has tested is a hope, not a
  safeguard — ransomware and accidental deletion are the two most
  common reasons businesses need to restore."
- **Options — now expanded to carry what Revision 1's free-text
  follow-up used to capture, as its own distinct, finite options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `BACKUPS_TESTED` | Backed up AND a restore has been tested | YES |
  | `BACKUPS_RESTORE_UNTESTED` | Backed up, but a restore has never been tested | PARTIAL |
  | `BACKUPS_COVERAGE_PARTIAL` | Backed up, but only some systems/data are covered | PARTIAL |
  | `BACKUPS_NONE` | Not backed up | NO |
  | `BACKUPS_NOT_SURE` | Not sure | UNKNOWN |
- **No follow-up field** (Revision 1's "What's covered?" free text
  removed — `BACKUPS_COVERAGE_PARTIAL` itself is the structured fact;
  which specific systems are covered is not collected at Foundation
  tier).
- **NOT_APPLICABLE eligible:** No (unchanged).
- **Option-level provenance — Central Architecture's own named
  example, implemented exactly:** `BACKUPS_RESTORE_UNTESTED` and
  `BACKUPS_COVERAGE_PARTIAL` both map to PARTIAL but require different
  wording downstream — "backed up but unverified" vs. "backed up but
  incomplete" are different gaps with different recommended actions
  (test a restore vs. extend coverage).

## 7. `joiner_mover_leaver` — Access removal

- **Customer-facing title:** Removing access when someone leaves or
  changes role
- **Question:** "When someone leaves the business or changes role, is
  their access removed or adjusted promptly?"
- **Why it matters:** "Former staff keeping access after they leave is
  a common, avoidable way confidential information or systems stay
  exposed."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `JML_DEFINED_FOLLOWED` | Defined process, followed consistently | YES |
  | `JML_INFORMAL_USUALLY` | Informal process, usually followed | PARTIAL |
  | `JML_INCONSISTENT` | Happens inconsistently / depends who remembers | PARTIAL |
  | `JML_NONE` | No process | NO |
  | `JML_NOT_SURE` | Not sure | UNKNOWN |
- **NOT_APPLICABLE eligible:** **Yes, but re-gated per Central
  Architecture's correction — no longer on bare `staff_count == 1`.**
  Requires BOTH: `people_with_system_access_count == 1` (the new
  dedicated fact, §0) AND an explicit confirmed follow-up choice at the
  point NOT_APPLICABLE is selected: "Confirm: no other staff,
  contractor, or shared/service accounts exist for this organisation"
  (a required checkbox-style confirmation, not free text, before
  `JML_NOT_APPLICABLE` can be submitted). `staff_count` alone is never
  consulted for this gate.
- **Option-level provenance:** `JML_INFORMAL_USUALLY` vs. `JML_
  INCONSISTENT` kept distinct — the first still broadly works, the
  second is a real process gap.

## 8. `privileged_access_separation` — Privileged access

- **Customer-facing title:** Keeping admin access separate from
  everyday accounts
- **Question:** "Do people with admin/privileged access use a separate
  account for admin tasks, rather than their everyday login?"
- **Why it matters:** "If the same account does admin tasks and
  everyday email/browsing, one phishing click can hand over
  admin-level access."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `PRIV_SEP_DEDICATED` | Dedicated separate admin accounts, used only for admin tasks | YES |
  | `PRIV_SEP_SOME` | Some separation, not consistently used | PARTIAL |
  | `PRIV_SEP_NONE` | Same account used for both | NO |
  | `PRIV_SEP_NOT_SURE` | Not sure / don't know who has admin access | UNKNOWN |
- **NOT_APPLICABLE eligible:** **No — removed per Central Architecture's
  correction.** Revision 1's sole-trader NA gate withdrawn; even a
  one-person business with any admin/privileged system answers this
  directly (if genuinely only one account exists, `PRIV_SEP_NONE` is
  the honest answer, not an N/A escape).

## 9. `security_awareness_training` — Staff awareness

- **Customer-facing title:** Helping staff recognise security risks
- **Question:** "Do staff get any security-awareness training, such as
  how to recognise phishing emails?"
- **Why it matters:** "Most breaches start with a person, not a
  technical flaw — a little awareness goes a long way."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `AWARENESS_REGULAR` | Regular, structured awareness activity | YES |
  | `AWARENESS_OCCASIONAL` | Occasional/informal | PARTIAL |
  | `AWARENESS_NONE` | No training provided | NO |
  | `AWARENESS_NOT_SURE` | Not sure | UNKNOWN |
- **NOT_APPLICABLE eligible:** **No — removed per Central Architecture's
  correction.** Even a sole trader answers this directly (typically
  `AWARENESS_NONE` if genuinely no activity exists) rather than
  escaping via N/A.

## 10. `incident_reporting_route` — Incident reporting

- **Customer-facing title:** Knowing who to tell if something goes
  wrong
- **Question:** "If a staff member suspects a security incident (e.g.
  clicked a bad link, lost a device), do they know who to tell and
  what happens next?"
- **Why it matters:** "Fast reporting limits damage — a known route
  means problems get handled in minutes, not discovered weeks later."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `INCIDENT_ROUTE_CLEAR` | Clear, known route and a named responsible person | YES |
  | `INCIDENT_ROUTE_INFORMAL` | Staff mostly know who to tell, but it's informal | PARTIAL |
  | `INCIDENT_ROUTE_NONE` | No clear route | NO |
  | `INCIDENT_ROUTE_NOT_SURE` | Not sure | UNKNOWN |
- **No follow-up field** (Revision 1's "link to governance role" idea
  removed as a question-time follow-up — the Security Responsible role,
  if assigned in Stage 2, is referenced automatically in policy wording
  via governance data already on file, never re-asked here).
- **NOT_APPLICABLE eligible:** No (unchanged).

## 11. `email_phishing_protection` — Email/phishing protection

- **Customer-facing title:** Protecting email from phishing and spam
- **Question:** "Are there protections against phishing and malicious
  email, beyond normal spam filtering?"
- **Why it matters:** "Email remains the single most common way
  attackers first get in — filtering reduces how many malicious
  messages staff ever see."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `PHISHING_PROTECTION_ACTIVE_ALL` | Active anti-phishing protection enabled on all business email | YES |
  | `PHISHING_PROTECTION_BASIC_DEFAULT` | Basic/default platform filtering only, nothing extra configured | PARTIAL |
  | `PHISHING_PROTECTION_PARTIAL` | Enabled for some accounts/domains, not all | PARTIAL |
  | `PHISHING_PROTECTION_NONE` | No specific protection beyond whatever arrives by default | NO |
  | `PHISHING_PROTECTION_NOT_SURE` | Not sure | UNKNOWN |
- **NOT_APPLICABLE eligible:** No (unchanged).
- **Option-level provenance:** `PHISHING_PROTECTION_BASIC_DEFAULT`
  ("default-only, nothing configured") vs. `PHISHING_PROTECTION_PARTIAL`
  ("actively enabled for some, not all") kept distinct — different
  current-state wording.

## 12. `remote_access_control` — Remote access

- **Customer-facing title:** Controlling how systems are reached
  remotely
- **Question:** "Where staff work remotely or access systems away from
  the office, is there control over how that access happens (e.g. VPN,
  conditional access)?"
- **Why it matters:** "Uncontrolled remote access is an easy path in if
  a device or connection is compromised."
- **Options:**
  | `option_code` | Label | Maps to |
  |---|---|---|
  | `REMOTE_ACCESS_GOVERNED` | Governed remote access for all applicable work | YES |
  | `REMOTE_ACCESS_SOME_UNMANAGED` | Some unmanaged/unguarded remote access paths exist | PARTIAL |
  | `REMOTE_ACCESS_NONE_GOVERNED` | No control over remote access | NO |
  | `REMOTE_ACCESS_NOT_SURE` | Not sure | UNKNOWN |
  | `REMOTE_ACCESS_NOT_APPLICABLE` | (only offered when gated, see below) | NOT_APPLICABLE |
- **NOT_APPLICABLE eligible:** **Yes, but re-gated per Central
  Architecture's correction — no longer on `working_model`.** Requires
  `OrganisationProfile.has_remote_or_offsite_access == "no"` (the new
  dedicated fact, §0), explicitly confirmed, not inferred from
  `working_model`/`primary_cloud_provider`. If that fact is `unknown` or
  `yes`, `REMOTE_ACCESS_NOT_APPLICABLE` is not offered at all.

---

## Summary table — all 12 controls (Revision 2)

| Key | Weight | NOT_APPLICABLE eligible (Rev. 2) | Option codes with shared canonical state, kept distinct |
|---|---:|---|---|
| `mfa_user_accounts` | 3 | No | `MFA_USER_SOME_REQUIRED` / `MFA_USER_AVAILABLE_NOT_ENFORCED` (both PARTIAL) |
| `mfa_privileged_accounts` | 5 | No | `MFA_ADMIN_SOME_REQUIRED` / `MFA_ADMIN_AVAILABLE_NOT_ENFORCED` (both PARTIAL) |
| `endpoint_protection` | 3 | **No (removed)** | `ENDPOINT_PROTECTION_MOST` / `ENDPOINT_PROTECTION_COMPANY_ONLY` (both PARTIAL) |
| `patching` | 5 | No | `PATCHING_MOSTLY_CURRENT` / `PATCHING_IRREGULAR` (both PARTIAL) |
| `device_encryption` | 3 | **No (removed)** | `DEVICE_ENCRYPTION_SOME` only PARTIAL option |
| `backups` | 5 | No | `BACKUPS_RESTORE_UNTESTED` / `BACKUPS_COVERAGE_PARTIAL` (both PARTIAL) — Central Architecture's own named example |
| `joiner_mover_leaver` | 3 | **Yes, re-gated** (new dedicated fact + explicit confirmation) | `JML_INFORMAL_USUALLY` / `JML_INCONSISTENT` (both PARTIAL) |
| `privileged_access_separation` | 3 | **No (removed)** | `PRIV_SEP_SOME` only PARTIAL option |
| `security_awareness_training` | 1 | **No (removed)** | `AWARENESS_OCCASIONAL` only PARTIAL option |
| `incident_reporting_route` | 1 | No | `INCIDENT_ROUTE_INFORMAL` only PARTIAL option |
| `email_phishing_protection` | 3 | No | `PHISHING_PROTECTION_BASIC_DEFAULT` / `PHISHING_PROTECTION_PARTIAL` (both PARTIAL) |
| `remote_access_control` | 3 | **Yes, re-gated** (new dedicated fact) | `REMOTE_ACCESS_SOME_UNMANAGED` only PARTIAL option |

All weights, scenario IDs, and policy section keys remain exactly as
Revision 1/the real existing source — nothing renumbered.
