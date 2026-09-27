# M007 — Dashboard Application Shell, Tiered Entitlements, Session Contract & Foundational Metrics

**Product:** Infosecurs  
**Module:** M007  
**Delivery recipient:** BAGMAN / FORGE  
**Product authority:** Matt  
**Central Product / Architecture authority:** Matt + Central ChatGPT Product/Architecture  
**Delivery roles:** Fresh Product Lead (PL) → Engineer(s) → Fresh Independent Auditor  
**Delivery framework:** FORGE  
**Status:** AUTHORISED FOR BUILD when this PID is handed to BAGMAN/FORGE by Product Authority  
**Canonical repository:** `github.com/maff0000/infosecurs`  
**Canonical development host:** `dell-debian`  
**Canonical project root:** `/srv/infosecurs`  
**Project truth:** GitHub  
**Current canonical `main` at PID authoring:** `ea28cb9c337b6fad824b5435378dcab231b637b0`  
**Accepted Beta 0.1 product identity:** `225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`  
**Accepted Beta 0.1 image:** `infosecurs-release:225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`  
**Accepted Beta 0.1 Image ID:** `sha256:afc488184d7bcd749befa88b2a9cfeaab4be82c8203568b168af49f77320a281`  
**Current application stack at PID authoring:** Django 6.1.1 / PostgreSQL / Docker / server-rendered templates  
**Data restriction:** synthetic / deliberately Customer-Zero-safe data only  
**Real customer data:** NOT AUTHORISED  
**Production-readiness:** NOT AUTHORISED by this PID  

---

## 0. Read this first — authority, baseline and intent

M006 / Infosecurs Beta 0.1 is `PRODUCT_GREEN`.

M007 begins the next bounded product step. It does **not** reopen M006 and it must not casually redesign proven security/domain logic.

This PID authorises the construction of the **Infosecurs application dashboard shell and the minimum entitlement/session/metric architecture that should exist before the GUI expands further**.

The core principle is:

> **Get the application bones right now so future UI, packages and assurance features do not require a structural rewrite.**

This is deliberately **function before form**.

M007 is not a visual redesign competition. It is not a marketing-site build. It is not a new authentication platform. It is not a compliance-framework expansion.

The output should be a plain, coherent, secure dashboard application whose structure can later be skinned with a professional dashboard framework, charts, icons and richer styling without changing the core navigation, entitlement, session or truth model.

### 0.1 GitHub preflight is mandatory

Before any implementation:

1. prove host is `dell-debian`;
2. prove project root is `/srv/infosecurs`;
3. fetch/prune Git;
4. prove canonical GitHub `main`;
5. compare actual `main` with the authoring SHA above;
6. read:
   - `/PID.md`;
   - `docs/pids/M006-CUSTOMER-ZERO-BETA-HARDENING.md`;
   - `docs/evidence/M006-CLOSURE.md`;
   - `docs/adr/ADR-0003-MANAGED-SECURITY-EXCEPTIONS-POLICY-TRUTH-AND-REMEDIATION.md`;
   - current session/auth settings;
   - current base/application templates;
   - current Overview derivation;
   - current baseline catalogue/models;
7. record the exact starting SHA in M007 evidence.

If GitHub has moved since this PID was written, the PL must reconcile the delta rather than blindly forcing this PID against stale source.

GitHub is engineering truth.

### 0.2 Preserve the accepted Beta

The accepted M006 image and its evidence remain historical accepted Beta 0.1 evidence.

Do not delete, retag, mutate or overwrite the accepted M006 image as part of M007.

M007 product source will necessarily create a **new product identity** if accepted.

---

# 1. Product objective

M007 must create a durable Infosecurs dashboard architecture with:

1. one canonical application shell;
2. a persistent left-hand sidebar;
3. responsive collapse to a hamburger/drawer on narrow screens;
4. a simple top bar with organisation context and user/account placeholder;
5. one central main-content window;
6. database-driven navigation;
7. cumulative package tiers:
   - `0 PAUSED`
   - `1 FOUNDATION`
   - `2 MONTHLY`
   - `3 PRO`
8. server-side session context containing the active package tier;
9. the same entitlement rule controlling both menu visibility **and direct route access**;
10. complete session destruction on logout;
11. fixed synthetic session fixtures for testing all package states;
12. a Home dashboard containing exactly two primary metrics initially:
    - **Foundational Security Posture**
    - **Security Foundations Completion**
13. a concise **Needs attention** section with explicit counts and `click here` links;
14. a basic Foundations workspace showing what is complete/incomplete;
15. preservation of all existing tenant-isolation, assurance-truth, AI, evidence, history and security invariants;
16. a final PL improvement report listing sensible future improvements discovered during delivery.

The dashboard must feel like **one application**, not a collection of unrelated pages.

---

# 2. Product shell doctrine — non-negotiable

## 2.1 One application shell

There must be one canonical authenticated application shell containing:

- Infosecurs product identity;
- top bar;
- active organisation context;
- user/account placeholder;
- logout action;
- left sidebar;
- responsive hamburger/drawer behaviour;
- global customer-facing messages;
- main content region.

Individual domain templates render **inside the main content region**.

They must not copy:

- menu markup;
- account controls;
- organisation header;
- hamburger behaviour;
- global application layout;
- entitlement-navigation logic.

Conceptually:

```text
application shell
├── top bar
│   ├── hamburger (narrow viewport)
│   ├── Infosecurs identity
│   ├── active organisation
│   └── user/account/logout
├── left sidebar
│   └── database-derived entitled navigation
└── main
    └── current workspace/template content
```

Changing the shell later must change the application once, not page-by-page.

## 2.2 Public/auth UI is a separate concern

Login, signup, password reset, MFA, email verification, account recovery and subscription/billing account management are **not part of the Infosecurs dashboard product shell**.

The current Django/allauth login mechanisms may remain temporarily as the Beta/development authentication harness where needed for existing tests and local operation.

M007 must:

- **not** build a new signup system;
- **not** redesign authentication pages;
- **not** add password-management features;
- **not** add billing management;
- **not** make dashboard templates depend on authentication-page markup.

The long-term architecture is:

```text
external account/auth system
        ↓
trusted authenticated session boundary
        ↓
Infosecurs dashboard
```

M007 builds the dashboard-side session contract so the external account system can replace the current Beta auth harness later without rewriting the dashboard.

## 2.3 Function before form

Do not add merely decorative complexity.

Not required in M007:

- charts;
- gauges;
- icon packs;
- animations;
- a SPA;
- React/Vue/etc.;
- an external dashboard UI framework;
- a CSS build pipeline;
- external font/CDN dependencies;
- dark mode;
- drag-and-drop navigation;
- configurable user-created menus.

Plain, clear cards/tables/forms are correct.

The future visual skin must be able to sit on top of this structure.

---

# 3. Navigation information architecture

The first-level customer navigation is:

```text
Home
Foundations
Customer Assurance
Security
Policies
Company
```

The first-level items represent **customer jobs/workspaces**, not internal database modules.

### 3.1 Initial nested navigation

Initial intended structure:

```text
Home

Foundations

Customer Assurance

Security
    Security State
    Baseline
    Assets
    Risks
    Evidence
    Remediation

Policies

Company
    Profile
    Governance
    Workplace
    Activity
```

The exact labels may receive tiny grammatical corrections by the PL, but no conceptual redesign is authorised without escalation.

### 3.2 Existing routes should be reused where practical

Do not rewrite proven domain workflows merely to obtain prettier URLs.

Examples:

