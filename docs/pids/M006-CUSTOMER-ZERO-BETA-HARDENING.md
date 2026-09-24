# M006 — Customer-Zero Beta Hardening

**Status:** AUTHORISED FOR BUILD  
**Parent:** `/PID.md`  
**Depends on:** M001–M005 PRODUCT_GREEN + M005→M006 Host Relocation Gate GREEN  
**Authoritative baseline main SHA at authorisation:** `bc47c2f167406b62aa3a0e59724357aa0478ef5b`  
**Accepted M005 product identity:** `dee18ef214bf892a41f2d52f2e33650e479e69cc`  
**Presentation target:** `PRODUCT_USABLE`  
**Required delivery framework:** FORGE  
**Canonical development host:** `dell-debian`  
**Canonical project root:** `/srv/infosecurs`  
**Project truth:** GitHub  
**Data restriction:** synthetic / deliberately Customer-Zero-safe data only  
**Real customer data:** NOT AUTHORISED by M006

---

## 1. Purpose

M006 closes Infosecurs Beta 0.1.

M001–M005 already provide the product's core security-assurance spine:

```text
Organisation/Profile
        ↓
Baseline + Assets
        ↓
Risks
        ↓
Evidence + Remediation
        ↓
Current Security State
        ↓
Governance + Workplace
        ↓
Information Security Policy
        ↓
Questionnaire Assurance
```

M006 does **not** add another security domain.

Its job is to turn those individually proven modules into one coherent, resilient,
secure and reproducible Customer-Zero Beta.

> **Harden the product we have. Do not expand the product we have.**

---

## 2. Beta 0.1 outcome

At M006 closure, a fresh Customer-Zero user must be able to complete the intended journey without understanding Infosecurs' internal module architecture:

1. sign in;
2. understand where they are and what to do next;
3. establish organisation/profile/workplace/governance context;
4. complete the baseline;
5. review assets/protection state;
6. review risks;
7. add evidence;
8. create/track remediation;
9. understand current security state;
10. generate/review/approve a concise Information Security Policy;
11. paste a questionnaire question;
12. receive a grounded answer;
13. understand any GAP/CONFIRM outcome;
14. inspect why the answer was produced;
15. inspect the organisation's activity/history.

---

## 3. Non-goals

M006 does not build:

- new security-assurance domains;
- supplier management;
- incident response;
- awareness training/phishing;
- uSecure/Huntress/Chargebee integration;
- questionnaire XLSX/DOCX/PDF ingestion;
- OCR/portal automation;
- vector/RAG platform;
- ISO/GDPR platform;
- multi-seat/RBAC expansion;
- enterprise SSO/SCIM;
- mobile app;
- microservices;
- background-job platform;
- production hosting topology;
- production customer-data migration;
- autonomous/cross-tenant learning;
- a new Exception subsystem.

---

## 4. Host preflight

Every M006 implementation start must prove:

```text
hostname == dell-debian
PROJECT_ROOT == /srv/infosecurs
```

Trinity is shared LiteLLM/infrastructure only.

A host mismatch is a delivery STOP condition.

---

## 5. UX architecture

M006 must create coherent organisation-scoped primary navigation equivalent to:

```text
Overview
Security
Evidence
Policy
Questionnaires
Activity
Organisation
```

Suggested destinations:

- **Overview** — assurance journey/status;
- **Security** — Current Security State with clear links to Baseline, Assets and Risks;
- **Evidence** — Evidence + Remediation Actions;
- **Policy** — policy/version workflow;
- **Questionnaires** — M005 Questionnaire Assurance;
- **Activity** — existing history;
- **Organisation** — Profile, Governance and Workplace.

The exact UI may use accessible links/tabs. Do not build a configurable navigation framework.

Every organisation-scoped screen must clearly show the active organisation.

Do not expose internal UUIDs as the primary customer UX.

---

## 6. Overview / journey page

Create a lightweight organisation Overview page derived entirely from existing domain state.

Suggested sections:

```text
Organisation setup
Security baseline
Assets
Risks
Evidence
Remediation
Security state
Governance / workplace
Policy
Questionnaire assurance
```

Show only useful deterministic states such as:

- `Not started`
- `Needs attention`
- `In progress`
- `Ready`

and counts/one clear next action where useful.

Do not create:

- a maturity percentage;
- numeric security grades;
- compliance scoring;
- an independent editable overview status store.

---

## 7. Cross-module workflow polish

Remove dead ends across the full journey.

At minimum:

- obvious next/back routes on major pages;
- security-state items link to relevant evidence/remediation;
- GAP/CONFIRM questionnaire answers link back to underlying controls/actions;
- risk/evidence/action terminology is consistent;
- policy statuses are obvious;
- questionnaire history is obvious;
- empty states explain the next action;
- messages are customer-facing rather than implementation-centric.

Link to the owning workflow rather than duplicating actions.

---

## 8. Terminology consistency

Preserve these distinctions everywhere:

```text
Policy requirement       != implemented control
Supporting evidence      != independent verification
Managed exception        != compliance
Accepted risk            != requirement satisfied
Completed remediation    != automatically confirmed control
Unknown                  != No
```

ADR-0003 remains binding.

---

## 9. Accessibility / responsive usability

Target remains WCAG 2.2 AA.

Materially test and harden:

- keyboard-only navigation;
- visible focus;
- skip-link behaviour;
- semantic headings;
- labelled forms;
- validation/error messages;
- status not conveyed by colour alone;
- table/list readability;
- small/medium viewport usability;
- no normal-page horizontal overflow.

The fresh real-browser Auditor must exercise keyboard navigation through the primary flow.

---

## 10. Error handling

Provide safe customer-facing 400/403/404/500 behaviour.

No stack trace, secret, SQL or filesystem path may leak in production-like mode.

AI outages must not break non-AI product areas. AI actions must fail clearly and remain retryable without accepting malformed partial output.

---

## 11. Security hardening

M006 performs a Beta-wide adversarial regression.

### Authentication / tenant isolation
Maintain an explicit route matrix proving every organisation-scoped customer route:
- requires auth;
- scopes to the authenticated organisation;
- does not leak cross-tenant object existence;
- rejects cross-tenant GET/POST manipulation.

### CSRF / methods
Every mutation must use an appropriate method and require CSRF.

### XSS / untrusted text
Exercise hostile strings through representative:
- organisation/person/workplace names;
- evidence titles/descriptions;
- remediation text;
- policy edits;
- questionnaire questions/source labels/edited answers.

### Uploads
Re-prove M003 MIME/signature/size/path/private-storage/tenant-download boundaries.

### Prompt injection
Re-prove containment across risk, policy and questionnaire AI surfaces.

### Secrets
No secret values in Git, evidence docs, unnecessary prompts, logs, errors or rendered HTML.

---

## 12. Production-like configuration check

Exercise:

```text
DJANGO_ENV=production
DEBUG=False
```

with synthetic configuration.

Prove:
- secure session cookie configuration;
- secure CSRF cookie configuration;
- HTTPS redirect behaviour under current settings;
- ALLOWED_HOSTS enforcement;
- CSRF trusted-origin behaviour;
- no debug error disclosure.

Run Django deployment checks.

Warnings that depend on a real deployment topology must be explicitly documented, not hidden.

M006 does not authorise public production deployment.

---

## 13. Health / operations

Keep `/healthz/` deliberately small.

Prove:
- healthy DB → 200;
- unavailable DB → 503;
- no sensitive details leak;
- endpoint remains unauthenticated.

Add an operator runbook covering:
- start/stop/status;
- migrations;
- health;
- logs;
- restart;
- AI gateway smoke;
- backup;
- restore.

Do not build a monitoring platform.

---

## 14. Backup / restore

Beta must have a tested recovery path for:

1. PostgreSQL data;
2. private evidence storage.

Use established PostgreSQL/Docker/archive tooling.

A backup should include:
- logical DB dump;
- evidence archive;
- manifest with source Git SHA, UTC time, filenames/checksums.

No credentials in manifests.

For Beta, quiescing application writes during backup is acceptable.

Restore into a fresh disposable stack and prove:
- app starts;
- migrations/schema compatible;
- representative organisation/domain records restored;
- evidence bytes/checksum identical;
- policy history intact;
- accepted questionnaire history intact;
- health 200.

