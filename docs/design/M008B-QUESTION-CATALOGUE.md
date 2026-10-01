# M008B — Complete Security Foundations Question Catalogue (Design Proposal)

**Status:** DESIGN ARTEFACT — not implemented, not approved. For Matt/Product
Authority review only. Nothing in this document has been coded.

**What this replaces:** `security_baseline/forms.py`'s `BaselineAssessmentForm`
— currently one `<select>` (YES/PARTIAL/NO/UNKNOWN/NOT_APPLICABLE) plus one
free-text `note` per question, for all 12 `security_baseline/catalogue.py`
controls. The `note` field is the one the form's own docstring already
names as "the customer narrative field to retire from Foundation-facing
UI" (WI0 inventory, item #11).

**What is preserved unchanged:** all 12 `CATALOGUE_KEYS`, the five canonical
`BaselineAnswer.answer` states (YES/PARTIAL/NO/UNKNOWN/NOT_APPLICABLE), the
`entitlements.metrics` posture formula (weighted, `earned/available*100`)
and the 18-item completion methodology. Nothing below changes a score —
only how the answer reaches that same, unchanged `BaselineAnswer.answer`
value.

**Format per control:** stable key, title, plain-English question, why it
matters, predefined answer choices (richer than YES/NO where the real
business situation varies), conditional follow-ups, canonical mapping,
NOT_APPLICABLE eligibility, deterministic risk/remediation/policy
consequences (using the *actual*, already-existing `risk_register.
methodology.CATALOGUE` scenario IDs and `policy` section keys — not
invented ones), evidence expectations, completion effect, and
versioning/migration note.

---

## 1. `mfa_user_accounts` — Multi-factor authentication (staff)

- **Customer-facing title:** Staff sign-in protection
- **Plain-English question:** "How is multi-factor authentication (MFA)
  used for ordinary staff accounts (e.g. Microsoft 365, Google Workspace)?"
- **Why it matters:** "MFA is one of the single most effective protections
  against stolen-password account takeover — without it, a leaked or
  guessed password is often enough to get in."
- **Predefined answers:**
  | Option | Meaning | Maps to |
  |---|---|---|
  | MFA required for all staff accounts | Enforced, no exceptions known | YES |
  | MFA required for some staff/groups, not all | Partial rollout | PARTIAL |
  | MFA available but not enforced | Technically possible, not required | PARTIAL |
  | MFA not currently used | No MFA anywhere | NO |
  | Not sure | — | UNKNOWN |
- **Conditional follow-up:** if "some staff/groups" → optional single-line
  bounded text "Which groups?" (short identifier, not narrative — e.g.
  "Sales team only"); stored as `AnswerSelectionDetail`-style provenance
  metadata (M008B §B4), never a second source of truth.
- **NOT_APPLICABLE eligible:** No — every organisation with staff accounts
  has an answer to this; there is no genuine "doesn't apply" case for a
  business with any staff productivity accounts at all.
- **Risk consequence:** triggers `identity_mfa_user_account_takeover`
  (`risk_register.methodology.CATALOGUE`) on NO/UNKNOWN, exactly as today —
  no change to the scenario engine.
- **Remediation suggestion (deterministic):** "Enable MFA for all staff
  accounts" — already the scenario's own `suggested_treatment`.
- **Policy clauses affected:** `access_and_authentication`.
- **Customer Assurance facts supported:** "Does the organisation require
  MFA for all user accounts?" (a common third-party questionnaire
  question this answer can directly support, once Customer Assurance's
  own separate workflow reads canonical baseline state).
- **Security weight:** 3 (unchanged, `FoundationRequirement.security_weight`).
- **Evidence expectation:** optional — a screenshot of the MFA enforcement
  policy/report is the natural evidence type if the customer wants to
  attach one; not required to answer.
