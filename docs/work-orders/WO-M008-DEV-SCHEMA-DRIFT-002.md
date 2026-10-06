# WO-M008-DEV-SCHEMA-DRIFT-002 — Dev Schema Drift Recovery: Operational Continuation

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Parent amendments:** `docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT.md`, `docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT-002.md`
**Exact source base:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Status:** APPROVED FOR DELIVERY CONTROLLER DISPATCH

## Scope

The bounded operational actions below — a temporary recovery `.env`, a Compose-identity stop gate, the governed backup, the canonical migration apply, post-migration verification, data-preservation proof, real browser acceptance, temporary-`.env` cleanup, and root-cause/prevention documentation. Nothing else.

## Phase B1 — create temporary operational `.env`

Authorised path: `/srv/infosecurs/.env`. An operational, gitignored secret file.

- Mode `0600`.
- Never added to Git.
- Never copied into evidence.
- Secret values are never printed to any terminal output that is captured for evidence, logged, or reported.
- Removed after successful incident recovery (Phase G).

Use the **existing running stack** as the authority for every value. At minimum establish:

```
COMPOSE_PROJECT_NAME=infosecurs-relocation

POSTGRES_DB=<exact value from the running db container>
POSTGRES_USER=<exact value from the running db container>
POSTGRES_PASSWORD=<exact existing value from the running db container>

POSTGRES_HOST_PORT=15432
WEB_HOST_PORT=8884
WEB_BIND_ADDRESS=192.168.11.10
```

`POSTGRES_PASSWORD` is a secret. Recover it silently from the already-running `db` container and write it directly into the file without printing it or recording it anywhere. **Do not invent or rotate it.** Do not populate unrelated OAuth, AI-gateway, Customer-Zero, or other secrets merely to make the file resemble `.env.example` — this is a recovery shim for the existing stack, not a reconstructed permanent application configuration.

## Phase B2 — Compose identity stop gate

**Before running backup**, prove this temporary configuration addresses the exact running deployment:

```
COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose config
COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose ps
```

Verify mechanically:

- `db` resolves to the existing `infosecurs-relocation-db-1`;
- `web` resolves to the existing `infosecurs-relocation-web-1`;
- container IDs match those recorded during Phase A;
- the db volume is the existing live PostgreSQL volume;
- the web service's `/data/evidence` mount resolves to the existing live evidence volume;
- no new Compose project is created;
- no alternate volume is selected;
- no environment-interpolation warning/error exists that could materially change service resolution.

**If ANY identity differs: STOP. Do not run backup. Return to the Architect.**

Explicitly run every subsequent Compose command with `COMPOSE_PROJECT_NAME=infosecurs-relocation` set — never rely only on directory-derived project naming.

## Phase B3 — governed backup

Once B2 proves exact identity, run the existing governed script:

```
COMPOSE_PROJECT_NAME=infosecurs-relocation scripts/backup.sh <bounded recovery backup directory>
```

Use a new, timestamped output directory. **Do not overwrite an existing backup.** The backup must produce: a logical PostgreSQL dump; an evidence archive; a manifest; SHA-256 checksums. Verify: the DB dump is non-empty; the evidence archive is non-empty; the manifest names the canonical source SHA; the recorded checksums independently match both files; the manifest contains no credential; the `web` service successfully restarts afterward; the same original web/db container identities are running again.

**If backup does not clearly succeed: STOP. Do not migrate.**

## Phase C — apply canonical migrations

Only after successful B3, apply the normal canonical Django migration graph to the **existing** development database:

```
COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose exec web python manage.py migrate --noinput
```

No direct SQL. No `--fake`. No volume recreation. No Customer Zero reset. No data deletion. Expected canonical migrations are exactly the three identified in Phase A. **If Django proposes any unexpected fourth migration or dependency behaviour materially inconsistent with Phase A: STOP before improvising.** Record the exact migration output.

## Phase D — post-migration schema proof

Prove: all migrations applied; `migrate --plan` reports no pending operation; `showmigrations` shows the three migrations applied; `makemigrations --check --dry-run` remains clean. Mechanically inspect (direct schema introspection, not inference from `django_migrations` alone) that `OrganisationProfile` now has `sector`/`people_with_system_access_count`/`has_remote_or_offsite_access`; that the `security_baseline` `AnswerSelectionDetail` table exists; that `policy/0003` is applied.

