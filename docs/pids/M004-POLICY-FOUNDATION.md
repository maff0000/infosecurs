# M004 — Policy Foundation

**Status:** AUTHORISED FOR BUILD  
**Parent:** `/PID.md`  
**Depends on:** M003 PRODUCT_GREEN  
**Authoritative baseline main SHA at authorisation:** `e47e7b7a1b0f6bd6c7698705283f8f95b8c496a6`  
**Presentation target:** `PRODUCT_USABLE`  
**Required delivery framework:** FORGE  
**Project root:** `/srv/infosecurs`  
**Development host:** `dell-debian`  
**Project truth:** GitHub  
**Binding architecture decision:** `docs/adr/ADR-0002-IDENTITY-GOVERNANCE-WORKPLACE-AND-DISTRIBUTION-BOUNDARIES.md`

---

## 1. Purpose

M004 gives Infosecurs the minimum human/governance/workplace context required to produce, review and approve a concise Information Security Policy grounded in the organisation's actual security state.

It has two deliberately bounded layers.

### Foundation
- customer-facing federated sign-in;
- one authenticated Account Holder per organisation;
- named organisation people;
- simple governance-role assignment;
- first-class workplace context.

### Policy
- generate one concise Information Security Policy;
- ground it only in authoritative tenant state;
- make unsupported assumptions visible instead of fabricating facts;
- allow review/edit;
- record approval honestly;
- retain immutable approved versions;
- provide a downloadable approved artefact.

M004 is not an identity platform, HR system, document-management suite, billing system, policy-distribution system or compliance framework.

---

## 2. Core invariants

### 2.1 Security truth remains upstream

M004 does not create a new security-control truth store.

Authoritative inputs remain:

- M001 organisation facts;
- M002 canonical `BaselineAnswer`;
- M002 assets/risks;
- M003 Current Security State;
- M003 evidence/provenance/remediation;
- M004 Workplace and governance-person facts.

Policy text is an output derived from these sources.

AI-generated policy prose never becomes a new security fact merely because it appears in a policy.

### 2.2 Normative policy is not evidence of implementation

A policy may establish a requirement such as:

`Privileged accounts must use multi-factor authentication.`

That does not prove the organisation currently meets it.

Current implementation remains governed by the canonical security-state/evidence model.

### 2.3 Unknown must remain unknown

AI must never convert an unknown/unconfirmed organisation fact into an implemented-control claim.

### 2.4 One login does not mean one named person

Only the Account Holder needs an Infosecurs login in V1.

Other named governance people may exist without a licence/login.

---

## 3. User outcome

A Customer Zero user can:

1. sign in through Google or Microsoft without creating an Infosecurs password;
2. return later and be recognised as the same account through local account/session mapping;
3. see themselves recorded as Account Holder;
4. confirm/edit their name and job title;
5. see themselves initially assigned as:
   - Policy Authoriser;
   - Security Responsible Person;
   - Senior Leadership Representative;
6. optionally create another named organisation person and assign one or more governance roles to that person;
7. describe where staff work using simple Workplace records;
8. see the old `working_model` summary remain consistent with richer Workplace truth;
9. request a draft Information Security Policy;
10. receive a concise draft grounded in actual organisation/security/workplace state;
11. see unresolved material facts or review warnings separately from the policy prose;
12. review/edit the draft;
13. approve it directly if they are Policy Authoriser, or record an external approval by the named Policy Authoriser;
14. receive an approved immutable policy version;
15. download the approved policy;
16. later create a new draft/version without overwriting the previously approved version.

---

## 4. Non-goals

M004 does not build:

- local-password customer registration;
- multi-seat licensing;
- invitations;
- RBAC/permission matrix;
- enterprise SSO/SCIM;
- Google/Microsoft API access beyond authentication;
- HR/personnel management;
- exact workplace geolocation;
- office floor plans;
- visitor-management workflow;
- active physical-security scanning;
- policy distribution to staff;
- staff acknowledgement;
- awareness training;
- phishing campaigns;
- uSecure integration;
- Chargebee integration;
- Huntress integration;
- billing/subscription enforcement;
- arbitrary policy library;
- ISO 27001 policy suite;
- policy-signature/non-repudiation platform;
- full document-management system.

Do not pre-build M005/M006.

---

## 5. Customer-facing identity

Follow ADR-0002.

### 5.1 Providers

Support:

- Google;
- Microsoft.

Use an established maintained OIDC/OAuth library.

Do not implement the protocol from scratch.

### 5.2 Data boundary