- **Completion effect:** any of the five deliberate answers (including
  NO) advances completion; UNKNOWN does not (PID's own "UNKNOWN never
  completes" rule, unchanged).
- **Versioning:** no change to `CATALOGUE_VERSION` needed — the *wording*
  of the question/options changes, not the `mfa_user_accounts` key or its
  canonical meaning, so this is the "wording-only, code unchanged" case
  M008B §B4.4 describes, not a version bump.

## 2. `mfa_privileged_accounts` — Multi-factor authentication (admin)

- **Customer-facing title:** Admin/privileged account protection
- **Plain-English question:** "How is multi-factor authentication used for
  admin/privileged accounts (e.g. IT admin, cloud admin, domain admin)?"
- **Why it matters:** "Admin accounts can change settings for everyone —
  if one is compromised, the attacker can often disable other
  protections too."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | MFA required for all admin/privileged accounts | YES |
  | MFA required for some admin accounts, not all | PARTIAL |
  | MFA available but not enforced for admin accounts | PARTIAL |
  | MFA not used for admin accounts | NO |
  | Not sure / don't know who holds admin accounts | UNKNOWN |
- **Conditional follow-up:** none required; if "not sure who holds admin
  accounts" is selected (folded into UNKNOWN per the catalogue's own
  explicit instruction not to treat "don't know who" as NOT_APPLICABLE).
- **NOT_APPLICABLE eligible:** No.
- **Risk consequence:** `identity_mfa_privileged_account_takeover`, and
  jointly contributes to `cloud_service_admin_mfa_account_takeover`
  (multi-control scenario, with `privileged_access_separation`) — the
  existing "worst applicable wording wins" rule in `scenario_engine.py`
  is unchanged.
- **Remediation suggestion:** "Enable MFA for all admin/privileged
  accounts."
- **Policy clauses affected:** `access_and_authentication`.
- **Security weight:** 5 (highest-weighted single control, unchanged).
- **Evidence expectation:** optional.
- **Completion effect:** standard.
- **Versioning:** wording-only, no bump.

## 3. `endpoint_protection` — Endpoint protection

- **Customer-facing title:** Device protection
- **Plain-English question:** "Do the devices staff use for work have
  anti-malware/endpoint protection?"
- **Why it matters:** "Protects against malware and ransomware that could
  spread from an infected device into the rest of the business."
- **Predefined answers:** distinguish company-managed vs BYOD coverage,
  reading `OrganisationProfile.endpoint_management` first so the question
  doesn't ask something already structurally known:
  | Option | Maps to |
  |---|---|
  | All work devices have endpoint protection | YES |
  | Most/some work devices have it, not all | PARTIAL |
  | Company devices do, personal/BYOD devices don't | PARTIAL |
  | No endpoint protection in place | NO |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** if `OrganisationProfile.endpoint_management ==
  "byod"` or `"both"`, the "Company devices do, personal/BYOD devices
  don't" option is shown; if `endpoint_management == "company_managed"`,
  that option is hidden (not a genuinely available real-world answer for
  a BYOD-free business) — a real applicability-driven option set, not a
  cosmetic relabel.
- **NOT_APPLICABLE eligible:** only if the organisation has genuinely no
  staff devices accessing business data at all (an extreme edge case,
  gated on a structural fact, never a free "I'd rather not say" escape).
- **Risk consequence:** `endpoint_anti_malware_compromise`.
- **Remediation suggestion:** "Deploy anti-malware/EDR to all work
  devices."
- **Policy clauses affected:** `devices_protection_and_updates`.
- **Security weight:** 3.
- **Evidence expectation:** optional (EDR console screenshot).
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 4. `patching` — Patching

- **Customer-facing title:** Keeping software up to date
- **Plain-English question:** "Are operating systems and business
  applications kept up to date with security updates?"
- **Why it matters:** "Unpatched software is one of the most common ways
  attackers get in — many attacks exploit a known, already-fixed flaw."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | Automatic updates enabled everywhere, checked regularly | YES |
  | Updates mostly kept current, some gaps | PARTIAL |
  | Updates happen irregularly / only when something breaks | PARTIAL |
  | No consistent update practice | NO |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** none.
- **NOT_APPLICABLE eligible:** No.
- **Risk consequence:** `endpoint_patching_known_vulnerability` AND
  `business_application_patching_known_vulnerability` — this control key
  already drives two scenarios today (device-level and
  application-level); both remain, unchanged.
- **Remediation suggestion:** "Enable automatic updates and establish a
  routine patching cadence."
- **Policy clauses affected:** `devices_protection_and_updates`.
- **Security weight:** 5.
- **Evidence expectation:** optional.
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 5. `device_encryption` — Device encryption

