# ADR-0002 — Identity, Governance, Workplace and Downstream-Service Boundaries

**Status:** ACCEPTED — Central Architecture, 2026-09-23  
**Applies from:** M004  
**Repository:** `maff0000/infosecurs`  
**Project truth:** GitHub

## 1. Context

Infosecurs M001–M003 established organisation profile, assets/controls/risk, evidence, remediation and current security state.

Before M004 can create an approvable Information Security Policy, the product needs the smallest credible answer to four practical questions:

1. Who is the customer/account holder?
2. Who holds relevant organisational governance roles?
3. Where do the organisation's people actually work?
4. What does Infosecurs itself own versus later external services such as Chargebee/uSecure?

The architecture must solve these without creating an identity platform, HR system, billing system, training platform or broad physical-security module.

## 2. Authentication

### 2.1 Product-facing authentication

For customer-facing use, prefer federated sign-in through established identity providers:

- Google;
- Microsoft.

Use standards-based OIDC/OAuth through an established maintained library. Do not implement the protocol from scratch.

Infosecurs must never receive or store the user's Google/Microsoft password.

After successful provider authentication, Infosecurs establishes its normal local Django authenticated session.

### 2.2 Local identity record

Keep a minimal local `User` plus external identity mapping sufficient to reconnect the same person on future logins.

Stable external identity is keyed by provider/issuer plus subject identifier, not email alone.

Store only what is needed:

- provider/issuer;
- provider subject;
- verified email where supplied;
- display/full name.

Do not request broad provider API permissions.

Do not request or retain refresh tokens merely for authentication.

Google/Microsoft API integration beyond authentication is not authorised here.

### 2.3 Existing local authentication

Existing Django local authentication may remain for synthetic development/audit fixtures and controlled Customer-Zero bootstrap where required by the existing test architecture.

It is not the intended customer sign-up experience.

Do not expose ordinary local-password registration as the primary product flow.

## 3. Single licensed account

Beta/commercial V1 is a **single authenticated-user licence per organisation**.

The authenticated person who creates the organisation is the Account Holder.

Existing `OrganisationMembership` remains the authenticated membership boundary.

Do not build:

- invitations;
- multiple licensed users;
- seat management;
- role-based application permissions;
- team administration;
- self-service account-holder transfer.

A future licensing change may expand this model without changing the distinction between authenticated users and named organisation people.

## 4. Organisation people and governance roles

Create a small `OrganisationPerson` concept for people relevant to governance but who do not need a login.

Minimum fields:

- organisation;
- full name;
- job title;
- optional email;
- optional linked local User;
- active/inactive state.

The sign-up user automatically gets an `OrganisationPerson` linked to their local User.

Governance roles for V1:

- Policy Authoriser;
- Security Responsible Person;
- Senior Leadership Representative.

One person may hold all roles.

Default all three roles to the Account Holder's `OrganisationPerson`.

Do not create duplicate Person rows merely because one human holds several roles.

The Account Holder is already represented by authenticated organisation membership; do not build a competing account-holder permission system.

### 4.1 Approval where authoriser has no login

A named Policy Authoriser does not need an Infosecurs licence/login.

If the Account Holder is also Policy Authoriser, approval may be recorded directly in-app.

If another named person is Policy Authoriser, V1 permits the Account Holder to record that external approval was obtained.

The product must distinguish these cases honestly, e.g.:

- `approved directly by account holder / policy authoriser`; or
- `external approval recorded by account holder; authoriser: Jane Smith, Managing Director`.

Do not imply authenticated/non-repudiable approval by a person who never logged in.

Direct multi-user approval is deferred.

## 5. Workplace is first-class organisation context

The existing M001 `OrganisationProfile.working_model` (`office`, `remote`, `hybrid`, `unknown`) is too coarse to represent real SME working context.

Add tenant-owned `Workplace` records.

Minimum fields:

- stable identifier;
- organisation;
- name;
- workplace type;
- location label;
- approximate people normally using that workplace/context;
- primary flag;
- active flag;
- created/updated timestamps.

