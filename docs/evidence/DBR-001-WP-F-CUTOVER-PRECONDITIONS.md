# PID-DBR-001 Work Package F — §3.5 Cutover-Authorisation Preconditions

**Status: all three preconditions satisfied. Returned for the final §3.5 GO/NO-GO decision — this document does not itself authorise cutover.**

This closes out the three outstanding items from WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md §3.5:

1. A concrete cutover configuration attaching to the existing PostgreSQL,
   evidence and questionnaire volume identities, with no new or
   substituted customer-data volumes.
2. An explicit preservation check for the current Beta access route, port
   and connectivity.
3. A tested first-release manual rollback restoring the historical
   application and original Compose configuration without altering or
   losing customer data.

All work in this document was done with either (a) read-only inspection
of the real, persistent `infosecurs-relocation` stack (container/volume
*names*, mount destinations, port bindings only — never environment
variables, never `docker compose config` output), or (b) entirely
disposable, distinctly-named (`dbr001-wpf-*`) resources that never
collide with, and were never any part of, the real stack. **The real
stack's `web`/`db`/`clamav` containers and its four real named volumes
were not stopped, started, modified, or attached to at any point in this
work package.**

---

## 1. Concrete cutover configuration — `docker-compose.cutover.yml`

A new, standalone compose file, `docker-compose.cutover.yml`, added at the
repository root. It is deliberately **not** a reusable template like
`docker-compose.release.yml` (which intentionally uses its own fresh
`infosecurs_release_*` volumes so disposable rehearsals never collide
with anything). This file does the opposite on purpose: it names, as
`external: true` with an explicit `name:`, the four Docker volumes the
real `infosecurs-relocation` project has used since before this WO
existed.

### Existing-volume identity check (read-only, verified 2026-10-22)

```
$ docker inspect infosecurs-relocation-web-1 --format '{{range .Mounts}}{{.Name}} -> {{.Destination}} ({{.Type}}){{println}}{{end}}'
 -> /app (bind)
infosecurs-relocation_infosecurs_evidence_data -> /data/evidence (volume)
infosecurs-relocation_infosecurs_questionnaire_data -> /data/questionnaire (volume)
 -> /run/secrets/litellm_gateway_key (bind)

$ docker inspect infosecurs-relocation-db-1 --format '{{range .Mounts}}{{.Name}} -> {{.Destination}} ({{.Type}}){{println}}{{end}}'
infosecurs-relocation_infosecurs_postgres_data -> /var/lib/postgresql/data (volume)

$ docker inspect infosecurs-relocation-clamav-1 --format '{{range .Mounts}}{{.Name}} -> {{.Destination}} ({{.Type}}){{println}}{{end}}'
infosecurs-relocation_infosecurs_clamav_data -> /var/lib/clamav (volume)
```

`docker-compose.cutover.yml` declares exactly these four names as
`external: true`:

```yaml
volumes:
  infosecurs_postgres_data:
    external: true
    name: infosecurs-relocation_infosecurs_postgres_data
  infosecurs_evidence_data:
    external: true
    name: infosecurs-relocation_infosecurs_evidence_data
  infosecurs_questionnaire_data:
    external: true
    name: infosecurs-relocation_infosecurs_questionnaire_data
  infosecurs_clamav_data:
    external: true
    name: infosecurs-relocation_infosecurs_clamav_data
```

`external: true` + an explicit `name:` is the whole mechanism: Compose
attaches to a volume that already exists under that literal name rather
than creating one scoped to whatever `-p` project the file runs under.
This was independently proven generically (not against the real volumes —
see §4 below) before being relied on here.

The file also carries forward, unchanged from `docker-compose.release.yml`,
the gunicorn-hardened `web.command` (no dev autoreloader, no in-container
`migrate`, `exec gunicorn` as PID 1), and the real stack's own secret bind
mount (from `docker-compose.override.yml`, not present in
`docker-compose.release.yml` since that file has no secret dependency):