- **Customer-facing title:** Protecting data if a device is lost or stolen
- **Plain-English question:** "Is full-disk encryption (e.g. BitLocker,
  FileVault) enabled on devices that hold business data?"
- **Why it matters:** "If a laptop is lost or stolen, encryption is what
  stops someone simply reading the files off the drive."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | Enabled on all relevant devices | YES |
  | Enabled on some, not all | PARTIAL |
  | Not enabled | NO |
  | We don't use devices that hold business data locally (fully cloud/browser-based) | NOT_APPLICABLE (gated) |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** the NOT_APPLICABLE option is only offered
  when `OrganisationProfile.primary_cloud_provider` is set to a real
  provider AND `working_model` doesn't imply local device storage is
  likely — this is the PID's own explicit "NOT_APPLICABLE requires a
  genuinely verified condition, never an easy escape" rule, implemented
  as a real applicability gate, not a free checkbox.
- **NOT_APPLICABLE eligible:** Yes, gated as above.
- **Risk consequence:** `endpoint_device_encryption_loss_theft`.
- **Remediation suggestion:** "Enable full-disk encryption on all
  business-data-holding devices."
- **Policy clauses affected:** `devices_protection_and_updates`.
- **Security weight:** 3.
- **Evidence expectation:** optional.
- **Completion effect:** NOT_APPLICABLE counts as completion-complete
  (unchanged rule) but excluded from the posture denominator.
- **Versioning:** wording-only (the NOT_APPLICABLE *gating condition* is
  new UX, but the underlying `NOT_APPLICABLE` semantic and its exclusion
  from the posture denominator is unchanged methodology).

## 6. `backups` — Backups

- **Customer-facing title:** Backups you can actually restore from
- **Plain-English question:** "Is important business data backed up, and
  has anyone actually tried restoring from that backup?"
- **Why it matters:** "A backup nobody has tested is a hope, not a
  safeguard — ransomware and accidental deletion are the two most common
  reasons businesses need to restore."