Synthetic data only.

---

## 15. Release artifact

Produce an immutable Beta application image bound to an accepted Git SHA.

Normal dev Compose may retain a source bind.

Release-candidate proof must run the image **without a source bind**.

Record:
- exact source SHA;
- SHA-bound image tag;
- image ID/digest;
- clean-checkout build;
- pinned dependency/base-image controls;
- Trivy GREEN;
- migrations/health/browser smoke against the image.

Do not add Kubernetes/registry infrastructure merely for this gate.

Do not introduce a new production web-server architecture solely for M006 unless a real deployment requirement proves it necessary.

---

## 16. Fresh Customer-Zero reproducibility

Prove:

```text
fresh volumes
    ↓
migrate
    ↓
Customer Zero bootstrap
    ↓
end-to-end journey
```

No real customer data.

---

## 17. AI regression at Beta release

On the exact release candidate run deterministic fake evaluation for:

- M002 risk;
- M004 policy;
- M005 questionnaire.

All GREEN.

Default closure also runs one final live Beta regression against real `trinity-core` using existing corpora/harnesses:

- risk GREEN;
- policy GREEN;
- questionnaire GREEN;
- prompt-injection cases GREEN;
- direct review of materially changed/flagged outputs.

A reduced live gate is allowed only if exact AI-subsystem tree identity is mechanically proven and Central Architecture explicitly accepts it.

---

## 18. End-to-end real-browser acceptance

Fresh FORGE Auditor must drive, on fresh synthetic data:

1. prove host = dell-debian and exact SHA;
2. sign in;
3. create/bootstrap Customer Zero;
4. complete profile/workplace/governance;
5. establish representative yes/no/partial/unknown/N/A baseline;
6. review assets/protection;
7. generate/review risks;
8. create/link evidence;
9. create remediation;
10. inspect Current Security State;
11. generate policy;
12. prove policy doesn't turn partial/unknown into completed implementation;
13. edit/approve/download PDF;
14. verify immutable policy history;
15. submit SUPPORTED/GAP/CONFIRM/NOT_APPLICABLE questionnaire cases;
16. verify `Why this answer?`;
17. edit/accept response and prove history;
18. prove policy cannot launder an implementation GAP;
19. navigate the whole journey using product navigation, not crafted URLs;
20. verify Overview states/next actions update;
21. inspect Activity;
22. verify empty/error states;
23. keyboard-navigate primary flow;
24. test smaller viewport;
25. verify zero unexplained browser/page errors;
26. cross-tenant probes;
27. CSRF negative mutation;
28. hostile XSS strings remain harmless;
29. prompt injection remains contained;
30. private evidence is inaccessible unauthenticated/cross-tenant;
31. DB-down health 503 then recovery to 200;
32. execute backup;
33. restore into fresh stack and verify representative data/evidence;
34. run SHA-bound image without source bind;
35. browser-smoke immutable image.

Every major check requires non-vacuity.

---

## 19. Additional adversarial Beta challenge

After normal Auditor GREEN, run one fresh zero-context adversarial challenge against the exact release candidate, concentrating on:

- tenant isolation;
- unsupported security claims;
- policy vs implementation;
- evidence semantics;
- managed exceptions;
- prompt injection;
- XSS/input handling;
- immutable history;
- backup/restore;
- release image/source identity;
- confusing/dead-end UX.

Critical/High product findings block closure.

Medium/Low findings require remediation or explicit durable Central Architecture acceptance.

---

## 20. Logging / audit

Do not build an observability platform.

Operational logs must be sufficient to diagnose:
- startup/config failure;
- DB failure;
- AI gateway failure;
- unexpected server error.

Logs must not contain secrets or unnecessary customer content.

Domain Activity remains the customer-visible business history.

---

## 21. Release documentation

Land/update at minimum:

```text
docs/pids/M006-CUSTOMER-ZERO-BETA-HARDENING.md
docs/runbooks/BETA-OPERATIONS.md
docs/runbooks/BACKUP-RESTORE.md
docs/evidence/M006-AUDIT-....md
docs/evidence/M006-LIVE-EVALUATION.md
docs/evidence/M006-BACKUP-RESTORE.md
docs/evidence/M006-RELEASE.md
```

