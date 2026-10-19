# Deployment Boundary — PID Amendment

**Status: Architecture-document PR. No infrastructure implementation is authorised by this document or its acceptance.** This amendment exists solely to establish the governing authority `WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md` (PR #114) must cite, per the mandatory delivery doctrine: **NO PID → NO WORK ORDER → NO IMPLEMENTATION.**

**Trigger:** `docs/evidence/INCIDENT-2026-10-19-DEPLOYMENT-BOUNDARY-EXPOSURE.md` (merged, PR #115, incident restoration CLOSED GREEN; structural prevention remains OPEN).

**Exact base SHA this amendment is written against:** `main` @ `fbaf2ddc55a63d2fbba0ccd083f9a14892d581d8`.

## 1. What this amends

- `PID.md` §6 ("Architecture") — adds a new §6.1 "Deployment boundary (persistent runtime)" making the already-stated principle *"Immutable production artifact by exact Git SHA"* a concrete, binding architecture decision rather than a bare bullet point.
- `PID.md` §11 ("Repository and GitHub doctrine") — replaces the existing simplified change-flow diagram with the full mandatory delivery doctrine Central Architecture has now reinforced, including the four NO-rules and explicit role boundaries.
- `docs/delivery/M005-M006-HOST-RELOCATION-GATE.md` — appends an amendment note narrowing its "Durable placement rule" (`PROJECT_ROOT = /srv/infosecurs`) to mean the deployment's build context only, never a shared development working tree. The original rule text is preserved unchanged, not rewritten or deleted; the amendment note points forward to this document and to `PID.md` §6.1.

## 2. The architecture decision (verbatim, as issued)

The persistent INFOSECURS Beta must run immutable, exact-SHA application artifacts. It must never execute source code from a mutable development Git working tree.

Development clones and worktrees are segregated from persistent deployment resources. Persistent runtime uses a proper WSGI/ASGI server without Django's development autoreloader.

Database migrations are explicit, separately controlled release operations. They never execute implicitly during container startup.

Database, evidence and questionnaire volume identities remain unchanged. Existing data is preserved. Any schema modification must be independently assessed for compatibility and recovery.

The initial remediation must preserve the existing deployed application revision `ad996bfa4527623d095862199b46db6e0ea94fd0`, unless separately authorised otherwise.

No M010 deployment, customer credential rotation, or feature expansion is included.

## 3. Scope and exclusions

**In scope:** the governing architecture text itself (`PID.md` §6.1, §11) and the amendment note on the relocation gate. **Nothing else.**

**Explicitly excluded:** any infrastructure change; any touch to the persistent `infosecurs-relocation` stack; any change to `docs/work-orders/WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md` (PR #114) — that update happens only *after* this amendment is accepted and merged, per the Architect's own sequencing instruction; M010 deployment; credential rotation; feature expansion.

## 4. Acceptance criteria

Architect Acceptance of this document authorises exactly one next step: updating PR #114 to cite this amendment as its governing authority and reconciling it against the resulting canonical `main`. It does not itself authorise any Work Order content, implementation, or persistent-stack change — those remain gated by PR #114's own, separate acceptance once corrected.