- **Predefined answers:** the manifest's own illustrative example,
  preserved exactly because it correctly distinguishes the one fact that
  matters most here:
  | Option | Maps to |
  |---|---|
  | Backed up AND a restore has been tested | YES |
  | Backed up but restore has never been tested | PARTIAL |
  | Backed up but only partially (some systems/data not covered) | PARTIAL |
  | Not backed up | NO |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** if "partially covered," optional bounded
  text "What's not covered?" (short identifier, e.g. "Shared drive
  archives") — provenance metadata only.
- **NOT_APPLICABLE eligible:** No — every business has something worth
  backing up.
- **Risk consequence:** `business_application_backups_data_loss` AND
  `information_backups_loss_or_corruption` (this control key already
  drives two scenarios today, unchanged).
- **Remediation suggestion:** "Implement backups and schedule a test
  restore."
- **Policy clauses affected:** `information_handling_and_backup`.
- **Security weight:** 5.
- **Evidence expectation:** optional (backup report/test-restore log).
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 7. `joiner_mover_leaver` — Access removal

- **Customer-facing title:** Removing access when someone leaves or
  changes role
- **Plain-English question:** "When someone leaves the business or
  changes role, is their access removed or adjusted promptly?"
- **Why it matters:** "Former staff keeping access after they leave is a
  common, avoidable way confidential information or systems stay
  exposed."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | Defined process, followed consistently | YES |
  | Informal process, usually followed | PARTIAL |
  | Happens inconsistently / depends who remembers | PARTIAL |
  | No process | NO |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** none.
- **NOT_APPLICABLE eligible:** only if `OrganisationProfile.staff_count`
  is 1 (a genuine sole-trader case with no other accounts to remove) —
  gated on the structural fact, not self-declared.
- **Risk consequence:** `people_joiner_mover_leaver_stale_access`.
- **Remediation suggestion:** "Define and follow a joiner/mover/leaver
  access-removal checklist."
- **Policy clauses affected:** `responsibilities_and_governance`.
- **Security weight:** 3.
- **Evidence expectation:** none expected.
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 8. `privileged_access_separation` — Privileged access

- **Customer-facing title:** Keeping admin access separate from everyday
  accounts
- **Plain-English question:** "Do people with admin/privileged access use
  a separate account for admin tasks, rather than their everyday login?"
- **Why it matters:** "If the same account does admin tasks and everyday
  email/browsing, one phishing click can hand over admin-level access."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | Dedicated separate admin accounts, used only for admin tasks | YES |
  | Some separation, not consistently used | PARTIAL |
  | Same account used for both | NO |
  | Not sure / don't know who has admin access | UNKNOWN |
- **Conditional follow-up:** none.
- **NOT_APPLICABLE eligible:** only if `staff_count` is 1 and that person
  genuinely holds no admin/privileged systems (rare, structurally gated).
- **Risk consequence:** `identity_privileged_access_not_separated`, and
  jointly `cloud_service_admin_mfa_account_takeover` (see control 2).
- **Remediation suggestion:** "Create dedicated admin accounts separate
  from everyday user accounts."
- **Policy clauses affected:** `access_and_authentication`.
- **Security weight:** 3.
- **Evidence expectation:** none expected.
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 9. `security_awareness_training` — Staff awareness

- **Customer-facing title:** Helping staff recognise security risks
- **Plain-English question:** "Do staff get any security-awareness
  training, such as how to recognise phishing emails?"
- **Why it matters:** "Most breaches start with a person, not a
  technical flaw — a little awareness goes a long way."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | Regular, structured awareness activity (e.g. annual training, simulated phishing) | YES |
  | Occasional/informal (e.g. a one-off session, shared articles) | PARTIAL |
  | No training provided | NO |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** none.
- **NOT_APPLICABLE eligible:** only if `staff_count` is 1.
- **Risk consequence:** `people_security_awareness_social_engineering`.
- **Remediation suggestion:** "Introduce regular security-awareness
  activity for staff."
- **Policy clauses affected:** `responsibilities_and_governance`.
- **Security weight:** 1 (lowest-weighted, unchanged).
- **Evidence expectation:** none expected.
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 10. `incident_reporting_route` — Incident reporting

- **Customer-facing title:** Knowing who to tell if something goes wrong
- **Plain-English question:** "If a staff member suspects a security
  incident (e.g. clicked a bad link, lost a device), do they know who to
  tell and what happens next?"
- **Why it matters:** "Fast reporting limits damage — a known route means
  problems get handled in minutes, not discovered weeks later."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | Clear, known route and a named responsible person | YES |
  | Staff mostly know who to tell, but it's informal | PARTIAL |
  | No clear route — staff wouldn't know who to tell | NO |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** if YES, optional link to the Account
  Holder/governance role already recorded in `governance.
  GovernanceRoleAssignment` (not a new free-text name — the person
  responsible is already a structured fact once a role exists).
- **NOT_APPLICABLE eligible:** No.
- **Risk consequence:** `people_incident_reporting_delayed_response`.
- **Remediation suggestion:** "Establish and communicate a clear incident
  reporting route."
- **Policy clauses affected:** `security_incidents_and_reporting`.
- **Security weight:** 1.
- **Evidence expectation:** none expected.
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 11. `email_phishing_protection` — Email/phishing protection

- **Customer-facing title:** Protecting email from phishing and spam
- **Plain-English question:** "Are there protections against phishing and
  malicious email, beyond normal spam filtering?"
- **Why it matters:** "Email remains the single most common way attackers
  first get in — filtering reduces how many malicious messages staff ever
  see."
- **Predefined answers:** reads `OrganisationProfile.productivity_platform`
  to tailor explanatory help text (Microsoft 365 vs Google Workspace
  guidance differs in wording only, never in underlying methodology, per
  PID §3's own explicit instruction):
  | Option | Maps to |
  |---|---|
  | Active anti-phishing protection enabled on all business email | YES |
  | Basic/default platform filtering only, nothing extra configured | PARTIAL |
  | Partial — enabled for some accounts/domains, not all | PARTIAL |
  | No specific protection beyond whatever arrives by default | NO |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** none.
- **NOT_APPLICABLE eligible:** No.
- **Risk consequence:** `identity_phishing_protection_delivery`.
- **Remediation suggestion:** "Enable advanced anti-phishing protection
  for all business email."
- **Policy clauses affected:** `access_and_authentication` (a cross-cutting
  clause reference; the identity-adjacent framing is intentional —
  phishing is primarily an identity-compromise vector).
- **Security weight:** 3.
- **Evidence expectation:** optional.
- **Completion effect:** standard.
- **Versioning:** wording-only.

## 12. `remote_access_control` — Remote access

- **Customer-facing title:** Controlling how systems are reached remotely
- **Plain-English question:** "Where staff work remotely or access
  systems away from the office, is there control over how that access
  happens (e.g. VPN, conditional access)?"
- **Why it matters:** "Uncontrolled remote access is an easy path in if a
  device or connection is compromised."
- **Predefined answers:**
  | Option | Maps to |
  |---|---|
  | Governed remote access for all applicable work | YES |
  | Some unmanaged/unguarded remote access paths exist | PARTIAL |
  | No control over remote access | NO |
  | We have no remote/hybrid working — everyone works on site | NOT_APPLICABLE (gated) |
  | Not sure | UNKNOWN |
- **Conditional follow-up:** the NOT_APPLICABLE option is only offered
  when `OrganisationProfile.working_model == "office"` — genuinely
  gated, matching M008B §B3's own explicit instruction ("cloud access
  may still be remote" — a cloud-only business is NOT automatically
  NOT_APPLICABLE even if `working_model` says office-based, so the
  gate checks `working_model` only, deliberately not combined with
  `primary_cloud_provider`, to avoid a false NOT_APPLICABLE for an
  office-based team that still reaches cloud systems remotely from
  home occasionally).
- **NOT_APPLICABLE eligible:** Yes, gated as above.
- **Risk consequence:** `network_remote_access_uncontrolled_path`.
- **Remediation suggestion:** "Implement governed remote access (VPN or
  conditional access) for all remote work."
