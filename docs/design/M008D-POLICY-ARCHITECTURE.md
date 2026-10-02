# M008D — Deterministic Policy Architecture (Design Proposal, Revision 2)

**Status:** DESIGN ARTEFACT — Revision 2, incorporating Central
Architecture's correction pass. Supersedes `M008D-POLICY-ARCHITECTURE.md`
(Revision 1) in full; that document's §1 (what an excellent SME policy
is), §4 (provenance) and §5 (immutability — unchanged) remain valid
background but §2/§3 (the composition pipeline and clause shape) are
revised below to reflect the NORMATIVE/implementation-status split.

## What changed since Revision 1

Revision 1 blended CURRENT_CONFIRMED_PRACTICE and GAP_OR_FUTURE_ACTION
sentences directly into the one distributable policy document. Central
Architecture's correction: **the distributable policy is primarily
NORMATIVE** (what the organisation commits to/must do); current-state
gaps move to a separate **Implementation status** view that is part of
the in-product review experience, not automatically disclosed in the
standard downloadable PDF.

## 1. Two outputs, one source of truth

```
confirmed structured facts (Stage 1-4 answers, by option_code)
        │
        ├──────────────────────────┬──────────────────────────┐
        ▼                          ▼
 NORMATIVE CLAUSE SET        IMPLEMENTATION-STATUS PROJECTION
 (applies to every           (per-control current state +
  organisation regardless     gap/action, keyed by the exact
  of current state — a        option_code selected — never the
  fixed, versioned set of     blended canonical five-state
  "must do" commitments,      alone, per Central Architecture's
  the same ones every         §4 option-level-provenance rule)
  organisation gets)
        │                          │
        ▼                          ▼
  PolicyVersion.sections      A separate, internal-only
  → existing ReportLab        structured record — NOT rendered
  renderer (UNCHANGED)        into the distributable PDF by
        │                     default; surfaced only in the
        ▼                     in-product "Implementation status"
  Distributable PDF            review screen (and, if the customer
  (NORMATIVE ONLY)             explicitly asks, an optional internal
                               export — not part of M008's own scope)
```

Both outputs are derived from the **same** confirmed facts and the
**same** clause-to-source provenance record — there is one source of
truth, rendered two ways for two different audiences (the policy is for
distribution; the implementation status is for the organisation's own
internal review).

## 2. The normative clause (what goes in the PDF)

Every clause in the distributable policy is a **requirement**, worded
identically regardless of whether the organisation currently meets it.
Illustrative, not final copy:

```
clause_id: "access.mfa_user_commitment"
section_key: "access_and_authentication"
applies_when: always
template: "Multi-factor authentication must be used for all staff and
  administrator accounts."
```