Store only minimal external identity information required to reconnect the same person:

- provider/issuer;
- stable provider subject;
- verified email where supplied;
- display/full name.

Identity matching must use provider/issuer + subject, not email alone.

Do not ask for broad provider API permissions.

Do not request refresh-token/offline access merely for authentication.

### 5.3 Local session

After successful provider authentication, use the normal Django authenticated session.

Existing local auth may remain for synthetic development/test fixtures.

The normal customer-facing sign-up/login UX must prefer Google/Microsoft and must not ask the customer to create an Infosecurs password.

### 5.4 Provider configuration

Client IDs/secrets are runtime secrets/configuration outside Git.

Tests must use a fake/stubbed OIDC seam; normal CI must not require live Google/Microsoft credentials.

A limited live provider smoke test may be performed separately if credentials/configuration exist, but it is not a substitute for deterministic tests.

---

## 6. Single licensed Account Holder

V1 permits one authenticated Account Holder per organisation.

The sign-up user:

- becomes the organisation's authenticated owner/account holder through existing membership semantics;
- gets a linked `OrganisationPerson`;
- is the default assignee for all M004 governance roles.

Do not add additional login seats.

---

## 7. OrganisationPerson

Create a small tenant-owned `OrganisationPerson`.

Minimum:

- stable UUID or stable ID;
- organisation;
- full name;
- job title;
- optional email;
- optional linked local User;
- active/inactive state;
- created/updated timestamps.

Constraints:

- linked User, where present, must belong to the same organisation;
- one person may hold multiple governance roles;
- do not duplicate one human merely because they hold several roles.

The sign-up Account Holder's person record should be created idempotently.

---

## 8. Governance roles

M004 V1 roles:

```text
policy_authoriser
security_responsible
senior_leadership
```

Use a simple role-assignment model.

Each role has exactly one active assignee in V1.

One `OrganisationPerson` may hold all three.

Default all roles to the Account Holder.

No configurable role catalogue or permission engine.

### 8.1 Role UX

Make the common path extremely simple:

> You are currently listed as the policy authoriser, security contact and senior leadership representative. Is that correct?

Default: yes.

If not, allow the Account Holder to create/select another named person.

---

## 9. Workplace

Add tenant-owned `Workplace` per ADR-0002.

Minimum:

- stable identifier;
- organisation;
- name;
- type;
- location label;
- approximate people;
- primary flag;
- active flag;
- created/updated timestamps.

Types:

```text
distributed_home
dedicated_office
shared_office
coworking_space
other
```

A full postal address is not required.

### 9.1 Simple onboarding

Ask:

> Where do people normally work?

Suggested choices:

- Everyone works from home;
- We have one office;
- We use a shared/coworking office;
- Office + home working;
- We have several locations.

Only ask follow-up fields relevant to the chosen pattern.

Examples:

```text
4 staff
Home / remote working
distributed_home
approx people: 4
```

```text
Woking shared office
shared_office
Woking, Surrey
approx people: 6
```

```text
London Head Office
dedicated_office
London
approx people: 15

Home / remote working
distributed_home
approx people: 5
```

Do not turn this into a physical-security questionnaire.

### 9.2 Existing working_model

`OrganisationProfile.working_model` remains physically available for backwards compatibility but becomes a derived summary once Workplace is authoritative.

Derive:

- no active workplace -> `unknown`;
- home-only -> `remote`;
- non-home only -> `office`;
- home + non-home -> `hybrid`.

Remove normal independent product editing of `working_model` after migration.

All M004 workplace writes must synchronise the derived summary transactionally.

M001/M002 regression tests must prove existing consumers continue to receive the correct summary.

---

## 10. Policy product

M004 V1 creates exactly one policy type:

```text
Information Security Policy
```

Do not create a generic policy-builder framework.

### 10.1 Length

The rendered approved policy must be **2–4 pages maximum**.

Target approximately **3 pages**.

The policy should be readable by ordinary staff in a small organisation.

No generic certification boilerplate and no padded prose to hit a page count.

### 10.2 Expected content

Keep sections short.

Expected subject areas:

1. Purpose and scope;
2. Responsibilities and governance;
3. Access/authentication;
4. Devices, protection and updates;
5. Information handling and backup;
6. Workplace/remote-working expectations;
7. Security incidents/reporting;
8. Review, approval and document control.

Sections may be combined to preserve the 2–4 page limit.

Only include subjects that make sense for the organisation.

---

## 11. Policy truth model

A generated policy contains two different semantic classes.