- **Policy clauses affected:** `workplace_and_remote_working`.
- **Security weight:** 3.
- **Evidence expectation:** optional.
- **Completion effect:** NOT_APPLICABLE counts as completion-complete,
  excluded from posture denominator (unchanged rule).
- **Versioning:** wording-only.

---

## Summary table — all 12 controls

| Key | Weight | Scenario(s) | NOT_APPLICABLE eligible | Policy section |
|---|---:|---|---|---|
| `mfa_user_accounts` | 3 | identity_mfa_user_account_takeover | No | access_and_authentication |
| `mfa_privileged_accounts` | 5 | identity_mfa_privileged_account_takeover, cloud_service_admin_mfa_account_takeover | No | access_and_authentication |
| `endpoint_protection` | 3 | endpoint_anti_malware_compromise | Gated (rare) | devices_protection_and_updates |
| `patching` | 5 | endpoint_patching_known_vulnerability, business_application_patching_known_vulnerability | No | devices_protection_and_updates |
| `device_encryption` | 3 | endpoint_device_encryption_loss_theft | Gated (cloud-only) | devices_protection_and_updates |
| `backups` | 5 | business_application_backups_data_loss, information_backups_loss_or_corruption | No | information_handling_and_backup |
| `joiner_mover_leaver` | 3 | people_joiner_mover_leaver_stale_access | Gated (sole trader) | responsibilities_and_governance |
| `privileged_access_separation` | 3 | identity_privileged_access_not_separated, cloud_service_admin_mfa_account_takeover | Gated (sole trader) | access_and_authentication |
| `security_awareness_training` | 1 | people_security_awareness_social_engineering | Gated (sole trader) | responsibilities_and_governance |
| `incident_reporting_route` | 1 | people_incident_reporting_delayed_response | No | security_incidents_and_reporting |
| `email_phishing_protection` | 3 | identity_phishing_protection_delivery | No | access_and_authentication |
| `remote_access_control` | 3 | network_remote_access_uncontrolled_path | Gated (office-only) | workplace_and_remote_working |

All weights, scenario IDs, and policy section keys are the *actual, already
existing* values in `security_baseline/catalogue.py`,
`risk_register/methodology.py`, and `ai_platform/policy_contracts.py` —
nothing above is a proposed renumbering. Only the question/answer
*presentation* is new.

## Explicit methodology non-change

No control's `security_weight`, no risk scenario's `trigger_states`, no
policy section key, and no completion-eligibility rule changes as a
result of this catalogue. If Product Authority wants to reconsider any of
these during review, that is a **separate, explicit methodology-change
decision** (per M008 PID §3 item 3: "M008 should improve how the answers
are gathered, not silently move the score") — flagged here as an open
question, not pre-decided.