- Home may reuse/replace the current organisation Overview destination.
- Customer Assurance may point to the existing Questionnaire Assurance workflow.
- Security children should point to existing Security State / Baseline / Assets / Risks / Evidence / Remediation routes.
- Policies should point to the existing policy workflow.
- Company children should point to existing organisation/governance/workplace/activity routes.

Changing a customer-facing navigation label does not require renaming every internal app/route.

### 3.3 Customer Assurance naming

The visible primary workflow should use **Customer Assurance**.

The existing one-question Questionnaire Assurance implementation remains the underlying Beta capability for now.

M007 does **not** build whole XLSX/DOCX/PDF questionnaire ingestion. That remains later product scope.

---

# 4. Database-driven product area/navigation registry

The sidebar must not be hard-coded as a large collection of links in the shell.

Create a small canonical database-backed registry representing product areas/capabilities.

Recommended model name:

`ProductArea`

Equivalent naming is acceptable if the semantics remain clear.

## 4.1 Required fields

At minimum:

```text
code                    stable unique machine identifier
label                   customer-facing navigation label
parent                  nullable self-FK for nested menu structure
destination_view_name   Django named route; never arbitrary external URL
min_package_tier        integer 0..3
display_order           integer
show_in_navigation      boolean
is_active               boolean
```

Optionally include a short description if genuinely useful.

Do not store arbitrary executable code, Python import paths, template fragments or user-supplied URLs in this table.

### 4.2 Constraints

Mechanically enforce:

- unique `code`;
- `min_package_tier` between 0 and 3;
- a row cannot parent itself;
- deterministic ordering;
- inactive rows do not render;
- rows hidden from navigation may still represent non-menu capabilities if needed later.

### 4.3 Seed data is governed in Git

Initial rows must be created by a deterministic migration/seed mechanism committed to Git.

Do not create an admin-editable commercial configuration surface in M007.

The fact that runtime data is stored in PostgreSQL does **not** mean an operator should casually mutate product methodology from Django Admin.

Initial product-area changes remain governed engineering/product changes.

### 4.4 Navigation service

Create one application service responsible for:

```text
session package tier
        ↓
active ProductArea rows
        ↓
min_package_tier <= current tier
        ↓
ordered parent/child navigation tree
```

The template loops over that output.

The template does not independently decide commercial entitlement.

### 4.5 No client-side entitlement logic

JavaScript may open/close the sidebar.

JavaScript must not decide whether a user is entitled to a product area.

Entitlement is server-side.

---

# 5. Commercial package hierarchy

The package hierarchy is cumulative and must be treated as canonical:

| Tier | Code | Meaning |
|---:|---|---|
| 0 | `PAUSED` | Account/session exists but paid product access is paused |
| 1 | `FOUNDATION` | 30-Day Security Foundations capability |
| 2 | `MONTHLY` | Everything in Foundation **plus** Monthly capabilities |
| 3 | `PRO` | Everything in Foundation **plus** Monthly **plus** Pro capabilities |

The invariant is:

```text
PRO ⊇ MONTHLY ⊇ FOUNDATION
```

Access rule:

```text
current_package_tier >= capability.min_package_tier
```

No separate “Foundation enabled” flag should be needed for a Monthly or Pro customer.

No separate “Monthly enabled” flag should be needed for a Pro customer.

### 5.1 Tier 0 / Paused

Tier `0` is a deliberate package state, not an error.

A paused customer should retain only the minimal shell necessary to understand that product access is paused and to leave the application safely.

Initial Tier-0 application access:

- Home / paused account message;
- top-right account placeholder;
- logout.

Do not expose Security, Foundations, Customer Assurance, Policies, Company or historic tenant content merely because the sidebar hid it.

Direct URL access must be denied by the server.

The exact long-term commercial policy for read-only historic access by paused accounts is **not** decided in M007.

### 5.2 Initial package mapping

Initial visible menu availability:

| Area | Minimum tier |
|---|---:|
| Home | 0 |
| Foundations | 1 |
| Security | 1 |
| Security State | 1 |
| Baseline | 1 |
| Assets | 1 |
| Risks | 1 |
| Evidence | 1 |
| Remediation | 1 |
| Policies | 1 |
| Company | 1 |
| Profile | 1 |
| Governance | 1 |
| Workplace | 1 |
| Activity | 1 |
| Customer Assurance | 2 |

M007 does not need to invent a fake Pro-only feature just to prove tier 3.

Tier 3 must still be mechanically tested to inherit every Tier-1 and Tier-2 area.

Future Pro areas can simply use `min_package_tier = 3`.

---

# 6. Session architecture

## 6.1 Principle

The browser must hold only the ordinary opaque session identifier.

Business/session meaning remains server-side.

Do **not** trust a client-writable object containing:

- package tier;
- organisation ID;
- role;
- entitlement;
- security permissions.

The current application already uses Django sessions. M007 must make the intended server-side session engine explicit.

Set/confirm:

```text
SESSION_ENGINE = django.contrib.sessions.backends.db
```

Do not use Django's signed-cookie session backend for this contract.

Reason: the application needs server-side invalidation and logout/revocation semantics. The browser cookie must be an opaque reference, not a container for the entitlement payload.

## 6.2 Canonical Infosecurs dashboard session key

Create one structured, versioned dashboard context under one session key, e.g.:

```text
request.session["infosecurs_context"]
```

Recommended schema V1:

```json
{
  "schema_version": 1,
  "subject_id": "synthetic-user-id",
  "organisation_id": "synthetic-organisation-uuid-or-null",
  "package_tier": 2,
  "package_code": "MONTHLY",
  "entitlement_version": 1,
  "issued_at": "UTC-ISO-8601",
  "auth_source": "django_beta"
}
```

Exact serialization may vary slightly, but preserve the semantics.

### 6.3 Keep the session context small

Do not unnecessarily duplicate:

- organisation name;
- user email;
- customer profile;
- security answers;
- permissions lists;
- evidence;
- roles;
- display data.

Load display data from canonical models when rendering.

The session should identify the user/context/contract level, not become another customer database.

### 6.4 Validation must fail closed

Every read of the session contract must validate:

- known schema version;
- authenticated user exists;
- `subject_id` matches the authenticated server-side user;
- package tier is exactly 0, 1, 2 or 3;
- package code matches package tier;
- organisation ID is either valid/allowed or deliberately absent before organisation context selection;
- where an organisation is active, the user remains a member of that organisation;
- malformed/missing contract never silently becomes Tier 3.

A bad/missing package tier is **deny**, not “default to Pro”.

### 6.5 Active organisation

The current application already uses organisation-scoped URLs and tenant membership.

M007 must preserve that model.

Where practical, standardise the active organisation into the structured session context rather than proliferating unrelated session keys.

Do not weaken the existing `get_member_organisation_or_404()` tenant-scoping discipline.

If organisation switching changes the active organisation context, the application should cycle/rotate the session key as a defence-in-depth measure because security context changed.

### 6.6 Current Beta authentication adapter

The current Django/allauth authentication remains a temporary adapter.

Create a small session-issuance boundary so current auth and future external auth both produce the same Infosecurs session contract.

Conceptually:

```text
current Django Beta login ─┐
                           ├─> SessionContextIssuer ─> infosecurs_context
future external account ───┘
```

Domain/dashboard code consumes the session contract, not assumptions about how authentication happened.

Do not build the future external provider in M007.

---

# 7. Fixed synthetic session fixtures

The Product Authority explicitly requires fixed test sessions from the beginning.

Create four canonical synthetic fixture profiles:

```text
PAUSED      tier=0 code=PAUSED
FOUNDATION  tier=1 code=FOUNDATION
MONTHLY     tier=2 code=MONTHLY
PRO         tier=3 code=PRO
```

