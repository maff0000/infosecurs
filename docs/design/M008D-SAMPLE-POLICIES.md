# M008D — Three Sample Policies Under the Proposed Deterministic Architecture

**Status:** DESIGN ARTEFACT. These three examples reuse the exact test
personas already defined and approved in the M008 master PID §8
(Persona A — remote-first M365; Persona B — office-first Google
Workspace; Persona C — newly reset/unknown), mapped onto Central
Architecture's requested Scenario A (mature)/B (incomplete)/C
(unknown) framing as follows, to avoid inventing a fourth, redundant set
of synthetic companies:

- **Scenario A (mature)** ≈ **Persona B's shape** (most controls
  confirmed, office-first, Google Workspace).
- **Scenario B (incomplete)** ≈ **Persona A's shape** (remote-first,
  Microsoft 365, several partial/no controls, open remediation).
- **Scenario C (unknown)** ≈ **Persona C** (freshly reset, nothing
  confirmed).

Rendered PDFs for all three are at `docs/design/M008D-sample-policy-a.pdf`,
`-b.pdf`, `-c.pdf` (produced via a real headless-Chromium print-to-PDF
from this same content — see the prototype package for the exact method).

---

## Scenario A — "Thornfield Bookkeeping Ltd" (mature, office-first)

### Synthetic input state

| Fact | Value |
|---|---|
| Legal name | Thornfield Bookkeeping Ltd |
| Staff count | 18 |
| Working model | Office (one London office) |
| Productivity platform | Google Workspace |
| Cloud provider | None beyond Workspace itself |
| Handles confidential business data | Yes (client financial records) |
| Handles payment card data | No |

### Baseline answers (structured facts)

| Control | Answer |
|---|---|
| mfa_user_accounts | YES |
| mfa_privileged_accounts | YES |
| endpoint_protection | YES |
| patching | YES |
| device_encryption | YES |
| backups | **PARTIAL** (backed up, restore never tested) |
| joiner_mover_leaver | YES |
| privileged_access_separation | YES |
| security_awareness_training | **PARTIAL** (occasional/informal) |
| incident_reporting_route | **NO** |
| email_phishing_protection | YES |
| remote_access_control | NOT_APPLICABLE (office-based) |

### Rendered policy

**1. Purpose and scope** `[NORMATIVE_REQUIREMENT]`
> This Information Security Policy sets out how Thornfield Bookkeeping
> Ltd protects the information and systems it uses, and applies to all
> staff, contractors and systems used to carry out the organisation's
> work.

**2. Responsibilities and governance** `[CURRENT_CONFIRMED_PRACTICE + NORMATIVE_REQUIREMENT]`
> Overall responsibility for information security sits with the
> organisation's designated Account Holder. [Governance roles have been
> assigned within the organisation.] All staff are responsible for
> following this policy and reporting concerns promptly.

**3. Access and authentication** `[CURRENT_CONFIRMED_PRACTICE]`
> Multi-factor authentication is required for all staff accounts and for
> all administrator/privileged accounts. Administrator access is kept
> separate from everyday user accounts.

**4. Devices, protection and updates** `[CURRENT_CONFIRMED_PRACTICE]`
> All work devices run anti-malware/endpoint protection, receive security
> updates automatically, and use full-disk encryption.

**5. Information handling and backup** `[CURRENT_CONFIRMED_PRACTICE + GAP_OR_FUTURE_ACTION]`
> Important business data is backed up regularly. **A test restore of
> these backups has not yet been carried out — this is an identified
> action.**

**6. Workplace and remote working** `[CURRENT_CONFIRMED_PRACTICE]`
> Staff work from the organisation's office. No remote-access
> arrangement currently applies; this will be reviewed if working
> arrangements change.

**7. Security incidents and reporting** `[GAP_OR_FUTURE_ACTION]`
> **A clear route for staff to report suspected security incidents has
> not yet been established. This is an identified action — staff
> currently have no confirmed, known point of contact for this.**
> Security-awareness activity for staff is currently informal and
> occasional; expanding this to a regular programme is recommended.

**8. Review, approval and document control** `[NORMATIVE_REQUIREMENT]`
> This policy is reviewed at least annually, or sooner if the
> organisation's circumstances change materially. It is approved by the
> designated Account Holder before distribution.

### Warnings / items requiring attention

1. **Backup restore untested** (PARTIAL) — a real gap, not hidden by the
   otherwise-strong backup practice.
2. **No incident reporting route** (NO) — the most serious open item;
   written as a gap, never softened.
3. **Awareness training informal only** (PARTIAL) — flagged, not
   upgraded to "regular training" language.

---

## Scenario B — "Harlow Digital Consulting Ltd" (incomplete, remote-first)

### Synthetic input state

| Fact | Value |
|---|---|
| Legal name | Harlow Digital Consulting Ltd |
| Staff count | 9 |
| Working model | Remote (fully distributed) |
| Productivity platform | Microsoft 365 |
| Cloud provider | AWS (client project hosting) |
| Handles confidential business data | Yes |

### Baseline answers

