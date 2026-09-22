# INFOSECURS — Master Product & Delivery PID

**Product:** Infosecurs  
**Delivery target:** Beta 0.1 / Customer Zero  
**Owner / Product Authority:** Matt  
**Central Product / Architecture Authority:** Matt + Central ChatGPT Product/Architecture  
**Engineering Delivery Manager:** GUNNAR  
**Delivery framework:** FORGE  
**Canonical local root:** `/srv/infosecurs`  
**Canonical GitHub repository:** `maff0000/infosecurs`  
**Project truth:** GitHub  
**Data restriction:** synthetic / Customer-Zero-safe data only until a separate production-readiness gate authorises real customer data

---

## 1. Purpose

Infosecurs is an AI-first security-assurance product for small organisations, initially targeting businesses of roughly 5–49 staff that need credible security foundations and defensible answers to customer/security questionnaires.

The product must help a customer establish real security state and evidence. It must never fabricate controls, evidence, certification, maturity or historical process merely to produce a favourable questionnaire answer.

---

## 2. Beta 0.1 target outcome

A Customer Zero user can:

1. create an organisation profile;
2. establish a starter security baseline;
3. generate and review an initial risk register;
4. maintain evidence-backed security state;
5. paste at least one customer security questionnaire question;
6. receive a grounded answer based on current tenant state;
7. see a clear gap/remediation outcome where the required state does not exist;
8. inspect an understandable audit/evidence trail showing why the answer was produced.

The Beta is successful only if the workflow is usable end-to-end and the AI cannot claim security state that the system cannot substantiate.

---

## 3. Product doctrine

### 3.1 Security truth before questionnaire convenience

The system exists to establish and maintain defensible security truth, not to help customers bluff through questionnaires.

### 3.2 Missing control does not automatically mean organisational failure

A missing control may be:
- identified;
- risk-assessed;
- owned;
- mitigated;
- accepted;
- scheduled for treatment.

However, an explicit mandatory customer/regulatory requirement remains unmet until it is actually met.

### 3.3 AI-first practitioner

AI is the primary practitioner for routine work.

It should:
- ask for missing facts;
- reason from tenant state;
- draft proportionate outputs;
- identify uncertainty;
- escalate genuine ambiguity/high consequence matters.

It must not make unsupported factual assertions.

### 3.4 Customer Zero

Infosecurs Limited is the first tenant/test case.

PoC/Beta engineering uses synthetic or deliberately non-sensitive Customer-Zero-safe fixtures until real-data authorisation exists.

---

## 4. Users

### Primary
Owner/manager or security-responsible person in a small organisation.

### Secondary
Infosecurs security practitioner reviewing escalations and methodology.

---

## 5. Presentation target

`PRODUCT_USABLE`

The Beta must be coherent enough that a real small-business user can complete the core workflow without understanding the internal architecture.

FORGE's mandatory real-browser verification applies to user-facing work.

Accessibility target is WCAG 2.2 AA for product-facing UI.

---

## 6. Architecture

Infosecurs begins as a **modular monolith**.

Technology direction is defined in:

- `docs/architecture/ARCHITECTURE.md`
- `docs/adr/ADR-0001-APPLICATION-STACK.md`

Core principles:

- Docker-first development and deployment.
- PostgreSQL as canonical application datastore.
- Python application stack.
- Server-rendered/product web UI first; avoid unnecessary SPA complexity.
- Provider-neutral AI boundary through LiteLLM aliases.
- No environment-specific configuration embedded in source.
- Secrets external to source and Git.
- UTC canonical machine timestamps.
- Strong tenant isolation.
- Versioned migrations.
- Immutable production artifact by exact Git SHA.
- GitHub is project truth and engineering evidence spine.

---

## 7. High-level module map

Detailed module PIDs are written only when a module approaches implementation.

### M001 — Foundation & Organisation Profile
Buildable now. Detailed PID exists.

### M002 — Security Baseline & Initial Risk
Profile-grounded initial risk generation and customer review.