These fixtures must be usable by:

- unit tests;
- integration tests;
- entitlement tests;
- browser tests.

## 7.1 Safe development/test seam

The Engineer may implement a small **development/test-only** fixture switch mechanism for real-browser testing if useful.

If a route is used for this purpose:

- it must be mounted only when `DJANGO_ENV` is `development` or `test`;
- it must not exist in production URL resolution;
- it must require an already-authenticated synthetic test user;
- it must use POST, not GET;
- it must require CSRF;
- it must only select one of the four fixed profiles;
- changing tier must cycle the session key;
- production tests must prove the route is absent/404.

Do not create a production “change my tier” endpoint.

A test helper that directly creates server-side session context is also acceptable.

The PL should choose the smallest safe seam that supports both mechanical and browser testing.

## 7.2 No client override

The following must have no authority over package access:

```text
?tier=3
?package=PRO
POST package_tier=3
X-Infosecurs-Tier: 3
X-Package: PRO
cookie package=PRO
hidden form field
localStorage
sessionStorage
JavaScript variable
```

Tests must deliberately try representative variants.

---

# 8. Logout and session destruction

Logout is a security boundary.

On logout:

> **the entire server-side session must be destroyed, not merely marked unauthenticated.**

Use Django's normal secure logout/session-flush mechanism unless a proven reason requires a wrapper.

Django's authentication logout currently flushes the session; M007 must prove that property rather than assuming it.

## 8.1 Required logout acceptance test

For each meaningful entitlement state, and at minimum PRO:

1. authenticate;
2. capture current session identifier;
3. prove an entitled page returns successfully;
4. logout;
5. prove the old server-side session no longer contains the Infosecurs context;
6. replay the old cookie manually;
7. attempt:
   - Foundation route;
   - Monthly route;
   - Pro-capability guard test;
   - Security;
   - Evidence;
   - Policy;
   - Company;
   - direct object URLs;
8. prove access is rejected/redirected appropriately;
9. authenticate again;
10. prove a new session identifier is issued;
11. prove access reflects only the newly issued package tier.

The old session must not be recoverable by Back, copied URLs or cookie replay.

## 8.2 Session fixation

Prove the session identifier changes on successful authentication/security-context establishment.

Prove it also changes when the test harness changes privilege tier or active organisation.

Do not preserve an attacker-supplied/pre-authentication session identifier across privilege establishment.

---

# 9. Server-side entitlement enforcement

Hiding a sidebar item is **not** access control.

The same commercial capability model that creates the sidebar must protect direct requests.

Create one central entitlement service / guard.

Conceptually:

```text
require_capability(request, "customer_assurance")
```

or a middleware/decorator equivalent.

The exact implementation is for the PL/Engineer to choose, but the invariant is mandatory:

> **One server-side entitlement decision; navigation and route protection consume the same decision.**

## 9.1 Default deny

For application capabilities governed by M007:

- known entitlement required;
- missing/malformed session fails closed;
- insufficient tier denied;
- inactive capability denied;
- tenant membership still separately required.

Do not create scattered logic such as:

```python
if request.session["package_tier"] == 2:
```

in individual views/templates.

Centralise it.

## 9.2 Route/capability mapping

Do not place arbitrary URL security policy in the database.

A small code-governed map from route namespace/view family to stable `ProductArea.code` is acceptable and preferred over executable/dynamic database configuration.

For example:

```text
questionnaire namespace → customer_assurance
security_state namespace → security
security_baseline namespace → security
key_assets namespace → security
risk_register namespace → security
evidence namespace → security
remediation namespace → security
policy namespace → policies
governance/workplace/activity/organisation-profile → company
```

The DB owns commercial metadata (`min_package_tier`, label/order/parent).

Application code owns safe routing/guard semantics.

## 9.3 Tenant isolation remains separate

A Tier-3 user in Organisation B must not access Organisation A.

Package entitlement and tenant authorisation are separate gates:

```text
authenticated session
    AND
package entitlement
    AND
organisation membership
    AND
object belongs to organisation
```

Never allow a package tier to become a substitute for tenant scoping.

---

# 10. Requirement / methodology registry

The Product Authority wants a durable database structure for requirements/compliance areas so commercial packaging and scoring can grow without a future rewrite.

Do **not** move all current security methodology out of Git into casually editable database rows.

Create a governed metadata table whose initial rows are seeded through Git/migrations and map onto stable existing canonical facts.

Recommended model:

`FoundationRequirement`

Equivalent naming is acceptable if the semantics remain clear.

## 10.1 Required fields

At minimum:

```text
code
title
product_area              FK to ProductArea
methodology_version
requirement_kind
source_key
min_package_tier
counts_toward_posture
counts_toward_completion
security_weight
display_order
is_active
```

### 10.2 Requirement kinds

Initial controlled kinds may include:

```text
BASELINE_CONTROL
DERIVED_MILESTONE
```

Do not store arbitrary Python callable paths in the DB.

Use a small application-owned resolver registry keyed by safe `requirement_kind` / `source_key`.

### 10.3 Methodology version

Introduce a clear current Foundations methodology version, e.g.:

```text
FOUNDATION_METRIC_VERSION = "2026-09-v1"
```

The exact string may be chosen by the PL.

The metric result should retain/expose its methodology version internally so a future change to weights/requirements is not silently indistinguishable from the previous method.

M007 does not need historical score trending.

### 10.4 No editable customer score

The requirement table stores product methodology.

It must not store a customer's computed:

- posture percentage;
- completion percentage;
- arbitrary manual “done” flags.

Customer metric state remains derived from canonical domain records.

---

# 11. Foundational Security Posture

## 11.1 Customer-facing title

Use:

> **Foundational Security Posture**

Do not use:

- Compliance Score;
- Cybersecurity Certification Score;
- Security Maturity Rating;
- Assurance Certification;
- Verified Security Score.

The number is an Infosecurs foundational measure derived from recorded customer state, not an independent audit/certification.

Display supporting copy substantially equivalent to:

> Based on your recorded foundational security state. This is not an independent security assessment.

## 11.2 Initial scope

The v1 posture percentage is based on the existing canonical 12-question `security_baseline` catalogue.

Do not include policy text, uploaded evidence, remediation existence or AI prose as bonus points.

### 11.3 State factors

For each applicable posture requirement:

| Baseline state | Factor |
|---|---:|
| `yes` | 1.0 |
| `partial` | 0.5 |
| `no` | 0 |
| `unknown` / missing | 0 |
| `not_applicable` | excluded from denominator |

Important invariant:

> `UNKNOWN` and `NO` may both earn zero posture points, but they remain semantically different states everywhere in the product.

Never rewrite UNKNOWN to NO for scoring convenience.

### 11.4 Weighting

Use security importance weights:

```text
5 = critical foundational importance
3 = important foundational importance
1 = supporting foundational importance
```

Initial v1 weight proposal:

| Existing baseline key | Weight |
|---|---:|
| `mfa_privileged_accounts` | 5 |
| `patching` | 5 |
| `backups` | 5 |
| `mfa_user_accounts` | 3 |
| `endpoint_protection` | 3 |
| `device_encryption` | 3 |
| `joiner_mover_leaver` | 3 |
| `privileged_access_separation` | 3 |
| `email_phishing_protection` | 3 |
| `remote_access_control` | 3 |
| `incident_reporting_route` | 1 |
| `security_awareness_training` | 1 |

If the PL identifies a strong security-methodology reason to change one of these weights before implementation, STOP that specific decision and return the proposed delta/rationale to Central Architecture rather than silently substituting preferences.

### 11.5 Formula

For applicable controls:

```text
earned_points = Σ(weight × state_factor)
available_points = Σ(weight)
posture_percentage = earned_points / available_points × 100
```

`not_applicable` removes that control's weight from `available_points`.

Missing rows are treated exactly as the existing product treats an unanswered baseline control: `UNKNOWN`.

Do not store the percentage.

Compute it fresh from canonical rows.

### 11.6 Rounding

Render as a simple whole percentage initially.

Use deterministic rounding.

Avoid float drift in tests; `Decimal` or equivalent deterministic arithmetic is preferred.

---

# 12. Security Foundations Completion

## 12.1 Customer-facing title

Use:

> **Security Foundations Completion**

Supporting copy substantially equivalent to:

> Progress towards completing your foundational security and assurance setup.

This number answers:

> “How much of the Foundations work have we completed?”

It does **not** answer:

> “How strong is our security?”

## 12.2 Completion is not weighted

Do not weight completion by security importance.

Each applicable required Foundations item contributes:

```text
complete = 1
incomplete = 0
not applicable = excluded
```

Formula:

```text
completed_applicable_items / total_applicable_items × 100
```

This keeps Completion meaningfully different from Posture.

## 12.3 Initial v1 completion catalogue

M007 should start with a finite, defensible set derived from facts the application already knows mechanically.

Initial v1:

### Baseline controls — 12 items

Each current baseline question is one completion item.

Complete when answer is one of:

```text
yes
partial
no
not_applicable
```

Incomplete when:

```text
unknown
missing
```

A deliberate `no` is a completed assessment answer even though it earns no posture points.

### Organisation profile — 1 item

Complete when the existing deterministic Overview logic considers Organisation setup complete/ready.

Do not invent a second definition if `organisations.overview` already contains the required factual logic.

### Governance roles — 1 item

Complete when all required governance roles are assigned to active people.

### Workplace — 1 item

Complete when at least one active workplace is recorded.

### Assets review — 1 item

Complete when the asset-review workflow has no unreviewed/suggested starter asset remaining.

### Risks review — 1 item

Complete when no AI-suggested draft risk remains awaiting customer review.

Do not require “no risks exist”. Honest risk identification is not failure.

### Information Security Policy — 1 item

Complete when an approved policy exists.

A policy review being due later may create a Needs Attention signal but does not rewrite history.

Initial total when all are applicable:

```text
12 baseline
+ 1 organisation profile
+ 1 governance
+ 1 workplace
+ 1 asset review
+ 1 risk review
+ 1 approved policy
= 18 Foundations items
```

### 12.4 Deliberately excluded from v1 completion denominator

Do not force ongoing/conditional workflows into a fake finite completion score merely to make the metric larger.

Initially exclude:

- Evidence quantity;
- remediation quantity;
- questionnaire/customer-assurance activity;
- Activity history;
- “Security State reviewed” where no canonical reviewed-event exists.

Evidence and remediation remain vital security facts, but their current domain semantics are conditional/ongoing rather than a universally finite checkbox.

The PL must list any recommended future additions in the final improvement report.

### 12.5 Derived truth only

Do not create:

```text
foundation_item.completed = True
```

as an independently editable customer state.

Resolvers derive completion from existing canonical domain records.

This preserves the established M006 doctrine:

> Overview/progress is derived truth, not a second status store.

---

# 13. Home dashboard

Home replaces the old “module overview” as the primary dashboard entry.

For Tier 1–3 the top of Home should initially show exactly two primary metric cards.

Conceptually:

```text
┌──────────────────────────────────┐
│ FOUNDATIONAL SECURITY POSTURE    │
│                                  │
│              72%                 │
│                                  │
│ Based on your recorded           │
│ foundational security state.     │
│ Not an independent assessment.   │
│                                  │
│ View security state →            │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ SECURITY FOUNDATIONS COMPLETION  │
│                                  │
│              61%                 │
│                                  │
│ 11 of 18 Foundations items       │
│ completed.                       │
│                                  │
│ Continue Foundations →           │
└──────────────────────────────────┘
```

Desktop may place cards side-by-side.

Narrow view stacks them.

No gauge/chart/icon is required.

## 13.1 Tier 0 Home

A PAUSED user must not receive the normal product dashboard.

Render a simple paused state instead, substantially equivalent to:

```text
Your Infosecurs subscription is currently paused.

Product areas are unavailable while the subscription is paused.

Account management is handled separately.
```

Top-right account placeholder and logout remain.

Do not expose security metrics to Tier 0 in M007 unless separately authorised later.

---

# 14. Needs attention

Under the two Home metrics, add a simple **Needs attention** section.

This is operational guidance, not a third score.

Only show lines whose count is non-zero.

Initial useful signals may include:

1. important foundational controls not fully implemented;
2. Foundations items incomplete;
3. baseline controls marked `Not sure`;
4. approved policy review overdue.

Recommended wording shape:

```text
3 important security controls are not fully implemented — click here
5 Security Foundations items still need completion — click here
2 security controls are marked Not sure — click here
1 policy review is overdue — click here
```

## 14.1 Link behaviour — Product Authority decision

The whole line must **not** be clickable.

The numeric count should be visually clear.

The explicit words:

> **click here**

at the end are the navigation link.

This is deliberate and must be preserved.

Each link goes directly to the relevant working area.

Examples:

- important controls → Security/Baseline or Security State;
- incomplete Foundations → Foundations workspace;
- Not sure controls → Baseline;
- policy review → Policies.

Where an existing safe filter can be added cheaply, use it.

Do not build a generic filtering framework just for M007.

## 14.2 Important-control count

For the initial posture methodology, “important” may be treated as:

```text
security_weight >= 3
```

and control state:

```text
partial or no
```

Unknown is shown separately as `Not sure`.

Do not treat `not_applicable` as a problem.

---

# 15. Foundations workspace

Create a basic Foundations workspace.

Purpose:

> show the customer what the 30-Day Security Foundations work consists of and what remains.

It may use grouped rows/cards but should remain plain.

At minimum show:

- requirement title;
- completion state;
- relevant area;
- direct action;
- where useful, security importance.

Do not create a second editable completion checklist.

Each displayed state is derived from the same resolver used by the Home completion metric.

The page should be capable of explaining:

```text
14 of 18 complete
4 remaining
```

and give a clear route to each incomplete item.

---

# 16. Sidebar behaviour

## 16.1 Desktop

At normal desktop width:

- sidebar visible;
- left-hand position;
- selected area clearly highlighted;
- parent/child hierarchy understandable;
- main content remains independent.

Approximate width is an implementation detail; do not over-polish.

## 16.2 Narrow viewport

At narrower widths:

- sidebar collapses out of the main layout;
- hamburger appears in the top-left;
- activating it opens the same navigation as a drawer/overlay;
- button uses appropriate `aria-expanded` / `aria-controls`;
- keyboard operation works;
- Escape should close the open menu where practical;
- selecting a link should not leave the drawer obscuring the destination;
- focus must remain usable.

Use minimal vanilla JavaScript.

No JS framework.

## 16.3 Do not duplicate menu DOM across pages

The menu may be rendered once in the shell and responsive CSS/JS changes its presentation.

Do not create separate desktop and mobile menu implementations with different entitlement logic.

---

# 17. User/account area

Top-right shell should contain a deliberately small account region.

Initial content:

- current user display name/identifier;
- active organisation name/context;
- `Account` placeholder;
- Logout.

Account management itself remains external/out of scope.

The placeholder must not pretend that Infosecurs currently manages billing/account lifecycle.

Avoid dead misleading links.

A disabled/clearly-labelled placeholder or simple “Account” destination explaining external ownership is acceptable.

