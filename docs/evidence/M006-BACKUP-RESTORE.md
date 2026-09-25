# M006 Round 5 — Backup / Restore

**PID:** `docs/pids/M006-CUSTOMER-ZERO-BETA-HARDENING.md` §14.
**Scope:** new operational tooling only (`scripts/backup.sh`,
`scripts/restore.sh`, `core/management/commands/seed_backup_restore_fixture.py`,
`docs/runbooks/BACKUP-RESTORE.md`). No `ai_platform/`,
`questionnaire/outcome.py`, `questionnaire/grounding.py`,
`policy/services.py` assurance logic, `security_state/services.py`, or any
existing product/runtime view/model/service code touched.

## How this was produced

Two disposable, synthetic Docker Compose stacks were built on dell-debian
from the real worktree content at `/srv/eng-worktrees/m006-round5-backup-restore`
(git SHA `22b995d12e4e1153fa789472646586f1101ce8e5`), never the canonical
`infosecurs-relocation` deployment or `/srv/infosecurs`:

- **Source** — project `m006r5source`, ports `19802` (web) / `19434` (db),
  throwaway `.env`.
- **Restore target** — project `m006r5restore1`, ports `19803` (web) /
  `19435` (db), a *different* throwaway `.env.restore-demo` — a genuinely
  separate Compose project, so Docker created brand-new, empty named
  volumes distinct from the source stack's.

## Fixture data

`core/management/commands/seed_backup_restore_fixture.py` was run against
the source stack:

```text
$ docker compose -p m006r5source exec -T web python manage.py seed_backup_restore_fixture
organisation_id=c8675c4b-c826-4ae5-abb4-ba0eeab80c54
evidence_item_id=12b99e6d-50f0-4e7e-85ac-23c239eeeb4b
Backup/restore demo fixture ready (idempotent, synthetic).
```

It built, entirely with synthetic Customer-Zero-safe values:

- Organisation **"Backup Restore Demo Org (synthetic)"**
  (`c8675c4b-c826-4ae5-abb4-ba0eeab80c54`), a user/membership, and an
  `OrganisationPerson` assigned as Policy Authoriser.
- A **real uploaded evidence file** (`evidence.services.create_file_evidence`
  — the actual product file-ingest path, not a raw DB row): 2200 bytes of
  synthetic plain text, stored as
  `12b99e6d-50f0-4e7e-85ac-23c239eeeb4b` /
  `c1b5f38ce6be4944b67afaa42b0876b0.txt` under
  `/data/evidence/c8675c4b-c826-4ae5-abb4-ba0eeab80c54/`.
- A **policy supersession chain**: `PolicyVersion` v1 created as a draft,
  approved (`policy.services.approve_policy_directly`), then
  `create_new_draft_from_approved` produced v2 with revised content, which
  was itself approved — leaving v1 `superseded` and v2 `approved`, exactly
  the product's real approval-lifecycle code path.
- A **questionnaire supersession chain**: `QuestionnaireResponse` #1
  (outcome `GAP`) created and accepted
  (`questionnaire.services.accept_questionnaire_response`), then response
  #2 (outcome `SUPPORTED`) created and accepted — leaving #1 `superseded`
  and #2 `accepted`, via the same service the product's real accept/review
  flow uses.

Verified directly against the source stack before backup:

```text
POLICY 1 superseded Information Security Policy (synthetic demo) 1
POLICY 2 approved   Information Security Policy (synthetic demo) 1
QRESP superseded GAP       Synthetic demo draft answer, v1.
QRESP accepted   SUPPORTED Synthetic demo draft answer, v2 - MFA now enforced.
EVIDENCE 12b99e6d-50f0-4e7e-85ac-23c239eeeb4b c1b5f38ce6be4944b67afaa42b0876b0.txt
  sha256=29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3 byte_size=2200
```