## Phase E — data-preservation proof

Compare against the Phase A snapshot. At minimum: Customer Zero's organisation UUID unchanged; Customer Zero's user unchanged; password hash unchanged; membership unchanged; `CustomerZeroFixture` marker unchanged; governance-role assignments unchanged; evidence DB rows unchanged; evidence file count unchanged; a representative evidence file's SHA-256 unchanged; policy/questionnaire historical records unchanged where present. The migrations must not require a reset to become usable.

## Phase F — real application acceptance

A `/healthz/` 200 alone is not an acceptable post-release application smoke by itself. Use real Chromium against `http://192.168.11.10:8884/`. Authenticate normally. Prove actual rendered navigation through: login → organisation Home → Foundations → Stage 1 ("Your Business") → Stage 2 ("Your People & Workplaces") → Stage 3 ("Your Technology & Data") → Stage 4 ("Your Security") → Risks & Actions → Security Policy → the dev reset confirmation screen. **Do not execute the reset.** Every page must render without a `ProgrammingError`/schema error. Also confirm `/healthz/` → `200`.

## Phase G — temporary `.env` cleanup

After successful backup, successful migration, data-preservation proof, and browser acceptance: remove the temporary `/srv/infosecurs/.env`. Confirm it no longer exists. **Do not remove it earlier** — the governed Compose commands during recovery require it. **Do not leave this minimal recovery file in place** as if it were the canonical permanent host configuration.

The incident evidence must explicitly state that the canonical dev stack is currently capable of continuing from its already-created containers, but that **recreating** that stack would still require proper host-configuration recovery — a longer-term host-configuration issue this incident does **not** silently solve.

## Phase H — root cause / prevention

Update the incident evidence with the verified root cause. Expected, subject to evidence:

1. M008 source was fast-forwarded into `/srv/infosecurs`.
2. The `web` service bind-mounts the repository at `/app`.
3. Django's development autoreloader consumed the new Python/model code.
4. The long-running `web` container was never recreated/restarted through the Compose startup command.
5. Therefore `python manage.py migrate --noinput` never reran.
6. Persistent PostgreSQL remained on the old schema.
7. `/healthz/` continued to return 200 because it proves database reachability, not ORM/schema compatibility.
8. The subsequent real organisation page exposed the drift.
9. Separately, `/srv/infosecurs/.env` was absent, making the documented backup/operator path non-operational.

Prevention documentation must require, after any canonical-main advance on a persistent development stack: verify the source SHA; `showmigrations`; `migrate --plan`; apply canonical migrations where necessary; `makemigrations --check --dry-run`; an authenticated real-page smoke (minimum: Home, Foundations, one Stage/model-backed page). **`/healthz/ == 200` alone must not be used as application-ready evidence after a schema-bearing change.** Also document that a persistent stack considered operator-recoverable must have a valid host-configuration source available — a set of running containers alone is not sufficient backup/recovery readiness. **Do not design a new secrets-management system under this incident.**

## Independent audit

A fresh Auditor must independently verify: all three pending migrations identified correctly; temporary `.env` creation stayed inside this Work Order; secret values never entered Git/evidence/logged output; Compose project/volume identity was exact before backup; the backup completed against the real `infosecurs-relocation` stack; no direct SQL or fake migration; the canonical migration graph completed; data was preserved; real authenticated browser surfaces render; the temporary `.env` was removed afterward; DARWIN untouched; root-cause/prevention evidence is accurate.

**Any product/source defect discovered: STOP. Return to the Architect. No repair under this Work Order.**

## Architect stop gate

After recovery, a fresh audit, and the documentation PR are GREEN:

**STOP. DO NOT MERGE.**

Return with:

1. Amendment/Work Order paths;
2. the exact three pending migrations from before;
3. Compose identity proof;
4. backup manifest/checksum proof;
5. migration command/output;
6. post-migration plan/status;
7. Customer Zero/evidence preservation proof;
8. Chromium application-page results;
9. temporary `.env` cleanup proof;
10. root-cause conclusion;
11. prevention/runbook change;
12. Auditor verdict;
13. PR/head SHA and every CI check.

**Only Project Architect acceptance closes the incident.**