Logout must be real and must perform the session destruction in §8.

---

# 18. Template/component architecture

The current code has a shared `templates/base.html` with hard-coded top navigation.

M007 must replace/refactor this into a deliberately canonical shell architecture.

A valid end-state might be:

```text
templates/
    public_base.html            # auth/public/error where needed
    application_shell.html      # one authenticated dashboard shell
    components/
        sidebar.html
        topbar.html
        messages.html
        metric_card.html
        needs_attention.html
```

Exact filenames are not binding.

The binding rule is:

> application framework code lives once.

Domain templates extend the shell and fill a main content block.

### 18.1 Styling

Shared shell/component styles belong in shared static CSS.

Avoid continuing the pattern of large repeated page-local `<style>` blocks for reusable primitives.

Domain-specific styles may remain local where genuinely domain-specific.

Do not perform a gratuitous whole-product CSS rewrite.

### 18.2 Existing hardening must survive

Preserve:

- systemic unbroken-text wrapping;
- badge wrapping;
- focus visibility;
- skip link;
- responsive behaviour;
- safe escaping;
- 375px no-horizontal-overflow invariant.

---

# 19. Security engineering baseline

M007 must be built using current secure-development principles even where this PID does not enumerate every attack.

Use **OWASP ASVS 5.0** as a verification reference, aiming at relevant Level-2-style controls for this security-sensitive web application.

This is a development/testing reference only.

Do **not** claim Infosecurs is “ASVS certified/compliant” merely because the team used the standard.

Relevant categories include:

- authentication boundary;
- session management;
- access control;
- input validation;
- output encoding/XSS;
- CSRF;
- error handling/logging;
- data protection;
- communications/security configuration;
- files/resources;
- business logic.

## 19.1 Session principles

Required:

- backend/server-side session verification;
- opaque unpredictable session IDs from Django/framework;
- session key rotation on authentication/context privilege change;
- complete invalidation on logout;
- HttpOnly session cookie;
- Secure cookie in production;
- appropriate SameSite;
- no package/user/customer data encoded into the client session identifier;
- no signed-cookie session backend for the Infosecurs context;
- no session identifiers in URLs;
- do not log session IDs.

## 19.2 Access-control principles

Required:

- deny by default;
- server-side entitlement;
- tenant scoping at query/object level;
- no IDOR;
- no client-supplied tier authority;
- direct URL tests;
- method safety;
- authorization on mutations, not just reads.

## 19.3 CSRF

Every state-changing browser request:

- correct HTTP method;
- CSRF protection;
- no unsafe GET mutation.

The dev/test tier selector, if built, must follow the same rule.

## 19.4 XSS / untrusted data

Preserve Django autoescaping.

Do not use `safe`, `mark_safe`, raw HTML injection or DOM `innerHTML` with customer/session/database content without a separately justified/sanitised boundary.

Real-browser XSS regression must cover shell areas that now render:

- user display;
- organisation name;
- database navigation labels (seeded, but still treat output normally);
- Needs Attention text/data;
- existing hostile customer fields.

## 19.5 SQL/database safety

Use Django ORM / parameterised access.

No string-built SQL.

If raw SQL is genuinely unavoidable, PL must explicitly justify and Auditor must inspect parameterisation.

## 19.6 Secrets/config

Preserve existing doctrine:

- no secrets in source;
- no secrets in Git/evidence;
- no session cookie values in evidence;
- no full external auth tokens logged;
- development fixture data synthetic;
- existing LiteLLM secret remains external/read-only.

## 19.7 Error handling

A malformed/expired/missing session must fail safely.

Do not leak:

- stack traces;
- secret values;
- raw database detail;
- filesystem paths;
- session internals.

## 19.8 Logging

Log enough to diagnose:

- invalid session-context schema;
- denied capability;
- unexpected server error.

Do not log:

- session IDs;
- raw cookies;
- secrets;
- unnecessary customer content.

Security denial logs must not themselves disclose foreign object details.

## 19.9 Dependency/security scanning

Preserve existing controls:

- pinned dependencies;
- secret scanning;
- dependency scanning;
- SAST/CodeQL;
- container scanning;
- Trivy final image scan;
- `makemigrations --check`;
- gitleaks.

If the repository's current dependency/security tooling has changed, use the current canonical implementation rather than an obsolete command copied from this PID.

---

# 20. Current Django security assumptions to preserve/re-prove

At PID authoring, the repository uses Django `6.1.1`.

Current settings already include:

```text
SessionMiddleware
AuthenticationMiddleware
CsrfViewMiddleware
XFrameOptionsMiddleware
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE="Lax"
CSRF_COOKIE_SAMESITE="Lax"
production SESSION_COOKIE_SECURE=True
production CSRF_COOKIE_SECURE=True
production SECURE_SSL_REDIRECT=True
```

M007 must not weaken these.

Explicitly set/verify the server-side database session engine as described above.

The existing production proxy/HSTS decision remains a later production-readiness concern.

Do not make an ungoverned proxy/HSTS deployment decision inside M007 merely because security review notices the existing documented gap.

Record it in the final suggestions if still relevant.

---

# 21. Preserve core Infosecurs truth doctrine

M007 is UI/entitlement/metric work.

It must not weaken these product truths:

```text
UNKNOWN != NO
Policy requirement != implemented control
Accepted risk != requirement satisfied
Managed exception != control implemented
Evidence attached != independently verified
Remediation completed != control automatically confirmed
AI output != organisational truth
```

The posture percentage must not collapse these distinctions.

Examples:

- `unknown` scores zero but remains UNKNOWN;
- customer-stated YES may earn posture points because posture is based on the customer's recorded control state, but the UI must not relabel that as independently verified;
- evidence attachment does not add posture points;
- approved policy does not increase the security-posture score;
- completed remediation does not auto-change the control answer;
- AI text cannot alter either metric.

---

# 22. Data migration / seeding rules

Create schema migrations normally.

Initial ProductArea and FoundationRequirement data must be deterministic and reconstructible from Git.

Use data migrations or an equally governed idempotent seed mechanism.

Requirements:

- fresh database produces exact intended rows;
- rerun/idempotency safe where applicable;
- no random IDs used as semantic identifiers;
- stable `code` values;
- no production/customer data embedded in migration;
- rollback behaviour understood/documented;
- no uncontrolled destructive migration.

`makemigrations --check --dry-run` must be clean at closure.

---

# 23. Metric service architecture

Create one read-only service layer for M007 metrics.

Recommended conceptual API:

```text
get_foundational_security_posture(organisation)
get_security_foundations_completion(organisation)
get_foundations_requirement_states(organisation)
get_needs_attention(organisation)
```

Do not calculate the same percentage independently in template context processors, Home view and Foundations view.

One canonical calculation.

Result objects should include enough deterministic detail for testing, e.g.:

```text
percentage
earned/completed
available/total
methodology_version
per-requirement states
```

Templates render.

Templates do not calculate product methodology.

---

# 24. Existing Overview logic — reuse, do not duplicate

At PID authoring, `organisations/overview.py` already has a strong invariant:

> Overview is derived fresh from real rows, never stored as a second status store.

Reuse its deterministic domain knowledge where appropriate.

M007 explicitly supersedes M006's earlier non-goal that prohibited numeric security/completion scores.

This PID now authorises the two named percentages.

That does **not** authorise arbitrary maturity/compliance scoring elsewhere.

Where Overview logic already defines:

- organisation setup ready;
- governance/workplace readiness;
- asset review;
- risk review;
- policy state;

prefer reusing/extracting the same underlying predicates rather than copying subtly different conditions into M007.

If reuse requires a small refactor to extract pure resolver functions, that is authorised.

