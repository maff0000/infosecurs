# Backup / Restore Runbook

**PID:** `docs/pids/M006-CUSTOMER-ZERO-BETA-HARDENING.md` §14.
**Scope:** operator-facing backup and restore of a single Infosecurs Beta
Docker Compose stack (`docker-compose.yml` — `db` + `web`). Not a
monitoring/DR platform (PID §13 "do not build a monitoring platform"
applies here in spirit too) — this is the small, direct recovery path PID
§14 requires: PostgreSQL data + private evidence storage, tested by an
actual restore into a fresh disposable stack.

Tooling: `scripts/backup.sh` and `scripts/restore.sh`, built on established
PostgreSQL/Docker/archive tooling only (`pg_dump`, `docker compose`, `tar`,
`sha256sum`) — no bespoke backup format, no new Python management command.

Every command and result below was actually run against a real disposable
Docker Compose stack on dell-debian during the M006 Round 5 dispatch
(source project `m006r5source`, ports `19802`/`19434`; restore-target
project `m006r5restore1`, ports `19803`/`19435` — never the canonical
`infosecurs-relocation` deployment on `18800`/`15432`, and never any other
stack `docker ps` showed running at the time). See
`docs/evidence/M006-BACKUP-RESTORE.md` for the full evidence write-up with
real command output.

---

## When to run a backup

Before anything that could destroy or corrupt data on a Beta/Customer-Zero
stack you care about (a risky migration, a manual DB operation, before
decommissioning a host, or just as a periodic Beta-stage safety net). PID
§14 explicitly allows quiescing writes for Beta, so a backup briefly stops
the `web` service — plan for a short (seconds-to-low-minutes, depending on
data volume) write-unavailability window.

## Running a backup

From the project root, with the stack already up (`docker compose up -d`)
and a real `.env` in place:

```bash
scripts/backup.sh [OUTPUT_DIR]
```

`OUTPUT_DIR` defaults to `backups/backup-<UTC timestamp>/` under the
project root. Each run produces one self-contained backup "set" in that
directory:

```text
db-<POSTGRES_DB>-<timestamp>.sql     logical pg_dump of the database
evidence-<timestamp>.tar.gz          full contents of the infosecurs_evidence_data volume
manifest-<timestamp>.json            source SHA / timestamp / filenames / checksums
```

What it does, in order:

1. Stops `web` (quiesces writes — `db` keeps running).
2. Runs `pg_dump` against `db` for the database named by `POSTGRES_DB` — a
   **logical** dump, not a physical/`pg_basebackup` copy, per PID §14.
