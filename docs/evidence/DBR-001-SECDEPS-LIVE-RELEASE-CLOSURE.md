# PID-DBR-001 — Security-Only Dependency Live Release: Execution and Closure

**Status: EXECUTED AND CLOSED GREEN.** Central Architecture issued
conditional live-release authorisation for source SHA
`b39eee9244e56f17bc4aa32904dd1b8def6286ac` against `infosecurs-relocation`
(`192.168.11.10:8884`), gated on a mandatory execution preflight. This
document is the durable record of that preflight, the execution itself,
immediate post-release verification, and an independent fresh-agent
re-verification of the live result.

## 1. Authorisation

Central Architecture authorised the live release of
`b39eee9244e56f17bc4aa32904dd1b8def6286ac` (the certifi/Pillow
security-dependency candidate; see
`docs/evidence/DBR-001-NEXT-RELEASE-SEC-DEPS-PREP.md`), conditional on:
PR #126 merged as a two-parent merge with its seven checks GREEN; a
mandatory execution preflight against a clean detached checkout at the
exact candidate SHA; and an explicit prohibition on merging the separate
historical release branch (`wo/DBR-001-release-base-secdeps`) into `main`.

## 2. PR #126 merge confirmation

- **Head:** `d845ffec78ebee3c7985fecf39f67f28baaa65f6`
- **All seven checks GREEN:** `CodeQL`, `ci/integration` (18m42s), `ci/unit`
  (3m46s), `security/container`, `security/dependencies`, `security/sast`,
  `security/secrets`.
- **Merge:** two-parent merge commit `1024b2e9a4d0470cbc54db732deaae64f68cb440`
  (parents `7121305c23c988237f5aaec0327e3c5659995c86` and
  `d845ffec78ebee3c7985fecf39f67f28baaa65f6`, confirmed via
  `git log -1 --format="%H %P"`).