### 11.1 Established organisational facts

Examples:

- organisation name;
- approximate staff size;
- workplace context;
- named governance responsibilities;
- confirmed technology/security-state facts where relevant.

These must come from authoritative tenant state.

### 11.2 Normative requirements

Examples:

- staff must protect company devices;
- privileged access must use appropriate MFA;
- security incidents must be reported promptly;
- confidential information must be handled appropriately.

These are policy requirements being adopted.

They are not claims that implementation is already complete.

### 11.3 Forbidden transformation

If current state is unknown, AI must not generate factual implemented-state claims.

Example from:

`backups = unknown`

Allowed:

`Important business information must be backed up appropriately.`

Forbidden:

`The company performs daily encrypted backups.`

Where a material unknown affects approval quality, show it in a separate review/gap panel rather than inventing prose.

---

## 12. Grounding payload

Build a deterministic, tenant-scoped policy-grounding service.

Input may include only what is necessary:

- organisation identity/name;
- high-level organisation profile;
- staff count;
- Workplace summaries;
- governance people/roles;
- canonical baseline/control states;
- M003 Current Security State labels;
- concise relevant open-risk/remediation context where useful.

Do not send evidence file bytes to AI.

Do not send arbitrary evidence free text unless separately authorised.

Do not expose database UUIDs merely so the model can reproduce them.

Application code owns all object identity/versioning.

Policy generation must be impossible to widen across tenants by caller-supplied IDs.

---

## 13. AI role

Use the existing governed AI boundary.

Recommended alias:

`trinity-core`

AI may:

- turn structured grounded state into concise readable policy prose;
- choose proportionate wording;
- adapt remote/shared-office/office language;
- keep the policy within the defined structure/length;
- identify unresolved facts requiring customer review.

AI may not:

- invent organisation facts;
- claim a control is implemented merely because the policy requires it;
- invent evidence;
- invent certification/compliance;
- create/change governance-role assignments;
- approve the policy;
- change BaselineAnswer/security state;
- create hidden policy requirements outside the authorised section contract.

---

## 14. Policy generation contract

Use a strict structured response.

Prefer section-oriented structured output rather than one unbounded markdown blob.

At minimum return:

- policy title;
- concise section content keyed to approved section identifiers;
- explicit review warnings/unknowns separate from policy text.

Validate before persistence.

Reject malformed/oversized/unexpected output.

Bound output length so the rendered artefact can satisfy 2–4 pages.

Version the prompt/contract.

Record AI invocation using the existing invocation/audit pattern, extended cleanly for policy drafting.

No chain-of-thought storage.

---

## 15. Policy persistence/versioning

Create a bounded policy domain.

### PolicyDocument

Tenant-owned logical policy identity.

For M004 V1 there is one active logical Information Security Policy per organisation.

### PolicyVersion

Approved historical versions are immutable.

Minimum:

- organisation/document;
- version number;
- status;
- title;
- structured/rendered content;
- generation source;
- prompt/methodology version where generated;
- AI invocation reference where applicable;
- draft created by;
- created_at;
- approved_at;
- named Policy Authoriser;
- approval mode;
- approval recorded by;
- next review date;
- superseded-by relationship where applicable.

Status:

```text
draft
approved
superseded
```

Editing an approved policy creates a new draft/version.

Never rewrite approved history in place.

---

## 16. Review and editing

The Account Holder must be able to review and edit the draft before approval.

Do not require raw JSON/markdown editing.

A simple section-based editor is sufficient.

Preserve learning signals from meaningful policy edits through the existing Learning Signal Capture doctrine without creating a learning engine.

The persisted PolicyVersion content provides the durable before/after material; activity events need not duplicate large policy text.

---

## 17. Approval semantics

### 17.1 Account Holder is Policy Authoriser

If the logged-in Account Holder is the assigned Policy Authoriser, they may approve directly.

Record:

- authoriser person;
- authenticated approving User;
- approval timestamp;
- direct approval mode.

### 17.2 Different named Policy Authoriser

If another `OrganisationPerson` is Policy Authoriser and has no login, V1 permits the Account Holder to record that approval was obtained externally.

Require an explicit confirmation action.

Record:

- named authoriser;
- Account Holder who recorded it;
- timestamp;
- approval mode = external approval recorded.

UI must not imply that the named authoriser authenticated into Infosecurs.

Do not build email approval links or second-user authentication in M004.

---

## 18. Policy review date

Default suggested review interval:

```text
12 months
```

Allow the Account Holder to choose/change the next review date before approval.