```
/srv/secrets/infosecurs/litellm_gateway_key -> /run/secrets/litellm_gateway_key (ro)
```

Full file, with its own detailed header comment explaining every
deliberate choice: `docker-compose.cutover.yml` at the repository root.

**This file must never be brought up against anything but the real
`infosecurs-relocation` project, and never as part of any rehearsal** —
its external volume names are the real customer-data volumes. See §4 for
how the underlying mechanism was tested instead.

---

## 2. Beta access-route / port preservation

Verified directly against the running containers (read-only, port/name
listing only):

```
$ docker ps --filter 'name=infosecurs' --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
NAMES                            IMAGE                       STATUS                PORTS
infosecurs-relocation-web-1      infosecurs-relocation-web   Up 2 days             192.168.11.10:8884->8000/tcp
infosecurs-relocation-db-1       postgres:16.6-alpine        Up 8 days (healthy)   127.0.0.1:15432->5432/tcp
infosecurs-relocation-clamav-1   clamav/clamav:1.4.6         Up 8 days (healthy)   3310/tcp, 7357/tcp
```

`docker-compose.cutover.yml` hard-codes these exact values (not a
`${VAR:-default}` guess, since this file exists for one specific real
target, not as a reusable template):

| Service | Current real binding | `docker-compose.cutover.yml` |
|---|---|---|
| `web`  | `192.168.11.10:8884 -> 8000` | `"192.168.11.10:8884:8000"` |
| `db`   | `127.0.0.1:15432 -> 5432`    | `"127.0.0.1:15432:5432"` |
| `clamav` | no host port (internal-only) | no `ports:` key (unchanged) |

The Beta access route (`http://192.168.11.10:8884`) and the
loopback-only Postgres port are therefore preserved exactly across the
cutover — nothing about this release changes how the application is
reached, by whom, or on what port.

---

## 3. Tested manual first-release rollback

### The gap (already documented in WP-D)

`scripts/rollback.sh` only knows how to roll back to an image a *prior*
`scripts/release.sh` run recorded in `releases/<project>/previous.json`.
The real stack's own first cutover under this mechanism has no such
prior record — the currently-deployed legacy container was never itself
brought up via `scripts/release.sh`. `rollback.sh` will correctly refuse
in this exact case. WP-D deliberately did not "fix" this by auto-seeding
a rollback target from the pre-existing container, because the legacy
image predates gunicorn being added to the dependency set — an automatic
"rollback" under the new mechanism's hardcoded gunicorn command would
crash on start, a worse, silent failure than today's clear refusal.

### What this work package adds: an actual, tested manual procedure

A disposable end-to-end drill proved the manual rollback mechanism this
one first cutover needs, using entirely fake-named resources — not the
real stack. Full commands and real output: see
`docs/evidence/DBR-001-WP-F-REHEARSAL-REPORT.md` (Drill 2). Summary:

