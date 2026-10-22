# PID-DBR-001 Work Package F — Cutover Precondition Rehearsal Evidence

**Author:** FORGE Engineer, WP-F dispatch.
**Worktree:** `/srv/openclaw/worktrees/wo/DBR-001-wp-f` on `dell-debian`, branch
`wo/DBR-001-wp-f-cutover-preconditions`, based on current `main`.
**Scope:** §3.5 cutover-authorisation gate preconditions 1 and 3 (external-volume
reuse mechanism, and a tested manual rollback procedure for the real stack's
first-ever cutover under this tooling, given the known `scripts/rollback.sh`
gap documented in WP-D). All work done with entirely disposable, fake-named
(`dbr001-wpf-*`) resources. `docker-compose.cutover.yml` was never brought up,
under any project name, at any point. The real `infosecurs-relocation` stack
and its four real named volumes were never stopped, started, modified, or
referenced except by read-only `docker ps`/`docker volume ls` name-listing for
collision avoidance.

---

## Pre-flight: collision check

Confirmed, before creating anything, that no `dbr001-wpf-*` container, volume,
or network already existed, and that the real stack's containers/volumes were
present and running as expected (`infosecurs-relocation-{web,db,clamav}-1`,
`infosecurs-relocation_infosecurs_{postgres,evidence,questionnaire,clamav}_data`).

---

## Drill 1 — external-volume reuse mechanism (generic, fake names)

### 1a. Postgres-shaped volume

Created and seeded a throwaway named volume with a disposable
`postgres:16.6-alpine` container (same pinned digest the real
`docker-compose.cutover.yml` uses):

```
$ docker volume create dbr001-wpf-fake-pg-data
$ docker run -d --name dbr001-wpf-pg-seed \
    -e POSTGRES_PASSWORD=rehearsalpass -e POSTGRES_DB=rehearsaldb -e POSTGRES_USER=rehearsaluser \
    -v dbr001-wpf-fake-pg-data:/var/lib/postgresql/data \
    postgres:16.6-alpine
$ docker exec dbr001-wpf-pg-seed pg_isready -U rehearsaluser -d rehearsaldb
/var/run/postgresql:5432 - accepting connections
```

Inserted distinctive, checksummable rows:

```sql
CREATE TABLE rehearsal_proof (id serial primary key, marker text, val int);
INSERT INTO rehearsal_proof (marker, val) VALUES
  ('dbr001-wpf-drill1-alpha', 111),
  ('dbr001-wpf-drill1-beta', 222),
  ('dbr001-wpf-drill1-gamma', 333);
```
Result at seed time:
```
 id |         marker          | val
----+-------------------------+-----
  1 | dbr001-wpf-drill1-alpha | 111
  2 | dbr001-wpf-drill1-beta  | 222
  3 | dbr001-wpf-drill1-gamma | 333
```

Stopped and removed the seed container (volume persists):
```
$ docker stop dbr001-wpf-pg-seed && docker rm dbr001-wpf-pg-seed
$ docker volume ls | grep dbr001-wpf
dbr001-wpf-fake-pg-data        # only the external volume, no anonymous volume
```

Wrote a disposable Compose file, structurally identical to
`docker-compose.cutover.yml`'s own `db.volumes` stanza, under a distinct
project name:

```yaml
# /tmp/dbr001-wpf-drill1-pg.yml
services:
  db:
    image: postgres:16.6-alpine@sha256:1d04b9ba1d4996401f2552b51beda8187f175c0645c091e4781134fc9c9a3eef
    environment:
      POSTGRES_DB: rehearsaldb
      POSTGRES_USER: rehearsaluser
      POSTGRES_PASSWORD: rehearsalpass
    volumes:
      - dbr001_wpf_fake_pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rehearsaluser -d rehearsaldb"]
      interval: 5s
      timeout: 5s
      retries: 10
volumes:
  dbr001_wpf_fake_pg_data:
    external: true
    name: dbr001-wpf-fake-pg-data
```

Brought it up under project `dbr001-wpf-rehearsal` (a name the external volume
was NOT created under) and queried it (no `env`/`inspect .Config.Env` used):

```
$ docker compose -p dbr001-wpf-rehearsal -f /tmp/dbr001-wpf-drill1-pg.yml up -d
...
Container dbr001-wpf-rehearsal-db-1  Started
$ docker exec dbr001-wpf-rehearsal-db-1 psql -U rehearsaluser -d rehearsaldb -c "SELECT * FROM rehearsal_proof ORDER BY id;"
 id |         marker          | val
----+-------------------------+-----
  1 | dbr001-wpf-drill1-alpha | 111
  2 | dbr001-wpf-drill1-beta  | 222
  3 | dbr001-wpf-drill1-gamma | 333
(3 rows)

$ docker volume ls | grep dbr001-wpf
dbr001-wpf-fake-pg-data          # still exactly one volume — no
                                  # "dbr001-wpf-rehearsal_dbr001_wpf_fake_pg_data"
                                  # project-prefixed volume was created
```

