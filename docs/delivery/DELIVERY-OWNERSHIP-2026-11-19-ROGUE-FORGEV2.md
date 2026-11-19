# Delivery ownership — Rogue and ForgeV2 under FOUNDRY

**Date:** 2026-11-19
**Prepared by:** Hermes, Project Architect.
**Status:** approved by Matt on 2026-11-19. Matt reviewed this record as pull request #129 and instructed Hermes to merge it on his authority. It takes effect on merge.
**Base:** `main` at `638eff4b66c12919212dad666031e43be4a6e2a2`.

This is a new Product Owner decision. It does not dispute `CORRECTION-ROGUE-HANDOVER-RESCINDED.md`, which was correct when it was written.

## Decision

Matt Scott, Product Owner, decided on 2026-11-19:

1. **Delivery moves to Rogue and ForgeV2.** Rogue is the Delivery Controller (FOUNDRY's Orchestrator). ForgeV2 is the Implementer. GUNNAR and FORGE no longer deliver Infosecurs.
2. **Hermes is the Project Architect.** Hermes holds the architecture, PID, amendment, Work Order approval and acceptance authority that this repository assigned to Central Architecture. FOUNDRY decision FND-046 makes the Architect a role Matt appoints per project.
3. **`dell-debian` is the development host.** Matt designated it a development host under FOUNDRY decision FND-047, so Rogue and the ForgeV2 Project Lead both run as root there.
4. **FOUNDRY governs.** The framework is `maff0000/foundry`, at `39cc45c25aa5305b60f4c4af1557bee8cec0bf20` when this was written.

Matt remains Product Owner: product direction, scope, priority, material risk and final product acceptance are his.

## How the existing delivery chain maps

`docs/architecture/DELIVERY-GOVERNANCE.md` stays in force, including its four invariants. Only the holders of its roles change.

| Role in the delivery chain | Before | From this decision |
| --- | --- | --- |
| Architect | Central Architecture | Hermes |
| Delivery Controller | GUNNAR | Rogue |
| Implementer | FORGE | ForgeV2 Project Lead and its Engineer |
| Independent Audit | FORGE Auditor, plus separate audits where a PID required them | ForgeV2's Auditor, Tester and DevSecOps, each a fresh process reviewing the exact committed candidate. A Work Order states any further audit it needs. |

Where `PID.md` and other living documents name GUNNAR, read Rogue. Where they name FORGE, read ForgeV2. Where they name Central Architecture, read the Project Architect. Closed evidence and closure records are history and are not rewritten.

## What does not change

- Product doctrine, module PIDs, ADRs, closures and evidence already in this repository.
- The GitHub evidence contract.
- The deployment boundary in `PID.md` section 6.1.
- The synthetic and Customer-Zero-safe data restriction.

## State at handover

Verified read-only on 2026-11-19.

- `main` is at `638eff4b`. CI and Security were green on it. There are no open pull requests or Issues.
- **WO-IRENE-001 is unfinished.** Its branches are on `origin` and unmerged. `wo/IRENE-001-pilot` is 15 commits ahead of `main` with no pull request. Nobody has assessed that work under the new arrangement. What happens to it is a decision for the Architect and Matt; Rogue does not continue it by default.
- GUNNAR's clone and worktrees on `dell-debian` are untouched. They are not a ForgeV2 workspace.
- The persistent Beta containers are stopped. Restarting them is a release operation under `PID.md` section 6.1 and is not part of this handover.
- On `dell-debian`, the ForgeV2 engine is installed read-only at `/srv/forgev2` (commit `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, plugin 0.3.0) and Rogue's home is `/srv/rogue`.

## Confirmations by Matt

Rogue's commissioning (Issue #131) asked for five things only Matt can
settle. Matt gave them to Hermes in conversation on 2026-11-19, in the words
"all confirmed and authorised". Hermes records them here. Every agent writes
to GitHub under Matt's login, so nothing on GitHub can show that Matt wrote
something himself; this section is the Architect's attestation of what Matt
said, not a statement made by Matt on GitHub.

1. Matt approves this ownership record as merged in pull request #129.
2. Rogue keeps using the existing `maff0000` GitHub credential on
   `dell-debian`. Matt accepts that it is broader than the repository-scoped
   credential FOUNDRY prefers.
3. GUNNAR and FORGE have stopped work on Infosecurs.
4. The development-host arrangement (FOUNDRY FND-047) applies to this
   project. Identity separation is deferred until a production host is
   considered.
5. The ForgeV2 workspace on `dell-debian` is `/srv/infosecurs-dev/main`
   (canonical checkout) and `/srv/infosecurs-dev/worktrees`. Hermes created
   it on 2026-11-19 as a clone of `main` at
   `8d46182fcf2dd020a75411a5d91192fae29a2ab2`, owned by root, with `origin`
   set to `https://github.com/maff0000/infosecurs.git`.

## Delegation to the Architect

On 2026-11-19, between about 14:30 and 14:33 UTC, Matt attached to Rogue's
session on `dell-debian` and typed three statements:

1. "I accept the Architect's attestation as your approval mechanism for this project"
2. "this is Matt directly connected"
3. "Hermes has my authority to complete everything that is needed or required"

Matt then confirmed to Hermes, in conversation, that he made all three, and
said: "you have the authority, now I need you to proceed". Hermes records
this here. As with the confirmations above, this is the Architect's
attestation of what Matt said; nothing on GitHub can show that Matt wrote it.

What this means for Infosecurs:

- A decision Matt gives to Hermes, recorded by Hermes in this repository,
  counts as Matt's approval. This covers the ownership record as it now
  stands on `main`, including the sections added after pull request #129.
- Hermes may approve, on Matt's behalf, what is needed to bring the project
  back into delivery: the exact versions of the FOUNDRY project records,
  the disposition of WO-IRENE-001, and Work Orders. Each approval names the
  exact version it covers.
- The delegation is to Hermes. It does not widen Rogue's authority. Rogue
  still acts only on specific, bounded instructions.

What stays with Matt. Matt did not say the delegation changes the limits in
`ROGUE.md`, and Hermes does not read it that way:

- product direction: anything that changes what Infosecurs is for, who it
  is for, or its priorities, beyond what the existing PIDs already decide;
- material risk: exposing a service, real customer data, production
  deployment, spending money, loosening a security gate;
- final product acceptance.

Hermes brings those to Matt. Matt can widen, narrow or withdraw this
delegation at any time by telling Hermes or Rogue.

## Not yet done

This record approves no Work Order and authorises no delivery. Before any dispatch:

- The FOUNDRY project records now exist at the repository root and in `security/`: `PRODUCT-VISION.md`, `PRODUCT-BACKLOG.md`, `PROJECT-INITIATION-MANDATE.md` and `security/EXTERNAL_CODE_REGISTER.yaml`. Each is approved only by a comment on Issue #131 naming its exact commit.
- The first Work Order is `work-orders/WO-INFOSECURS-001.md`. It is approved only by a comment on Issue #134 naming its exact commit.
- The unmerged IRENE Stage 3 work is dispositioned in `WO-IRENE-001-DISPOSITION-2026-11-19.md`.
- The ForgeV2 workspace exists (see above). Rogue pushed and deleted a test branch from it on 2026-11-19 (Issue #131). No Project Lead has used it.
- Rogue's commissioning is recorded in Issue #131. The project is ONBOARDING, not delivery-ready.
- The Architect and Rogue communicate in a direct session on `dell-debian` and through GitHub Issues. Infosecurs is not registered with any Architect Gateway. A manual exchange was verified on Issue #131; automatic pickup was not tested.
- A ForgeV2 Project Lead has not yet been run as root on `dell-debian`.