V1 workplace types:

- distributed/home-based;
- dedicated office;
- shared office;
- coworking space;
- other.

`location_label` should normally be human-level location such as:

- `Woking, Surrey`;
- `London`;
- `Manchester`;
- `Home / remote working`.

A full postal address is not required for V1.

### 5.1 Examples

Four-person remote consultancy:

- `Home / remote working`
- type: `distributed_home`
- approx people: 4.

Six-person business in shared premises:

- `Woking shared office`
- type: `shared_office`
- location: `Woking, Surrey`
- approx people: 6.

Twenty-person organisation:

- `London Head Office`
- type: `dedicated_office`
- location: `London`
- approx people: 15;
- plus `Home / remote working`, approx people: 5, where appropriate.

### 5.2 Existing `working_model` compatibility

Do not create two independently editable workplace truths.

After Workplace migration, `OrganisationProfile.working_model` becomes a backward-compatible **derived summary**.

Derivation:

- no active workplace context -> `unknown`;
- active contexts all `distributed_home` -> `remote`;
- active contexts contain non-home workplaces and no distributed-home context -> `office`;
- mixture of distributed-home and non-home workplace contexts -> `hybrid`.

The existing field may remain physically present for compatibility with M001/M002 code/tests, but product writes after migration must flow through the workplace service and keep the summary synchronised.

Remove/disable independent editing of `working_model` in the normal product UI once Workplace is authoritative.

Do not rewrite M002 merely to consume the new model. Existing M002 consumers may continue using the derived summary until a separately authorised methodology change needs richer workplace context.

## 6. Starter policy length and purpose

The starter Information Security Policy is deliberately concise.

**Maximum rendered length: 2–4 pages. Target approximately 3 pages.**

It is a practical SME policy intended to be read, understood and approved.

Do not generate ISO-style policy packs or generic boilerplate.

Policy language must distinguish:

- organisational facts actually established;
- normative requirements the organisation is adopting;
- unresolved facts/gaps that must not be presented as already implemented.

Example, where backups are unknown:

Allowed:

> Important business information must be backed up appropriately.

Forbidden:

> The company performs daily encrypted backups.

## 7. Downstream policy distribution and training

M004 owns:

- what the approved policy says;
- why it says it;
- which organisation/security facts grounded it;
- who approved it;
- policy version/history;
- downloadable approved artefact.

M004 does **not** own:

- staff policy distribution;
- staff acknowledgement;
- security-awareness training;
- phishing campaigns;
- training completion;
- external service enrolment.

No uSecure API integration is authorised in M004.

After the core product is in place, Infosecurs may offer distribution options.

The preferred future option is uSecure, potentially including a 30-day trial, because it can own policy distribution/acknowledgement/training rather than Infosecurs duplicating those systems.

That integration must be separately authorised.

A future integration should ideally return meaningful evidence to Infosecurs, such as policy acknowledgement/training state.

## 8. Chargebee

Chargebee integration is deferred.

Authentication must not depend on Chargebee identity.

Future billing/subscription state attaches to the **Organisation/account**, not to a Google/Microsoft identity.

Conceptually:

```text
External Identity -> User -> Organisation Membership
                                |
                                +-> future Billing Account -> Chargebee
```

Do not create Chargebee code/config/API work as part of M004.

## 9. Consequences

The bounded foundation is:

```text
Federated identity
      ↓
single Account Holder
      ↓
named OrganisationPeople + governance roles
      ↓
first-class Workplace context
      ↓
grounded concise policy
      ↓
approval/versioned artefact
```

It deliberately avoids:

- password infrastructure;
- RBAC;
- multi-seat licensing;
- HR/personnel management;
- billing;
- policy distribution;
- awareness training;
- large physical-security/GRC taxonomy.

## 10. Future review points

Revisit only when there is an observed requirement:

- additional licensed users;
- direct policy-authoriser login/approval;
- billing/Chargebee;
- uSecure policy distribution/training;
- technical workplace/location integrations;
- richer workplace-driven risk methodology;
- provider API access beyond login.
