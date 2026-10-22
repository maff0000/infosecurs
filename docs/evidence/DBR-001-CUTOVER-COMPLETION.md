# PID-DBR-001 — Cutover Completion Report (WO §3.5 + §3.6)

**Status: CLOSED GREEN. Central Architecture issued Final Architect Acceptance on 2026-10-22, accepting this report and the independent post-cutover audit below. The initial deployment-boundary remediation campaign is complete.**

This is the durable Git record of the authorised cutover of the persistent
`infosecurs-relocation` stack on `192.168.11.10`, executed under the
conditional GO issued by Central Architecture against the sole authorised
release SHA. It supersedes conversation history as the citable record of
this event, per this PID's standing practice (see
`docs/evidence/DBR-001-WP-E-INDEPENDENT-AUDIT.md` for the same discipline
applied to an earlier gate).

## 1. Authorisation

Central Architecture issued a **CONDITIONAL CUTOVER GO** naming the sole
authorised release SHA `0bce2555e0a6b9eec4d6dc645ac606f8d7309285`
(branch `wo/DBR-001-release-base-ad996bf`) against target
`infosecurs-relocation` on `192.168.11.10`, gated on five hard preflight
checks (P1–P5) passing before any swap, per WO §3.5.

## 2. Preflight gates (all GREEN, verified before any swap)

| Gate | Result |
|---|---|
| **P1 — Source and artifact** | Isolated detached worktree at exact SHA `0bce2555e0a6b9eec4d6dc645ac606f8d7309285`; clean `git status`/`git fsck`; 38 migrations (matches deployed `ad996bf`, zero M010); image built, `org.opencontainers.image.revision` label matched the requested SHA exactly; image digest `sha256:ac5cc5c51fafd0f5676a3f184fd1455aaf8a1c94d323830515619dca1501bc6c` (pre-final-build; see §4 for the digest of the image actually running). |
| **P2 — Existing runtime continuity** | `docker compose ... up -d db clamav --dry-run` reported both containers `Running` (no recreate), standalone and inside the full `up -d web --dry-run` plan, which showed only `web` → `Recreate`. Image digests for `db` (`postgres:16.6-alpine@sha256:1d04b9ba1d4996401f2552b51beda8187f175c0645c091e4781134fc9c9a3eef`) and `clamav` (`clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`) confirmed byte-identical to the running containers before touching anything. |
| **P3 — Access compatibility** | `.env.cutover` constructed as an exact copy of the real `.env` (never re-typed/guessed). Confirmed `DJANGO_ENV=development` (non-secret value, read directly) is preserved unchanged, so `SECURE_SSL_REDIRECT` stays off exactly as before — no new HTTPS redirect introduced. Current actual behaviour captured pre-cutover: `/` → 302 to `/accounts/login/`, `/healthz/` → 200, `Server: WSGIServer/0.2 CPython/3.12.14` (the legacy dev server) — confirmed unchanged in kind post-cutover except the `Server` header correctly now reads `gunicorn`. |
| **P4 — Data and recovery** | All four real volume identities confirmed via read-only `docker inspect` (names/mounts only, never env/secret dumps). Original `docker-compose.yml` + `docker-compose.override.yml` and the historical legacy web image (`sha256:7ce3234c2b0bfd9562efff0cf0c926976ac69658abe14631a81fe1d199091ccd`, tag `infosecurs-relocation-web`) confirmed present and preserved — not pruned. Manual-rollback command proven executable via a read-only `--dry-run` against the real, currently-running legacy config (no error, resolved cleanly). Fresh quiesced backup taken via the unmodified `scripts/backup.sh` (`/srv/infosecurs/backups/backup-20261022T100344Z/`): DB dump 284,885 bytes, evidence archive, questionnaire archive, manifest with SHA-256 checksums — all three checksums independently recomputed and matched the manifest exactly; both `.tar.gz` archives verified as structurally valid (`tar tzf`). |
| **P5 — Zero migration** | `python manage.py migrate --plan`, run against the live database using the authorised image, with `RELEASE_APPLY_MIGRATIONS` unset throughout: **empty plan** ("No planned migration operations."). |

## 3. Execution

`scripts/release.sh infosecurs-relocation .env.cutover 0bce2555e0a6b9eec4d6dc645ac606f8d7309285`
(with `RELEASE_IMAGE`/`COMPOSE_FILE=docker-compose.cutover.yml`) ran the
documented build → plan-check → (skip apply, plan was empty) → swap
sequence. `db`/`clamav` containers were not stopped, started, or recreated
at any point — their container IDs and `StartedAt` timestamps were
confirmed identical before and after. Only the `web` container was
stopped and recreated on the new image.

### 3.1 Accepted operational exception — release-script smoke-check defect