Do not build scheduled reminders/automation in M004 unless separately authorised.

---

## 19. Approved artefact

An approved policy must have a stable downloadable representation suitable for later sharing.

Preferred user outcome: downloadable PDF.

Requirements:

- generated from the exact immutable approved PolicyVersion;
- title/version/organisation visible;
- approval information visible;
- next review date visible;
- no hidden mutable live-state lookup when downloading an old approved version;
- 2–4 page maximum under the accepted rendering path.

Use an established rendering mechanism rather than building a custom layout engine.

M004 PRODUCT_GREEN requires a downloadable customer-usable policy artefact.

---

## 20. Distribution boundary

M004 stops at:

```text
approved policy
      ↓
downloadable artefact
```

Do not implement:

- policy emailing;
- employee recipient lists;
- policy acknowledgements;
- training;
- uSecure;
- other awareness vendors.

Future options are deliberately deferred until the core product is in place.

The preferred future integration candidate is uSecure, potentially with a 30-day trial, but there must be **zero vendor-specific implementation dependency in M004**.

---

## 21. Chargebee boundary

Do not integrate Chargebee in M004.

Future billing will attach to the Organisation/account rather than to Google/Microsoft identity.

Do not make authentication conditional on Chargebee.

Do not create subscription tables/API calls merely as placeholders.

---

## 22. Activity/provenance

Extend existing activity/provenance discipline with meaningful events such as:

```text
organisation_person_created
governance_role_changed
workplace_created
workplace_updated
policy_draft_generated
policy_draft_edited
policy_approved
policy_superseded
```

Capture structured before/after metadata where useful.

Do not duplicate large policy text in activity events.

Do not let the event stream become a second truth store.

---

## 23. Tenant isolation

Every new tenant-owned object must be organisation-scoped.

Negative tests must prove organisation A cannot:

- view/edit B's people;
- assign B's person to A's role;
- view/edit B's workplace;
- generate a policy using B's state;
- view/edit/approve B's draft;
- download B's approved policy;
- infer B's policy/person/workplace existence through identifiers/errors.

Cross-tenant policy generation or download is catastrophic.

---

## 24. Security considerations

At minimum:

- no user passwords handled by Infosecurs in the federated customer flow;
- OIDC state/nonce/redirect validation delegated to established library;
- secure session/cookie settings appropriate to environment;
- CSRF on mutating forms;
- no open redirect;
- no account linking by unverified email alone;
- provider subject/issuer treated as identity key;
- tenant scope enforced before people/workplace/policy operations;
- policy download tenant-scoped;
- no provider/client secrets in Git/logs;
- no AI access to provider tokens;
- no evidence-file bytes in policy prompts;
- no sensitive prompt dumping.

---

## 25. AI evaluation

Because M004 adds a new consequential AI behaviour, run a real live evaluation against `trinity-core` before closure.

Use a small synthetic golden corpus covering at minimum:

1. four-person fully remote company;
2. six-person shared-office company in Woking;
3. twenty-person London HQ + remote workers;
4. several unknown baseline controls;
5. strong evidence-backed security state;
6. explicit control gaps/open remediation;
7. different named Policy Authoriser;
8. adversarial/prompt-injection-like untrusted notes already present upstream.

Evaluate objectively where possible:

- no unsupported implemented-state claim;
- unknown not converted to yes/no;
- governance names/roles faithful;
- workplace context faithful;
- no UUID/database identifier leakage;
- no certification/compliance fabrication;
- output contract valid;
- required sections present;
- output length within configured bound.

Human review must assess:

- readable for an SME;
- proportionate;
- not padded;
- no misleading assurance language;
- sensible distinction between requirements and current state.

A valid policy-generation path that has material unknowns may return review warnings and still succeed.

---

## 26. Mechanical tests

At minimum:

### Identity
- provider+subject stable mapping;
- email change does not create duplicate identity;
- unsafe/mismatched account-link path rejected;
- returning external identity maps to same local account;
- no customer local-password signup in normal flow;
- fake/stub provider sufficient for CI.

### People/roles
- Account Holder person created idempotently;
- default governance roles all point to Account Holder;
- one person may hold all roles;
- reassignment works;
- cross-tenant assignment impossible;
- inactive-person handling explicit.

### Workplace
- home-only/office-only/hybrid representations;
- derived `working_model` correct;
- normal UI cannot independently contradict derived working model;
- multiple locations supported;
- tenant isolation.

### Policy grounding
- exact tenant only;
- correct people/roles/workplaces;
- no evidence bytes;
- unknown preserved;
- no identifier-reproduction dependency.

