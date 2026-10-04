# Delivery Governance

**Status:** AUTHORISED — Central Architecture, 2026-10-04.
**Scope:** every work item delivered against this repository from this point forward, without exception.

This document records, as durable Git-tracked authority, the mandatory delivery chain and the roles and hard invariants that govern how architectural decisions become merged, closed product.

## The mandatory delivery chain

```
Architecture decision
  → PID / Amendment
  → Git-tracked Work Order
  → Delivery Controller
  → Implementer
  → Independent Audit
  → PR
  → Architect Acceptance
  → Merge
  → Closure
```

Every link in this chain must exist, in order, as a durable, Git-tracked artefact before the next link may proceed. A step that exists only as a chat instruction, a verbal decision, or an unrecorded intention is not a step in this chain — it has not happened, for delivery-governance purposes, until it is committed.

## Roles

- **The Architect** owns architecture, PIDs, amendments, sequencing, and acceptance. Only the Architect decides what gets built, in what order, and whether a delivered result is accepted. Only the Architect declares a product's governed-closure status (e.g. PRODUCT_GREEN).
- **The Delivery Controller** owns bounded execution. It dispatches implementation only against an approved Work Order — never against a chat instruction alone, never by inventing scope the Work Order does not name.
- **The Implementer** works only inside the Work Order it was dispatched against. It does not invent architecture, does not widen scope, and does not treat an ambiguous instruction as licence to improvise. Any architectural ambiguity encountered by an Implementer means **STOP** and return to the Architect — never resolve it unilaterally.

## The four hard invariants

1. **NO PID → NO WORK ORDER.** A Work Order may not be issued, and no Delivery Controller may dispatch against one, unless a PID (or an Amendment to an existing PID) already exists, durably, in Git, authorising the work.
2. **NO WORK ORDER → NO IMPLEMENTATION.** An Implementer may not be dispatched, and no implementation work may begin, without an approved, Git-tracked Work Order naming its exact scope and boundaries.
3. **NO INDEPENDENT AUDIT + ARCHITECT ACCEPTANCE → NO MERGE.** A PR may not be merged until a genuinely independent audit of the delivered work has returned a positive verdict AND the Architect has recorded explicit acceptance. Neither step may be skipped, assumed, or inferred from the other.
4. **NO GIT RECORD → NOT DURABLE PROJECT AUTHORITY.** Nothing that exists only in a chat transcript, a conversation summary, or an unrecorded verbal instruction constitutes durable project authority. Durable authority exists only once it is committed to this repository as a PID, an Amendment, a Work Order, an audit record, an Architect acceptance record, or a closure record.

## Chat is the control surface; Git/GitHub is the durable authority

A chat instruction — from the Architect, from Central Architecture, from any other party — may **direct** the preparation of durable authority (for example: "write a PID for X," "open a Work Order for Y"). A chat instruction does **not itself** replace, satisfy, or stand in for:

- a PID or Amendment,
- a Work Order,
- an audit record,
- an Architect acceptance record, or
- a closure record.

Each of those remains a separate, durable, Git-tracked artefact that must actually be created and committed. The chat message that requested it is not a substitute for it, no matter how detailed or explicit that chat message was. This distinction exists precisely so that project authority can always be reconstructed from the Git history alone, by anyone, without needing access to any particular chat transcript.

## Why this document exists

This delivery chain and these four invariants govern every work item from this document's authorisation date forward. Work delivered before this document existed is not retroactively judged against it — see `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md` for how this principle was applied to the M008 epic's own delivery history.