This single clause appears in every organisation's policy — Scenario A
(where it's already true) and Scenario B (where it isn't yet) get
**identical** wording in the PDF. The difference between them lives
entirely in the implementation-status projection, not in the policy
text. This is the literal mechanism that prevents "every policy reads
the same regardless of whether the controls are real" from becoming
true in the other direction — the *commitment* is genuinely the same
for every SME (that's what a policy is), while the *organisation's own
internal review* of whether it's met is kept honest and separate.

## 3. The implementation-status projection (what does NOT go in the PDF by default)

One row per control, keyed by the **exact `option_code`** selected
(never the collapsed canonical state alone — Central Architecture's §4
rule applied here too):

```
control: mfa_user_accounts
option_code: MFA_USER_SOME_REQUIRED
current_state_text: "MFA is currently required for some staff
  accounts, not all."
action_text: "Extend MFA enforcement to every staff account."
status: GAP
```

```
control: backups
option_code: BACKUPS_RESTORE_UNTESTED
current_state_text: "Backups exist but a restore has never been
  tested."
action_text: "Schedule and carry out a test restore."
status: GAP
```

```
control: backups
option_code: BACKUPS_COVERAGE_PARTIAL
current_state_text: "Backups exist but do not cover all systems/data."
action_text: "Extend backup coverage to the remaining systems."
status: GAP
```

The last two examples are Central Architecture's own named case,
implemented exactly: two different `option_code`s, both PARTIAL, two
genuinely different `current_state_text`/`action_text` pairs — never
collapsed into one generic "partially covered" row.

**UNKNOWN rows** get their own status, never silently folded into GAP:

```
control: security_awareness_training
option_code: AWARENESS_NOT_SURE
current_state_text: "Whether staff receive security-awareness activity
  has not yet been confirmed."
action_text: "Confirm current practice."
status: NOT_YET_CONFIRMED
```

`status ∈ {MET, GAP, NOT_YET_CONFIRMED}` — `MET` for YES/
NOT_APPLICABLE answers, `GAP` for NO/PARTIAL, `NOT_YET_CONFIRMED` for
UNKNOWN. UNKNOWN is never silently treated as GAP in this projection,
preserving the existing M002 UNKNOWN != NO doctrine all the way through.

## 4. Where the implementation-status projection is shown

In the product's own Policy review screen (Stage 6), as a distinct,
clearly separate section titled **"Implementation status / actions"**,
below or alongside the policy preview — never merged into the preview's
own body text. It is not part of the standard downloadable PDF. A
future, separately authorised export of this projection (e.g. an
internal-only PDF a practitioner could generate) is explicitly out of
M008's scope, not built here.

## 5. Governance roles in policy wording

Policy clause templates reference the organisation's actual assigned
governance roles by their real, business-facing names — **not**
Infosecurs's own internal "Account Holder" product-identity term:

| Policy wording | Backing data |
|---|---|
| "The Security responsible person is accountable for day-to-day information security matters." | `GovernanceRoleAssignment` where `role == ROLE_SECURITY_RESPONSIBLE` → `OrganisationPerson.full_name` |
| "This policy is approved by the Policy authoriser." | `role == ROLE_POLICY_AUTHORISER` |
| "Senior leadership maintains overall accountability for information security." | `role == ROLE_SENIOR_LEADERSHIP` |

All three role labels already exist verbatim in `governance.models.
GovernanceRoleAssignment.ROLE_CHOICES` — no new role taxonomy is
proposed; this is a wording-source correction only (use the existing
business-facing role labels in policy prose, not the internal "Account
Holder" bootstrap-identity term that happens to also hold one of these
roles by default).

## 6. Policy readiness gate

Approval is permitted only when ALL of the following hold — none of
which requires every control to be YES:

1. Required business/context facts exist (Stage 1–3 minimally
   complete: legal name, sector, at least one workplace, at least one
   governance role assignment per role).
2. All 12 security controls have been **deliberately reviewed** (per
   §1 of this addendum's progress semantics — a genuine selection made,
   including "Not sure," on every control; an unvisited question blocks
   approval).
3. NO/PARTIAL control states do **not** block approval — a policy can
   be approved with real, disclosed gaps (the gaps live in the
   implementation-status projection, reviewed alongside approval, never
   hidden from the approver — just not baked into the distributed PDF's
   prose).
4. UNKNOWN is never silently converted to NO or guessed at approval
   time — any remaining UNKNOWN controls are shown explicitly in the
   implementation-status section at the moment of approval, as
   "Confirm current practice" items, not swept under a completed state.
5. Approving the policy does **not** imply implementation or
   compliance — a persistent, explicit statement to this effect appears
   on the approval confirmation step itself (not just in a help
   tooltip): "Approving this policy records your organisation's
   security commitments. It does not certify that every control is
   currently in place — see Implementation status for the current
   picture."
6. `Security Foundations Completion` (the existing, unchanged 18-item
   M007 metric) is **not** a gate for policy approval and can remain
   below 100% after approval — approving the policy is one of the 18
   items, not a precondition reached only once all 18 are already done.

## 7. What is unchanged from Revision 1

- Existing eight `policy` section keys, `PolicyVersion.save()`
  immutability guard, approval/review lifecycle, ReportLab PDF renderer,
  tenant-scoped download/history.
- Zero LLM calls in the default path (Central Architecture §10:
  explicitly do not reintroduce a routine policy-generation call).
- `generation_source` enum gains the same additive `template`/
  `deterministic` member Revision 1 proposed.
- The clause library's versioned, Git-tracked, reviewed shape
  (`risk_register.methodology`/`security_baseline.catalogue`-style
  module, not a DB table).
