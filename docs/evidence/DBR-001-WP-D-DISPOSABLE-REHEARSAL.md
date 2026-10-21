# PID-DBR-001 Work Package D — Disposable-Stack Rehearsal Evidence

**Author:** FORGE Implementer (Engineer), WP-D dispatch.
**Worktree:** `/srv/openclaw/worktrees/wo/DBR-001-wp-d` on `dell-debian`, detached at
`c47c4c4c2beb779abb49152912dadda4c0a4b1b2` (branch `wo/DBR-001-release-base-ad996bf`
— `ad996bf` + WP-A/B/C release-mechanism hardening only; no M010, no certifi/pillow
bump). Not current `main`.
**Scope:** `docs/work-orders/WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md` §3.1–§3.3 —
the mandatory disposable-stack rehearsal that must pass (and be independently
audited, §3.4) before any cutover of the real `infosecurs-relocation` stack can
even be requested. This document records what was actually run and observed; it
is not a restatement of the WO's own claims.

All disposable stacks and the throwaway git clone created for this rehearsal were
torn down before this document was written; `infosecurs-relocation-*` (the real
persistent Beta) was never stopped, started, or modified — confirmed by uptime
continuity (`infosecurs-relocation-db-1` showed `Up 8 days` both before and after
this dispatch).

---

## §3.1 — Disposable-stack rehearsal build

Project name: `dbr001-release-rehearsal`. Ports: web `18900` (plain HTTP, loopback),
TLS smoke `18902` (loopback), Postgres `18901` (loopback). Env file: `.env.release`
(gitignored, removed at teardown) — `DJANGO_ENV=production`, synthetic secrets.

**Run 1 — against a fresh, unmigrated DB** (`bash scripts/release.sh
dbr001-release-rehearsal .env.release c47c4c4c2beb779abb49152912dadda4c0a4b1b2`):
built `infosecurs-release:c47c4c...` (OCI revision label matched the requested
SHA), brought up `db`/`clamav`, then Step 2 (`migrate --plan`) printed the full
73-operation plan (38 custom-app migrations + 35 Django/third-party-app
migrations) and **refused to proceed**, exiting 1, exactly as designed:

```
Plan is NOT EMPTY (see full plan printed above).
Refusing to proceed automatically (WO Sec2 row 2 - no auto-approval
of a migration plan). ...
STOPPING before any apply or container swap. Old 'web' container,
if any, is untouched and still serving.
```

Confirmed by re-running with output captured: `EXIT_CODE=1`; `docker compose ...
ps` at that point showed only `db`/`clamav` running, no `web` container existed yet.