### Policy lifecycle
- draft generation;
- edit;
- direct approval;
- external approval recorded;
- approved version immutable;
- new draft does not mutate approved version;
- supersession correct;
- download exact approved version;
- length/page bound tested through accepted rendering path.

### Regression
- M001/M002/M003 tests remain GREEN;
- M002 deterministic risk behaviour unchanged;
- M003 Current Security State remains authoritative evidence/security-state projection.

---

## 27. Real-browser acceptance

Fresh FORGE Auditor must drive at least:

1. exact audited SHA, fresh Docker data;
2. authenticate through deterministic test/fake federated-auth seam and prove returning identity maps to same local account/session;
3. create organisation;
4. confirm Account Holder's name/title;
5. verify all governance roles default to Account Holder;
6. create another named person and assign Policy Authoriser to that person;
7. configure a realistic workplace case including shared-office or hybrid;
8. prove derived `working_model` matches Workplace state;
9. complete enough existing baseline/security-state data;
10. generate draft policy;
11. verify policy is 2–4 pages under accepted rendering;
12. inspect policy for no unsupported implemented-control claims;
13. edit at least one section;
14. record external approval by the different named Policy Authoriser;
15. download approved artefact;
16. confirm approval wording says approval was recorded by Account Holder rather than falsely authenticated by named authoriser;
17. create a new draft/change and prove previous approved version remains content-stable;
18. exercise cross-tenant person/workplace/policy/download manipulation;
19. verify activity events;
20. confirm no unexplained browser console errors.

Also cover direct approval automatically where Account Holder == Policy Authoriser.

---

## 28. Delivery gates

Mandatory existing checks:

```text
ci/unit
ci/integration
security/secrets
security/dependencies
security/sast
security/container
```

Also required:

- live M004 AI evaluation GREEN;
- fresh FORGE Auditor GREEN;
- real-browser acceptance GREEN;
- exact-SHA closure under the existing GitHub Evidence Contract;
- fresh-clone reproduction.

If live Google/Microsoft provider configuration is unavailable, do not invent credentials. Deterministic library/protocol tests and fake-provider acceptance remain required; record live-provider proof as a production-readiness item unless Central Architecture separately supplies/configures credentials.

---

## 29. Post-audit delta rule

Use `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md` mechanically.

After Auditor GREEN:

- evidence-only delta may follow evidence-only proof;
- CI/control-plane delta must rerun affected checks;
- any product/runtime source-file touch, including comments/docstrings, requires a fresh Auditor.

No judgment call.

---

## 30. Definition of PRODUCT_GREEN

M004 is PRODUCT_GREEN only when:

1. M003 remains PRODUCT_GREEN.
2. customer-facing auth has governed Google/Microsoft federated-login support using an established library and local Django session.
3. ordinary customers are not asked to create an Infosecurs password.
4. one authenticated Account Holder per organisation is maintained for V1.
5. Account Holder has a linked named OrganisationPerson.
6. Policy Authoriser, Security Responsible and Senior Leadership roles exist and default to Account Holder.
7. one person may hold multiple roles without duplication.
8. a different named non-login Policy Authoriser can be represented honestly.
9. Workplace is first-class tenant state.
10. legacy `working_model` is deterministically derived from Workplace and cannot drift through normal product use.
11. Information Security Policy generation uses only authoritative tenant state.
12. AI cannot silently establish organisation/security facts.
13. unknowns remain unknown; normative requirements are not presented as evidence of implementation.
14. policy is concise: 2–4 rendered pages maximum.
15. draft is reviewable/editable.
16. direct approval and externally-recorded approval are truthfully distinguished.
17. approved PolicyVersion is immutable.
18. later revisions do not rewrite approved history.
19. approved policy is downloadable as a stable customer-usable artefact.
20. policy distribution/training/uSecure remain absent.
21. Chargebee remains absent.
22. relevant learning/provenance signals are preserved without building a learning engine.
23. cross-tenant people/workplace/policy/download paths are negatively tested.
24. live policy-generation AI evaluation is GREEN.
25. all M001–M003 regressions remain GREEN.
26. all required GitHub checks are GREEN on the closing head.
27. fresh FORGE Auditor is GREEN on the exact audited SHA.
28. closure obeys the post-audit delta doctrine.
29. merged main reproduces the accepted result from a fresh clone.
30. GUNNAR stops and returns closure to Central Architecture.

Stop after M004 PRODUCT_GREEN. Do not begin M005.
