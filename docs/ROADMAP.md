# Infosecurs Beta 0.1 — Delivery Roadmap

| Module | Purpose | Detailed PID |
|---|---|---|
| M001 | Foundation & Organisation Profile | AUTHORISED |
| M002 | Security Baseline & Initial Risk | Write after M001 |
| M003 | Evidence & Security State | Write after M002 |
| M004 | Policy Foundation | AUTHORISED |
| M005 | Questionnaire Assurance | PRODUCT_GREEN |
| M006 | Customer-Zero Beta Hardening | PRODUCT_GREEN |
| M007 | Dashboard Shell, Entitlements & Foundation Metrics | PRODUCT_GREEN |
| M008 | Guided Security Foundations Experience Redesign | CLOSED PRODUCT_GREEN — includes the M008E visual/UX design hardening extension (see `docs/evidence/M008-DEV-SCHEMA-DRIFT-CLOSURE.md`, `docs/evidence/M008E-CLOSURE.md`) |
| M009 | Customer Assurance / Questionnaire Completion | Increments 1 (Foundations Assurance Readiness + CSV ingestion) and 2 (M005 prepare/persist extraction) CLOSED GREEN and merged (PRs #107, #109; see `docs/evidence/M009B-INCREMENT-1-CLOSURE.md`, `docs/evidence/M009B-INCREMENT-2-CLOSURE.md`); Increments 3–4 (bulk orchestration, claim ledger) not yet authorised for implementation |
| M010 | IRENE AI Adviser, shared Security Tasks and proactive guided Foundations | Implementation Architect-Accepted and merged to main (PR #112, merge commit `ac88787`), after a fresh Independent Audit plus a supplementary audit (tenant lifecycle/backup-restore, independent AI attack corpus, accessibility sweep, targeted spot-checks) with one accessibility defect found, fixed and re-verified GREEN (see `docs/evidence/M010-CLOSURE.md`); production deployment, live Adviser Mode, real customer data, the scheduled review job on a persistent environment, tenant export/DSAR readiness and M009B Increments 3-4 remain separately governed and are NOT authorised by this merge |

Do not pre-build later modules merely because they are listed here.

M002/M003 status rows above predate this table's current maintainer and have not
been independently reconciled against their actual delivery state in this pass;
left unchanged rather than guessed.