Update `docs/ROADMAP.md` to actual state.

No huge agent transcripts.

---

## 22. Mechanical tests

Add/extend deterministic tests for:

- navigation/active organisation;
- Overview derived state/no independent state;
- tenant scoping;
- CSRF/method safety;
- hostile HTML/script escaping;
- safe error pages;
- production-like cookie/settings behaviour;
- upload regression;
- health 200/503;
- AI outage/malformed-output fail-closed paths;
- backup manifest/checksums;
- disposable restore;
- release image/source identity.

Full existing suite remains mandatory.

---

## 23. GitHub gates

Existing merge-blocking checks remain exactly:

```text
ci/unit
ci/integration
security/secrets
security/dependencies
security/sast
security/container
```

Do not rename them during M006 without separately authorised governance change.

---

## 24. Post-audit delta

Apply `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md` mechanically.

After Auditor GREEN:
- evidence-only delta requires product-tree identity proof;
- CI/control-plane delta requires affected checks rerun;
- **any product/runtime source delta requires a fresh Auditor**.

Same rule applies after adversarial challenge fixes.

---

## 25. Real customer data remains gated

M006 PRODUCT_GREEN means:

> Infosecurs Beta 0.1 is ready for Customer-Zero/synthetic Beta use.

It does **not** authorise unrestricted real-customer production data.

A later production-readiness gate must address the actual chosen deployment, including as relevant:
- public HTTPS/proxy topology;
- MFA expectations;
- account recovery;
- support/break-glass;
- scheduled backup/retention;
- monitoring/alerting;
- production secrets lifecycle;
- privacy/data handling;
- customer support/incident process.

---

## 26. Definition of PRODUCT_GREEN / Beta 0.1 GREEN

M006 is GREEN only when:

1. M001–M005 remain PRODUCT_GREEN.
2. Host relocation remains GREEN.
3. M006 runs from `dell-debian:/srv/infosecurs`.
4. No unauthorised new product domain is introduced.
5. Product navigation makes the end-to-end journey understandable.
6. Overview is derived truth, not a second store.
7. Full journey works without crafted URLs.
8. ADR-0003 terminology is consistent.
9. Keyboard/responsive usability is proven.
10. Error handling is safe/useful.
11. Cross-tenant regression across M001–M005 is GREEN.
12. CSRF/method safety is GREEN.
13. XSS/untrusted-text regression is GREEN.
14. Private upload/security regression is GREEN.
15. Prompt-injection regression across AI surfaces is GREEN.
16. Production-like config behaviour is exercised/documented.
17. `/healthz/` 200/503 is proven.
18. Operator runbook exists and works.
19. PostgreSQL + evidence backup is documented/tested.
20. Fresh-stack restore is GREEN.
21. Restored evidence checksum is proven.
22. Fresh Customer Zero is reproducible from GitHub + external config.
23. SHA-bound Beta image is built from clean checkout.
24. Release image runs without source bind.
25. Release image security scan is GREEN.
26. Release image browser smoke is GREEN.
27. M002 deterministic AI eval GREEN.
28. M004 deterministic AI eval GREEN.
29. M005 deterministic AI eval GREEN.
30. Final live AI Beta regression GREEN, or explicitly approved bounded alternative.
31. Fresh FORGE Auditor full Beta scenario GREEN.
32. Fresh adversarial Beta challenge has no unresolved Critical/High defect.
33. No unresolved Critical/High security finding exists without explicit Central Architecture acceptance.
34. All six required GitHub checks GREEN on closing head.
35. Post-audit/post-challenge delta doctrine obeyed.
36. Release evidence binds source SHA to image identity.
37. Fresh clone reconstructs accepted Beta environment.
38. GitHub contains sufficient closure/recovery/release evidence.
39. Roadmap reflects actual closure.
40. Real customer data remains explicitly NOT AUTHORISED.
41. GUNNAR stops and returns complete Beta 0.1 closure to Central Architecture.

Stop after Beta 0.1 GREEN.

Do not start production-readiness work or post-Beta feature expansion without new Central Architecture authority.