**Result: data preserved exactly, and Compose created NO second volume
alongside the external one.**

### 1b. File-tree volume (evidence/questionnaire stand-in)

Seeded a throwaway named volume with known files + a checksum manifest:

```
$ docker volume create dbr001-wpf-fake-evidence-data
$ docker run --rm -v dbr001-wpf-fake-evidence-data:/data alpine:3.20 sh -c '
    mkdir -p /data/org-1
    echo "dbr001-wpf-drill1b-evidence-marker-alpha" > /data/org-1/evidence-alpha.txt
    echo "dbr001-wpf-drill1b-evidence-marker-beta"  > /data/org-1/evidence-beta.txt
    dd if=/dev/urandom of=/data/org-1/evidence-binary.bin bs=1024 count=16 2>/dev/null
    sha256sum /data/org-1/* | sort > /data/.seed-checksums.sha256
  '
3a141e7dd7370c2a2c8fde12401c4b14f520675573a12daab72922fa4106767f  /data/org-1/evidence-alpha.txt
5fd4a402e541cf5c1a99e876bfe73a987b4b9cab2b1feea18c8fd114a03b79f6  /data/org-1/evidence-beta.txt
8b08bdf9316add9f08807e8dc7833aa22e8b8880f6ff9f2b0147c2d0366a6024  /data/org-1/evidence-binary.bin
```

Disposable Compose file, same `external: true` pattern, different project:

```yaml
# /tmp/dbr001-wpf-drill1-evidence.yml
services:
  checker:
    image: alpine:3.20
    command: sleep 300
    volumes:
      - dbr001_wpf_fake_evidence_data:/data
volumes:
  dbr001_wpf_fake_evidence_data:
    external: true
    name: dbr001-wpf-fake-evidence-data
```

```
$ docker compose -p dbr001-wpf-evidence-rehearsal -f /tmp/dbr001-wpf-drill1-evidence.yml up -d
...
Container dbr001-wpf-evidence-rehearsal-checker-1  Started
$ docker exec dbr001-wpf-evidence-rehearsal-checker-1 sh -c "sha256sum -c /data/.seed-checksums.sha256"
/data/org-1/evidence-alpha.txt: OK
/data/org-1/evidence-beta.txt: OK
/data/org-1/evidence-binary.bin: OK
$ docker volume ls | grep dbr001-wpf
dbr001-wpf-fake-evidence-data   # unchanged - no new volume
```

**Result: checksums unchanged, and again Compose created NO new volume.**

Both 1a and 1b torn down immediately after (`docker compose ... down`,
`docker volume rm ...`) before starting Drill 2.

---

## Drill 2 — manual first-cutover rollback, end to end

### Setup

```
$ docker volume create dbr001-wpf-rollback-data
$ mkdir -p /tmp/dbr001-wpf-oldstyle-src
$ echo "dbr001-wpf-drill2-oldstyle-source-tree-marker" > /tmp/dbr001-wpf-oldstyle-src/marker.txt
$ docker run --rm -v dbr001-wpf-rollback-data:/data alpine:3.20 sh -c '
    echo "dbr001-wpf-drill2-rollback-customer-record-1" > /data/record1.txt
    echo "dbr001-wpf-drill2-rollback-customer-record-2" > /data/record2.txt
    dd if=/dev/urandom of=/data/record-binary.bin bs=1024 count=8 2>/dev/null
    sha256sum /data/record1.txt /data/record2.txt /data/record-binary.bin | sort > /data/.seed-checksums.sha256
  '
0d6582d7636931941831d4e63cca615f5fd358e30d65e3bb4bc819e39582d6dc  /data/record2.txt
3a960d561f1cf5932f6b2adc2d7094941e5ad6339d56cc355105399acf407a2c  /data/record-binary.bin
eda2020e58015e7074c8e96a6a9754e4f9d54f506aa1d99366493dc94d38f313  /data/record1.txt
```

### Step 1 — bring up the "old-style" container

```yaml
# /tmp/dbr001-wpf-drill2-oldstyle.yml
services:
  web:
    image: python:3.12-alpine
    command: sh -c "cd /app && python3 -m http.server 8000"
    volumes:
      - /tmp/dbr001-wpf-oldstyle-src:/app
      - dbr001_wpf_rollback_data:/data
volumes:
  dbr001_wpf_rollback_data:
    external: true
    name: dbr001-wpf-rollback-data
```

