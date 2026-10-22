# PID-DBR-001 — Next Release Preparation: Security-Only Dependency Deployment

**Status: PREPARED, NOT EXECUTED.** This document records the preparation of
a security-only certifi/Pillow dependency release onto the already-cutover
`infosecurs-relocation` baseline (`docs/evidence/DBR-001-CUTOVER-COMPLETION.md`).
Per Central Architecture's instruction, this is tracked as its own,
separately-gated preparation requiring its own independent audit and its
own, separately-required live-release authorisation before any further
persistent-stack change. **No live deployment action has been taken.**

## 1. Why this release

The live cutover (`docs/evidence/DBR-001-CUTOVER-COMPLETION.md`) deployed
release SHA `0bce2555e0a6b9eec4d6dc645ac606f8d7309285`, which — being
branched from the pre-M010 baseline `ad996bf` — still carries the
vulnerable dependency versions that `main` already fixed separately:
`certifi==2026.7.22` and `pillow==12.3.0`. `main` has since merged three
already-reviewed, already-tested security commits fixing both:

| Commit | Subject | Files touched |
|---|---|---|
| `83d565f` | sec: bump certifi to 2026.10.19 (GHSA-6q48-6c7w-9gw2) | `requirements.txt`, `requirements-dev.txt`, own WO/evidence docs |
| `659dbed` | sec: amend WO to authorise pillow remediation; fix ClamAV-skip wording | pure governance/doc (2 files) |
| `4906ca1` | sec: bump pillow to 13.0.0 (8 disclosed CVEs, WO-amended scope) | `requirements.txt`, `requirements-dev.txt`, same evidence doc |

Both were already independently tested on `main` at merge time (pip-audit
clean, full `ci/unit`+`ci/integration` re-run, hash-verified install for
certifi; PDF-rendering suite + full CI re-run, hash-verified install for
Pillow). This preparation does not re-litigate that review — it carries
the fix onto the live-deployed baseline without pulling in M010.

## 2. Candidate branch and commit history

Branch `wo/DBR-001-release-base-secdeps`, created directly off the
**live-deployed** SHA `0bce2555e0a6b9eec4d6dc645ac606f8d7309285` — not off
`main` — specifically to avoid pulling in M010 or any of its 6 new
migrations.

```
b39eee9  fix: derive release.sh smoke-check host/port from container, not hardcoded loopback
690fcc4  sec: bump pillow to 13.0.0 (8 disclosed CVEs, WO-amended scope)
80da124  sec: amend WO to authorise pillow remediation; fix ClamAV-skip wording
0ec21af  sec: bump certifi to 2026.10.19 (GHSA-6q48-6c7w-9gw2)
```

(the cutover's own 8-file baseline is the branch point, not a commit on
this branch)

All three security commits (`83d565f`→`0ec21af`, `659dbed`→`80da124`,
`4906ca1`→`690fcc4`) were cherry-picked in order and applied **cleanly,
with no conflicts** — `requirements.txt`/`requirements-dev.txt` auto-merged.

The fourth commit, `b39eee9`, pulls forward the `scripts/release.sh`
smoke-check fix from PR #124 (merged to `main` as `7121305c`) — see §5 of
`docs/evidence/DBR-001-CUTOVER-COMPLETION.md` for the defect this corrects.
It was applied via `git checkout origin/main -- scripts/release.sh` (a
selective single-file pull, the same technique already used earlier in
this PID to pull `docker-compose.cutover.yml` onto the original release
base) rather than cherry-picking the full closure commit, which would have
brought unrelated evidence docs onto this release-mechanism-only branch.

**Final candidate SHA: `b39eee9244e56f17bc4aa32904dd1b8def6286ac`.** This is
the commit that was built, labelled, and migration-plan-checked in §4–5
below — it is **not** the same as this branch's eventual HEAD once this
document itself is committed one commit later (a self-referential docs
commit cannot also be the thing it documents). Anyone re-deriving §3's
file/commit counts must diff against `b39eee9`, not against the branch's
own HEAD at read time — diffing against HEAD after this commit lands will
correctly show one additional file (this document) and one additional
commit, which is expected and not a discrepancy.

## 3. Scope proof — zero migrations, zero application code, no M010

- Migration file count: **38** — identical to the deployed baseline
  (`ad996bf`/`0bce2555e...`) and to `main`'s pre-M010 state. Verified by
  direct count on the built worktree.