Do not change the underlying semantics without explicit evidence/reason.

---

# 25. Required tests — package/session matrix

At minimum mechanically prove:

## 25.1 Tier matrix

### PAUSED / 0

Visible:

- Home paused state;
- account placeholder;
- logout.

Not visible and direct access denied:

- Foundations;
- Customer Assurance;
- Security;
- Policies;
- Company;
- all nested routes.

### FOUNDATION / 1

Visible/accessible:

- Home;
- Foundations;
- Security + children;
- Policies;
- Company + children.

Not visible/directly denied:

- Customer Assurance;
- any future/test Tier-3 capability.

### MONTHLY / 2

Visible/accessible:

- all Foundation;
- Customer Assurance.

Must prove inheritance, not duplicated flags.

### PRO / 3

Visible/accessible:

- all Foundation;
- all Monthly;
- any test fixture capability requiring Tier 3 where needed mechanically.

No fake customer-facing Pro menu item is required.

## 25.2 Session tampering

Try representative:

- query tier;
- POST tier;
- fake header;
- extra cookie;
- invalid package code;
- out-of-range tier;
- code/tier mismatch;
- missing schema version;
- unsupported schema version;
- subject mismatch.

Fail closed.

## 25.3 Session lifecycle

Prove:

- session creation;
- ID rotation on auth;
- ID rotation on privilege/context switch;
- logout flush;
- old cookie replay fails;
- new login creates new identifier;
- package context restored only through legitimate issuer.

## 25.4 Tenant + tier combinations

Use at least two organisations and two users.

Prove:

- PRO tenant B cannot access Foundation tenant A merely because tier is higher;
- Monthly cannot access Customer Assurance objects belonging to another tenant;
- Foundation cannot bypass Customer Assurance using a copied own-tenant response URL;
- paused cannot use old previously-authorised object URL.

---

# 26. Required metric tests

## 26.1 Posture

Prove:

- all YES → 100%;
- all NO → 0%;
- all UNKNOWN/missing → 0%;
- PARTIAL earns exactly half weight;
- N/A excluded from denominator;
- mixed weights calculate correctly;
- missing BaselineAnswer is UNKNOWN, not NO;
- evidence presence/absence does not change posture;
- policy approval does not change posture;
- remediation completion does not change posture;
- raw AI output does not change posture;
- deterministic methodology version returned.

## 26.2 Completion

Prove:

- initial untouched organisation produces correct incomplete total;
- every answered baseline question increments completion exactly once;
- UNKNOWN does not count complete;
- NO counts complete;
- PARTIAL counts complete;
- valid N/A counts complete for an assessment question;
- profile resolver;
- governance resolver;
- workplace resolver;
- assets-review resolver;
- risks-review resolver;
- policy-approved resolver;
- no duplicate counting;
- total equals current v1 definition;
- no customer-editable completion flag exists.

## 26.3 Separation between metrics

Construct:

### Scenario A

High completion, weak controls:

```text
Completion high
Posture low
```

Prove possible.

### Scenario B

Strong answered controls but unfinished workflow:

```text
Posture high
Completion lower
```

Prove possible.

This demonstrates the two percentages are not aliases.

---

# 27. Needs Attention tests

Prove:

- zero-count line omitted;
- count is correct;
- row itself is not one giant anchor;
- explicit `click here` is the link;
- link destination is correct;
- important control count does not include N/A;
- `Not sure` count uses UNKNOWN only;
- partial/no remain distinct from unknown;
- overdue-policy count follows canonical policy dates/state;
- hostile/unbroken organisation/customer text cannot force horizontal overflow.

Real-browser verification required.

---

# 28. Required UI/browser acceptance

Fresh real-browser acceptance must run at least:

```text
375px width
768px width
1280px width
```

Prove:

- desktop sidebar visible;
- selected item state clear;
- nested navigation understandable;
- narrow viewport hamburger appears;
- drawer opens/closes;
- keyboard can operate hamburger/navigation;
- focus remains visible;
- no normal-page horizontal overflow;
- Home metric cards stack appropriately;
- Needs Attention links are explicit;
- Tier-0 paused screen clear;
- top-right account/logout area remains usable;
- organisation name with long unbroken hostile token does not break shell;
- XSS payloads remain inert in header/customer content;
- logout from real browser destroys access;
- Back button after logout does not re-authorise protected content.

Do not judge visual polish beyond functional usability.

---

# 29. Existing workflow regression

Because the shell touches nearly every customer page, the Auditor must not limit testing to Home.

Against an entitled session, real-browser smoke must still cover:

- organisation/profile;
- baseline;
- assets;
- risks;
- evidence;
- remediation;
- Security State;
- governance/workplace;
- policy;
- Customer Assurance for Tier 2+;
- activity;
- PDF/download where relevant.

The goal is to prove the shell/entitlement changes did not break the M006 product.

---

# 30. AI regression

M007 is not authorised to change risk/policy/questionnaire AI semantics.

Engineer must mechanically compare relevant AI/domain trees against the accepted baseline.

Regardless, run the existing evaluation harnesses before closure:

- risk fake;
- risk live;
- policy fake;
- policy live;
- questionnaire fake;
- questionnaire live.

All GREEN.

If M007 accidentally changes AI prompt/grounding/decision source:

> STOP — scope breach unless separately authorised.

---

# 31. Backup/recovery regression

M007 adds database methodology/navigation rows and session state.

Prove existing backup/restore still works.

At minimum:

- database backup contains ProductArea/FoundationRequirement rows;
- restore recreates them correctly;
- customer/domain history remains intact;
- evidence checksum remains intact;
- session records are not treated as durable business truth.

It is acceptable for active web sessions to be lost across a restore; they are transient authentication state, not customer assurance records.

Document this explicitly.

---

# 32. Fresh install / reproducibility

From a fresh clone/fresh volumes:

```text
migrate
    ↓
seed governed product-area/requirement metadata
    ↓
create Customer Zero synthetic fixture
    ↓
issue synthetic session context
    ↓
dashboard renders
```

Prove:

- no manual SQL;
- no hidden local file;
- no hand-edited DB row required;
- menu deterministic;
- metrics deterministic.

---

# 33. Release artifact

After product source is accepted:

1. merge correction/build PR;
2. exact merge SHA becomes candidate product SHA;
3. clean checkout at exact SHA;
4. build new SHA-bound image;
5. retain it;
6. OCI revision exact;
7. no source bind;
8. `DEBUG=False`;
9. external secrets remain external;
10. migrations clean;
11. health 200;
12. browser smoke;
13. entitlement smoke;
14. Trivy 0 CRITICAL/HIGH;
15. no session/customer secret baked into image.

Do not overwrite the M006 accepted image tag.

---

# 34. GitHub gates

Preserve the repository's required checks.

At PID authoring these are:

```text
ci/unit
ci/integration
security/secrets
security/dependencies
security/sast
security/container
```

CodeQL must also be GREEN on the relevant PR head.

Do not rename required contexts merely for M007.

PL must confirm the actual current branch-protection/check configuration before closure.

---

# 35. FORGE delivery method

Use bounded work packages.

Recommended sequence:

## M007-WI1 — architecture/data spine

- ProductArea model;
- FoundationRequirement model;
- migrations/seeds;
- package constants;
- session contract/service;
- entitlement service;
- deterministic tests.

## M007-WI2 — application shell

- canonical shell;
- left sidebar;
- dynamic DB navigation;
- top-right account/logout;
- responsive hamburger;
- active-state logic;
- existing template migration.

## M007-WI3 — access enforcement/session hardening

