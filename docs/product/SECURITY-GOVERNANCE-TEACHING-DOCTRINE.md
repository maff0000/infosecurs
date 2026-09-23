# Security Governance Teaching Doctrine — Imperfect Security and Managed Exceptions

**Status:** PRODUCT DOCTRINE — 2026-09-23  
**Binding architecture:** `docs/adr/ADR-0003-MANAGED-SECURITY-EXCEPTIONS-POLICY-TRUTH-AND-REMEDIATION.md`

## Core message

> **No business has perfect security.**

Good security is not pretending that every control is complete.

Good security means:

- knowing what is true today;
- recognising where controls are incomplete;
- understanding the risk;
- documenting the exception;
- assigning somebody to own it;
- setting a remediation or review date;
- taking action;
- retaining evidence;
- confirming the improved state.

## Customer teaching sequence

Use this simple model in future tutorials/onboarding:

```text
We found a gap.
        ↓
What could happen because of it?
        ↓
Who owns it?
        ↓
What are we going to do?
        ↓
By when?
        ↓
What evidence will show it is fixed?
        ↓
Confirm the new security state.
```

## Example

Four partners have privileged accounts.

Two use MFA and two do not.

Do not tell the customer:

> You have failed security.

Do not tell them:

> You use MFA on privileged accounts.

Explain:

> MFA is partially implemented for privileged accounts. The remaining accounts are a known security exception. Record the risk, assign an owner and target date, and track enabling MFA on the remaining accounts.

The policy can state:

> Multi-factor authentication is required for privileged accounts. Where full implementation is not yet complete, any remaining exceptions must be documented, risk-assessed and tracked through remediation.

Once all privileged accounts are confirmed as protected by MFA, the policy can be strengthened in the next approved version to:

> All privileged accounts must be protected by multi-factor authentication.

## Mandatory caveat

Always teach:

> **Documenting an exception does not make an explicit external requirement compliant.**

If a contract, regulation, law or customer requirement says all privileged accounts must use MFA, partial MFA still means the requirement is unmet.

The difference is that a managed organisation can demonstrate:

- it knows about the gap;
- it understands the risk;
- someone owns it;
- remediation is planned;
- progress and evidence are retained.

That is security governance.

## Tone

Tutorials should be reassuring without being misleading.

Avoid:

- perfection language;
- shame/failure language for ordinary gaps;
- false compliance reassurance;
- implying a recorded exception means "problem solved".

Prefer:

- `Known gap`;
- `Managed exception`;
- `Remediation in progress`;
- `Owner`;
- `Target date`;
- `Review date`;
- `Evidence of completion`.

The customer should finish the tutorial understanding:

> **Security maturity is the ability to see, own and improve risk — not the ability to claim there is none.**