**Migrated directly** (not via `RELEASE_APPLY_MIGRATIONS=1` — per dispatch
instruction, to exercise the "operator migrates outside the mechanism, then the
mechanism detects the now-clean state" path): `docker compose ... run --rm
--no-deps web python manage.py migrate --noinput` — all 73 migrations applied OK.
`showmigrations --plan | grep -c '\[X\]'` → `73`. Custom-app migration file count
on disk (`find . -path '*/migrations/*.py' ! -name '__init__.py'`) → `38` —
matches the incident record's "Live `django_migrations` (73 rows) matches
`ad996bf`'s 38 custom-app migration files 1:1" exactly.

**Run 2 — re-running `scripts/release.sh`** with the DB now migrated: Step 2 plan
was empty (`No planned migration operations.`), Step 3 skipped, Step 4 swapped in
the new `web` container. Verified running-container facts the script itself
checked and printed:

- `Config.Cmd`: `sh -c "python manage.py collectstatic --noinput && exec gunicorn
  config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4
  --worker-class gthread ..."`
- Running processes (`docker top`): three `gunicorn` processes (1 master + 2
  workers), **no** `runserver`, **no** `StatReloader`.
- `Mounts`: only `infosecurs_release_evidence_data` and
  `infosecurs_release_questionnaire_data` named volumes — **no `/app` bind mount**
  (the script's own check `grep -q '"Destination":"/app"'` would have failed the
  release if one existed; it passed).
- Health check: `GET http://127.0.0.1:18900/healthz/ -> HTTP 301` — the
  already-documented, already-accepted `DJANGO_ENV=production` +
  `SECURE_SSL_REDIRECT=True` + no `SECURE_PROXY_SSL_HEADER` result (script
  comment/PID §15/§F); treated as `pass-with-note`, matching the script's own
  design, not a weakening of anything for this rehearsal.
- Release manifest written to `releases/dbr001-release-rehearsal/<sha>-<ts>.json`
  recording `migration_plan_was_empty: true`, `migration_applied: false`,
  `image_digest: sha256:e759c6cb...`, real `container_mounts`/`container_command`.

**To get a genuine 200-over-HTTPS proof of a real page** (used for §3.2 below),
the existing `scripts/release_tls_smoke_wrap.py` mechanism was started inside the
running `web` container (a throwaway self-signed cert generated with `openssl
req -x509 ...`, `docker cp`'d in, then `docker compose exec -d ... web python
scripts/release_tls_smoke_wrap.py` — exactly the documented, pre-existing
invocation, no product code touched). `curl -sk https://127.0.0.1:18902/healthz/`
→ `200`; `.../accounts/login/` → `200`, title `Log in — Infosecurs`.

**Finding (wrinkle, not a defect):** `docker-compose.release.yml`'s `web` service
declares `env_file: - .env.release` as a **literal path**, independent of the
`ENV_FILE` argument passed to `scripts/release.sh` (which only governs Compose's
`--env-file` CLI flag for `${...}` interpolation, e.g. `${POSTGRES_DB}`). The
first attempt at this rehearsal used an env file named `.env.release.wpd` as the
script argument and got `env file .../.env.release not found` from inside the
`web` container build — the literal file genuinely has to be named `.env.release`
at the project root regardless of what's passed to the script. This mirrors the
exact wrinkle `scripts/restore.sh`'s own header comment documents for
`docker-compose.yml`'s `web` service and its literal `.env` — it is not unique to
this rehearsal, it is how both Compose files are written. Not a STOP; documented
so the next operator doesn't lose time on it.

---

## §3.2 — The negative test

**Baseline, recorded before the git operation:**
- Web container image ID: `sha256:e759c6cbb54099e712e720babe6a54e6fe6e70cd28288518bd0d7fc9106e1b59`
- Mounts: evidence + questionnaire named volumes only, no bind mount (as above)
- `curl -sk https://127.0.0.1:18902/healthz/` → `200`; login page → `200`,
  `sha256sum` of the rendered HTML: `e7bb2dfd2da963bd2b18068f546b838759b982abc799d41f2d4a6ba81580ad26`

**The git operation**, in a genuinely separate clone
(`git clone --no-local --origin local-source /srv/openclaw/worktrees/wo/DBR-001-wp-d
/tmp/dbr001-wpd-devclone-scratch/infosecurs-devclone` — not this worktree, not
`/srv/openclaw/gunnar-dev/infosecurs`, not `wp-abc`): at `2026-10-21T17:18:45.4Z`,
`git checkout -b negative-test-main-checkout local-source/main` — an ordinary
branch-switch, changing **188 files** on disk including
`questionnaire/upload_handler.py` (the exact file whose change triggered the
2026-10-19 incident's autoreload). Confirmed via `git diff --stat` beforehand
(21,982 insertions / 896 deletions across 188 files) and `stat` on
`upload_handler.py` showing its new mtime at `18:18:45` local time.

**Observation immediately after** (`2026-10-21T17:18:54.7Z`, ~9 seconds later):
- Web container image ID: **unchanged** — `sha256:e759c6cbb54099e712e720babe6a54e6fe6e70cd28288518bd0d7fc9106e1b59`
- Mounts: **unchanged** — still only the two named volumes, no `/app` path of any
  kind exists on this container to be affected by any clone's filesystem
- `docker inspect ... .State.StartedAt`: `2026-10-21T17:17:12Z` — **predates** the
  git operation; the container was never restarted
- Health check: `200`; login page: `200`, byte-identical except for the
  per-request CSRF token (expected — a fresh random token every render, not a
  sign of change); page title, structure, every other byte unchanged
- Container logs: gunicorn worker-boot lines all timestamped `17:17:1x`, before
  the git operation; **zero** autoreload/"changed, reloading" lines of any kind
  (there is no `StatReloader` process in this container at all — gunicorn has no
  such mechanism)

**Conclusion:** the rehearsal stack's served code and behaviour were completely,
measurably unaffected by the git operation in the separated clone — because,
unlike the 2026-10-19 incident's `volumes: - .:/app`, there is no bind mount of
any kind from any git working tree into this container. This is the direct,
falsifiable antidote WO §1.9/§3.2 require, not an assertion.

---

## §3.3a — Fresh-install-from-zero migration run

`docker compose -p dbr001-release-rehearsal ... down -v` (full teardown including
the Postgres volume) → `up -d db clamav` → confirmed genuinely empty:
`showmigrations --plan | grep -c '\[X\]'` → `0`.

Ran the full migration graph **directly** via `manage.py migrate --noinput`
(chosen over re-running `scripts/release.sh` for this specific check, since
`release.sh`'s own job is sequencing an *existing-stack* release, not a bare
greenfield install — documented here as the explicit choice the dispatch left to
the implementer). Result: **73/73 migrations applied, exit code 0**, zero errors.
Post-run `migrate --plan` → `No planned migration operations.`; `showmigrations
--plan` → `73` applied; migration-file count on disk → `38` custom-app files,
matching exactly.

---

## §3.3b — Backup/restore cycle

**Genuine ambiguity found and resolved (flagged, not papered over):**
`scripts/backup.sh` and `scripts/restore.sh` are both hard-wired to the plain
`docker-compose.yml` (dev/bind-mount shape) — `backup.sh` literally checks
`[ -f docker-compose.yml ]` and calls bare `docker compose ...` with no `-f`
flag and no project-name parameter at all (relying on ambient `.env`/
`COMPOSE_PROJECT_NAME`/directory-name project resolution); `restore.sh` takes
`PROJECT_NAME`/`ENV_FILE` but still calls `docker compose -p ... --env-file ...`
with no `-f`, i.e. the same implicit-`docker-compose.yml` default. Neither script
accepts a compose-file argument, and `restore.sh`'s own `web`-env swap trick is
explicitly written for `docker-compose.yml`'s literal `env_file: .env` directive,
not `docker-compose.release.yml`'s `env_file: .env.release`. Pointing them at the
release-shaped stack without modifying them is not straightforwardly possible —
the WO text ("§3.3 ... on the rehearsal stack") doesn't anticipate this, and
modifying the scripts was explicitly out of scope for this dispatch.

**Resolution taken:** ran both scripts exactly as designed/documented (the same
way `docs/runbooks/BACKUP-RESTORE.md`'s own M006 Round 5 precedent did), against
a **separate disposable dev-compose-shaped stack** at this worktree's own commit
and 38/38 migration graph, seeded with real representative data via the
purpose-built, already-existing `core/management/commands/
seed_backup_restore_fixture.py` (one organisation, one evidence file, an
approved `PolicyVersion` that superseded an earlier approved one, an accepted
`QuestionnaireResponse` that superseded an earlier accepted one, a scanned
`QuestionnaireImport`). Driven via `COMPOSE_PROJECT_NAME=dbr001-bkrestore-src` in
a literal `.env` at the worktree root (standard Compose env-var override, not a
script modification) — ports `18910`/`18911`, loopback-only.

**Backup** (`bash scripts/backup.sh backups/dbr001-wpd-bktest`): stopped `web`
(quiesce), `pg_dump`'d, archived both volumes, restarted `web`, wrote manifest
with SHA-256 checksums of all three artifacts. Pre-backup, on-disk bytes
independently hashed and matched the DB-recorded checksums:
- Evidence: `29c1b4fc...` (both DB column and on-disk `sha256sum`)
- Questionnaire import: `2f91503b...` (both DB column and on-disk `sha256sum`)

Backup sanity: dump has 44 `CREATE TABLE` paired with 44 `COPY` (no truncation);
both `.tar.gz` archives pass `gzip -t`.

**Restore** (`bash scripts/restore.sh backups/dbr001-wpd-bktest dbr001-bkrestore-dst
.env.bkrestore-dst` — a genuinely fresh, separate project, ports `18912`/`18913`,
never the source project): checksums verified against manifest before touching
anything; fresh `db` brought up; dump restored; both volumes un-tarred; `web`
brought up and `migrate --noinput` → **"No migrations to apply."** — the
schema-compatibility proof the runbook asks for.

**Full §14 verification checklist, run against the restored stack:**

| Check | Result |
|---|---|
| App starts, health 200 | `curl http://127.0.0.1:18912/healthz/` → `200` |
| Migrations/schema compatible | `migrate --noinput` → "No migrations to apply." |
| Org/record restored | `Organisation` row present, name matches |
| Evidence bytes/checksum identical | restored on-disk `sha256sum` `29c1b4fc...` == source's pre-backup value (compared directly, not re-hashed-only) |
| Policy history intact | 2 `PolicyVersion` rows: one `superseded`, one `approved` |
| Questionnaire history intact | 2 `QuestionnaireResponse` rows: one `superseded`, one `accepted` |
| Questionnaire import bytes/checksum (M009A) | restored on-disk `sha256sum` `2f91503b...` == source's pre-backup value, == `QuestionnaireImport.sha256_hash` DB column on the restored stack |

All seven checks passed with real, directly-compared values — not restatements.

---

## Rollback-safety statement for THIS release (WO §2 row 4 / §1.8)

**This release's own manifest:** `migration_plan_was_empty: true`,
`migration_applied: false` — a pure topology/container change against the schema
exactly as it stands, per the WO's own "migration default" for its initial
repair. By WO §2 row 4's text alone, a release that applied no migration is
exactly the case `scripts/rollback.sh` claims to handle automatically (no
`ROLLBACK_FORCE_AFTER_MIGRATION` needed) — and this rehearsal **directly
exercised and confirmed that specific mechanics**: run `rollback.sh` after a
*second* release under the same project (so a real `previous.json` existed) →
it read `migration_applied=False`, required no force flag, stopped the current
container, started the previous image, re-ran the health smoke, and swapped the
pointer files — **exit 0, genuinely observed, not assumed**.

**However — a concrete, falsifiable finding that changes the practical answer
for the *actual* first cutover of the real stack:** `scripts/rollback.sh` has no
notion of "roll back to whatever was running before this mechanism existed" — it
only rolls back to the image/state recorded in a *prior `scripts/release.sh`-
written* `previous.json`. Run immediately after this rehearsal's **first**
release (before any second release existed under the project), `rollback.sh`
refused outright:

```
error: previous.json has no recorded image_tag (this project's prior state
predates scripts/release.sh, or is itself the first release) - nothing to
roll back to
```

The real `infosecurs-relocation` stack's *actual* initial cutover under this
mechanism **is** exactly that "first release" case — the currently-deployed
`ad996bf` container was never brought up via `scripts/release.sh`, so there is
**no `previous.json` for it**, and `scripts/rollback.sh` will refuse identically
if invoked right after the real cutover's first release. **A container-only
rollback via `scripts/rollback.sh` is not actually available, automatically, for
this specific first release of the real stack** — not because the release is
unsafe (it is expand-only/no-migration, genuinely qualifying under WO §2 row 4
and the "expand/contract discipline" section), but because the tool's own
rollback-target bookkeeping starts empty. The safe recovery path for *this one*
cutover, if the post-cutover smoke (§3.6) fails, is a **manual** step an operator
must perform directly (`docker stop`/re-run the old `docker-compose.yml`-based
`infosecurs-relocation` stack from its own already-known-good state, or rebuild
and re-deploy the exact prior image by hand) — not `scripts/rollback.sh` as-is,
until a second release has been run under the mechanism and a real
`previous.json` exists. This is a genuine WO-text gap (§2 row 4 describes the
*general* container-only-rollback safety property; it does not separately
address the *bootstrap* case of the mechanism's own very first use against a
stack it did not originally deploy) and should be flagged to Central
Architecture/the independent §3.4 audit explicitly, not silently assumed covered.

For any future release of the real stack **after** this first one, once a real
`previous.json` exists, the demonstrated mechanics above (migration_applied
read, force-flag gate, pointer-file swap) apply exactly as designed and were
directly exercised and proven working in this rehearsal.

---

## Teardown

All three disposable Compose projects (`dbr001-release-rehearsal`,
`dbr001-bkrestore-src`, `dbr001-bkrestore-dst`) torn down with `down -v`
(containers, networks, and all named volumes removed); built images
(`infosecurs-release:c47c4c4c...`, `dbr001-bkrestore-dst-web`) removed; the
throwaway git clone (`/tmp/dbr001-wpd-devclone-scratch`) removed; all `.env*`
files and the `releases/`/`backups/` directories created in the worktree during
this rehearsal removed. `git status --short` in the worktree is empty.
Post-teardown `docker ps` shows no container matching `dbr001|bkrestore|
release-rehearsal|devclone`; `infosecurs-relocation-db-1` shows the same
multi-day uptime continuity as before this dispatch began — it was never
touched.