`scripts/release.sh`'s built-in smoke check hard-codes
`http://127.0.0.1:${WEB_HOST_PORT}${HEALTH_PATH}`. `docker-compose.cutover.yml`
deliberately binds `web`'s port explicitly to `192.168.11.10` (preserving
the real Beta access route), not `0.0.0.0`/loopback, so `127.0.0.1` never
reaches the container. The script therefore observed `HTTP 000` and
exited 1 **before** writing its release manifest — a false negative, not
a real outage. This was caught immediately: the actual bound address
(`http://192.168.11.10:8884/healthz/`) returned `HTTP 200` throughout, and
`db`/`clamav` were never touched regardless of the script's own exit
status.

**No rollback was performed or required.** The release manifest and
rollback pointer files (`releases/infosecurs-relocation/current.json` /
`previous.json`) were written by hand from independently verified facts
(container ID, image digest, mounts, running processes via `docker top`),
checksummed and transferred with the standard trinity→dell-debian
discipline, matching the exact JSON shape `scripts/release.sh` itself
would have written.

**Central Architecture has accepted this as a recorded operational
exception, requiring correction before the next live release** — tracked
as a defect to fix in `scripts/release.sh` (use the actual configured bind
host, not a hard-coded loopback assumption) ahead of the next
maintenance-priority release (certifi/Pillow security deployment).

## 4. Post-cutover facts (verified twice — directly, then independently re-audited)

- **Exact running image:** `infosecurs-release:0bce2555e0a6b9eec4d6dc645ac606f8d7309285`, digest `sha256:8492c8e1b07865a6a02dbd9d6a17430103a98508583257acffce704e6fd06031` (the final build; OCI revision label confirmed equal to the requested SHA).
- **Volume identities (unchanged, no new/duplicate volume created):** `infosecurs-relocation_infosecurs_postgres_data`, `infosecurs-relocation_infosecurs_evidence_data`, `infosecurs-relocation_infosecurs_questionnaire_data`, `infosecurs-relocation_infosecurs_clamav_data`.
- **Port/access-route preservation:** `web` → `192.168.11.10:8884->8000/tcp`; `db` → `127.0.0.1:15432->5432/tcp`; `clamav` → no host port — all unchanged from pre-cutover.
- **Runtime shape:** gunicorn only (3 processes: 1 master + 2 `gthread` workers via `docker top`), no Django autoreloader, no `/app` bind mount, secret bind mount (`/run/secrets/litellm_gateway_key`) preserved read-only.
- **Functional smoke:** `/healthz/` → 200; `/` → 302 to `/accounts/login/` (`Server: gunicorn`); `/accounts/login/` → 200 with a real rendered form (`<title>Log in — Infosecurs</title>`, `csrfmiddlewaretoken` present); a static asset served via WhiteNoise under gunicorn → 200.
- **Migration state:** `showmigrations --plan` — all applied, zero pending.
- **Data integrity:** 17 users, 15 organisations present post-cutover (read-only ORM count) — not reset, not lost.
- **`db`/`clamav` continuity:** identical container IDs and `StartedAt` timestamps (`2026-10-13T09:11:14Z`, `RestartCount: 0`) before and after the web-only swap.

## 5. Independent post-cutover verification

A **fresh** agent, with no memory of the execution above, independently
re-derived all ten of the facts in §4 directly from the live host — not
from this report's claims about them (same discipline as the §3.4 WP-E
audit). It additionally cross-checked the `com.docker.compose.project.config_files`
label (a file-path label, never an env/secret dump) to confirm the live
stack was genuinely composed from `docker-compose.cutover.yml` alone.

**Verdict: GREEN — 10/10 checks passed**, with two non-blocking notes
(the locally-built image has no registry `RepoDigests`, verified instead
via exact `.Id` match; the compose config is a single consolidated file
rather than a base+override pair — both confirmed intentional, not
defects).

## 6. Scope discipline

No M010 feature, migration, or code was deployed. No credential was
rotated, printed, or altered. No volume was created, pruned, or
substituted. The real `infosecurs-relocation` stack's `db`/`clamav`
containers were never stopped or restarted at any point in this entire
work package. This report, together with the independent audit in §5,
closes WO §3.5 and §3.6 and PID-DBR-001 as a whole.

## 7. Final Architect Acceptance

Central Architecture accepted this report and the independent audit
verdict on 2026-10-22, and issued final closure instructions:

1. Record this report in durable Git evidence (this document).
2. Record the §3.1 smoke-check defect as an accepted operational
   exception requiring correction before the next live release (tracked
   above; the fix itself is prepared in `docs/evidence/DBR-001-NEXT-RELEASE-SEC-DEPS-PREP.md`).
3. Close PID-DBR-001 and the 2026-10-19 deployment-boundary incident
   (`docs/evidence/INCIDENT-2026-10-19-DEPLOYMENT-BOUNDARY-EXPOSURE.md`)
   as structurally remediated.

**No further PID-DBR-001 implementation cycle is authorised or needed.**
The next bounded maintenance priority (security-only certifi/Pillow
dependency deployment onto this baseline) is tracked as its own,
separately-gated preparation — see
`docs/evidence/DBR-001-NEXT-RELEASE-SEC-DEPS-PREP.md` — which requires its
own independent audit and its own, separately required live-release
authorisation before any further persistent-stack change.