| Control | Answer |
|---|---|
| mfa_user_accounts | **PARTIAL** (some staff/groups) |
| mfa_privileged_accounts | YES |
| endpoint_protection | **PARTIAL** (mixed company/BYOD coverage) |
| patching | **PARTIAL** |
| device_encryption | **PARTIAL** |
| backups | **PARTIAL** (not restore-tested) |
| joiner_mover_leaver | **PARTIAL** |
| privileged_access_separation | YES |
| security_awareness_training | **NO** |
| incident_reporting_route | **PARTIAL** |
| email_phishing_protection | YES |
| remote_access_control | **PARTIAL** (some unmanaged paths) |

### Rendered policy

**1. Purpose and scope** `[NORMATIVE_REQUIREMENT]`
> This Information Security Policy sets out how Harlow Digital
> Consulting Ltd protects the information and systems it uses, and
> applies to all staff, contractors and systems used to carry out the
> organisation's work, including fully remote working arrangements.

**2. Responsibilities and governance** `[CURRENT_CONFIRMED_PRACTICE + NORMATIVE_REQUIREMENT]`
> Overall responsibility for information security sits with the
> organisation's designated Account Holder. All staff are responsible for
> following this policy and reporting concerns promptly.

**3. Access and authentication** `[mixed — CURRENT_CONFIRMED_PRACTICE + GAP_OR_FUTURE_ACTION]`
> Multi-factor authentication is required for all administrator/
> privileged accounts, and administrator access is kept separate from
> everyday accounts. **Multi-factor authentication is currently enabled
> for some, but not all, staff accounts — extending this to every
> account is an identified action.**

**4. Devices, protection and updates** `[GAP_OR_FUTURE_ACTION, three items]`
> **Endpoint protection, security updates and full-disk encryption are
> each in place for some devices but not consistently across all devices
> used for work, including personally owned devices. Extending full
> coverage to every device is an identified action.**

**5. Information handling and backup** `[GAP_OR_FUTURE_ACTION]`
> Important business data is backed up. **A test restore has not been
> carried out — this is an identified action.**

**6. Workplace and remote working** `[CURRENT_CONFIRMED_PRACTICE + GAP_OR_FUTURE_ACTION]`
> Staff work remotely. **Some remote-access paths are not currently
> managed or governed consistently; bringing all remote access under a
> governed method (e.g. VPN or conditional access) is an identified
> action.**

**7. Security incidents and reporting** `[mixed]`
> **A reporting route for suspected security incidents exists informally
> but is not consistently known across the organisation — making this
> clear and well-known to all staff is an identified action.** No
> structured security-awareness activity is currently provided to staff;
> introducing one is recommended.

**8. Review, approval and document control** `[NORMATIVE_REQUIREMENT]`
> This policy is reviewed at least annually, or sooner if the
> organisation's circumstances change materially. It is approved by the
> designated Account Holder before distribution.

### Warnings / items requiring attention (7 identified actions)

1. MFA not enforced for all staff accounts.
2. Endpoint protection inconsistent, including BYOD gaps.
3. Patching cadence inconsistent.
4. Device encryption inconsistent.
5. Backup restore untested.
6. Joiner/mover/leaver access removal inconsistent.
7. No structured security-awareness training; incident-reporting route
   not consistently known.

Nowhere does the document claim a control is "in place" when the
confirmed state is PARTIAL — every PARTIAL control produces an explicit
two-part sentence (what's true today + what's missing), never a single
upgraded claim.

---

## Scenario C — freshly reset / all-UNKNOWN

### Synthetic input state

The exact state M008A's own reset leaves behind (independently verified
on the live dev stack during M008A closure): legal name present (the
one bounded identifier that always exists), every other `OrganisationProfile`
fact UNKNOWN/absent, all 12 baseline controls UNKNOWN, zero assets,
zero risks, zero evidence, governance roles present (the Account
Holder's own bootstrap roles — unrelated to any policy content).

### Rendered preview (NOT an approvable document — a preview only)

**1. Purpose and scope** `[NORMATIVE_REQUIREMENT — the only section with real content]`
> This Information Security Policy will set out how [Organisation Name]
> protects the information and systems it uses, once enough information
> has been confirmed to produce a complete policy.

**2–7. Every other section** `[GAP_OR_FUTURE_ACTION, explicit disclosure, no fabricated content]`
> **Not enough has been confirmed yet to state this section's content.
> Complete the Security Foundations questions to populate this policy.**
> (repeated per section — access/authentication, devices, backup,
> workplace, incidents, responsibilities — each individually, not
> merged into one generic disclaimer, so the customer can see exactly
> which sections are blocked on which missing facts.)

**8. Review, approval and document control**
> This document is a **preview only** and cannot be approved in this
> state. [Approve] is disabled; only [Return to question] is offered.

### Warnings / items requiring attention

All 12 baseline controls UNKNOWN, zero confirmed facts beyond the
organisation's name — the preview makes this the headline message, not
a buried warning, and the UI's own **Approve** action is structurally
disabled (not merely discouraged) while this state persists, per M008D
§D4's "no auto-approve" rule.
