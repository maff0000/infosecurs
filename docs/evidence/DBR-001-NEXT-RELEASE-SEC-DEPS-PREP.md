# PID-DBR-001 — Security-Only Dependency Release: Preparation, Independent Audit, and Live-Release GO/NO-GO Package

**Status: PREPARED AND AUDITED GREEN. NOT DEPLOYED.** This is the durable
Git record, on canonical `main`, of the preparation and independent audit
of a security-only certifi/Pillow dependency release for the already
cutover `infosecurs-relocation` Beta stack. **No live deployment action
has been taken against `/srv/infosecurs` or `infosecurs-relocation`.**
A separate, explicit live-release authorisation from Central Architecture
is required before any `scripts/release.sh` execution against that stack.

**Repository note:** the release candidate itself lives on branch
`wo/DBR-001-release-base-secdeps`, which is deliberately based on the
live-deployed SHA `0bce2555e0a6b9eec4d6dc645ac606f8d7309285` rather than on
`main`, because its sole purpose is to produce the isolated Beta release
artifact without pulling in `main`'s M010 feature/migrations. Per Central
Architecture's explicit instruction, **that branch is not merged into
`main`** — its dependency-bump and release.sh-fix content already exists
on `main` independently (via earlier, separate merges); merging it here
would only reconcile genuinely divergent history for no benefit (GitHub
itself reports `CONFLICTING` merge status for the PR that attempted it,
PR #125, now closed unmerged for this reason). This document — the
preparation and audit record — is what belongs on `main`, on its own
branch cut from canonical `main`.

**Final candidate SHA (on the release branch): `b39eee9244e56f17bc4aa32904dd1b8def6286ac`.**

## 1. Why this release

The live cutover (`docs/evidence/DBR-001-CUTOVER-COMPLETION.md`) deployed
release SHA `0bce2555e0a6b9eec4d6dc645ac606f8d7309285`, branched from the
pre-M010 baseline `ad996bf`, which still carried `certifi==2026.7.22` and
`pillow==12.3.0` — both already fixed, separately and independently
tested, on `main` (`83d565f`, `659dbed`, `4906ca1`: certifi → `2026.10.19`
GHSA-6q48-6c7w-9gw2; pillow → `13.0.0`, 8 disclosed CVEs). This release
carries those two fixes, and only those two fixes plus the release-script
smoke-check correction below, onto the live-deployed baseline.

## 2. Candidate branch, commits, and scope proof

Branch `wo/DBR-001-release-base-secdeps`, based directly on the
live-deployed SHA, carries 4 commits: the three cherry-picked security
commits (`0ec21af`, `80da124`, `690fcc4` ← `83d565f`, `659dbed`,
`4906ca1`, applied cleanly, no conflicts) and one commit (`b39eee9`)
selectively pulling forward only `scripts/release.sh` from `main`'s
closure PR #124 (`7121305c`) via `git checkout origin/main --
scripts/release.sh`.

- **Migration count: 38** — identical to the deployed baseline, zero new
  migrations, zero M010.
- **Full diff vs `ad996bf`: exactly 10 files** (`b39eee9` vs `ad996bf`),
  all compose/requirements/docs/shell-script — zero application code,
  zero migration files.
- `requirements.txt` confirmed: `certifi==2026.10.19`, `pillow==13.0.0`,
  `gunicorn==26.2.0` unchanged.

## 3. Candidate image build and identity

- **Image:** `infosecurs-release:b39eee9244e56f17bc4aa32904dd1b8def6286ac`
- **Image digest:** `sha256:b308cb77a7c16e12700f01daed97daf020779385cc6fb75937b122d0019c4b59`
- **OCI revision label** confirmed via `docker inspect` to equal
  `b39eee9244e56f17bc4aa32904dd1b8def6286ac` exactly.
- Installed package versions inside the image independently confirmed
  (not just the label): `certifi 2026.10.19`, `pillow 13.0.0`,
  `gunicorn 26.2.0`.

## 4. Security verification — hashes, vulnerability scan, and scope of findings

- **Hash verification:** `requirements.txt` pins every dependency with
  `--hash=sha256:...`. `pip download --no-deps --require-hashes` was run
  inside the candidate image against the certifi/Pillow requirement
  entries (and, incidentally, their full transitive set, since the
  extraction pattern matched a broader block) — result:
  `Successfully downloaded [...] certifi [...] pillow [...]` with no hash
  mismatch for any package in scope. `pip`'s own hash verification aborts
  loudly and downloads nothing on any mismatch, so a clean
  "Successfully downloaded" result is conclusive.
- **Vulnerability scan:** `pip-audit --strict` run inside the built
  candidate image. **Zero vulnerabilities reported for `certifi` or
  `pillow`** — confirms the fix is effective at the installed-package
  level, not just the requirements-file level.
- **Two pre-existing, out-of-scope findings surfaced by the same scan**
  (not introduced or worsened by this release): `pip` 25.0.1 (base-image
  bundled, not pinned by this project at all) and `pypdf` 6.19.0 (5 CVEs,
  pinned in `requirements-dev.txt`). Both confirmed present, unchanged,
  at the historical `ad996bf` baseline already — i.e. they predate this
  PID entirely. Recorded as a **distinct, separately-tracked open
  finding** (`docs/evidence/DBR-001-BETA-PIP-PYPDF-PREEXISTING-VULNS-FINDING.md`)
  rather than folded into or blocking this dependency-only release, per
  the same scope discipline already applied to the dev-mode/plain-HTTP
  finding.

## 5. Release-script smoke-check fix — proven against a LAN-bound port

The original cutover's smoke check hard-coded `127.0.0.1`, which does not
reach a container whose compose file binds its host port to a specific
LAN IP (as `docker-compose.cutover.yml` does deliberately, to preserve
the real Beta's access route) — this produced a false-negative exit
during the original cutover (`docs/evidence/DBR-001-CUTOVER-COMPLETION.md`
§3.1). The fix, now carried onto this candidate, derives the host/port
from the actual container's published port binding instead.

**Proven, not just code-reviewed**, using a disposable equivalent (no
real Beta containers touched): a throwaway `python:3.12.14-slim-trixie`
container was run with `-p 192.168.11.10:18899:8000` — the same LAN-IP
binding pattern as the real Beta — and the fixed script's exact
derivation commands were run against it:

```
Derived HEALTH_HOST=192.168.11.10 HEALTH_PORT=18899
Probing derived URL: http://192.168.11.10:18899/
HTTP_STATUS=200
```

For direct contrast, probing the same container via the **old**
hard-coded-loopback assumption reproduced the original failure exactly:

```
OLD_HARDCODED_LOOPBACK_STATUS=000
```

The disposable container was stopped and removed (`--rm`); confirmed no
residue.

## 6. Runtime configuration, volumes, access route, database, ClamAV — unchanged

`git diff` between the already-deployed SHA
(`0bce2555e0a6b9eec4d6dc645ac606f8d7309285`) and this candidate
(`b39eee9244e56f17bc4aa32904dd1b8def6286ac`) on every compose/runtime file
(`docker-compose.cutover.yml`, `docker-compose.release.yml`,
`docker-compose.yml`, `docker-compose.override.yml`) is **byte-identical,
zero lines changed**. This release touches only dependency pins and the
release tooling itself — it cannot alter port bindings, volume mounts,
the database service, or the ClamAV service, because none of the files
that define them differ at all from the already-verified, already-live
baseline.

## 7. Backup and rollback readiness; migration plan

- `scripts/backup.sh` and `scripts/rollback.sh` are **byte-identical**
  between the deployed baseline and this candidate (zero diff) — the
  exact same scripts already proven functional against the real
  `infosecurs-relocation` stack during the original cutover's P4 gate
  (fresh backup taken and checksum-verified; rollback dry-run resolved
  cleanly against the real legacy config).
- The current release manifest (`releases/infosecurs-relocation/current.json`,
  held in the cutover worktree, gitignored by design) records
  `"migration_applied": false` for the currently-live release — meaning
  `scripts/rollback.sh` remains auto-eligible to roll back a future
  release from this candidate without any manual override, exactly as
  designed, since this candidate also applies zero migrations.
- **Migration plan:** a read-only `python manage.py migrate --plan` was
  run against the **live** database using the candidate image —
  `No planned migration operations.` — independently re-run and confirmed
  by the fresh auditor in §9 below (not merely read from this document).

## 8. Transient Trinity `.env` copy — assessed and contained

During preparation, a copy of the real `/srv/infosecurs/.env` was
briefly written to a local file on the Trinity host's session scratchpad
(not dell-debian) via an `ssh ... cat` redirection, before the standing
discipline of keeping secrets confined to dell-debian was correctly
applied for the rest of this work. This was caught immediately in the
same operation:

- The file's **contents were never displayed, echoed, or printed** in any
  command output, transcript, or log — the redirection captured the
  content silently; only a line count (`26`) was ever shown.
- The file was deleted within the same operation, and its absence was
  explicitly verified (`ls` → "No such file or directory") before any
  further action.
- A subsequent filesystem-wide check of the Trinity scratchpad directory
  confirms no file of that specific name remains, and no bash history
  entry references displaying its content.
- No credential value from that file was ever reproduced in any
  document, commit, PR body, or audit artifact — this document itself
  contains none.
- All subsequent `.env` handling for this preparation (the read-only
  migration-plan check in §7/§9) was performed correctly: copied and
  deleted entirely within dell-debian, never transiting to Trinity,
  confirmed removed both by this preparation and independently by the
  fresh auditor.

**Assessment: contained. No credential exposure occurred.** The lapse was
procedural (a secret briefly touched the wrong host) rather than a
disclosure (nothing was ever shown, retained, or transmitted further).

## 9. Independent audit

A fresh agent, with no memory of this preparation, independently
re-derived every claim above directly from the repository and the live
host — not from this document's claims about them. It independently
re-ran the migration-plan check itself (not trusting this document's
transcript of it), inspected installed package versions inside the image
directly, confirmed the base/history divergence from `main`, content-diffed
each cherry-picked commit against its `main` original, and confirmed no
stray `.env` copy exists anywhere on dell-debian outside `/srv/infosecurs`
itself.

**Verdict: GREEN.** All claims independently confirmed. One
documentation-precision nuance was raised and resolved: the candidate SHA
`b39eee9` (what was actually built, labelled, and checked) sits one
commit behind this branch's own HEAD once its preparation document is
itself committed — a self-referential offset, not a discrepancy, and now
stated explicitly on the release branch's own copy of the preparation
record.

## 10. Live-release GO/NO-GO package — summary for Central Architecture

| Check | Result |
|---|---|
| certifi/Pillow fixes present, hash-valid | ✅ `certifi==2026.10.19`, `pillow==13.0.0`; hash-verified download, zero mismatches |
| Independent vulnerability scan | ✅ zero vulnerabilities in certifi/pillow; 2 pre-existing out-of-scope findings recorded separately (§4) |
| Release-script smoke-check fix | ✅ proven against a disposable LAN-bound-port container; reproduces the original failure under the old logic, succeeds under the new |
| Historical app, 38 migrations, no M010 | ✅ confirmed in source tree and independently inside the built image |
| Runtime config/volumes/access route/db/ClamAV unchanged | ✅ byte-identical compose files vs. deployed baseline |
| Backup/rollback readiness | ✅ unchanged, already-proven scripts; manifest chain remains auto-rollback-eligible |
| Migration plan | ✅ empty, independently re-confirmed against the live DB |
| Trinity `.env` transient copy | ✅ assessed, contained, no exposure (§8) |
| Independent audit | ✅ GREEN (§9) |

**GUNNAR recommendation: ready for live-release authorisation.**
**No deployment will be executed without Central Architecture's separate,
explicit GO.**