```
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-oldstyle.yml up -d
...
Container dbr001-wpf-rollback-web-1  Started
$ docker inspect dbr001-wpf-rollback-web-1 --format "Mounts: {{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Type}}); {{end}}"
Mounts: /tmp/dbr001-wpf-oldstyle-src -> /app (bind); /var/lib/docker/volumes/dbr001-wpf-rollback-data/_data -> /data (volume);
$ docker inspect dbr001-wpf-rollback-web-1 --format "Cmd: {{.Config.Cmd}}"
Cmd: [sh -c cd /app && python3 -m http.server 8000]
$ docker exec dbr001-wpf-rollback-web-1 sh -c "cat /app/marker.txt; sha256sum -c /data/.seed-checksums.sha256"
dbr001-wpf-drill2-oldstyle-source-tree-marker
/data/record2.txt: OK
/data/record-binary.bin: OK
/data/record1.txt: OK
```
Confirms the dev-server shape (bind-mounted source, non-gunicorn command) and
baseline data integrity.

### Step 2 — "cutover" to a new-style container

```yaml
# /tmp/dbr001-wpf-drill2-newstyle.yml
services:
  web:
    image: alpine:3.20
    command: sh -c "sleep 300"
    volumes:
      - dbr001_wpf_rollback_data:/data
volumes:
  dbr001_wpf_rollback_data:
    external: true
    name: dbr001-wpf-rollback-data
```

```
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-oldstyle.yml stop web
Container dbr001-wpf-rollback-web-1  Stopped
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-oldstyle.yml rm -f web
Container dbr001-wpf-rollback-web-1  Removed
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-newstyle.yml up -d
Container dbr001-wpf-rollback-web-1  Started
$ docker inspect dbr001-wpf-rollback-web-1 --format "Mounts: {{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Type}}); {{end}}"
Mounts: /var/lib/docker/volumes/dbr001-wpf-rollback-data/_data -> /data (volume);
$ docker inspect dbr001-wpf-rollback-web-1 --format "Cmd: {{.Config.Cmd}}  Image: {{.Config.Image}}"
Cmd: [sh -c sleep 300]  Image: alpine:3.20
$ docker exec dbr001-wpf-rollback-web-1 sh -c "sha256sum -c /data/.seed-checksums.sha256"
/data/record2.txt: OK
/data/record-binary.bin: OK
/data/record1.txt: OK
```
Different image, different command, no bind mount — only the volume carried
over, and the new container sees identical data.

### Step 3 — manual rollback: stop new, bring the ORIGINAL old-style container back

```
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-newstyle.yml stop web
Container dbr001-wpf-rollback-web-1  Stopped
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-newstyle.yml rm -f web
Container dbr001-wpf-rollback-web-1  Removed
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-oldstyle.yml up -d
Container dbr001-wpf-rollback-web-1  Started
$ docker inspect dbr001-wpf-rollback-web-1 --format "Mounts: {{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Type}}); {{end}}"
Mounts: /tmp/dbr001-wpf-oldstyle-src -> /app (bind); /var/lib/docker/volumes/dbr001-wpf-rollback-data/_data -> /data (volume);
$ docker inspect dbr001-wpf-rollback-web-1 --format "Cmd: {{.Config.Cmd}}  Image: {{.Config.Image}}"
Cmd: [sh -c cd /app && python3 -m http.server 8000]  Image: python:3.12-alpine
$ docker exec dbr001-wpf-rollback-web-1 sh -c "cat /app/marker.txt; sha256sum -c /data/.seed-checksums.sha256; echo RECOMPUTED:; sha256sum /data/record1.txt /data/record2.txt /data/record-binary.bin"
dbr001-wpf-drill2-oldstyle-source-tree-marker
/data/record2.txt: OK
/data/record-binary.bin: OK
/data/record1.txt: OK
RECOMPUTED:
eda2020e58015e7074c8e96a6a9754e4f9d54f506aa1d99366493dc94d38f313  /data/record1.txt
0d6582d7636931941831d4e63cca615f5fd358e30d65e3bb4bc819e39582d6dc  /data/record2.txt
3a960d561f1cf5932f6b2adc2d7094941e5ad6339d56cc355105399acf407a2c  /data/record-binary.bin
```
Recomputed checksums are byte-identical to the original seed-time values
(`eda2020e58...` / `0d6582d763...` / `3a960d561c...`). The volume was never
destroyed or recreated across either transition — `docker volume ls | grep
dbr001-wpf` showed exactly `dbr001-wpf-rollback-data` and nothing else at every
point in the drill, confirming no project-prefixed duplicate volume was ever
created.

---

## Verdicts

