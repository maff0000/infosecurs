# Delivery ownership — Rogue and ForgeV2 under FOUNDRY

**Date:** 2026-11-19
**Prepared by:** Hermes, Project Architect.
**Status:** takes effect when Matt merges this document. The merge is Matt's approval of this exact version.
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

## Not yet done

This record approves no Work Order and authorises no delivery. Before any dispatch:

- The FOUNDRY project records do not exist yet: `PRODUCT-VISION.md`, `PRODUCT-BACKLOG.md`, `PROJECT-INITIATION-MANDATE.md` and `security/EXTERNAL_CODE_REGISTER.yaml`. They will be written from the existing PIDs and evidence, for Matt's approval.
- The ForgeV2 checkout and worktree locations for this project are not chosen.
- Rogue has not run its project commissioning.
- The Architect and Rogue communicate in a direct session on `dell-debian` and through GitHub Issues. Infosecurs is not registered with any Architect Gateway.
- A ForgeV2 Project Lead has not yet been run as root on `dell-debian`.