- route/capability guard;
- fixed session fixtures;
- logout invalidation;
- fixation/rotation tests;
- tier matrix;
- tenant+tier probes.

## M007-WI4 — metric methodology/services

- posture;
- completion;
- requirement resolvers;
- Needs Attention derivation;
- deterministic tests.

## M007-WI5 — Home + Foundations workspace

- two metric cards;
- paused Home;
- Needs Attention;
- Foundations list/action links;
- functional responsive UI.

## M007-WI6 — full regression/release

- browser journeys;
- security probes;
- AI evals;
- backup/restore;
- exact-SHA image;
- fresh independent Auditor.

The PL may adjust work-package boundaries if implementation evidence shows a cleaner split.

Do not collapse Product Lead, Engineer and Auditor into one self-approving role.

---

# 36. Engineer rules

Engineer must:

- implement the PID, not reinterpret product strategy;
- raise ambiguity to PL;
- preserve existing truth/security invariants;
- use existing patterns/services where sound;
- avoid unrelated cleanup;
- avoid dependency/framework expansion;
- add tests with implementation;
- keep commits coherent;
- never weaken a test merely to obtain GREEN;
- never bypass tenant/package security for test convenience;
- never create a production test backdoor;
- leave working tree clean.

---

# 37. Product Lead responsibilities

PL must independently:

1. inspect current GitHub baseline;
2. reconcile Engineer diff against PID;
3. review schema/migrations;
4. review session lifecycle;
5. review entitlement centralisation;
6. prove no navigation-only security;
7. inspect metric math manually;
8. reproduce representative tests independently;
9. run full suite;
10. run migrations check;
11. run gitleaks;
12. run fake/live AI evaluations;
13. verify current security checks;
14. build/review exact release artifact;
15. dispatch fresh independent Auditor;
16. reconcile findings;
17. enforce post-audit delta doctrine;
18. land evidence;
19. return closure **and improvement suggestions** to Central Architecture.

Narrative claims without mechanical evidence are insufficient.

---

# 38. Fresh independent Auditor mandate

The Auditor must not merely read the PL report.

The Auditor receives:

- this PID;
- repository/product access;
- exact candidate SHA/image;
- synthetic credentials/session-fixture instructions.

The Auditor must independently challenge:

### Architecture

- one shell, no repeated nav framework;
- DB navigation really drives menu;
- tiers cumulative;
- Pro inherits Monthly/Foundation;
- sidebar/hamburger function.

### Access control

- hidden menu ≠ route access;
- direct URL bypass;
- malformed session;
- tier tampering;
- tenant IDOR;
- paused-account bypass.

### Session security

- fixation;
- logout flush;
- old-cookie replay;
- tier/context switching;
- session context not exposed/logged.

### Metrics

- arithmetic;
- weights;
- N/A;
- UNKNOWN != NO;
- completion != posture;
- no editable score store;
- no evidence/policy/remediation score laundering.

### UI

- Home metrics;
- Needs Attention explicit `click here`;
- desktop/sidebar;
- narrow hamburger;
- keyboard/focus;
- long text;
- XSS;
- major existing workflows.

### Release

- exact SHA;
- image identity;
- no source bind;
- `DEBUG=False`;
- secret boundary;
- Trivy;
- health/browser smoke.

The Auditor should actively try to falsify the build.

---

# 39. Finding severity / closure

Any Critical/High finding:

> RED / STOP.

Any Medium/Low:

- remediate before closure; or
- return to Central Architecture for explicit durable acceptance.

Do not silently accept residual findings.

Any product/runtime source fix after Auditor GREEN invalidates that Auditor verdict and requires a fresh Auditor against the new exact product candidate.

Evidence-only landing after GREEN may preserve the verdict only if mechanical product-tree identity is proven.

---

# 40. Required evidence

Land concise durable evidence, not huge transcripts.

At minimum:

```text
docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md
docs/evidence/M007-SESSION-ENTITLEMENTS.md
docs/evidence/M007-METRICS.md
docs/evidence/M007-BROWSER-ACCEPTANCE.md
docs/evidence/M007-SECURITY-REGRESSION.md
docs/evidence/M007-RELEASE.md
docs/evidence/M007-AUDIT-0001.md
docs/evidence/M007-PL-IMPROVEMENT-SUGGESTIONS.md
```

Exact grouping may vary, but every major gate must be recoverable from GitHub.

---

# 41. Definition of PRODUCT_GREEN for M007

M007 is GREEN only when all of the following are true:

1. M006/Beta 0.1 accepted product behaviour remains intact.
2. Canonical host/root correct.
3. One application shell exists.
4. Domain pages do not duplicate shell/menu/account framework.
5. Desktop left sidebar works.
6. Narrow hamburger/drawer works.
7. Navigation is database-driven.
8. Package tiers 0/1/2/3 exist with cumulative semantics.
9. Monthly mechanically inherits Foundation.
10. Pro mechanically inherits Foundation + Monthly.
11. Tier 0 is safely restricted.
12. Session context is structured/versioned/server-side.
13. Explicit DB-backed Django session engine proven.
14. Missing/malformed session fails closed.
15. Package tier cannot be overridden by client input.
16. Route entitlement uses the same capability truth as navigation.
17. Tenant isolation remains independent and GREEN.
18. Logout completely invalidates session.
19. Old session replay fails.
20. Session fixation/rotation tests GREEN.
21. Fixed PAUSED/FOUNDATION/MONTHLY/PRO test fixtures exist.
22. ProductArea data is governed/reproducible from Git.
23. FoundationRequirement metadata is governed/reproducible from Git.
24. Foundational Security Posture formula is deterministic.
25. Posture preserves UNKNOWN != NO.
26. Posture excludes N/A from denominator.
27. Evidence/policy/remediation/AI cannot inflate posture.
28. Security Foundations Completion is deterministic and unweighted.
29. Completion derives from canonical records, not editable flags.
30. Initial v1 completion catalogue is mechanically correct.
31. Home displays the two authorised metrics.
32. Tier-0 Home displays paused state instead of product metrics.
33. Needs Attention count/link behaviour matches this PID.
34. Foundations workspace is usable.
35. No new compliance/certification claim is introduced.
36. 375/768/1280 browser checks GREEN.
37. Keyboard/focus behaviour GREEN.
38. No normal-page horizontal overflow.
39. XSS regression GREEN.
40. CSRF/method regression GREEN.
41. Cross-tenant regression GREEN.
42. Major existing M001–M006 workflows browser-smoke GREEN.
43. All six AI evals GREEN.
44. Backup/restore regression GREEN.
45. Fresh-clone/fresh-volume reconstruction GREEN.
46. Full test suite GREEN.
47. `makemigrations --check` GREEN.
48. gitleaks GREEN.
49. required GitHub checks GREEN.
50. CodeQL GREEN.
51. exact-SHA immutable release image built.
52. no source bind.
53. `DEBUG=False`.
54. secrets absent from image.
55. Trivy 0 Critical/High.
56. fresh independent Auditor GREEN.
57. no unauthorised post-audit product delta.
58. roadmap/PID/evidence reflect actual state.
59. PL improvement-suggestions report landed.
60. real customer data remains NOT AUTHORISED.
61. production-readiness remains NOT AUTHORISED.
62. PL stops and returns full closure to Central Architecture.

---

# 42. Mandatory PL improvement report

This is an explicit Product Authority requirement.

At the end of M007, **even if everything is GREEN**, the PL must return a structured list of suggestions for how Infosecurs should be improved next.

This is not permission to implement them.

Create:

```text
docs/evidence/M007-PL-IMPROVEMENT-SUGGESTIONS.md
```

and include the same list in the closure report to Central Architecture.