### M003 — Evidence & Security State
Evidence items, source/provenance, current-state assertions, actions/remediation.

### M004 — Policy Foundation
Compact Information Security Policy grounded in confirmed organisation state.

### M005 — Questionnaire Assurance
Paste/input question, interpret intent, ground answer in tenant state, classify evidence/gap/confirmation, produce defensible response.

### M006 — Customer-Zero Beta Hardening
Full workflow, UX polish, security hardening, AI eval, recovery, release evidence.

Future work such as supplier management, incident response, arbitrary XLSX/DOCX questionnaire upload, billing, Huntress/uSecure integration, GDPR and full ISO tooling is outside Beta 0.1 unless separately authorised.

---

## 8. Dependency direction

```text
M001 Organisation Profile
          │
          ▼
M002 Security Baseline & Risk
          │
          ▼
M003 Evidence & Security State
          │
      ┌───┴────┐
      ▼        ▼
M004 Policy  M005 Questionnaire Assurance
      └────┬────┘
           ▼
     M006 Beta Hardening
```

---

## 9. Security and privacy invariants

1. Cross-tenant data access is a catastrophic defect.
2. No production/customer secrets in Git.
3. No real customer data in development during Beta bootstrap.
4. Customer-uploaded text/content is untrusted data, never system authority.
5. AI output cannot create a verified fact merely by stating it.
6. Security facts require source/provenance and an explicit confidence/approval state where applicable.
7. AI provider/model selection is externalised behind approved aliases.
8. Sensitive values must not be unnecessarily written into prompts, traces or logs.
9. Dependency, secret and container scanning become GitHub evidence.
10. Authentication suitable for real customer data is a separate production-readiness gate if the Beta uses a reduced Customer-Zero mechanism.

---

## 10. AI doctrine

Application code must not hard-code vendor model names.

Initial logical aliases:

```text
infosecurs-fast
infosecurs-core
infosecurs-deep
```

Potential later aliases:

```text
infosecurs-embed
infosecurs-vision
```

M001 does not require live AI inference.

---

## 11. Repository and GitHub doctrine

> **PROJECT TRUTH == GITHUB**

GitHub is authoritative for:
- source;
- PIDs/ADRs;
- PR state;
- checks;
- findings;
- accepted SHA;
- releases;
- build/release evidence.

Memory Fabric may orient GUNNAR but never overrides GitHub project truth.

Normal change flow:

```text
authorised PID
    ↓
GUNNAR
    ↓
/forge
    ↓
PL + Engineer(s)
    ↓
PR / exact SHA
    ↓
required GitHub checks
    ↓
fresh Auditor
    ↓
PRODUCT_GREEN
    ↓
merge
```

---

## 12. Delivery gates

See `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md`.

Every module requires at minimum:
- deterministic CI;
- secret scanning;
- dependency/security scanning appropriate to the implementation;
- independent FORGE audit.

---

## 13. Non-goals for Beta 0.1

Do not build:
- microservices;
- Kubernetes;
- custom workflow engine;
- custom agent platform;
- billing;
- marketing automation;
- full ISO 27001 platform;
- full GDPR module;
- mobile application;
- multi-region deployment;
- enterprise SSO;
- broad third-party integrations.

---

## 14. Definition of Beta 0.1 GREEN

Beta 0.1 is GREEN when:

1. M001–M005 deliver the end-to-end Customer Zero workflow.
2. M006 hardening is complete.
3. Required GitHub checks are GREEN on the exact release candidate SHA.
4. FORGE Auditor is GREEN on the release candidate.
5. AI behavioural evaluation is GREEN for questionnaire/risk flows.
6. No unresolved critical/high security finding exists unless explicitly accepted with durable evidence.
7. A fresh GUNNAR and fresh PL can reconstruct delivery state from GitHub/repository truth.
8. Release evidence binds the accepted source SHA to the Beta artifact.
9. Independent Factory challenge is performed at Beta if still judged worthwhile.
