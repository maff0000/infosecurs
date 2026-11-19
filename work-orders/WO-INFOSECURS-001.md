# WO-INFOSECURS-001 — Retire the superseded GUNNAR startup directives

**Issue:** https://github.com/maff0000/infosecurs/issues/134
**Parent backlog items:** PBI-006 (truthful records) and PBI-001 (delivery
works again) in `PRODUCT-BACKLOG.md`.
**Author:** Hermes (Project Architect), 2026-11-19.
**Approval:** none in this file. This Work Order is approved only by an
Architect comment on the Issue above that names this file's path, the
commit containing it, and the starting commit on `main`. Without that
comment it must not be dispatched. If this file changes, the approval lapses.

## Why

Two files at the repository root, `GUNNAR-START.md` and
`INFOSECURS-GUNNAR-START.md`, tell a new session to start as GUNNAR and to
use `/srv/infosecurs` as its working root. Both statements are now wrong:
delivery belongs to Rogue and ForgeV2
(`docs/delivery/DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md`), and
`/srv/infosecurs` is the persistent Beta's build context, which must never
be a development tree (`PID.md` §6.1). The two files are byte-identical.

This is also the first Work Order through ForgeV2 on this project. It is
small and changes no executable code on purpose, so that a failure points
at the delivery chain and not at the change.

## Governing records

- FOUNDRY `maff0000/foundry` at `39cc45c25aa5305b60f4c4af1557bee8cec0bf20`:
  `standards/work-order-contract.md`, `standards/secure-engineering.md`,
  `delivery/rogue-handoff.md`.
- This repository: `PROJECT-INITIATION-MANDATE.md`, `PID.md`,
  `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md`.
- Engine: ForgeV2 at `adb89037ea1f166720659e188cf4e0d5e9f4482a`, plugin
  0.3.0, installed at `dell-debian:/srv/forgev2` (protected).

## Repository and workspace

| Field | Value |
| --- | --- |
| `WO` | `WO-INFOSECURS-001` |
| `REPO` | `maff0000/infosecurs` |
| `HOST` | `dell-debian` |
| `ROOT` | `/srv/infosecurs-dev/main` |
| `WORKTREES` | `/srv/infosecurs-dev/worktrees` |
| `BASE` | `main` |
| `KNOWN_COMMIT` | the starting commit named in the approval comment |
| `BROWSER` | `no` |
| Delivery branch | `forge/WO-INFOSECURS-001`, created by ForgeV2 |

The Project Lead runs as root on `dell-debian`, started with
`FORGE_ALLOW_ROOT=1`, from root's home directory, never from inside `ROOT`
or a worktree. Rogue runs on the same host; no remote execution route is
involved.

Must remain untouched: `ROOT` itself (no direct edits), `/srv/infosecurs`,
`/srv/openclaw`, `/srv/forgev2`, `/srv/rogue`, every other project on the
host, every branch other than `forge/WO-INFOSECURS-001`.

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

   - then one blank line, then the complete, unmodified content of the
     current `GUNNAR-START.md`.
2. Delete `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md` from the
   repository root.

## Out of scope

Everything else. In particular: no edit to `README.md`, `CLAUDE.md`,
`PID.md`, `docs/ROADMAP.md` or anything under `docs/evidence/` (the
historical mention of these files in
`docs/evidence/M005-M006-HOST-RELOCATION-GATE.md` stays as it is); no code,
test, dependency, workflow or configuration change; no new dependency.

## Acceptance criteria

1. `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md` do not exist at the
   repository root in the candidate.
2. `docs/history/GUNNAR-START.md` exists. Its first eight lines are the
   banner above, character for character. After one blank line, the rest
   of the file is byte-identical to `GUNNAR-START.md` at the starting
   commit.
3. Apart from ForgeV2's own delivery record under `.forge/`, the candidate
   differs from the starting commit in exactly those three paths: two
   deletions and one addition.
4. In the candidate, the string `GUNNAR-START` appears in tracked files
   only in `docs/history/GUNNAR-START.md`,
   `docs/evidence/M005-M006-HOST-RELOCATION-GATE.md`,
   `work-orders/WO-INFOSECURS-001.md` and `PRODUCT-BACKLOG.md`.
5. The branch `forge/WO-INFOSECURS-001` is pushed and a pull request to
   `main` is open, not merged.

## Verification

- **Engineer:** makes the change; checks criteria 1 to 4 with `git` and
  `diff` in the worktree.
- **Auditor:** independent review of the candidate against this Work
  Order: scope, exact banner text, byte-identity of the preserved content.
- **Tester:** independent check of criteria 1 to 4 by running the
  comparisons itself against the starting commit, not by reading the
  Engineer's report.
- **DevSecOps:** confirms no secret, credential, internal address beyond
  what the original file already contained, or executable content is
  introduced, and that nothing outside scope changed.

Order: Engineer, Auditor, Tester, DevSecOps. All four apply.

**Running the application test suite is not required of any specialist
for this Work Order.** Reason: the change touches no executable code, and
the suite needs PostgreSQL and the pinned dependencies, which a ForgeV2
specialist on this host is not expected to have (see the mandate, "Not
verified"). The full suite runs in GitHub Actions on the pull request and
is a required check before merge. A specialist that tries to run the suite
and cannot should say so in its report as an observation; that is useful
evidence and is not a failed criterion.

## Evidence and reporting

- ForgeV2's delivery record under `.forge/WO-INFOSECURS-001/` on the
  delivery branch: ledger, report, prompts and specialist reports. Its
  private ledger is in `/root/.local/state/forgev2`. ForgeV2 has no
  separate per-role log files.
- Rogue posts on the Issue: dispatch (with the Work Order version and
  starting commit), the validated final status, the branch, the candidate
  commit and the pull request link. Rogue keeps the Project Lead's raw
  JSON output.
- Completion report: outcome, changed paths, starting and final commits,
  each criterion's result, each reviewer's verdict against the same
  candidate, deviations, limitations.

## Limits and stop conditions

- One ForgeV2 delivery cycle. At most four executions per specialist. No
  replacement Work Order to get round an exhausted limit.
- BLOCKED, with the reason, if any entry gate fails: identity, paths,
  starting commit, approval comment missing or not matching this file.
- Stop and report, do not improvise, if: the two root files are not
  identical at the starting commit; the sandbox cannot start; a push is
  refused; anything outside the three paths would need to change.
- Rogue does not merge. A DELIVERED verdict is not Architect acceptance.
  The Architect reviews the pull request and merges on Matt's authority
  once the required checks pass.
