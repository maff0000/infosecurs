You are an independent reviewer (role stated at the end). Assess independently; do not modify anything in the worktree.

- Worktree: /srv/infosecurs-dev/worktrees/WO-INFOSECURS-001 (read only)
- Candidate SHA: 4335f41a7d4ccf1fc5fbb0090e13631d0cb0d058
- Base SHA: 3946d7c918697b29ab61af68a3798cf37e76687c
- Scratch directory (yours to write): /srv/infosecurs-dev/worktrees/.forge-scratch/WO-INFOSECURS-001

Review the candidate against this Work Order, quoted verbatim:

---
# WO-INFOSECURS-001 — Retire the superseded GUNNAR startup directives

## Why

Two files at the repository root, `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md`, tell a new session to start as GUNNAR and to use `/srv/infosecurs` as its working root. Both statements are now wrong: delivery belongs to Rogue and ForgeV2 (`docs/delivery/DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md`), and `/srv/infosecurs` is the persistent Beta's build context, which must never be a development tree (`PID.md` §6.1). The two files are byte-identical.

This is also the first Work Order through ForgeV2 on this project. It is small and changes no executable code on purpose, so that a failure points at the delivery chain and not at the change.

## Change

1. Create `docs/history/GUNNAR-START.md` containing:
   - first, this banner, exactly, starting each line at column one:

     ```
     > **Superseded on 2026-11-19. Do not follow these instructions.**
     > This was the startup directive for GUNNAR, the previous delivery
     > controller. Delivery now belongs to Rogue and ForgeV2; see
     > `docs/delivery/DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md` and
     > `PROJECT-INITIATION-MANDATE.md`. `/srv/infosecurs` is the persistent
     > Beta's build context and is not a development working tree.
     > Kept for history only. It was stored at the repository root as two
     > identical files, `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md`.
     ```

   - then one blank line, then the complete, unmodified content of the current `GUNNAR-START.md`.
2. Delete `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md` from the repository root.

## Out of scope

Everything else. In particular: no edit to `README.md`, `CLAUDE.md`, `PID.md`, `docs/ROADMAP.md` or anything under `docs/evidence/` (the historical mention of these files in `docs/evidence/M005-M006-HOST-RELOCATION-GATE.md` stays as it is); no code, test, dependency, workflow or configuration change; no new dependency.

## Acceptance criteria

1. `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md` do not exist at the repository root in the candidate.
2. `docs/history/GUNNAR-START.md` exists. Its first eight lines are the banner above, character for character. After one blank line, the rest of the file is byte-identical to `GUNNAR-START.md` at the starting commit.
3. Apart from ForgeV2's own delivery record under `.forge/`, the candidate differs from the starting commit in exactly those three paths: two deletions and one addition.
4. In the candidate, the string `GUNNAR-START` appears in tracked files only in `docs/history/GUNNAR-START.md`, `docs/evidence/M005-M006-HOST-RELOCATION-GATE.md`, `work-orders/WO-INFOSECURS-001.md` and `PRODUCT-BACKLOG.md`.
5. The branch is pushed and a pull request to `main` is open, not merged. (Handled by the Project Lead after review; not a review criterion.)

## Verification roles

- **Auditor:** independent review of the candidate against this Work Order: scope, exact banner text, byte-identity of the preserved content.
- **Tester:** independent check of criteria 1 to 4 by running the comparisons itself against the starting commit, not by reading anyone's report.
- **DevSecOps:** confirms no secret, credential, internal address beyond what the original file already contained, or executable content is introduced, and that nothing outside scope changed.

Running the application test suite is not required of any specialist for this Work Order (no executable code is touched; the suite needs PostgreSQL and pinned dependencies). If you try and cannot, mention it as an observation; it is not a failed criterion.
---

Report your final message beginning with a line `STATUS: pass` (nothing blocking found) or `STATUS: findings` (list each finding with severity blocking/advisory and evidence) or `STATUS: inconclusive` (say why).

Your role: TESTER.
