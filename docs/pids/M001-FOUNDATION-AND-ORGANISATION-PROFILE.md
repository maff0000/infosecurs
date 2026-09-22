# M001 — Foundation & Organisation Profile

**Status:** AUTHORISED FOR BUILD  
**Parent:** `/PID.md`  
**Presentation target:** `PRODUCT_USABLE`  
**Required delivery framework:** FORGE  
**Project root:** `/srv/infosecurs`

## 1. Purpose

Create the minimum executable Infosecurs product foundation and the first real
customer-domain capability: a user can establish and later revisit the
security-relevant profile of an organisation.

M001 must leave a clean foundation for M002 risk generation without building
M002 in advance.

## 2. User outcome

A Customer Zero user can:

1. open Infosecurs locally;
2. authenticate using the approved Beta development mechanism;
3. create/select a synthetic organisation;
4. complete a concise organisation profile;
5. save it;
6. reload/reopen it;
7. see the same confirmed data;
8. edit and save it again;
9. clearly distinguish confirmed facts from absent/unknown values.

The UI must feel like a real product, not Django Admin.

## 3. Organisation profile — initial facts

### Identity
- legal/trading name;
- short description;
- approximate staff count.

### Working model
- office / remote / hybrid;
- company-managed endpoints / BYOD / both.

### Technology
- Microsoft 365 / Google Workspace / other;
- primary cloud provider if applicable;
- whether organisation develops/hosts its own software/service.

### Data
- handles personal data;
- handles customer confidential/sensitive business data;
- handles payment-card data directly;
- handles special-category/highly sensitive personal data.

### Assurance context
- customers send security questionnaires;
- Cyber Essentials status;
- ISO 27001 certification status;
- immediate commercial/security driver.

Use explicit unknown/not-confirmed semantics where appropriate.

## 4. Domain concepts

### Organisation
Stable tenant identity.

### OrganisationMembership
Associates authenticated user with organisation.

M001 may use one meaningful role if the model leaves room for future roles
without speculative permission machinery.

### OrganisationProfile
Current confirmed organisation facts.

Do not store the whole profile as an untyped generic JSON blob.

### Audit event
Minimal durable record of profile created/updated:
- organisation;
- action;
- actor;
- timestamp.

Do not build the final evidence/provenance system in M001.

## 5. Tenant isolation

Automated tests must use at least two synthetic organisations.

Prove:
- A member can read/update A;
- A cannot read/update B;
- URL/form identifier manipulation cannot cross the tenant boundary.

Cross-tenant access is release-blocking.

## 6. Runtime scaffold

M001 establishes only what it needs:

- Django project;
- PostgreSQL;
- Docker development runtime;
- migrations;
- health/readiness proof;
- configuration loading;
- tests;
- baseline GitHub CI/security;
- product UI shell/navigation.

Do not create empty future modules.

## 7. Authentication

Use Django built-in authentication/session capability for Beta development.

Requirements:
- no default credentials committed;
- test users only via fixtures/helpers;
- safe local Customer Zero user creation;
- unauthenticated users cannot access organisation profile state.

Production MFA/external identity is outside M001.

## 8. UI

Provide:
- product header/name;
- clear current organisation context;
- Organisation/Profile navigation;
- grouped readable sections;
- help text;
- obvious Save/Continue action;
- success/error states;
- responsive ordinary desktop/tablet behaviour;
- accessible labels/keyboard operation.

Do not expose Django Admin as product UI.

## 9. Validation

Examples:
- staff count cannot be negative;
- enums reject unsupported values;
- required organisation identity cannot silently save empty;
- unknown/not-confirmed is deliberate, not ambiguous empty text.

## 10. Security

- keep CSRF enabled;
- no secrets in Git/logs;
- no raw SQL unless justified;
- no intentionally unscoped tenant query;
- no secret config in error pages;
- dependencies pinned;
- GitHub security checks per evidence contract.

## 11. Configuration

Externalise at minimum:
- database connection;
- Django secret key;
- debug/environment mode;
- host/origin configuration as required.

Provide safe example config with no real secret.

Missing required config should fail loudly.

## 12. Mechanical tests

### Domain
- profile validation;
- create/update;
- unknown semantics.

### Authentication
- unauthenticated access denied.

### Tenant isolation
- same-tenant positive;
- cross-tenant read negative;
- cross-tenant write negative.

### Persistence
- save/reload preserves data.

### HTTP/UI
- form renders;
- validation visible;
- save works;
- reload persists.

### Bootstrap
- clean database migrates successfully.

## 13. Browser acceptance

FORGE Auditor must drive the real application:

1. exact audited commit;
2. sign in as synthetic Customer Zero;
3. open assigned organisation;
4. open Organisation Profile;
5. complete representative fields;
6. save;
7. verify visible confirmation;
8. reload/reopen;
9. verify values persist;
10. change one meaningful value;
11. save/reload and verify;
12. submit at least one invalid value and verify visible validation;
13. verify another synthetic tenant cannot be reached by manipulated ID/navigation;
14. confirm no unexplained browser console errors.

Record exact SHA.

## 14. Required GitHub evidence

```text
ci/unit
ci/integration
security/secrets
security/dependencies
security/sast
security/container
forge/audit
```

No AI behavioural gate is required in M001.

## 15. Non-goals

Do not build:
- AI risk generation;
- risk register;
- policy generation;
- evidence repository;
- questionnaire answering;
- suppliers;
- incidents;
- billing;
- Huntress/uSecure;
- production SSO/MFA;
- Redis/Celery;
- generic REST API;
- arbitrary document upload.

## 16. GREEN

M001 is PRODUCT_GREEN only when:

1. declared behaviour exists;
2. clean bootstrap/migrations work;
3. tenant isolation tests pass;
4. required GitHub checks are GREEN on the exact audited head;
5. FORGE Auditor completes browser acceptance against that exact commit;
6. no blocking finding remains;
7. closure identifies module PID, PR and accepted SHA;
8. merged `main` reproduces the accepted result.

GUNNAR must verify GitHub before treating M001 as complete.