**Evidence file checksum — BEFORE backup** (bytes read directly from the
source stack's `web` container, not the DB-recorded value):

```text
$ docker compose -p m006r5source exec -T web sh -c \
    'sha256sum /data/evidence/c8675c4b-c826-4ae5-abb4-ba0eeab80c54/c1b5f38ce6be4944b67afaa42b0876b0.txt'
29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3  /data/evidence/.../c1b5f38ce6be4944b67afaa42b0876b0.txt
```

## Backup run

```text
$ export COMPOSE_PROJECT_NAME=m006r5source
$ bash scripts/backup.sh backups/round5-run1
Infosecurs backup starting: 20260925T000657Z
Source Git SHA: 22b995d12e4e1153fa789472646586f1101ce8e5
Output directory: /srv/eng-worktrees/m006-round5-backup-restore/backups/round5-run1
Stopping web service (quiescing writes)...
 Container m006r5source-web-1  Stopping
 Container m006r5source-web-1  Stopped
Waiting for db to be ready...
Dumping database 'infosecurs_m006r5' (logical dump via pg_dump)...
Archiving evidence volume...
Restarting web service...
 Container m006r5source-db-1  Waiting
 Container m006r5source-db-1  Healthy
 Container m006r5source-web-1  Starting
 Container m006r5source-web-1  Started
Backup complete.
  DB dump:  .../backups/round5-run1/db-infosecurs_m006r5-20260925T000657Z.sql
  Evidence: .../backups/round5-run1/evidence-20260925T000657Z.tar.gz
  Manifest: .../backups/round5-run1/manifest-20260925T000657Z.json
```

Manifest produced (`manifest-20260925T000657Z.json`):

```json
{
  "source_git_sha": "22b995d12e4e1153fa789472646586f1101ce8e5",
  "backup_utc_timestamp": "20260925T000657Z",
  "postgres_db": "infosecurs_m006r5",
  "db_dump_file": "db-infosecurs_m006r5-20260925T000657Z.sql",
  "db_dump_sha256": "b0ca50f60f73b18f8fa93043a714292166948766b3a4fb38fa5f0ab0e298a700",
  "evidence_archive_file": "evidence-20260925T000657Z.tar.gz",
  "evidence_archive_sha256": "e225ffe01c58e1c7da960f356ff6ccaaf507ead1d2d4e4ca9a39df42e3c5ed0b"
}
```

Web was back up and healthy immediately after the backup completed:

```text
$ curl -s -w '\nHTTP:%{http_code}\n' http://localhost:19802/healthz/
{"status": "ok", "database": true}
HTTP:200
```

### No credential anywhere in the backup set

```text
$ cd backups/round5-run1 && grep -c 'm006r5-throwaway-pw-9f3a7c21e6' *
db-infosecurs_m006r5-20260925T000657Z.sql:0
evidence-20260925T000657Z.tar.gz:0
manifest-20260925T000657Z.json:0
```

The database dump does contain real synthetic product data (proving it is
a genuine dump, not empty):

```text
$ grep -c 'Backup Restore Demo Org' db-infosecurs_m006r5-20260925T000657Z.sql
1
```

## Restore run

A second throwaway `.env.restore-demo` (ports `19803`/`19435`, distinct
Postgres/Django values) was used to bring up a **fresh, disposable**
Compose project:

```text
$ bash scripts/restore.sh backups/round5-run1 m006r5restore1 .env.restore-demo
Verifying archive checksums against manifest before restoring...
Checksums verified OK.
Bringing up fresh disposable stack (project: m006r5restore1)...
 Network m006r5restore1_default  Created
 Volume m006r5restore1_infosecurs_postgres_data  Created
 Container m006r5restore1-db-1  Started
Waiting for fresh db to be healthy...
Restoring logical DB dump into fresh database 'infosecurs_m006r5'...
Un-tarring evidence archive into fresh evidence volume...
 Volume m006r5restore1_infosecurs_evidence_data  Created
Bringing up web and applying migrations (proves schema compatibility)...
 Container m006r5restore1-web-1  Started
Waiting for web to finish migrating/starting...
Operations to perform:
  Apply all migrations: account, activity, admin, ai_platform, auth, contenttypes,
  evidence, governance, key_assets, organisations, policy, questionnaire,
  remediation, risk_register, security_baseline, sessions, sites, socialaccount,
  workplace
Running migrations:
  No migrations to apply.
Restore complete. Stack is running under project 'm006r5restore1'.
```

`m006r5restore1_infosecurs_postgres_data` and
`m006r5restore1_infosecurs_evidence_data` are new volumes created by this
run — never the source stack's `m006r5source_*` volumes.

## Verification (PID §14's required proof, every item checked)

### 1. App starts / health 200

```text
$ curl -s -w '\nHTTP:%{http_code}\n' http://localhost:19803/healthz/
{"status": "ok", "database": true}
HTTP:200
```

### 2. Migrations / schema compatible

`scripts/restore.sh`'s own `manage.py migrate --noinput` on the restored,
same-SHA stack reported **"No migrations to apply."** — the restored
schema was already fully migrated by the dump alone, proving schema
compatibility at this SHA.

### 3. Representative organisation/domain records restored

```text
$ docker compose -p m006r5restore1 exec -T web python manage.py shell -c "..."
ORG c8675c4b-c826-4ae5-abb4-ba0eeab80c54 Backup Restore Demo Org (synthetic)
```

Same organisation UUID and name as the source stack — the identical row,
round-tripped through dump/restore.

### 4. Evidence bytes/checksum identical (BEFORE vs AFTER, both shown)

```text
BEFORE (source stack, pre-backup):
29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3

AFTER (restored stack, post-restore):
$ docker compose -p m006r5restore1 exec -T web sh -c \
    'sha256sum /data/evidence/c8675c4b-c826-4ae5-abb4-ba0eeab80c54/c1b5f38ce6be4944b67afaa42b0876b0.txt'
29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3  /data/evidence/.../c1b5f38ce6be4944b67afaa42b0876b0.txt
```

**Identical.** The EvidenceItem row's own recorded `sha256`/`byte_size`
also matched (`29c1b4fc...`/`2200`) — same as before backup.

### 5. Policy history intact

```text
POLICY 1 superseded Information Security Policy (synthetic demo)
  sections=[{'content': 'Synthetic demo purpose and scope content, v1.', 'section_key': 'purpose_and_scope'}]
POLICY 2 approved   Information Security Policy (synthetic demo)
  sections=[{'content': 'Synthetic demo purpose and scope content, v2 (revised).', 'section_key': 'purpose_and_scope'}]
```

Both the superseded v1 and the currently-approved v2 survived restore with
their status and content byte-identical to the source stack.

### 6. Accepted questionnaire history intact

```text
QRESP superseded GAP       Synthetic demo draft answer, v1.
QRESP accepted   SUPPORTED Synthetic demo draft answer, v2 - MFA now enforced.
```

Both the superseded (GAP) response and the currently-accepted (SUPPORTED)
response survived restore with their status, outcome and answer text
byte-identical to the source stack.

## Judgement calls

- **Shell script, not a management command**, for both backup and
  restore — PID's own wording ("established PostgreSQL/Docker/archive
  tooling") and this project's "do not build a monitoring platform"
  restraint pointed the same direction; a thin Python wrapper around
  `subprocess` calls to the same `pg_dump`/`docker compose`/`tar` commands
  would have added a layer without adding safety.
- **`docker compose run` against the `web` service definition** to read/
  write the evidence volume, rather than a hard-coded
  `<project>_infosecurs_evidence_data` volume name — Compose resolves the
  real volume for the current project itself, so the script never needs to
  guess or reconstruct Compose's naming convention.
- **Credential never leaves the `db` container.** `pg_dump`/`psql` read
  `PGPASSWORD` from the container's *own* already-set `POSTGRES_PASSWORD`
  environment variable via `sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" ...'` —
  the host script itself never assigns, exports, or prints the value. This
  satisfies PID §14's "No credentials in manifests" more strongly than
  merely omitting it from the manifest file: it is never even transiently
  a host-side value.
- **Fixture built via ORM/service-layer calls in a management command**,
  not HTTP — per this dispatch's own explicit scope, this round's job is
  proving the backup/restore *mechanism*, not re-proving product business
  logic already proven by M001-M005 and Rounds 1-4. The command reuses the
  real service functions (`create_file_evidence`,
  `approve_policy_directly`, `create_new_draft_from_approved`,
  `accept_questionnaire_response`) rather than constructing rows in
  whatever shape by hand, so the fixture still exercises the product's own
  supersession logic, not a hand-rolled approximation of it.
- **`restore.sh` requires an explicit `PROJECT_NAME`** (no default) as a
  structural safeguard against ever restoring into a stack an operator
  didn't mean to touch — see the runbook's operator safety note.
- **No new mechanical pytest test file was added for the backup/restore
  scripts themselves.** PID §22 lists "backup manifest/checksums" and
  "disposable restore" among mechanical tests to add/extend, and this
  dispatch's own instructions offer a manifest-well-formedness smoke test
  as an example. Judgement call: `.github/workflows/ci.yml`'s `ci/unit`
  and `ci/integration` jobs bring up a bare `postgres` service container
  only — there is no Docker-in-Docker/Compose capability in CI for a test
  to actually invoke `scripts/backup.sh`/`scripts/restore.sh` (which
  themselves orchestrate `docker compose run`/`stop`/`start` against named
  volumes) non-vacuously. A test that only checked, say, "the manifest
  JSON template string contains these keys" without ever running the real
  script would be exactly the kind of false-green-by-name vacuous test
  this codebase's own discipline elsewhere explicitly rules out. The real,
  non-vacuous proof PID §14/§18 actually asks for — a genuine backup taken
  from a real running stack, restored into a genuinely fresh disposable
  stack, with every required check independently verified — is what this
  document records instead, matching how PID §18 itself frames backup/
  restore as an end-to-end Auditor-driven proof rather than a unit test.
  If Docker-in-CI capability is added for M006/post-M006, a real
  script-invoking mechanical test could be added at that point.
- **Manual `docker compose run` invocation for the full pytest suite**
  (see the closing report) needed explicit `-e` overrides rather than
  `docker compose --env-file`, because `docker-compose.yml`'s `web`
  service uses a literal `env_file: .env` — `--env-file` only affects
  variable interpolation *within* the compose YAML (e.g. the `db`
  service's `${POSTGRES_PASSWORD}`), not which file `web` loads at
  runtime. Not a script change (this was purely how this dispatch invoked
  the test suite for its own verification, not new product/tooling
  behaviour) — noted here for anyone reproducing this dispatch's steps.

## Full existing test suite

Run against a third disposable stack (project `m006r5test`, ports
`19805`/`19437`, its own throwaway env values, `--reuse-db`), from the same
worktree/SHA:

```text
1367 passed, 6 skipped in 763.61s (0:12:43)
```

Identical to the stated pre-dispatch baseline (1367 passed / 6 skipped) —
no regressions, and this dispatch added no new pytest test files (see
"Judgement calls" below for why). `makemigrations --check --dry-run`
against the source stack reported "No changes detected" — migrations
remain clean.

## Cleanup

All three throwaway stacks (`m006r5source`, `m006r5restore1`, `m006r5test`)
were torn down with their volumes, their built images removed, and every
locally-generated artifact (`backups/`, `.env`, `.env.test`,
`.env.restore-demo`) deleted from the worktree:

```text
$ docker compose -p m006r5source down -v
$ docker compose -p m006r5restore1 down -v
$ docker compose -p m006r5test down -v
$ rm -rf backups .env .env.test .env.restore-demo
$ git status --porcelain=v1
 M docs/runbooks/BETA-OPERATIONS.md
?? core/management/
?? docs/evidence/M006-BACKUP-RESTORE.md
?? docs/runbooks/BACKUP-RESTORE.md
?? scripts/
$ gitleaks detect --source . --no-git -v
1:27AM INF scanned ~2767452 bytes (2.77 MB) in 972ms
1:27AM INF no leaks found
```

Nothing under `backups/` was left in the working tree; no `.env*` file was
left in the working tree either (all gitignored, and none contained a
value used anywhere else).

## PL independent verification — defect found and fixed

Per standing PL discipline, the delivered mechanism was independently
reproduced end-to-end from scratch (a fourth disposable stack, `m006pl5`,
ports `19810`/`19442`, its own throwaway `.env`/passwords, distinct from
every project name/port used above) rather than trusting this dispatch's
own report alone — this run surfaced a real defect the dispatch's own
successful run did not hit.

**Defect:** `scripts/restore.sh`'s `ENV_FILE` argument did not actually
govern the `web` container's database credentials. `docker-compose.yml`'s
`web` service declares `env_file: .env` as a **literal** path; `docker
compose --env-file <X>` only affects `${VAR}` interpolation *within* the
compose YAML (which is how `db`'s `environment:` block gets its
`POSTGRES_PASSWORD`), not what `web`'s own `env_file:` directive loads.
When `ENV_FILE` differs from whatever `.env` file is physically sitting in
the project root — the realistic case for a restore target, and the exact
case this document's own restore run above did not hit only because its
`.env.restore-demo` happened to carry the same `POSTGRES_PASSWORD` as the
project root's own `.env` at the time — the fresh `db` comes up with
`ENV_FILE`'s password while `web` comes up with the root `.env`'s
password, and `web` crash-loops:

```text
$ bash scripts/restore.sh backups/pl-run1 m006pl5restore .env.pl-restore
...
Waiting for web to finish migrating/starting...
service "web" is not running
$ docker compose -p m006pl5restore logs web --tail 5
django.db.utils.OperationalError: connection failed: connection to server
at "192.168.48.2", port 5432 failed: FATAL:  password authentication
failed for user "infosecurs"
```

**Fix:** `scripts/restore.sh` now temporarily copies `ENV_FILE`'s content
over the literal `./.env` for exactly as long as it takes to create the
`web` container (Compose bakes `env_file` content in at container-creation
time and never re-reads it afterward), then unconditionally restores
whatever `.env` content was there before via an `EXIT` trap — mirroring
`scripts/backup.sh`'s own `restart_web` trap pattern. Confirmed the
original `.env` content was genuinely restored after the script exited,
not merely left as the swapped copy:

```text
$ grep POSTGRES_PASSWORD .env
POSTGRES_PASSWORD=m006pl5-throwaway-pw-4b7e91a   # the m006pl5 SOURCE stack's own value, unchanged
```

**Re-verified with the fix, full PID §14 checklist, all independently
reproduced (fresh restore-target stack `m006pl5restore2`, ports
`19811`/`19443`):**

```text
$ bash scripts/restore.sh backups/pl-run1 m006pl5restore2 .env.pl-restore
...
Running migrations:
  No migrations to apply.
Restore complete. Stack is running under project 'm006pl5restore2'.

$ curl -s -w '\nHTTP:%{http_code}\n' http://localhost:19811/healthz/
{"status": "ok", "database": true}
HTTP:200

# Evidence checksum — BEFORE (captured independently, pre-backup):
29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3

# Evidence checksum — AFTER (restored stack):
$ docker compose -p m006pl5restore2 exec -T web sh -c \
    'find /data/evidence/48496df2-7bb7-4cb0-b280-82cc45400ce5 -type f -exec sha256sum {} \;'
29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3  .../c5b011f4d9684f02ae87f12d6607393d.txt

# Records:
ORG 48496df2-7bb7-4cb0-b280-82cc45400ce5 Backup Restore Demo Org (synthetic)
POLICY 1 superseded [...'content': 'Synthetic demo purpose and scope content, v1.'...]
POLICY 2 approved   [...'content': 'Synthetic demo purpose and scope content, v2 (revised).'...]
QRESP superseded GAP       Synthetic demo draft answer, v1.
QRESP accepted   SUPPORTED Synthetic demo draft answer, v2 - MFA now enforced.
```

Evidence checksum identical, org record identical, policy history intact,
questionnaire history intact, migrations clean, health 200 — all matching
the source stack exactly. Manifest and both archives re-checked
independently for the throwaway credential value used in this
verification pass (`m006pl5-throwaway-pw-4b7e91a` /
`pl-verify-customerzero-pw-12chars`): zero matches in any of the three
files. `gitleaks detect --source . --no-git -v` re-run after this fix:
"no leaks found". Full existing suite (`1367 passed, 6 skipped`) and
`makemigrations --check --dry-run` ("No changes detected") independently
re-run against this same worktree state — see PR for the exact commit
this evidence corresponds to.

All PL-verification throwaway stacks (`m006pl5`, `m006pl5restore`,
`m006pl5restore2`) and their volumes were torn down; `backups/`, `.env`,
`.env.pl-verify`, `.env.pl-restore` removed from the working tree.
