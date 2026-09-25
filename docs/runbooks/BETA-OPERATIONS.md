# Beta Operations Runbook

**PID:** `docs/pids/M006-CUSTOMER-ZERO-BETA-HARDENING.md` §13.
**Scope:** day-to-day operation of a single Infosecurs Beta/Customer-Zero
Docker Compose stack (`docker-compose.yml` — `db` + `web`). Not a
monitoring platform (PID §13 explicitly says not to build one) — this is
the small, direct set of commands an operator actually runs.

Every command section below except **Backup** and **Restore** was actually
run against a real disposable Docker Compose stack on dell-debian during
the M006 Round 4 dispatch (throwaway project name `m006r4opscheck`,
`DJANGO_ENV=development`, synthetic `.env`, ports `19801`/`19433` — never
the canonical `infosecurs-relocation` deployment) and produced exactly the
output shown or described. Adjust the project name / `.env` path / ports
for your own stack; the commands themselves are unchanged.

Run every `docker compose` command from the project root (where
`docker-compose.yml` lives), with your real `.env` in place
(`cp .env.example .env` and fill in real local values if you don't have one
yet).

---

## Start

```bash
docker compose up -d
```

Brings up `db` (waits for `pg_isready` via its healthcheck) then `web`
(`web`'s command runs `python manage.py migrate --noinput` before starting
the dev server, so a fresh stack is migrated automatically). Verified:
`db` reported `healthy`, `web` came up and began serving within a few
seconds, `/healthz/` returned `200` once the server finished booting.

If you've stopped (not removed) the stack, `docker compose start` restarts
the existing containers in place — see **Restart** below, same command
family.

## Stop

```bash
docker compose stop
```

Stops both containers without removing them or their volumes — data
persists. Verified: `docker compose ps -a` afterwards showed both
containers `Exited (0)` (`db`) / `Exited (137)` (`web`, SIGKILL after the
default stop grace period — expected for the plain dev server, not a
crash), still present, not removed.

To also remove the containers/network (data volumes persist unless you add
`-v`, which permanently deletes them — do not do this without a deliberate
reason):

```bash
docker compose down
```

## Status

```bash
docker compose ps
```

Verified output shape (values will differ per stack):

```text
NAME                   IMAGE                  ...   STATUS                    PORTS
<project>-db-1         postgres:16.6-alpine   ...   Up 10 seconds (healthy)   127.0.0.1:<port>->5432/tcp
<project>-web-1        <project>-web          ...   Up 4 seconds              127.0.0.1:<port>->8000/tcp
```

`docker compose ps -a` also shows stopped/exited containers (used above to
confirm `stop` worked without removing anything).

## Migrations

Migrations already run automatically on `web` startup (see **Start**).  To
check migration state or apply migrations manually (e.g. after pulling new
code without restarting the container):

```bash
docker compose exec web python manage.py showmigrations --plan
docker compose exec web python manage.py migrate --noinput
```

Verified: `showmigrations --plan` listed every applied migration `[X]`
across all installed apps; re-running `migrate --noinput` against an
already-migrated stack printed `No migrations to apply.` — confirms the
migration set is idempotent/safe to re-run.

## Health

```bash
curl -s http://localhost:8000/healthz/
```

(replace `8000` with your `WEB_HOST_PORT`). Verified:
`{"status": "ok", "database": true}`, HTTP `200`, on a healthy stack.
`core/views.py::healthz` also returns `503` with `{"status": "degraded",
"database": false}` when the database is unreachable, with no connection
detail (host/port/credential) in the body — proven mechanically by
`core/tests/test_health.py::test_healthz_returns_503_with_no_leakage_when_db_unavailable`
(added this round), which forces a real database connection failure rather
than mocking one. The endpoint requires no authentication (also proven by
that same test file).

**Caution (M006 PID §12 finding, see `config/settings.py`'s
`SECURE_SSL_REDIRECT` comment and
`docs/evidence/M006-ROUND4-PRODCONFIG-HEALTH.md`):** under
`DJANGO_ENV=production`, `/healthz/` is *not* exempted from
`SECURE_SSL_REDIRECT` — a plain-HTTP health check (the common shape for a
load balancer / container orchestrator probe) gets a `301` redirect
instead of a `200`/`503`, unless the probe itself is HTTPS or is exempted
via `SECURE_REDIRECT_EXEMPT`. This is a real deployment-topology decision
(load balancer TLS behaviour, probe configuration) M006 does not authorise
choosing — documented here, not fixed.

## Logs

```bash
docker compose logs --tail 100 web
docker compose logs -f web        # follow
docker compose logs --tail 100 db
```

Verified: `--tail 5 web` returned the expected dev-server startup lines
plus per-request access log lines (e.g.
`[24/Sep/2026 22:53:55] "GET /healthz/ HTTP/1.1" 200 34`).

## Restart

```bash
docker compose restart web
```

Verified: `docker compose ps web` showed the container recreated/`Up`
within seconds, and `/healthz/` returned `200` again a few seconds after
the restart command completed (the dev server needs a short moment to
finish re-binding — treat an immediate post-restart health check failure
as "still booting," not "broken," and retry for a few seconds before
concluding otherwise).

## AI gateway smoke

Do **not** invent a new mechanism for this. The established, governed
pattern — used for the M002 AI-platform preflight and every live AI
evaluation since — is:

1. The real credential lives only at
   `/srv/secrets/infosecurs/litellm_gateway_key` on dell-debian (a
   HELM-provisioned host secret, `600 root:root`, outside both
   `/srv/infosecurs` and Git). It never moves off that host, is never
   printed, and is never written into this repository or any evidence
   document.
2. Bind-mount it **read-only** into a throwaway container at a
   `/run/secrets/...`-style path; point `AI_GATEWAY_API_KEY_FILE` at that
   in-container path (the app reads it as a **file path**, never a literal
   env var value — see `.env.example`'s `AI_GATEWAY_API_KEY_FILE` comment).
3. Point `AI_GATEWAY_BASE_URL` at the existing Trinity LiteLLM gateway and
   `AI_RISK_MODEL_ALIAS` at a governed alias (e.g. `trinity-fast` for a
   cheap/fast smoke call).
4. Make exactly **one** bounded call proving reachability + auth + a real
   model response (not a full evaluation run) — see
   `docs/evidence/M002-AI-GATEWAY-PREFLIGHT.md` for the exact `docker run
   --rm` / `curl` shape already established and proven GREEN.
5. Tear the throwaway container down immediately after
   (`docker run --rm` already does this); never persist the credential or
   any response containing it.

For a full behavioural check (not just reachability), see
`docs/evidence/M002-AI-GATEWAY-PREFLIGHT.md` (platform preflight) and
`docs/evidence/M005-LIVE-EVALUATION.md` (full questionnaire-assurance
golden-corpus run) — both already GREEN and current as of this round; this
dispatch did not re-run a real AI call, since `ai_platform/` is explicitly
out of scope for M006 Round 4 and the existing preflight/evaluation
evidence already proves the mechanism live and working.

## Backup

```bash
scripts/backup.sh [OUTPUT_DIR]
```

See `docs/runbooks/BACKUP-RESTORE.md` (landed in M006 Round 5, PID §14) for
the full operator runbook — what it does, credential handling, and output
shape.

## Restore

```bash
scripts/restore.sh BACKUP_DIR PROJECT_NAME [ENV_FILE]
```

Always restores into a **fresh, disposable** Compose project — never the
source/live stack. See `docs/runbooks/BACKUP-RESTORE.md` (landed in M006
Round 5, PID §14) for the full operator runbook, the operator safety note,
and what "verified" means.
