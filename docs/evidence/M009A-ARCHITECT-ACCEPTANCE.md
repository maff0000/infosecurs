# M009A — Architect Acceptance

**Architect:** Central Architecture / Project Architect
**Acceptance date:** 2026-10-13
**PR:** #102
**Canonical base:** `93acc86405597641c46b050dd603ab335ebb60d1`
**Independently audited implementation SHA:** `dedba3b18b5fb51498da63f316fb6c2b83cfa59f`
**Candidate head before Architect-governance delta:** `fe2fad861036f990a8c1989974a793bd06ad14de`
**Decision:** **ACCEPTED FOR MERGE**

## Outcome

M009A establishes the secure artifact-ingestion foundation for Customer Assurance.

A Monthly+ customer can now upload a bounded XLSX questionnaire through the real INFOSECURS Customer Assurance surface.

The application:

- preserves the original accepted artifact immutably;
- performs bounded streaming upload enforcement;
- performs fail-closed OOXML structural validation;
- rejects hostile/malformed packages;
- rejects macros and external relationships;
- hardens XML parsing;
- performs real internal malware scanning;
- distinguishes deterministic rejection from retryable security infrastructure failure;
- extracts deterministic tabular questionnaire questions;
- preserves source and future answer-cell provenance;
- creates explicit auditable dispositions rather than silently dropping ambiguous content;
- maintains tenant isolation;
- exposes a safe responsive upload/status experience;
- persists questionnaire artifacts across container recreation;
- includes questionnaire artifacts in backup/restore;
- reconciles Customer Zero reset;
- invokes no AI.

## Truth architecture

M005 remains the sole questionnaire truth engine.

M009A does not generate answers.

M009A does not interpret questions through AI.

M009A does not alter:

- `QuestionnaireQuestion` truth semantics;
- `QuestionnaireResponse` truth semantics;
- grounding;
- outcome derivation;
- drafting;
- accepted-response history.

The new ingestion layer prepares trusted, provenance-bearing candidate questions for later M009 increments.

## Security acceptance

Accepted ClamAV runtime:

`clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`

Installed pcre2:

`10.49-r0`

Final Trivy:

`0 CRITICAL / 0 HIGH`

Real scanner acceptance:

- legitimate file → CLEAN;
- EICAR → INFECTED;
- scanner unavailable/error → fail closed.

The GitHub `security/container` gate now permanently scans both:

- the INFOSECURS application image;
- the pinned ClamAV runtime image.

## Verification

Fresh Independent Audit:

**GREEN**

Full repository suite:

`2343 passed, 7 skipped, 1 xfailed, 0 failed`

M009A hostile/evaluation corpus:

**GREEN**

Existing M005 corpus:

**UNCHANGED / GREEN**

Tenant isolation:

**GREEN**

Supersedes tenant safety:

**GREEN**

Customer Zero reset reconciliation:

**GREEN**

Backup/restore:

**GREEN**

Immutable-original proof:

**GREEN**

Real-browser/XSS/responsive acceptance:

**GREEN**

Migration state:

**CLEAN**

gitleaks:

**CLEAN**

pip-audit:

**CLEAN**

All seven GitHub CI/security checks:

**GREEN**

AI boundary:

**CLEAN**

DARWIN:

**UNTOUCHED**

## Decision

**M009A / PR #102 IS ACCEPTED FOR MERGE.**

This does not authorise M009B implementation.

M009B may begin Work Order architecture only after:

1. PR #102 is merged;
2. persistent development reconciliation is GREEN;
3. M009A receives durable closure.