1. A disposable "old-style" container (bind-mounted source, plain
   dev-server command — mirroring `docker-compose.yml`'s `web` shape) was
   seeded with known, checksummed data on an externally-named volume.
2. "Cut over" to a disposable "new-style" container (different
   image/command, no bind mount, same external volume) — data confirmed
   identical.
3. Manually rolled back — stopped/removed the new-style container,
   brought the *original* old-style container back up, unchanged, against
   the *same, never-destroyed* volume.
4. Recomputed checksums were byte-identical to the original seed values
   across **both** transitions. No project-prefixed duplicate volume was
   ever created at any point.

**Verdict: PASS.** The manual rollback pattern preserves customer data
with zero alteration or loss.

### The generalised procedure for the real stack (documented here; not executed against it)

1. Stop the cutover `web` container:
   ```
   docker compose -p infosecurs-relocation --env-file .env.cutover \
     -f docker-compose.cutover.yml stop web
   ```
2. Remove the stopped cutover container (the volumes are `external: true`
   and are never touched by this — no `-v` flag, ever):
   ```
   docker compose -p infosecurs-relocation --env-file .env.cutover \
     -f docker-compose.cutover.yml rm -f web
   ```
3. Bring the original historical application back up under its original
   Compose configuration, against the same, never-destroyed, never-recreated
   real volumes:
   ```
   docker compose -p infosecurs-relocation --env-file .env \
     -f docker-compose.yml -f docker-compose.override.yml up -d web
   ```
4. `db`/`clamav` are untouched throughout (the above only stops/starts
   `web`) — confirm they were never restarted, then smoke-test the
   restored `web` container the same way `scripts/release.sh`'s own
   health check does.

This is a named, pre-checked manual fallback — not a discovery to be made
mid-incident. It must remain available (do not remove the pre-existing
`infosecurs-relocation-web` legacy image, and do not prune it, until at
least one subsequent release has succeeded under the new mechanism and a
real `previous.json` exists for `scripts/rollback.sh` to use automatically
from then on).

---

## 4. Mechanism rehearsal (Drill 1 — supports §1 above)

Full commands/output: `docs/evidence/DBR-001-WP-F-REHEARSAL-REPORT.md`
(Drill 1). Summary: the `external: true` + explicit `name:` attachment
pattern was proven, generically, against two disposable volume shapes
(a seeded Postgres data directory, and a seeded file-tree directory
standing in for evidence/questionnaire storage) — in both cases, data
was confirmed unchanged after attachment, and `docker volume ls` showed
Compose created no second, project-prefixed volume alongside the
external one. **Never run against `docker-compose.cutover.yml` itself or
any real volume name** — this is what justifies relying on the same
mechanism in §1 without having to "test" it against real customer data.

---

## 5. Release-plan components (WO §3.5's required package)

| Component | Value / reference |
|---|---|
| Exact application + packaging source SHA | `c47c4c4c2beb779abb49152912dadda4c0a4b1b2` (branch `wo/DBR-001-release-base-ad996bf` = `ad996bf` + WP-A/B/C only) — see note below on the superseding SHA once this work package's own commit is added to that branch |
| Locally built OCI image identity | `infosecurs-release:<exact-release-candidate-SHA>`, built by `scripts/release.sh` step 1, which itself refuses to proceed unless the image's own `org.opencontainers.image.revision` OCI label matches the requested SHA exactly |
| Zero-new-migration proof | Release-candidate branch has exactly 38 migrations, identical to the currently-deployed `ad996bf` revision (verified during release-base branch construction) — current `main` has 44 (M010's +6), explicitly excluded from this release by design |
| Actual release commands | `RELEASE_IMAGE=infosecurs-release:<SHA> COMPOSE_FILE=docker-compose.cutover.yml scripts/release.sh infosecurs-relocation .env.cutover <SHA>` (see `docker-compose.cutover.yml` header for the full invocation) |
| Pre-cutover backup | `scripts/backup.sh` (M006 PID §14, unmodified, already proven in WP-D's own backup/restore cycle) — run from the real project root before step 4 (container swap) of the release |
| Existing-volume identity checks | §1 above — the four real volume names, confirmed by read-only `docker inspect`, immediately before cutover |
| Independent WP-E audit verdict | GREEN — `docs/evidence/DBR-001-WP-E-INDEPENDENT-AUDIT.md` |

**Required pre-cutover checklist item (named explicitly, per Central
Architecture's instruction):** the rollback-bootstrap manual-fallback
procedure in §3 above must be read and confirmed by the operator
**before** cutover begins — not discovered after a failed smoke test.

---

## Explicit scope discipline

No persistent Beta change of any kind was made by this work package. The
real `infosecurs-relocation` containers were not stopped, started, or
modified; the real volumes were not attached to, copied, or altered. No
M010 change, no credential rotation, no infrastructure redesign, no
feature work. This document, `docker-compose.cutover.yml`, the WP-E audit
record, and the WP-F rehearsal report together satisfy all three §3.5
preconditions and the full release-plan component list — returned here
for the separate, final §3.5 GO/NO-GO decision.
