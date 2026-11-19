# Infosecurs — Project Initiation Mandate

**Project:** Infosecurs. **Route:** EXISTING project, brought under FOUNDRY.
**Author:** Hermes (Project Architect). **Date:** 2026-11-19. **Version:** 1.
**Governing framework:** FOUNDRY, `maff0000/foundry` at
`39cc45c25aa5305b60f4c4af1557bee8cec0bf20`.

This is a snapshot of what was verified when Infosecurs was picked up
again. It is not the living product direction (that is
`PRODUCT-VISION.md`, `PRODUCT-BACKLOG.md` and `PID.md`) and it authorises no
delivery. Every delivery needs an approved Work Order.

"VERIFIED" below means the Architect checked it directly on 2026-11-19.

## Why this exists

Infosecurs was delivered from September to October 2026 by a different
chain (GUNNAR, FORGE, "Central Architecture"). Development stopped
abruptly around 2026-10-23 because of an office move. On 2026-11-19 Matt
moved delivery to Rogue and ForgeV2 under FOUNDRY, with Hermes as Project
Architect. The record of that decision, Matt's confirmations and his
delegation to the Architect is
`docs/delivery/DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md`.

## Product intent

See `PRODUCT-VISION.md`. In one line: AI-first security assurance for small
organisations, which never claims security state it cannot substantiate.
The immediate aim of this initiation is narrower: get the project
deliverable again, then finish the work that was cut off.

## Repository (VERIFIED)