- Full diff vs `ad996bf`, exactly **10 files**, all dependency/tooling/docs:

  ```
  docker-compose.cutover.yml                         | 139 +++++++
  docker-compose.release.yml                         |  43 ++-
  docs/evidence/SEC-CERTIFI-GHSA-6Q48-6C7W-9GW2-EVIDENCE.md |  73 ++++
  docs/runbooks/BETA-OPERATIONS.md                   |  38 +-
  docs/work-orders/WO-SEC-CERTIFI-GHSA-6Q48-6C7W-9GW2.md    |  43 +++
  requirements-dev.txt                               | 182 ++++-----
  requirements.in                                    |  16 +
  requirements.txt                                   | 182 ++++-----
  scripts/release.sh                                 | 424 +++++++++++++++++++++
  scripts/rollback.sh                                | 182 +++++++++
  10 files changed, 1134 insertions(+), 188 deletions(-)
  ```

  (the original 8 cutover-mechanism files, plus the 2 docs introduced by
  the certifi/Pillow WO — Pillow's own commits amended the same evidence
  doc rather than adding a separate file). No application code
  (`*/models.py`, `*/views.py`, templates, etc.) and no migration file
  appears in this diff.
- `requirements.txt` confirmed to show `certifi==2026.10.19`,
  `pillow==13.0.0`, with `gunicorn==26.2.0` unchanged from the cutover
  baseline.

## 4. Candidate image build

Built on dell-debian directly from the worktree at
`b39eee9244e56f17bc4aa32904dd1b8def6286ac`, with `GIT_SHA` and
`BUILD_DATE_UTC` passed explicitly as literal/remote-evaluated build-args
(not local shell substitution — an earlier attempt in this PID's history
mistakenly let `$(git rev-parse HEAD)` evaluate on the wrong host inside a
double-quoted SSH string; corrected before use here).

- **Image:** `infosecurs-release:b39eee9244e56f17bc4aa32904dd1b8def6286ac`
- **Image digest:** `sha256:b308cb77a7c16e12700f01daed97daf020779385cc6fb75937b122d0019c4b59`
- **OCI revision label** (`org.opencontainers.image.revision`): confirmed
  via `docker inspect` to equal `b39eee9244e56f17bc4aa32904dd1b8def6286ac`
  exactly — the built artifact is provably the candidate commit, not a
  stale or substituted one.

## 5. Read-only migration-plan check against the live database

Run as a disposable `docker run --rm` container on the candidate image,
attached to the real `infosecurs-relocation_default` network, using a
copy of the real `/srv/infosecurs/.env` made and removed entirely within
dell-debian (never transferred off-host), plus `POSTGRES_HOST=db` /
`POSTGRES_PORT=5432` supplied explicitly (these are set via the real
compose file's own `environment:` block for the `web` service, not via
`.env`, so they do not travel with a bare `--env-file` run).

```
Planned operations:
  No planned migration operations.
```

**Empty plan — confirms zero schema change, matching §3's file-level
proof.** This check is read-only: `manage.py migrate --plan` does not
execute DDL. No container belonging to the live `infosecurs-relocation`
stack was touched, stopped, or restarted. The disposable check container
exited and was removed automatically (`--rm`); confirmed no leftover
container remains. The temporary `.env` copy used for this check was
deleted immediately after, confirmed removed.

## 6. What was explicitly NOT done

- No `scripts/release.sh` execution against `infosecurs-relocation`.
- No image swap, no container recreation, no `up -d` of any kind against
  the real stack.
- No credential read, print, or rotation beyond the read-only `.env` copy
  used transiently for the plan check (confirmed deleted).
- No credential or secret of any kind was committed, pushed, or left on
  disk outside dell-debian at any point in this preparation.
- `docs/evidence/DBR-001-BETA-DEVMODE-PLAINHTTP-FINDING.md` (the open
  dev-mode/plain-HTTP finding) was not touched, folded in, or corrected as
  part of this preparation, per Central Architecture's explicit
  instruction to keep it a distinct, separately-tracked item.

## 7. Independent audit and remaining steps

A fresh independent auditor, with no memory of this preparation,
re-derived every claim in §1–6 directly from the repository and the live
host — including independently re-running the §5 migration-plan check
itself (not reading this document's transcript of it) and inspecting
package versions installed inside the built image, not just its label.

**Verdict: GREEN.** All seven claims independently confirmed. One
documentation-precision nuance was surfaced and is addressed in §2 above
(the candidate SHA `b39eee9` vs. this branch's later HEAD once this
document is committed) — not a functional or security defect.

Branch `wo/DBR-001-release-base-secdeps` has been pushed to `origin`.

**Remaining steps (not yet executed):**

1. Open a PR for this preparation (evidence + branch only, no live deploy
   in the PR).
2. Return to Central Architecture for the separately-required live-release
   authorisation before any `scripts/release.sh` execution against
   `/srv/infosecurs` / `infosecurs-relocation`.