| Property | Verdict |
|---|---|
| (a) External-volume reuse (`external: true` + explicit `name:`) creates no new/substituted volume, and preserves pre-existing data exactly, across two independent volume shapes (Postgres data dir, file-tree data dir) | **PASS** |
| (b) Manual rollback round-trip (old-style -> new-style -> old-style again, same volumes never destroyed/recreated) preserves data with zero alteration across both transitions | **PASS** |

---

## Generalised manual-rollback procedure for the REAL stack (documented, NOT executed)

This is the procedure the drill above validates, phrased for the real
`infosecurs-relocation` project. It is written down for the PL/architect to
fold into the §3.5 evidence doc and is **not** something this rehearsal ran
against the real stack:

1. Stop the cutover `web` container under the real project:
   ```
   docker compose -p infosecurs-relocation --env-file .env.cutover \
     -f docker-compose.cutover.yml stop web
   ```
2. Remove the stopped cutover container (volumes are untouched by this —
   `rm` without `-v`, and the volumes are `external: true` regardless):
   ```
   docker compose -p infosecurs-relocation --env-file .env.cutover \
     -f docker-compose.cutover.yml rm -f web
   ```
3. Bring the ORIGINAL historical application back up under its original
   Compose configuration, against the same, never-destroyed, never-recreated
   real volumes (`infosecurs-relocation_infosecurs_{postgres,evidence,
   questionnaire,clamav}_data`):
   ```
   docker compose -p infosecurs-relocation --env-file .env \
     -f docker-compose.yml -f docker-compose.override.yml up -d web
   ```
4. Confirm `db`/`clamav` were never stopped during this (they aren't touched
   by the `web`-only stop/rm above), and smoke-test the restored `web`
   container the same way `scripts/release.sh`'s own health check does.

This is a manual substitute, specific to this one first cutover, for what
`scripts/rollback.sh` cannot yet do (per the WP-D finding: it requires a prior
`scripts/release.sh`-written `previous.json`, which will not exist until a
second release has been run under the mechanism).

---

## Teardown confirmation

```
$ docker compose -p dbr001-wpf-rollback -f /tmp/dbr001-wpf-drill2-oldstyle.yml down
Container dbr001-wpf-rollback-web-1  Removed
Network dbr001-wpf-rollback_default  Removed
$ docker volume rm dbr001-wpf-rollback-data
dbr001-wpf-rollback-data
$ rm -rf /tmp/dbr001-wpf-oldstyle-src
$ rm -f /tmp/dbr001-wpf-drill2-oldstyle.yml /tmp/dbr001-wpf-drill2-newstyle.yml \
        /tmp/dbr001-wpf-drill1-pg.yml /tmp/dbr001-wpf-drill1-evidence.yml

$ docker ps -a --format "{{.Names}}" | grep dbr001-wpf || echo "NONE"
NONE
$ docker volume ls --format "{{.Name}}" | grep dbr001-wpf || echo "NONE"
NONE
$ docker network ls --format "{{.Name}}" | grep dbr001-wpf || echo "NONE"
NONE
$ ls /tmp/dbr001-wpf-* 2>/dev/null || echo "NONE"
NONE
```

All `dbr001-wpf-*` containers, volumes, networks, and scratch files were
removed. (Base images `postgres:16.6-alpine`, `alpine:3.20`, `python:3.12-alpine`
pulled during the rehearsal were left in the local image cache — they are
shared, unnamed-to-us upstream images, not `dbr001-wpf-*` resources, and removing
them was not required by the dispatch.)

**Real stack integrity, confirmed post-rehearsal:**
```
$ docker ps --filter "name=infosecurs-relocation"
NAMES                            STATUS
infosecurs-relocation-web-1      Up 2 days
infosecurs-relocation-db-1       Up 8 days (healthy)
infosecurs-relocation-clamav-1   Up 8 days (healthy)
$ docker volume ls | grep infosecurs-relocation
infosecurs-relocation_infosecurs_clamav_data
infosecurs-relocation_infosecurs_evidence_data
infosecurs-relocation_infosecurs_postgres_data
infosecurs-relocation_infosecurs_questionnaire_data
```
Uptimes show the real stack's containers were never stopped or restarted at
any point during this dispatch.

**Worktree integrity, confirmed post-rehearsal:**
```
$ cd /srv/openclaw/worktrees/wo/DBR-001-wp-f && git status --short
?? docker-compose.cutover.yml
?? docs/evidence/DBR-001-WP-E-INDEPENDENT-AUDIT.md
```
Both untracked files pre-existed this dispatch (the cutover file was supplied
with the dispatch itself; the WP-E audit doc is from a prior work package).
Nothing in the worktree was modified or added by this rehearsal.
