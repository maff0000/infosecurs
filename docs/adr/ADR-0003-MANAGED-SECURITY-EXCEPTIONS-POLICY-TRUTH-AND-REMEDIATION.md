# ADR-0003 — Managed Security Exceptions, Policy Truth and Remediation Doctrine

**Status:** ACCEPTED — Central Architecture, 2026-09-23  
**Applies from:** immediately for future policy revisions, M005 and later modules  
**Repository:** `maff0000/infosecurs`  
**Authoritative baseline at decision:** `19019b8e3507fd39ac0879e64bd171bec506d67b`  
**Project truth:** GitHub

---

## 1. Context

Small organisations rarely have every desirable security control fully implemented.

Infosecurs must not force a customer into one of two bad outcomes:

1. pretend a control is fully implemented when it is not; or
2. adopt policy wording so absolute that the organisation immediately breaches its own policy while it is actively remediating a known gap.

A mature security posture is not defined by perfection. It is defined by knowing the current state, recognising material gaps, understanding the associated risk, assigning ownership, setting a remediation path and target date, and retaining evidence when remediation is completed.

This doctrine governs how Infosecurs represents partial implementation, policy requirements, documented exceptions, remediation and educational/tutorial content.

---

## 2. Core doctrine

> **No business has perfect security. Good security means knowing where weaknesses exist, recognising the risk, documenting the exception, assigning an owner, setting a remediation path and target date, and closing the gap with evidence.**

A documented exception is evidence of governance and awareness.

It is **not** evidence that the underlying requirement has been met.

It is **not** a waiver from an explicit customer, contractual, regulatory or legal requirement.

---

## 3. Policy wording must distinguish target standard from current implementation

Infosecurs policy generation must separate:

1. the organisation's intended security requirement; and
2. the organisation's current implementation state.

### 3.1 Fully implemented and confirmed

Where the relevant control is fully implemented and confirmed, policy wording may use the clean mandatory form.

Example:

> All privileged accounts must be protected by multi-factor authentication.

### 3.2 Partially implemented

Where implementation is partial, policy wording should retain the intended standard while honestly recognising managed exceptions.

Preferred pattern:

> Multi-factor authentication is required for privileged accounts. Where full implementation is not yet complete, any remaining exceptions must be documented, risk-assessed and tracked through remediation.

Do not use vague escape clauses such as:

> Where possible, MFA should be enabled.

unless a genuinely unavoidable technical limitation makes that wording objectively necessary.

"Where possible" must not become a permanent loophole.

### 3.3 Not implemented or unconfirmed

Where the control is `no` or `unknown`, policy wording may still establish the intended requirement, but must not claim that implementation already exists.

Example:

> Privileged accounts must use multi-factor authentication. Current implementation must be confirmed and any identified gaps addressed through the organisation's remediation process.

The policy may state the required future standard.

It must not transform an unknown or absent control into a current-state fact.

---

## 4. Managed-exception representation

Do **not** create a new generic Exception subsystem in this phase.

A managed exception can be represented using the existing security model:

```text
Canonical control state
        +
Risk / consequence
        +
RemediationAction
        +
Owner
        +
Target date or explicit review date
        +
Evidence / completion outcome
        =
Managed security exception
```

This avoids duplicating state already owned by M002/M003.

A dedicated `Exception` entity may be considered later only if real product usage shows the existing composition cannot represent required governance cleanly.

---

## 5. Minimum information for a documented exception

Where a meaningful control is not fully implemented, Infosecurs should be capable of showing:

- **Control / requirement** — what the intended standard is;
- **Current gap** — what is not fully implemented or confirmed;
- **Risk** — what could reasonably happen because of that gap;
- **Owner** — who is responsible for resolving or reviewing it;
- **Remediation path** — what will be done;
- **Target date** — when remediation is expected, where remediation is planned;
- **Review date / acceptance basis** — where the risk is consciously accepted rather than immediately remediated;
- **Status** — open / in progress / done / accepted through existing remediation semantics;
- **Evidence on completion** — what demonstrates the gap was addressed.

Do not invent dates or owners.

If either is unknown, surface that as an incomplete governance item rather than silently filling it in.

---

## 6. Example — privileged MFA

Organisation:

- four partners have privileged accounts;
- two accounts use MFA;
- two do not.

Current control state:

`partial`

Policy:

> Multi-factor authentication is required for privileged accounts. Where full implementation is not yet complete, any remaining exceptions must be documented, risk-assessed and tracked through remediation.

Managed exception:

```text
Requirement:
All privileged accounts use MFA.

Current gap:
2 of 4 privileged accounts do not yet have MFA enabled.

Risk:
Compromise of an unprotected privileged account could permit unauthorised access or administrative change.

Owner:
Named responsible person.

Remediation:
Enable MFA on the remaining privileged accounts.

Target date:
Customer-supplied target date.

Status:
Open / In progress.
```

Once all four privileged accounts use MFA and the state is fully confirmed with appropriate evidence:

- the control may move from `partial` to `yes`;
- associated risk can be reassessed;
- remediation can be completed;
- supporting evidence can be attached;
- Infosecurs may propose stronger policy wording.

The next proposed policy wording may become:

> All privileged accounts must be protected by multi-factor authentication.

---

## 7. Policy changes are proposed, never silently applied

A security-state improvement may make stronger policy wording appropriate.

Infosecurs may detect and suggest that change.

It must not silently mutate an approved policy.

Required flow:

```text
security state changes
        ↓
policy clause can be strengthened
        ↓
new policy draft/version proposed
        ↓
authoriser reviews
        ↓
new approved version
```

Previously approved policy versions remain immutable.

---

## 8. Risk and policy remain different concepts

A policy states the organisation's intended rules and expectations.

Risk/security state records what is actually happening.

Therefore:

- policy requirement != implemented control;
- documented exception != compliant control;
- accepted risk != requirement satisfied;
- completed remediation != automatically confirmed control;
- evidence + explicit canonical state change are still required where the control state must change.

---

## 9. External requirements override internal comfort

A documented exception can demonstrate good governance, but it does not satisfy an explicit external requirement by itself.

Example:

If a customer contract states:

> MFA must be enabled for all privileged accounts.

and only two of four privileged accounts use MFA, then the requirement remains unmet.

Infosecurs should say so plainly while also showing:

- the gap is known;
- the risk is understood;
- an owner exists;
- remediation is underway;
- a target date exists where supplied.

Do not turn "managed risk" into a false `EVIDENCED` or compliant answer.

---

## 10. Questionnaire doctrine

M005 and later questionnaire functionality must distinguish at least:

- **policy requires the control**;
- **control fully implemented and evidenced**;
- **control partially implemented / managed exception exists**;
- **control absent**;
- **control unconfirmed**;
- **control genuinely not applicable**.

Questionnaire answers must be grounded in implementation/evidence state, not merely in the wording of the policy.

A policy saying "MFA is required" must not cause an answer of "Yes, all privileged accounts use MFA" where the canonical control state is partial.

---

## 11. Tutorial / education doctrine

Future tutorials and onboarding guidance must explicitly teach:

> **No business has perfect security.**

The purpose of Infosecurs is not to create the appearance of perfection.

Customers should understand the practical governance loop:

```text
identify the gap
        ↓
understand the risk
        ↓
document the exception
        ↓
assign an owner
        ↓
set remediation or review date
        ↓
take action
        ↓
attach evidence
        ↓
confirm the new state
        ↓
reassess risk
```

Tutorials must explain that documenting an exception:

- shows that the organisation recognises the issue;
- makes ownership visible;
- establishes a path and date for remediation/review;
- creates defensible governance history;
- helps avoid hiding or forgetting weaknesses.

Tutorials must also explicitly explain:

> **A documented exception does not make an unmet contractual, legal, regulatory or customer requirement compliant.**

This distinction is mandatory in future security-governance educational content.

---

## 12. UX doctrine

Use plain language.

Avoid making customers feel they have "failed" merely because a control is partial.

Prefer language such as:

- `Partially implemented`;
- `Known exception`;
- `Remediation in progress`;
- `Target date`;
- `Risk accepted until review date`;
- `Evidence required to confirm completion`.

Do not use language that implies an exception is automatically acceptable merely because it has been recorded.

---

## 13. Learning-signal doctrine

Managed-exception lifecycle provides useful future learning signals.

Preserve structured outcomes such as:

- control changed from partial -> yes;
- remediation completed;
- target date moved;
- risk accepted rather than remediated;
- policy clause strengthened after control confirmation;
- customer edited proposed exception wording;
- questionnaire answer changed after remediation.

Continue the existing rule:

> capture now, learn later.

Do not build autonomous learning from these events in this phase.

---

## 14. Build implications

Future modules and policy revisions must:

1. preserve the separation between policy requirement and implementation truth;
2. support honest partial-control wording;
3. use existing Risk/RemediationAction/Evidence structures before inventing a new Exception subsystem;
4. preserve owner/target-date governance where supplied;
5. never silently strengthen an approved policy;
6. never use policy text alone as proof in questionnaires;
7. include the tutorial doctrine when product education is built.

This ADR does not reopen M004 PRODUCT_GREEN.

It governs future revisions and all downstream modules from M005 onward.