For every suggestion record:

| Field | Required |
|---|---|
| Category | Yes |
| Suggestion | Yes |
| Evidence / observation | Yes |
| Why it would help | Yes |
| Security/product impact | Yes |
| Estimated effort | S / M / L |
| Recommended timing | Now / Next / Later |
| Requires Central Architecture decision | Yes/No |

Categories should include at least:

- Dashboard / UX;
- Entitlements / packaging;
- Session / authentication boundary;
- Security hardening;
- Foundations methodology;
- Metrics/scoring;
- Customer Assurance;
- Data/model architecture;
- Testing/audit;
- Operations/deployment;
- Performance;
- Accessibility.

The PL must distinguish:

### A. Defects

Anything that should have blocked M007 GREEN.

These must be fixed or explicitly accepted before closure.

### B. Improvements

Good future ideas that do not invalidate current correctness.

Do not smuggle new scope into M007 under the label “suggestion”.

The report should explicitly identify:

- what would most improve customer usability;
- what would most reduce future engineering cost;
- what would most improve security;
- what should **not** be built yet.

---

# 43. Explicit non-goals

M007 does not build:

- external signup;
- password reset;
- MFA;
- billing;
- Chargebee;
- subscription collection;
- payment-failure automation;
- production SSO;
- customer role/RBAC expansion;
- XLSX/DOCX/PDF questionnaire ingestion;
- supplier assurance;
- incident-response module;
- awareness-training platform;
- compliance certification;
- ISO 27001 implementation platform;
- Cyber Essentials certification platform;
- customer-facing trend charts;
- scoring history;
- benchmarking against other companies;
- gamification;
- dashboard chart framework;
- icon library;
- production hosting/proxy topology;
- real-customer migration;
- entitlement polling/revocation service to an external account platform.

The architecture should leave room for these where appropriate without prematurely building them.

---

# 44. Stop conditions

STOP and report to Central Architecture if any of the following occurs:

1. current GitHub source materially contradicts this PID's assumptions;
2. implementation would require changing M001–M006 assurance truth semantics;
3. session design requires trusting browser-supplied entitlement;
4. package control cannot be centralised cleanly;
5. metric formula requires inventing customer security facts;
6. an existing canonical state must be duplicated to make scoring work;
7. an AI subsystem must be changed;
8. a security regression is found outside the authorised correction scope;
9. product/runtime source changes after Auditor GREEN;
10. real customer data becomes necessary;
11. production topology must be chosen to proceed.

Do not resolve architectural ambiguity by silently broadening scope.

---

# 45. Security reference basis

M007 should use current primary references as engineering guidance:

1. **OWASP Application Security Verification Standard (ASVS) 5.0**
   - https://owasp.org/projects/asvs/
2. **OWASP Session Management Cheat Sheet**
   - https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
3. **Django 6.1 — How to use sessions**
   - https://docs.djangoproject.com/en/6.1/topics/http/sessions/
4. **Django 6.1 — Security in Django**
   - https://docs.djangoproject.com/en/6.1/topics/security/

Use the current versions available at implementation time if these move.

These are reference standards, not marketing claims.

---

# Appendix A — initial ProductArea seed intent

Illustrative canonical seed intent:

| code | label | parent | min tier | destination |
|---|---|---|---:|---|
| `home` | Home | — | 0 | current organisation Home |
| `foundations` | Foundations | — | 1 | new Foundations workspace |
| `customer_assurance` | Customer Assurance | — | 2 | existing questionnaire workflow |
| `security` | Security | — | 1 | Security State |
| `security_state` | Security State | Security | 1 | existing Security State |
| `baseline` | Baseline | Security | 1 | existing baseline |
| `assets` | Assets | Security | 1 | existing assets |
| `risks` | Risks | Security | 1 | existing risk register |
| `evidence` | Evidence | Security | 1 | existing evidence |
| `remediation` | Remediation | Security | 1 | existing remediation |
| `policies` | Policies | — | 1 | existing policy |
| `company` | Company | — | 1 | existing organisation hub |
| `profile` | Profile | Company | 1 | existing profile |
| `governance` | Governance | Company | 1 | existing governance |
| `workplace` | Workplace | Company | 1 | existing workplace |
| `activity` | Activity | Company | 1 | existing activity |

Do not treat this table as permission to change underlying domain routes unnecessarily.

---

# Appendix B — session fixture examples

Conceptual only:

```json
{
  "schema_version": 1,
  "subject_id": "fixture-user",
  "organisation_id": "fixture-org",
  "package_tier": 0,
  "package_code": "PAUSED",
  "entitlement_version": 1,
  "issued_at": "2026-09-27T00:00:00Z",
  "auth_source": "test_fixture"
}
```

```json
{
  "schema_version": 1,
  "subject_id": "fixture-user",
  "organisation_id": "fixture-org",
  "package_tier": 1,
  "package_code": "FOUNDATION",
  "entitlement_version": 1,
  "issued_at": "2026-09-27T00:00:00Z",
  "auth_source": "test_fixture"
}
```

```json
{
  "schema_version": 1,
  "subject_id": "fixture-user",
  "organisation_id": "fixture-org",
  "package_tier": 2,
  "package_code": "MONTHLY",
  "entitlement_version": 1,
  "issued_at": "2026-09-27T00:00:00Z",
  "auth_source": "test_fixture"
}
```

```json
{
  "schema_version": 1,
  "subject_id": "fixture-user",
  "organisation_id": "fixture-org",
  "package_tier": 3,
  "package_code": "PRO",
  "entitlement_version": 1,
  "issued_at": "2026-09-27T00:00:00Z",
  "auth_source": "test_fixture"
}
```

These arrays are server-side session objects.

They are never a client-authoritative JSON token.

---

# Appendix C — product interpretation examples

## C.1 High Completion, weak Posture

Example:

```text
All 18 Foundations items completed.
Several important controls deliberately answered NO/PARTIAL.

Security Foundations Completion: 100%
Foundational Security Posture: materially below 100%
```

Correct.

The customer has completed the assessment/setup work and discovered weaknesses.

## C.2 Strong Posture, incomplete Foundations

Example:

```text
Most answered baseline controls are YES.
Governance/workplace/policy work not completed.

Foundational Security Posture: high
Security Foundations Completion: lower
```

Correct.

The known controls appear strong, but Foundations work remains.

## C.3 Unknown

Example:

```text
MFA privileged accounts = Not sure
```

Correct:

```text
Posture credit = 0
Completion credit for that baseline item = 0
Stored/displayed semantic state = UNKNOWN / Not sure
```

Incorrect:

```text
answer = NO
```

## C.4 Evidence

Example:

```text
MFA privileged accounts = YES
zero evidence attached
```

Posture may earn the YES state points because the metric is explicitly a recorded foundational posture.

The UI must still not say:

```text
independently verified
certified
evidence-backed
```

unless separate canonical state supports those claims.

Evidence is an assurance/confidence dimension, not a hidden posture bonus.

---

# Final instruction to BAGMAN / FORGE

Build M007 as a bounded product module.

Protect the accepted Infosecurs truth model.

Prefer small, explicit, testable architecture over framework cleverness.

The goal is not to make the dashboard beautiful yet.

The goal is to make the dashboard **structurally right**:

- one shell;
- one entitlement truth;
- one session contract;
- cumulative packages;
- server-side enforcement;
- deterministic metrics;
- direct next actions;
- strong security;
- easy future expansion.

After a fresh independent Auditor returns GREEN, the Product Lead must return the complete closure evidence **plus the structured improvement-suggestions report** to Central Architecture and then STOP.

Do not begin the next module without new Product Authority.