- The separate historical release branch (`wo/DBR-001-release-base-secdeps`)
  was **not** merged into `main` — an earlier attempt (PR #125) was closed
  unmerged after GitHub itself reported `CONFLICTING` merge status,
  confirming that branch's deliberate divergence from `main`.

## 3. Mandatory execution preflight (all passed, before any swap)

- **Clean detached checkout** at exactly `b39eee9244e56f17bc4aa32904dd1b8def6286ac`
  (worktree `/srv/openclaw/worktrees/wo/DBR-001-secdeps-execution`), not the
  evidence-branch HEAD — confirmed via `git rev-parse HEAD` and a clean
  `git status`.
- **Historical application + migrations reconfirmed** at this exact SHA:
  38 migration files, zero referencing M010; full diff vs `ad996bf` exactly
  10 files, all compose/requirements/docs/shell-script, zero app code.
- **Pre-swap live-stack snapshot:** web `infosecurs-relocation-web-1`
  (container `9ff0c4a6b0ae...`, image digest `sha256:8492c8e1b078...`,
  port `192.168.11.10:8884->8000`); db (container `2cce06b581ae...`,
  `StartedAt 2026-10-13T09:11:14.46159067Z`, port `127.0.0.1:15432->5432`);
  clamav (container `4996ddd0f1c2...`, `StartedAt 2026-10-13T09:11:14.460577307Z`,
  no host port). All four named volumes confirmed:
  `infosecurs-relocation_infosecurs_postgres_data` (db),
  `_evidence_data`/`_questionnaire_data` (web), `_clamav_data` (clamav).
- **Fresh quiesced backup taken** (`/srv/infosecurs/scripts/backup.sh`,
  byte-identical to the candidate's copy): DB dump, evidence archive,
  questionnaire archive, manifest at
  `/srv/infosecurs/backups/backup-20261022T171101Z/`. All three SHA-256
  checksums independently recomputed and matched the manifest exactly;
  both `.tar.gz` archives passed `tar tzf` structural validation. The
  backup's own stop/start cycle left `db`/`clamav` container IDs and
  `StartedAt` timestamps unchanged — only `web` was quiesced, as designed.
- **Existing durable release history located and reused, not reinitialised:**
  `/srv/openclaw/worktrees/wo/DBR-001-cutover-release/releases/infosecurs-relocation/`
  (containing the original cutover's `current.json`/`previous.json`/dated
  manifest) was passed explicitly as `RELEASES_DIR` to this execution, so
  the new release correctly extends that same history rather than starting
  a fresh, empty one.
- **Previous image and manual fallback confirmed operationally recoverable**
  before the swap: both `infosecurs-release:0bce2555e0a6b9eec4d6dc645ac606f8d7309285`
  and the original legacy pre-cutover image (`infosecurs-relocation-web`)
  present, not pruned.
- **Rollback script's remaining loopback-only limitation accounted for
  explicitly before execution:** `scripts/rollback.sh` still hard-codes
  `http://127.0.0.1:${WEB_HOST_PORT}${HEALTH_PATH}` (only `scripts/release.sh`
  was fixed, not `rollback.sh`). Any future rollback invocation against
  `docker-compose.cutover.yml`'s LAN-bound port will likely report a
  misleading `HTTP 000` regardless of whether the restore actually
  succeeded — the exact same false-negative class already documented for
  the old `release.sh`. This is accounted for, not fixed, per Central
  Architecture's explicit instruction; any future rollback must be verified
  manually against the real bound address, never trusted from the script's
  own smoke-check exit status alone.

## 4. Execution

`RELEASE_IMAGE=infosecurs-release:b39eee9244e56f17bc4aa32904dd1b8def6286ac
COMPOSE_FILE=docker-compose.cutover.yml
RELEASES_DIR=/srv/openclaw/worktrees/wo/DBR-001-cutover-release/releases/infosecurs-relocation
scripts/release.sh infosecurs-relocation .env.cutover b39eee9244e56f17bc4aa32904dd1b8def6286ac`

One operational note: the compose file's `env_file:` directive hard-codes
the literal filename `.env.cutover` (not parameterised), so the working
env-file copy had to be named exactly that — an initial attempt using a
differently-named copy failed harmlessly at the migration-plan step
(before any container was touched) and was corrected by renaming the file.

- **Build:** fresh image built with a new build timestamp, as expected —
  the image digest legitimately differs from the one recorded at
  preparation time. **Actual built/deployed image digest:**
  `sha256:6c957dc896cbb34f6bc3e080fc8b30ad731414e9d63c14f52a4b29069eb3198e`.
  **OCI revision label independently confirmed** to equal
  `b39eee9244e56f17bc4aa32904dd1b8def6286ac` exactly — the deployed
  artifact is provably built from the authorised source, regardless of
  the digest difference.
- **Migration plan:** empty (`No planned migration operations.`) — apply
  step skipped entirely, exactly as designed.
- **Swap:** only the `web` container was stopped and recreated. `db` and
  `clamav` were confirmed `Running` (no recreate) both before and after.
- **Smoke check:** `GET http://192.168.11.10:8884/healthz/ -> HTTP 200`
  — the corrected script resolved the real LAN-bound address natively
  this time; no false negative, no manual-fallback note was needed
  (contrast with the original cutover, whose manifest for this same
  mechanism explicitly records the pre-fix failure).

## 5. Immediate post-release verification

- **Live image:** container `ca1d510c9b48ff711e3c4e83f9217167330a7a686e301d6678b53e3e9ee95f36`,
  image digest `sha256:6c957dc896cbb34f6bc3e080fc8b30ad731414e9d63c14f52a4b29069eb3198e`,
  OCI revision label `b39eee9244e56f17bc4aa32904dd1b8def6286ac` — exact match.
- **certifi/pillow inside the running container:** `certifi==2026.10.19`,
  `pillow==13.0.0` — confirmed via `pip show`.
- **Runtime:** gunicorn only (3 processes), no Django dev server, no
  `/app` bind mount (only the two named data volumes plus the read-only
  secret bind).
- **db/clamav continuity:** container IDs and `StartedAt` timestamps
  (`2026-10-13T09:11:14.46159067Z` / `.460577307Z`) identical to the
  pre-swap snapshot — neither was restarted or recreated by this release.
- **Four named volumes:** unchanged, no new/duplicate volume.
- **Functional smoke:** `/` → 302 to `/accounts/login/` (`Server: gunicorn`);
  `/accounts/login/` → 200, real rendered form, CSRF token present;
  a WhiteNoise-served static asset → 200; a Foundations-journey route
  (`/organisations/<real-uuid>/foundations/`) → 302 to login — same
  pre-existing auth-redirect behaviour, not broken by this release (an
  initial check using a non-UUID placeholder ID produced a benign
  URL-routing 404, corrected by using a real organisation UUID).
- **Data integrity:** 17 users, 15 organisations — unchanged.
- **Migrations:** `showmigrations --plan` — 73 applied, 0 pending.
- **Release manifest reconciliation:** `current.json`'s `container_id`
  and `image_digest` match the live running container/image exactly;
  `previous.json` correctly holds the prior release
  (`0bce2555e0a6b9eec4d6dc645ac606f8d7309285`, timestamp `20261022T100535Z`)
  — a genuine two-entry chain, not a freshly-initialised empty history.
- **Rollback resources preserved:** both
  `infosecurs-release:0bce2555e0a6b9eec4d6dc645ac606f8d7309285` and the
  original legacy image remain present, not pruned.

## 6. Independent post-release audit

A fresh agent, with no memory of this execution, independently re-derived
all of the above directly against the live host — not from this
document's claims. It re-ran the image-label check, the certifi/pillow
version check, the db/ClamAV continuity check (byte-for-byte identical
container IDs/timestamps), the four-volume check, the full functional
smoke suite (including independently pulling a real organisation UUID
itself), the data-integrity ORM queries, the migration-state check, and
read the manifest files directly from their durable location on
dell-debian.

**Verdict: GREEN — all 13 independently-checked items confirmed, zero
defects, zero regressions.** It additionally confirmed, from the
manifest's own content, that the smoke-check fix demonstrably took effect
in this release (`current.json` records a clean automated
`"health_check_result": "pass"`, with no manual-fallback annotation,
unlike `previous.json`'s record of the original cutover's false-negative).

## 7. Known findings — explicitly not affected by this release

This release changed only `certifi`, `pillow`, and the release-script
smoke-check. It did **not** fix, touch, or waive any of the following,
which remain open, separately tracked items:

- `docs/evidence/DBR-001-BETA-DEVMODE-PLAINHTTP-FINDING.md` — dev-mode
  config, plain HTTP, Customer Zero reset flag.
- `docs/evidence/DBR-001-BETA-PIP-PYPDF-PREEXISTING-VULNS-FINDING.md` —
  pre-existing `pip`/`pypdf` vulnerabilities.

## 8. Closure

Per Central Architecture's authorisation: the security-only certifi/Pillow
release is **executed, independently verified, and CLOSED GREEN.** No
database migration, M010 functionality, customer-data reset, credential
change, or runtime security-configuration change occurred. All findings
listed in §7 remain open and are not implicitly resolved by this closure.