3. Archives the real `infosecurs_evidence_data` named volume's contents
   via `docker compose run` against the `web` service definition (so the
   *actual* volume Compose created for this project is read — never a
   guessed name, never the git working copy's own bind-mounted `/app`).
4. Restarts `web` (this happens as soon as both archives are safely
   written — not only in a failure-path cleanup — so the app is back up
   as quickly as possible either way).
5. Writes the manifest with SHA-256 checksums of both archives.

**Credential handling (hard PID requirement — "No credentials in
manifests"):** `scripts/backup.sh` never reads `POSTGRES_PASSWORD` at all.
The `db` container already has it as its own environment variable (set by
`docker-compose.yml` from `.env` when the stack came up); the script asks
that container to export its own `POSTGRES_PASSWORD` as `PGPASSWORD` for
the `pg_dump` process it runs *inside itself*. The value never reaches this
host script, is never assigned to a host shell variable, never appears in
a filename, and is never printed by anything this script does. Verified by
grepping every file the backup produced for the throwaway password value
used during this dispatch and finding zero matches (see evidence doc).

## Operator safety note — restore never touches a live stack

**`scripts/restore.sh` requires an explicit `PROJECT_NAME` argument and
refuses to guess one.** This is deliberate: it forces you to name a fresh,
disposable Docker Compose project — never the project name of a stack you
care about. A different `-p`/project name means Docker Compose creates
**brand-new, empty named volumes**; restoring never reuses or overwrites
the source stack's own `infosecurs_postgres_data` /
`infosecurs_evidence_data` volumes. Do not repurpose a `PROJECT_NAME` that
is already running something you don't want disturbed.

## Running a restore

```bash
scripts/restore.sh BACKUP_DIR PROJECT_NAME [ENV_FILE]
```

- `BACKUP_DIR` — a directory containing one backup set from
  `scripts/backup.sh` (it locates the `manifest-*.json` inside it and reads
  the other two filenames from there).
- `PROJECT_NAME` — a **new** Docker Compose project name for the fresh
  disposable stack, e.g. `m006r5restore1`. Must not collide with a stack
  you care about.
- `ENV_FILE` — `.env` to bring the fresh stack up with (defaults to the
  project root's own `.env` if omitted). Give this stack **different host
  ports** than any stack already running (`POSTGRES_HOST_PORT` /
  `WEB_HOST_PORT`) — Compose will otherwise fail to bind. The script
  briefly swaps the literal `./.env` to `ENV_FILE`'s content while the
  `web` container is created (`docker-compose.yml`'s `web` service reads
  its own env from that literal path, not from `--env-file`), then always
  restores whatever `.env` content was there before — see
  `docs/evidence/M006-BACKUP-RESTORE.md`'s "PL independent verification"
  section for the defect this fixes and why it's needed.

What it does, in order:

1. **Verifies both archive checksums against the manifest before touching
   anything** — refuses to restore from a corrupted/tampered set.
2. Brings up a fresh `db` under `PROJECT_NAME` (new named volumes).
3. Restores the logical dump via `psql` into that fresh database.
4. Un-tars the evidence archive into that fresh stack's own
   `infosecurs_evidence_data` volume.
5. Brings up `web` and runs `manage.py migrate --noinput` — this is the
   schema-compatibility proof: a same-SHA restore target should already be
   fully migrated, and `migrate --noinput` printing "No migrations to
   apply" (rather than applying anything) is the successful outcome PID
   §14 asks for.
6. Leaves the stack running. **It does not verify data for you** —
   verification (health, record checks, evidence checksum comparison,
   policy/questionnaire history) is a separate, explicit step (see below);
   the restore evidence document shows the exact commands actually run for
   this.

Tear the restored stack down when you're done, including its volumes
(never do this to a stack you care about):

```bash
docker compose -p PROJECT_NAME down -v
```

## What "verified" means (PID §14)

A restore is only proven, not merely "ran without an error", once every
one of these is checked against the *restored* stack:

| Check | How |
|---|---|
| App starts | `web` container `Up`, `manage.py migrate --noinput` completes |
| Migrations/schema compatible | `migrate --noinput` on the restored stack reports no pending migrations for the source SHA |
| Representative org/domain records restored | Query the restored DB for the known organisation/record and compare to what was backed up |
| Evidence bytes/checksum identical | `sha256sum` the evidence file's bytes on the **source** stack before backup, and the same file's bytes on the **restored** stack after restore, and compare the two values directly — not merely re-hashing the restored copy alone |
| Policy history intact | An approved `PolicyVersion` and the earlier version it superseded both exist post-restore with unchanged content |
| Accepted questionnaire history intact | An accepted `QuestionnaireResponse` and the earlier response it superseded both exist post-restore with unchanged content |
| Health 200 | `curl http://localhost:<WEB_HOST_PORT>/healthz/` returns `200` on the restored stack |

`core/management/commands/seed_backup_restore_fixture.py` builds a
synthetic organisation with exactly this shape (a real uploaded evidence
file, an approved policy version that superseded an earlier approved one,
and an accepted questionnaire response that superseded an earlier accepted
one) so there is something real to check. See
`docs/evidence/M006-BACKUP-RESTORE.md` for the full real-command run of
every check above.

## Cleaning up

Backup archives are large/binary and never belong in Git. After you're
done with a backup set and any restore you took from it:

```bash
rm -rf backups/<your-backup-dir>
docker compose -p <restore-project-name> down -v
```