| Fact | Value |
| --- | --- |
| Repository | `maff0000/infosecurs`, private |
| Default branch | `main` |
| Baseline when the pickup began | `638eff4b66c12919212dad666031e43be4a6e2a2` (pull request #128, 2026-10-23) |
| Baseline for this mandate | `6b4cb6ca5d580ef3d0a36567da47e63c93a776de` (pull request #132) |
| Merge rules | Ruleset `main-governance`: six required checks (`ci/unit`, `ci/integration`, `security/sast`, `security/secrets`, `security/dependencies`, `security/container`), no bypass |
| Unmerged work | `wo/IRENE-001-pilot` at `f3be6305e129e43f93dcd1b4f0d8bbcf41e09101`; see `docs/delivery/WO-IRENE-001-DISPOSITION-2026-11-19.md` |

## Development host and workspace (VERIFIED)

Matt named `dell-debian` (LAN address `192.168.11.10`) as the development
host for this project and designated it a development host under FOUNDRY
FND-047.

| Purpose | Location on `dell-debian` |
| --- | --- |
| Execution target for engineering | `dell-debian:/srv/infosecurs-dev` |
| Canonical checkout (`ROOT`) | `/srv/infosecurs-dev/main` — clean, on `main`, owned by root, `origin` = `https://github.com/maff0000/infosecurs.git`, repository-local author and committer identity `maff0000` (GitHub noreply address) |
| Worktree parent (`WORKTREES`) | `/srv/infosecurs-dev/worktrees` — empty |
| ForgeV2 engine | `/srv/forgev2` at `adb89037ea1f166720659e188cf4e0d5e9f4482a`, plugin 0.3.0, owned by root, protected: no application Work Order writes there |
| Rogue (Orchestrator) home | `/srv/rogue`, with `ROGUE.md` identical to FOUNDRY at the revision above (Git blob `8261fb92700e5455c461f121f6740dfd2ca6d795`). Rogue runs here, on the same host as the execution target |
| Host tools | `/usr/local/bin/claude` 2.1.322, tmux, bubblewrap, socat, gitleaks 8.30.1 |

**Not part of the workspace, and not to be used for development:**

- `/srv/infosecurs` — the persistent Beta's build context (`PID.md` §6.1).
- `/srv/openclaw/gunnar-dev/infosecurs` and `/srv/openclaw/worktrees/wo/*`
  — the previous chain's clone and worktrees. Left untouched.
- Every other project on the host. Several are live.

## Identities and credentials

- Rogue, the Project Lead and the specialists all run as **root** on
  `dell-debian`, with root's existing Claude login. A root Project Lead is
  started with `FORGE_ALLOW_ROOT=1` (ForgeV2 FV2-D024). There is no
  `forgev2-pl` account on this host.
- GitHub access is root's existing `maff0000` credential. It is broader
  than this repository; Matt accepted that. A dry-run push from `ROOT`
  succeeded (Issue #131). A real push has not been tested.
- Every agent, including the Architect, writes to GitHub as `maff0000`.
  Authorship on GitHub therefore proves nothing about who wrote a comment.
- No secret, token or key is recorded in this repository.

Accepted risk: with one account, the ForgeV2 sandbox is the only barrier
between a specialist and the rest of the host. Matt accepted this for
development; it is to be reviewed before any production host.

## Communications

- Architect and Rogue: a direct session on `dell-debian` (tmux session
  `rogue`) and GitHub Issues.
- Onboarding Issue: `https://github.com/maff0000/infosecurs/issues/131`.
  A manual round trip was verified there (**MANUAL_EXCHANGE_VERIFIED**).
- Architect Gateway: **NOT_REGISTERED / UNSUPPORTED** for this project.
  Nothing in scope depends on automatic pickup.
- Each Work Order has its own Issue. ForgeV2 writes each Work Order's
  delivery record (ledger, report, every prompt and every specialist
  report) under `.forge/<WO>/` on the branch `forge/<WO>`; its private
  ledger is in the Project Lead account's `~/.local/state/forgev2`.
  ForgeV2 does not produce separate per-role `.log` files.
- Escalation: specialists to the Project Lead, the Project Lead to Rogue,
  Rogue to the Architect, the Architect to Matt for product direction,
  material risk and final product acceptance.
- Status for Matt is also posted to Discord `#project-infosecurs`.

## Security expectations

`PID.md` §9 is binding. Synthetic or Customer-Zero-safe data only. No real
customer data, no production deployment and no exposure of the persistent
Beta is authorised by this mandate. Third-party software:
`security/EXTERNAL_CODE_REGISTER.yaml`. Changes to dependencies follow
`docs/delivery/BUILD-REPRODUCIBILITY.md`.

## What was done during initiation

- Host commissioned for Rogue and ForgeV2; FOUNDRY Amendment 006
  (FND-046, FND-047) and ForgeV2 FV2-D024 recorded the development-host
  arrangement.
- Delivery ownership recorded (pull request #129, with a one-off ruleset
  exception Matt approved).
- Security dependencies recovered (pull request #130). Done directly by
  the Architect on Matt's recovery authority, outside the normal chain;
  evidence in `docs/evidence/SECURITY-REMEDIATION-2026-11-19.md`.
- Matt's confirmations and delegation recorded (pull requests #132, #133).
- Rogue's commissioning: Issue #131.

## Not verified, and what it blocks

| Unknown | Blocks |
| --- | --- |
| A ForgeV2 Project Lead has never run as root on this host | Everything; WO-INFOSECURS-001 is the test |
| A real branch push from `ROOT` | Delivery of any Work Order |
| Whether specialists can run this project's tests inside the ForgeV2 sandbox (expected not: no PostgreSQL or project dependencies on the host, no network in the sandbox) | Any Work Order that changes code |
| Which AI gateway the product should use here, and whether it reaches a model | The IRENE real-model evaluation |
| ForgeV2's own host boundary test (`tests/host/sandbox-boundary.sh`) has not been run here; it is broken at this version (ForgeV2 issue #5) | Confidence in the sandbox boundary on this host |

## Authority and stop conditions

- This mandate authorises Rogue to verify the facts above and to dispatch
  only Work Orders the Architect has approved at an exact version.
- Stop and return to the Architect on: any path outside
  `/srv/infosecurs-dev`; any touch of `/srv/infosecurs`, the previous
  chain's clones, another project or `/srv/forgev2`; any real-model call;
  any deployment action; any change to merge rules or security gates.
- No self-approval. A Project Lead cannot approve its own Work Order or
  merge. Rogue does not merge. The Architect merges on Matt's authority
  after the required checks pass.

## Exit criteria for initiation

1. These records are on `main` and approved at an exact version.
2. Rogue reports DELIVERY_READY on Issue #131.
3. WO-INFOSECURS-001 has returned a valid ForgeV2 result.
